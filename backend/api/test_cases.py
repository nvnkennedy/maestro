"""Test case CRUD, cloning, templates and version management."""

from __future__ import annotations

import json
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import __version__
from backend.config import ARTIFACTS_DIR
from backend.database import get_db
from backend.models.project import Project, TestCase, TestStep
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.cleanup import cascade_delete_test_case
from backend.services.versioning_service import (
    diff_versions,
    list_versions,
    rollback_to_version,
    snapshot_version,
)

router = APIRouter(prefix="/test-cases", tags=["test-cases"])


class StepIn(BaseModel):
    step_number: int = Field(ge=1)
    action: str = Field(min_length=1)
    parameters: dict = Field(default_factory=dict)
    timeout_seconds: int = 30
    retry_count: int = 0


class TestCaseIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    test_type: str = "generic"
    scenario: str = ""
    default_target_id: int | None = None  # Run Target (local if null)
    steps: list[StepIn] = Field(default_factory=list)


def _apply_steps(db: Session, test_case: TestCase, steps: list[StepIn]) -> None:
    for step in list(test_case.steps):
        db.delete(step)
    db.flush()
    for step in steps:
        db.add(
            TestStep(
                test_case_id=test_case.id,
                step_number=step.step_number,
                action=step.action,
                parameters=json.dumps(step.parameters),
                timeout_seconds=step.timeout_seconds,
                retry_count=step.retry_count,
            )
        )
    db.flush()
    db.refresh(test_case)


@router.get("")
def list_test_cases(
    project_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    query = db.query(TestCase)
    if project_id:
        query = query.filter(TestCase.project_id == project_id)
    return [tc.to_dict(include_steps=False) for tc in query.order_by(TestCase.id.desc())]


@router.post("", status_code=201)
def create_test_case(
    body: TestCaseIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    if db.get(Project, body.project_id) is None:
        raise HTTPException(404, "Project not found")
    test_case = TestCase(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        test_type=body.test_type,
        scenario=body.scenario,
        default_target_id=body.default_target_id,
        created_by=user,
        modified_by=user,
    )
    db.add(test_case)
    db.flush()
    _apply_steps(db, test_case, body.steps)
    snapshot_version(db, test_case, created_by=user)
    record_audit(db, user, "create", "test_case", test_case.id, {"name": body.name})
    db.commit()
    return test_case.to_dict()


@router.get("/templates")
def list_templates(_: str = Depends(require_role("read"))):
    """Pre-built step templates grouped by test type.

    Built-in templates come from ``backend/templates/*_templates.json``;
    user-created templates from the writable ``data/templates`` dir are merged
    on top, and each registered custom script contributes its subcommands as a
    ready-to-drop palette item.
    """
    from backend.services.script_registry import as_templates
    from backend.services.template_store import (
        builtin_key,
        grouped,
        list_hidden_builtins,
        load_builtins,
    )

    templates: dict[str, list] = {}
    hidden = set(list_hidden_builtins())
    for group, items in load_builtins().items():
        visible = [it for it in items if builtin_key(group, it) not in hidden]
        if visible:
            templates[group] = visible

    # User-defined templates (writable), bucketed under their chosen group.
    for group, items in grouped().items():
        templates.setdefault(group, [])
        templates[group].extend(items)

    # Registered scripts → one palette item per subcommand.
    script_templates = as_templates()
    if script_templates:
        templates.setdefault("scripts", [])
        templates["scripts"].extend(script_templates)

    return templates


PLANNED_DIR = ARTIFACTS_DIR / "planned"
_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB per planned attachment


@router.post("/attachments", status_code=201)
async def upload_attachment(
    request: Request,
    filename: str = Query(default="file"),
    _: str = Depends(require_role("design")),
):
    """Store a file planned for a step; returns a reference saved in the step.

    The file is sent as the raw request body (no python-multipart dependency).
    These travel with the test case and surface as that step's attachments in
    the report when the test runs.
    """
    data = await request.body()
    if not data:
        raise HTTPException(400, "Empty upload")
    if len(data) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "Attachment exceeds 25 MB limit")
    PLANNED_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.\-]+", "_", filename or "file").strip("_") or "file"
    dest = PLANNED_DIR / f"{uuid.uuid4().hex}_{safe}"
    dest.write_bytes(data)
    return {"name": filename or safe, "path": str(dest), "size": len(data)}


EXPORT_FORMAT = "maestro.testcase/v1"


@router.get("/{test_case_id}/export")
def export_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """A portable JSON bundle of a test case (steps included), for moving the
    design to another Maestro install. Device bindings and uploaded-file paths
    are machine-specific and will need re-pointing after import."""
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "Test case not found")
    data = test_case.to_dict()
    return {
        "format": EXPORT_FORMAT,
        "exported_from": __version__,
        "name": data["name"],
        "description": data["description"],
        "test_type": data["test_type"],
        "scenario": data["scenario"],
        "created_by": data["created_by"],
        "modified_by": data["modified_by"],
        "origin": data["origin"],
        "created_at": data["created_at"],
        "steps": [
            {
                "step_number": s["step_number"],
                "action": s["action"],
                "parameters": s["parameters"],
                "timeout_seconds": s["timeout_seconds"],
                "retry_count": s["retry_count"],
            }
            for s in data.get("steps", [])
        ],
    }


class ImportIn(BaseModel):
    project_id: int
    format: str = ""
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    test_type: str = "generic"
    scenario: str = ""
    created_by: str = ""
    steps: list[StepIn] = Field(default_factory=list)


