"""User role (RBAC) and audit log models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.project import utcnow


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("username", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # admin | designer | executor | viewer | auditor
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )  # NULL = system-wide
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create/update/delete/run
    resource_type: Mapped[str] = mapped_column(String(50), default="")
    resource_id: Mapped[int] = mapped_column(Integer, nullable=True)
    changes: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip_address: Mapped[str] = mapped_column(String(45), default="")

    def to_dict(self) -> dict:
        import json

        try:
            changes = json.loads(self.changes or "{}")
        except ValueError:
            changes = {}
        return {
            "id": self.id,
            "username": self.username,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "changes": changes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address,
        }
