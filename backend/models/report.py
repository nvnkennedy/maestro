"""Scheduling, versioning and test data set models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.project import utcnow

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class ScheduledTest(Base):
    __tablename__ = "scheduled_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    # When suite is set this schedule runs the whole suite/scenario (resolved at
    # fire time); test_case_id then just anchors the FK to one member case.
    suite: Mapped[str] = mapped_column(String(200), default="")
    scenario: Mapped[str] = mapped_column(String(200), default="")
    project_id: Mapped[int] = mapped_column(Integer, nullable=True)
    # once = run a single time at run_at | daily/weekly = recurring at time_of_day
    schedule_type: Mapped[str] = mapped_column(String(20), default="once")
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # for "once"
    time_of_day: Mapped[str] = mapped_column(String(5), default="")  # "HH:MM" recurring
    weekday: Mapped[int] = mapped_column(Integer, nullable=True)  # 0=Mon..6=Sun (weekly)
    cron_expression: Mapped[str] = mapped_column(String(100), default="")  # advanced
    # Optional active window for recurring schedules: don't fire before start_at;
    # auto-disable after end_at ("run from X until Y").
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def target_label(self) -> str:
        if self.suite:
            return f"Suite: {self.suite}" + (f" / {self.scenario}" if self.scenario else "")
        return ""

    def describe(self) -> str:
        if self.schedule_type == "once":
            stamp = self.run_at.strftime("%d %b %Y, %H:%M") if self.run_at else "?"
            return f"Once on {stamp}"
        if self.schedule_type == "daily":
            base = f"Every day at {self.time_of_day or '?'}"
        elif self.schedule_type == "weekly":
            day = _WEEKDAYS[self.weekday] if self.weekday is not None else "?"
            base = f"Every {day} at {self.time_of_day or '?'}"
        else:
            base = f"Cron: {self.cron_expression}"
        window = []
        if self.start_at:
            window.append(f"from {self.start_at.strftime('%d %b %Y')}")
        if self.end_at:
            window.append(f"until {self.end_at.strftime('%d %b %Y')}")
        return base + (" (" + " ".join(window) + ")" if window else "")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "suite": self.suite,
            "scenario": self.scenario,
            "project_id": self.project_id,
            "target_label": self.target_label(),
            "schedule_type": self.schedule_type,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "time_of_day": self.time_of_day,
            "weekday": self.weekday,
            "cron_expression": self.cron_expression,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "description": self.describe(),
            "enabled": self.enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TestCaseVersion(Base):
    __tablename__ = "test_case_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON snapshot
    created_by: Mapped[str] = mapped_column(String(100), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self, include_steps: bool = False) -> dict:
        import json

        data = {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "version_number": self.version_number,
            "name": self.name,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_current": self.is_current,
        }
        if include_steps:
            try:
                data["steps"] = json.loads(self.steps_json)
            except ValueError:
                data["steps"] = []
        return data


class TestDataSet(Base):
    __tablename__ = "test_data_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    data_type: Mapped[str] = mapped_column(String(20), default="json")  # csv | json
    content: Mapped[str] = mapped_column(Text, default="[]")  # inline data rows (JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def to_dict(self, include_content: bool = False) -> dict:
        import json

        data = {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "data_type": self.data_type,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_content:
            try:
                data["content"] = json.loads(self.content)
            except ValueError:
                data["content"] = []
        return data
