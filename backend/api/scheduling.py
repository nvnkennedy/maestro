"""Scheduled test management endpoints (date-based scheduling)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.project import TestCase
from backend.models.report import ScheduledTest
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.scheduler_service import build_trigger, scheduler_service
from backend.utils.validators import is_valid_cron

router = APIRouter(prefix="/schedules", tags=["scheduling"])


class ScheduleIn(BaseModel):
    # Either a single test case...
    test_case_id: Optional[int] = None
    # ...or a whole suite / scenario (resolved at fire time).
    suite: str = ""
    scenario: str = ""
    project_id: Optional[int] = None
    schedule_type: str = "once"  # once | daily | weekly | cron (advanced)
    run_at: Optional[datetime] = None  # required for "once"
    time_of_day: str = ""  # "HH:MM", required for daily/weekly
    weekday: Optional[int] = None  # 0=Mon..6=Sun, required for weekly
    cron_expression: str = ""  # only for type "cron"
    start_at: Optional[datetime] = None  # active-window start (recurring)
    end_at: Optional[datetime] = None  # auto-disable after this (recurring)
    enabled: bool = True


def _validate(body: ScheduleIn) -> None:
    if body.schedule_type == "once":
        if body.run_at is None:
            raise HTTPException(422, "A date and time (run_at) is required")
        if body.run_at.tzinfo is None and body.run_at <= datetime.now():
            raise HTTPException(422, "The scheduled time must be in the future")
    elif body.schedule_type in ("daily", "weekly"):
        if build_trigger(body.schedule_type, None, body.time_of_day, body.weekday) is None:
            raise HTTPException(
                422,
                "A valid time (HH:MM) is required"
                + (" plus a weekday" if body.schedule_type == "weekly" else ""),
            )
    elif body.schedule_type == "cron":
        if not is_valid_cron(body.cron_expression):
            raise HTTPException(422, f"Invalid cron expression: '{body.cron_expression}'")
    else:
        raise HTTPException(422, "schedule_type must be once, daily, weekly or cron")


def _resolve_target(db: Session, body: ScheduleIn) -> int:
    """Return the anchor test_case_id for the schedule (404s if unresolvable)."""
    if body.suite:
        query = db.query(TestCase).filter(TestCase.test_type == body.suite)
        if body.project_id:
            query = query.filter(TestCase.project_id == body.project_id)
        if body.scenario:
            query = query.filter(TestCase.scenario == body.scenario)
        anchor = query.order_by(TestCase.id).first()
        if anchor is None:
            raise HTTPException(404, "No test cases found in this suite/scenario")
        return anchor.id
    if not body.test_case_id:
        raise HTTPException(422, "Provide a test_case_id or a suite name")
    if db.get(TestCase, body.test_case_id) is None:
        raise HTTPException(404, "Test case not found")
    return body.test_case_id


def _apply(schedule: ScheduledTest, body: ScheduleIn, anchor_id: int) -> None:
    schedule.test_case_id = anchor_id
    schedule.suite = body.suite
    schedule.scenario = body.scenario if body.suite else ""
    schedule.project_id = body.project_id
    schedule.schedule_type = body.schedule_type
    schedule.run_at = body.run_at.replace(tzinfo=None) if body.run_at else None
    schedule.time_of_day = body.time_of_day
    schedule.weekday = body.weekday
    schedule.cron_expression = body.cron_expression
    schedule.start_at = body.start_at.replace(tzinfo=None) if body.start_at else None
    schedule.end_at = body.end_at.replace(tzinfo=None) if body.end_at else None
    schedule.enabled = body.enabled


@router.get("")
def list_schedules(
    db: Session = Depends(get_db), _: str = Depends(require_role("read"))
):
    schedules = db.query(ScheduledTest).order_by(ScheduledTest.id.desc()).all()
    tc_names = {
        tc.id: tc.name
        for tc in db.query(TestCase)
        .filter(TestCase.id.in_({s.test_case_id for s in schedules}))
        .all()
    }
    results = []
    for s in schedules:
        data = s.to_dict()
        data["test_case_name"] = (
            s.target_label() or tc_names.get(s.test_case_id, f"#{s.test_case_id}")
        )
        results.append(data)
    return results


@router.post("", status_code=201)
def create_schedule(
    body: ScheduleIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    _validate(body)
    anchor_id = _resolve_target(db, body)
    schedule = ScheduledTest()
    _apply(schedule, body, anchor_id)
    db.add(schedule)
    db.flush()
    schedule.next_run_at = scheduler_service.compute_next_run(schedule)
    record_audit(db, user, "create", "schedule", schedule.id, body.model_dump(mode="json"))
    db.commit()
    scheduler_service.reload_jobs()
    return schedule.to_dict()


@router.put("/{schedule_id}")
def update_schedule(
    schedule_id: int,
    body: ScheduleIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    schedule = db.get(ScheduledTest, schedule_id)
    if schedule is None:
        raise HTTPException(404, "Schedule not found")
    _validate(body)
    anchor_id = _resolve_target(db, body)
    _apply(schedule, body, anchor_id)
    schedule.next_run_at = scheduler_service.compute_next_run(schedule)
    record_audit(db, user, "update", "schedule", schedule_id, body.model_dump(mode="json"))
    db.commit()
    scheduler_service.reload_jobs()
    return schedule.to_dict()


@router.post("/{schedule_id}/toggle")
def toggle_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    schedule = db.get(ScheduledTest, schedule_id)
    if schedule is None:
        raise HTTPException(404, "Schedule not found")
    schedule.enabled = not schedule.enabled
    record_audit(db, user, "update", "schedule", schedule_id, {"enabled": schedule.enabled})
    db.commit()
    scheduler_service.reload_jobs()
    db.refresh(schedule)
    return schedule.to_dict()


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    schedule = db.get(ScheduledTest, schedule_id)
    if schedule is None:
        raise HTTPException(404, "Schedule not found")
    db.delete(schedule)
    record_audit(db, user, "delete", "schedule", schedule_id)
    db.commit()
    scheduler_service.reload_jobs()
