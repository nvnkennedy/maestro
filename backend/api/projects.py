"""Project CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.project import Project
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.cleanup import cascade_delete_project
from backend.services.project_service import dashboard_stats
from backend.utils.helpers import utcnow

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


@router.get("")
def list_projects(db: Session = Depends(get_db), _: str = Depends(require_role("read"))):
    return [p.to_dict() for p in db.query(Project).order_by(Project.name).all()]


@router.post("", status_code=201)
def create_project(
    body: ProjectIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    if db.query(Project).filter(Project.name == body.name).first():
        raise HTTPException(409, f"Project '{body.name}' already exists")
    project = Project(name=body.name, description=body.description, created_by=user)
    db.add(project)
    db.flush()
    record_audit(db, user, "create", "project", project.id, {"name": body.name})
    db.commit()
    return project.to_dict()


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project.to_dict()


@router.put("/{project_id}")
def update_project(
    project_id: int,
    body: ProjectIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    project.name = body.name
    project.description = body.description
    record_audit(db, user, "update", "project", project_id, body.model_dump())
    db.commit()
    return project.to_dict()


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("admin")),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    cascade_delete_project(db, project)
    record_audit(db, user, "delete", "project", project_id)
    # Never leave Maestro without a project to work in.
    if db.query(Project).count() == 0:
        from backend.services.project_service import ensure_default_project

        ensure_default_project(db)
    db.commit()


@router.get("/{project_id}/export")
def export_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("read")),
):
    """Download a JSON backup of the project (test cases, targets, schedules).

    Credentials are intentionally excluded — they never leave the vault.
    """
    import json

    from fastapi import Response

    from backend import __version__
    from backend.models.device_config import DeviceConfig
    from backend.models.report import ScheduledTest

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    tc_ids = [tc.id for tc in project.test_cases]
    payload = {
        "maestro_version": __version__,
        "exported_at": utcnow().isoformat(),
        "project": project.to_dict(),
        "test_cases": [tc.to_dict(include_steps=True) for tc in project.test_cases],
        "device_configs": [
            c.to_dict()
            for c in db.query(DeviceConfig)
            .filter(DeviceConfig.project_id == project_id)
            .all()
        ],
        "schedules": [
            s.to_dict()
            for s in db.query(ScheduledTest)
            .filter(ScheduledTest.test_case_id.in_(tc_ids))
            .all()
        ],
    }
    record_audit(db, user, "run", "project", project_id, {"action": "export"})
    db.commit()
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in project.name)
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="maestro-backup-{safe_name}.json"'
        },
    )


@router.get("/{project_id}/stats")
def project_stats(
    project_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    return dashboard_stats(db, project_id)
