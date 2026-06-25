"""Execution and ExecutionStep models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.project import utcnow


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    # queued | running | paused | passed | failed | error | stopped
    execution_mode: Mapped[str] = mapped_column(String(20), default="serial")
    triggered_by: Mapped[str] = mapped_column(String(100), default="admin")
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    # Non-empty when this execution is part of a suite/scenario run.
    suite_run_id: Mapped[str] = mapped_column(String(64), default="")
    # The Run Target (DeviceConfig of type "target") this run used; null = local.
    target_id: Mapped[int] = mapped_column(Integer, nullable=True)
    target_label: Mapped[str] = mapped_column(String(200), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)

    steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.id",
    )

    def to_dict(self, include_steps: bool = False) -> dict:
        data = {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "triggered_by": self.triggered_by,
            "correlation_id": self.correlation_id,
            "suite_run_id": self.suite_run_id,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
        }
        if include_steps:
            data["steps"] = [s.to_dict() for s in self.steps]
        return data


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), nullable=False)
    test_step_id: Mapped[int] = mapped_column(Integer, nullable=True)
    step_number: Mapped[int] = mapped_column(Integer, default=0)
    action: Mapped[str] = mapped_column(String(200), default="")
    label: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | running | passed | failed | skipped
    actual_output: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    execution: Mapped["Execution"] = relationship(back_populates="steps")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "test_step_id": self.test_step_id,
            "step_number": self.step_number,
            "action": self.action,
            "label": self.label,
            "status": self.status,
            "actual_output": self.actual_output,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


class CycleResult(Base):
    """One iteration of an endurance/stability run (a looped test case).

    A run with ``cycles > 1`` records one row per cycle so the report can show a
    per-cycle list plus a roll-up (first-failure cycle, pass/fail counts).
    """

    __tablename__ = "cycle_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), nullable=False)
    cycle_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="passed")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "cycle_index": self.cycle_index,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
        }
