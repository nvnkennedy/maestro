"""Cascade deletion helpers.

SQLite enforces foreign keys (PRAGMA foreign_keys=ON), so deleting a test
case, execution or project must remove dependent rows first. These helpers
centralise that logic for every delete endpoint.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.config import REPORTS_DIR
from backend.models.artifact import ExecutionArtifact
from backend.models.device_config import DeviceConfig
from backend.models.execution import Execution, ExecutionStep
from backend.models.project import Project, TestCase
from backend.models.report import ScheduledTest, TestCaseVersion, TestDataSet
from backend.models.user import UserRole


def cascade_delete_execution(db: Session, execution: Execution) -> None:
    """Delete an execution with its steps, artifacts and report files."""
    db.query(ExecutionArtifact).filter(
        ExecutionArtifact.execution_id == execution.id
    ).delete(synchronize_session=False)
    db.query(ExecutionStep).filter(
        ExecutionStep.execution_id == execution.id
    ).delete(synchronize_session=False)
    for suffix in ("html", "json"):
        path = REPORTS_DIR / f"execution_{execution.id}.{suffix}"
        if path.exists():
            path.unlink()
    db.delete(execution)


def cascade_delete_test_case(db: Session, test_case: TestCase) -> None:
    """Delete a test case with versions, schedules and execution history."""
    db.query(TestCaseVersion).filter(
        TestCaseVersion.test_case_id == test_case.id
    ).delete(synchronize_session=False)
    db.query(ScheduledTest).filter(
        ScheduledTest.test_case_id == test_case.id
    ).delete(synchronize_session=False)
    executions = (
        db.query(Execution).filter(Execution.test_case_id == test_case.id).all()
    )
    for execution in executions:
        cascade_delete_execution(db, execution)
    db.delete(test_case)  # ORM cascades remove the test steps


def cascade_delete_project(db: Session, project: Project) -> None:
    """Delete a project and everything inside it."""
    for test_case in list(project.test_cases):
        cascade_delete_test_case(db, test_case)
    configs = (
        db.query(DeviceConfig).filter(DeviceConfig.project_id == project.id).all()
    )
    for config in configs:
        db.delete(config)  # ORM cascades remove vault entries
    db.query(TestDataSet).filter(TestDataSet.project_id == project.id).delete(
        synchronize_session=False
    )
    db.query(UserRole).filter(UserRole.project_id == project.id).delete(
        synchronize_session=False
    )
    db.delete(project)
