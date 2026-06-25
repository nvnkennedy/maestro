"""Project, TestCase and TestStep models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.utils.helpers import utcnow as _utcnow


def utcnow() -> datetime:
    return _utcnow()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(100), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "test_case_count": len(self.test_cases),
        }


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    test_type: Mapped[str] = mapped_column(String(50), default="generic")
    scenario: Mapped[str] = mapped_column(String(200), default="")
    created_by: Mapped[str] = mapped_column(String(100), default="admin")
    # Who last changed the design, and where the case came from (authored vs
    # imported) — surfaced in the UI so provenance survives import/export.
    modified_by: Mapped[str] = mapped_column(String(100), default="")
    origin: Mapped[str] = mapped_column(String(20), default="authored")
    # Run Target this case runs on (a DeviceConfig of type "target"): Local or a
    # saved remote host. Null = run locally. Overridable at run time.
    default_target_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    project: Mapped["Project"] = relationship(back_populates="test_cases")
    steps: Mapped[list["TestStep"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestStep.step_number",
    )

    def to_dict(self, include_steps: bool = True) -> dict:
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type,
            "scenario": self.scenario,
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "origin": self.origin,
            "default_target_id": self.default_target_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "step_count": len(self.steps),
        }
        if include_steps:
            data["steps"] = [s.to_dict() for s in self.steps]
        return data


class TestStep(Base):
    __tablename__ = "test_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    test_case: Mapped["TestCase"] = relationship(back_populates="steps")

    def to_dict(self) -> dict:
        import json

        try:
            params = json.loads(self.parameters or "{}")
        except ValueError:
            params = {}
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "step_number": self.step_number,
            "action": self.action,
            "parameters": params,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
        }