@router.post("/import", status_code=201)
def import_test_case(
    body: ImportIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    """Create a test case from an exported bundle (see ``/export``)."""
    if body.format and body.format != EXPORT_FORMAT:
        raise HTTPException(422, f"Unsupported bundle format '{body.format}'")
    if db.get(Project, body.project_id) is None:
        raise HTTPException(404, "Project not found")
    test_case = TestCase(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        test_type=body.test_type or "generic",
        scenario=body.scenario or "General",
        # Preserve the original author; record who imported it and mark origin.
        created_by=body.created_by.strip() or user,
        modified_by=user,
        origin="imported",
    )
    db.add(test_case)
    db.flush()
    _apply_steps(db, test_case, body.steps)
    snapshot_version(db, test_case, created_by=user)
    record_audit(db, user, "create", "test_case", test_case.id, {"imported": body.name})
    db.commit()
    return test_case.to_dict()


@router.get("/{test_case_id}")
def get_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "Test case not found")
    return test_case.to_dict()


@router.put("/{test_case_id}")
def update_test_case(
    test_case_id: int,
    body: TestCaseIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "Test case not found")
    test_case.name = body.name
    test_case.description = body.description
    test_case.test_type = body.test_type
    test_case.scenario = body.scenario
    test_case.default_target_id = body.default_target_id
    test_case.modified_by = user
    _apply_steps(db, test_case, body.steps)
    snapshot_version(db, test_case, created_by=user)
    record_audit(db, user, "update", "test_case", test_case_id, {"name": body.name})
    db.commit()
    return test_case.to_dict()


@router.delete("/{test_case_id}", status_code=204)
def delete_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "Test case not found")
    cascade_delete_test_case(db, test_case)
    record_audit(db, user, "delete", "test_case", test_case_id)
    db.commit()


class BulkDeleteIn(BaseModel):
    ids: list[int]


@router.post("/bulk-delete")
def bulk_delete(
    body: BulkDeleteIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    deleted = 0
    for test_case_id in body.ids:
        test_case = db.get(TestCase, test_case_id)
        if test_case is not None:
            cascade_delete_test_case(db, test_case)
            deleted += 1
    record_audit(db, user, "delete", "test_case", None, {"bulk_ids": body.ids})
    db.commit()
    return {"deleted": deleted}


class MoveIn(BaseModel):
    ids: list[int]
    suite: str = Field(min_length=1)
    scenario: str = "General"


@router.post("/move")
def move_test_cases(
    body: MoveIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    """Move test cases into another suite/scenario."""
    moved = 0
    for test_case_id in body.ids:
        test_case = db.get(TestCase, test_case_id)
        if test_case is not None:
            test_case.test_type = body.suite
            test_case.scenario = body.scenario
            moved += 1
    record_audit(
        db, user, "update", "test_case", None,
        {"moved_ids": body.ids, "suite": body.suite, "scenario": body.scenario},
    )
    db.commit()
    return {"moved": moved}


class RenameGroupIn(BaseModel):
    project_id: int
    suite: str = Field(min_length=1)
    scenario: str = ""  # when set, rename the scenario inside the suite
    new_name: str = Field(min_length=1)


@router.post("/rename-group")
def rename_group(
    body: RenameGroupIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    """Rename a suite (or a scenario within a suite) across the project."""
    query = db.query(TestCase).filter(
        TestCase.project_id == body.project_id, TestCase.test_type == body.suite
    )
    if body.scenario:
        query = query.filter(TestCase.scenario == body.scenario)
    cases = query.all()
    if not cases:
        raise HTTPException(404, "No test cases in this group")
    for test_case in cases:
        if body.scenario:
            test_case.scenario = body.new_name
        else:
            test_case.test_type = body.new_name
    record_audit(db, user, "update", "test_case", None, body.model_dump())
    db.commit()
    return {"renamed": len(cases)}


@router.post("/{test_case_id}/clone", status_code=201)
def clone_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    source = db.get(TestCase, test_case_id)
    if source is None:
        raise HTTPException(404, "Test case not found")
    clone = TestCase(
        project_id=source.project_id,
        name=f"{source.name} (copy)",
        description=source.description,
        test_type=source.test_type,
        scenario=source.scenario,
        created_by=user,
        modified_by=user,
    )
    db.add(clone)
    db.flush()
    for step in source.steps:
        db.add(
            TestStep(
                test_case_id=clone.id,
                step_number=step.step_number,
                action=step.action,
                parameters=step.parameters,
                timeout_seconds=step.timeout_seconds,
                retry_count=step.retry_count,
            )
        )
    db.flush()
    db.refresh(clone)
    snapshot_version(db, clone, created_by=user)
    record_audit(db, user, "create", "test_case", clone.id, {"cloned_from": test_case_id})
    db.commit()
    return clone.to_dict()


# ---- versioning -------------------------------------------------------------


@router.get("/{test_case_id}/versions")
def get_versions(
    test_case_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    return list_versions(db, test_case_id)


@router.get("/{test_case_id}/versions/diff")
def get_version_diff(
    test_case_id: int,
    a: int = Query(...),
    b: int = Query(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    try:
        return diff_versions(db, test_case_id, a, b)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{test_case_id}/versions/{version_number}/rollback")
def rollback(
    test_case_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    try:
        test_case = rollback_to_version(db, test_case_id, version_number, created_by=user)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    record_audit(
        db, user, "update", "test_case", test_case_id, {"rollback_to": version_number}
    )
    db.commit()
    return test_case.to_dict()
