"""Test case versioning: history snapshots, diff and rollback."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.models.project import TestCase, TestStep
from backend.models.report import TestCaseVersion


def snapshot_version(db: Session, test_case: TestCase, created_by: str = "admin") -> TestCaseVersion:
    """Save the current state of a test case as a new version."""
    latest = (
        db.query(TestCaseVersion)
        .filter(TestCaseVersion.test_case_id == test_case.id)
        .order_by(TestCaseVersion.version_number.desc())
        .first()
    )
    next_number = (latest.version_number + 1) if latest else 1

    db.query(TestCaseVersion).filter(
        TestCaseVersion.test_case_id == test_case.id,
        TestCaseVersion.is_current,
    ).update({"is_current": False})

    version = TestCaseVersion(
        test_case_id=test_case.id,
        version_number=next_number,
        name=test_case.name,
        steps_json=json.dumps([s.to_dict() for s in test_case.steps], default=str),
        created_by=created_by,
        is_current=True,
    )
    db.add(version)
    db.flush()
    return version


def list_versions(db: Session, test_case_id: int) -> list[dict]:
    versions = (
        db.query(TestCaseVersion)
        .filter(TestCaseVersion.test_case_id == test_case_id)
        .order_by(TestCaseVersion.version_number.desc())
        .all()
    )
    return [v.to_dict() for v in versions]


def diff_versions(db: Session, test_case_id: int, version_a: int, version_b: int) -> dict:
    """Step-level diff between two versions of a test case."""

    def load(version_number: int) -> list[dict]:
        row = (
            db.query(TestCaseVersion)
            .filter(
                TestCaseVersion.test_case_id == test_case_id,
                TestCaseVersion.version_number == version_number,
            )
            .first()
        )
        if row is None:
            raise ValueError(f"Version {version_number} not found")
        return json.loads(row.steps_json)

    steps_a = {s["step_number"]: s for s in load(version_a)}
    steps_b = {s["step_number"]: s for s in load(version_b)}
    diffs = []
    for num in sorted(set(steps_a) | set(steps_b)):
        sa, sb = steps_a.get(num), steps_b.get(num)
        if sa is None:
            diffs.append({"step_number": num, "change": "added", "after": sb})
        elif sb is None:
            diffs.append({"step_number": num, "change": "removed", "before": sa})
        elif (sa.get("action"), sa.get("parameters")) != (
            sb.get("action"),
            sb.get("parameters"),
        ):
            diffs.append(
                {"step_number": num, "change": "modified", "before": sa, "after": sb}
            )
    return {"version_a": version_a, "version_b": version_b, "diffs": diffs}


def rollback_to_version(
    db: Session, test_case_id: int, version_number: int, created_by: str = "admin"
) -> TestCase:
    """Restore a test case's steps from a stored version (saved as new version)."""
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise ValueError(f"Test case {test_case_id} not found")
    version = (
        db.query(TestCaseVersion)
        .filter(
            TestCaseVersion.test_case_id == test_case_id,
            TestCaseVersion.version_number == version_number,
        )
        .first()
    )
    if version is None:
        raise ValueError(f"Version {version_number} not found")

    steps = json.loads(version.steps_json)
    for step in list(test_case.steps):
        db.delete(step)
    db.flush()
    for step in steps:
        db.add(
            TestStep(
                test_case_id=test_case_id,
                step_number=step["step_number"],
                action=step["action"],
                parameters=json.dumps(step.get("parameters") or {}),
                timeout_seconds=step.get("timeout_seconds", 30),
                retry_count=step.get("retry_count", 0),
            )
        )
    db.flush()
    db.refresh(test_case)
    snapshot_version(db, test_case, created_by=created_by)
    return test_case
