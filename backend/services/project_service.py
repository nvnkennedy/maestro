"""Project isolation helpers and dashboard statistics."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.execution import Execution
from backend.models.project import Project, TestCase
from backend.models.report import ScheduledTest


def ensure_default_project(db: Session) -> Project:
    """Guarantee at least one project exists (smooth first-run experience)."""
    project = db.query(Project).first()
    if project is None:
        project = Project(
            name="Default Project",
            description="Created automatically on first start",
        )
        db.add(project)
        db.flush()
    return project


def dashboard_stats(db: Session, project_id: int | None = None) -> dict:
    """Aggregate metrics for the dashboard cards and charts."""
    exec_query = db.query(Execution).join(TestCase)
    if project_id:
        exec_query = exec_query.filter(TestCase.project_id == project_id)

    status_counts = dict(
        exec_query.with_entities(Execution.status, func.count(Execution.id))
        .group_by(Execution.status)
        .all()
    )
    total = sum(status_counts.values())
    passed = status_counts.get("passed", 0)
    failed = status_counts.get("failed", 0) + status_counts.get("error", 0)

    # Executions per test type for the bar chart.
    by_type = dict(
        exec_query.with_entities(TestCase.test_type, func.count(Execution.id))
        .group_by(TestCase.test_type)
        .all()
    )

    # Last 14 executions for the trend line.
    recent = (
        exec_query.order_by(Execution.id.desc()).limit(14).all()
    )
    trend = [
        {
            "execution_id": e.id,
            "status": e.status,
            "duration_seconds": e.duration_seconds,
            "started_at": e.started_at.isoformat() if e.started_at else None,
        }
        for e in reversed(recent)
    ]

    last_execution = recent[0].to_dict() if recent else None
    next_scheduled = (
        db.query(ScheduledTest)
        .filter(ScheduledTest.enabled, ScheduledTest.next_run_at.isnot(None))
        .order_by(ScheduledTest.next_run_at)
        .first()
    )

    tc_query = db.query(func.count(TestCase.id))
    if project_id:
        tc_query = tc_query.filter(TestCase.project_id == project_id)

    return {
        "total_executions": total,
        "passed": passed,
        "failed": failed,
        "running": status_counts.get("running", 0),
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
        "status_counts": status_counts,
        "executions_by_type": by_type,
        "trend": trend,
        "last_execution": last_execution,
        "next_scheduled": next_scheduled.to_dict() if next_scheduled else None,
        "test_case_count": tc_query.scalar() or 0,
        "project_count": db.query(func.count(Project.id)).scalar() or 0,
    }
