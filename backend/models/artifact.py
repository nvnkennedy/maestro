"""Execution artifact and plugin registry models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
from backend.models.project import utcnow


class ExecutionArtifact(Base):
    __tablename__ = "execution_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(30), default="log")
    # screenshot | video | log | report
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    step_number: Mapped[int] = mapped_column(Integer, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "artifact_type": self.artifact_type,
            "file_path": self.file_path,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "step_number": self.step_number,
        }


class PluginRegistryEntry(Base):
    __tablename__ = "plugin_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plugin_type: Mapped[str] = mapped_column(String(30), default="adapter")
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    manifest: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        import json

        try:
            manifest = json.loads(self.manifest or "{}")
        except ValueError:
            manifest = {}
        return {
            "id": self.id,
            "plugin_name": self.plugin_name,
            "plugin_type": self.plugin_type,
            "version": self.version,
            "manifest": manifest,
            "enabled": self.enabled,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
