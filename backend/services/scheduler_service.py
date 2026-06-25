"""Scheduled test execution on top of APScheduler.

Schedules are date-based (user-friendly): run **once** at a specific
date/time, **daily** at a time, or **weekly** on a weekday + time. A raw
cron expression remains available as an advanced option. Schedules persist
in the ``scheduled_tests`` table and are re-registered on startup.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from backend.database import session_scope
from backend.models.report import ScheduledTest
from backend.utils.helpers import utcnow
from backend.utils.logger import get_logger

logger = get_logger("maestro.scheduler")

_APS_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def build_trigger(
    schedule_type: str,
    run_at: datetime | None = None,
    time_of_day: str = "",
    weekday: int | None = None,
    cron_expression: str = "",
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> BaseTrigger | None:
    """Build the APScheduler trigger for a schedule (None = nothing to run).

    ``start_at`` / ``end_at`` bound recurring schedules to an active window
    (e.g. "run daily from Mon until Fri"); they map to the CronTrigger's
    start_date / end_date.
    """
    if schedule_type == "once":
        if run_at is None or run_at <= datetime.now():
            return None  # already in the past
        return DateTrigger(run_date=run_at)

    if schedule_type in ("daily", "weekly"):
        try:
            hour_str, _, minute_str = time_of_day.partition(":")
            hour, minute = int(hour_str), int(minute_str)
        except ValueError:
            return None
        common = {"hour": hour, "minute": minute, "start_date": start_at, "end_date": end_at}
        if schedule_type == "daily":
            return CronTrigger(**common)
        if weekday is None or not 0 <= weekday <= 6:
            return None
        return CronTrigger(day_of_week=_APS_WEEKDAYS[weekday], **common)

    if schedule_type == "cron" and cron_expression:
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
        except ValueError:
            return None
        # Apply the active window to the raw cron trigger too.
        if start_at is not None:
            trigger.start_date = start_at
        if end_at is not None:
            trigger.end_date = end_at
        return trigger
    return None


def trigger_for(schedule: ScheduledTest) -> BaseTrigger | None:
    return build_trigger(
        schedule.schedule_type,
        schedule.run_at,
        schedule.time_of_day or "",
        schedule.weekday,
        schedule.cron_expression or "",
        schedule.start_at,
        schedule.end_at,
    )


class SchedulerService:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if not self._scheduler.running:
            self._scheduler.start()
        self.reload_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    # ----------------------------------------------------------------- jobs

    def reload_jobs(self) -> None:
        """Sync APScheduler jobs with the scheduled_tests table."""
        self._scheduler.remove_all_jobs()
        count = 0
        with session_scope() as db:
            schedules = db.query(ScheduledTest).filter(ScheduledTest.enabled).all()
            for schedule in schedules:
                trigger = trigger_for(schedule)
                if trigger is None:
                    # One-shot schedules whose time has passed get disabled.
                    if schedule.schedule_type == "once":
                        schedule.enabled = False
                        schedule.next_run_at = None
                    continue
                next_run = self.compute_next_run(schedule)
                if next_run is None:
                    # Recurring schedule whose active window (end_at) has elapsed.
                    schedule.enabled = False
                    schedule.next_run_at = None
                    continue
                self._scheduler.add_job(
                    self._fire,
                    trigger,
                    args=[schedule.id, schedule.test_case_id],
                    id=f"schedule-{schedule.id}",
                    replace_existing=True,
                )
                schedule.next_run_at = next_run
                count += 1
        logger.info("schedules_loaded", count=count)

    def compute_next_run(self, schedule: ScheduledTest) -> datetime | None:
        trigger = trigger_for(schedule)
        if trigger is None:
            return None
        return trigger.get_next_fire_time(None, datetime.now())

    def _fire(self, schedule_id: int, test_case_id: int) -> None:
        """Job callback (runs in scheduler thread) — dispatch to event loop."""
        logger.info("schedule_fired", schedule_id=schedule_id, test_case_id=test_case_id)
        with session_scope() as db:
            schedule = db.get(ScheduledTest, schedule_id)
            if schedule is None or not schedule.enabled:
                return
            schedule.last_run_at = utcnow()
            if schedule.schedule_type == "once":
                schedule.enabled = False
                schedule.next_run_at = None
            else:
                schedule.next_run_at = self.compute_next_run(schedule)

        if self._loop is None or not self._loop.is_running():
            return
        from backend.services.test_executor import executor

        # Suite schedules resolve their member test cases at fire time.
        suite = scenario = ""
        project_id = None
        with session_scope() as db:
            schedule = db.get(ScheduledTest, schedule_id)
            if schedule is not None:
                suite, scenario, project_id = (
                    schedule.suite, schedule.scenario, schedule.project_id
                )
        if suite:
            from backend.models.project import TestCase

            with session_scope() as db:
                query = db.query(TestCase.id).filter(TestCase.test_type == suite)
                if project_id:
                    query = query.filter(TestCase.project_id == project_id)
                if scenario:
                    query = query.filter(TestCase.scenario == scenario)
                ids = [row[0] for row in query.order_by(TestCase.id).all()]
            if ids:
                label = f"{suite}{' / ' + scenario if scenario else ''} (scheduled)"
                asyncio.run_coroutine_threadsafe(
                    executor.start_suite(ids, "serial", triggered_by="scheduler", label=label),
                    self._loop,
                )
            return

        asyncio.run_coroutine_threadsafe(
            executor.start(test_case_id, mode="serial", triggered_by="scheduler"),
            self._loop,
        )


scheduler_service = SchedulerService()
