"""Device configuration and encrypted credential vault models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.project import utcnow


class DeviceConfig(Base):
    __tablename__ = "device_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ssh, adb, ...
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # Non-secret connection settings as JSON (host, port, device serial, paths...)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tested_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    credentials: Mapped[list["CredentialVaultEntry"]] = relationship(
        back_populates="config", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        import json

        try:
            settings = json.loads(self.settings_json or "{}")
        except ValueError:
            settings = {}
        return {
            "id": self.id,
            "project_id": self.project_id,
            "config_type": self.config_type,
            "label": self.label,
            "settings": settings,
            "is_active": self.is_active,
            "last_tested_at": self.last_tested_at.isoformat()
            if self.last_tested_at
            else None,
            "last_test_ok": self.last_test_ok,
            "credential_keys": [c.credential_key for c in self.credentials],
        }


class CredentialVaultEntry(Base):
    __tablename__ = "credentials_vault"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("device_config.id"), nullable=False)
    credential_key: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # AES-256-GCM
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    rotated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    config: Mapped["DeviceConfig"] = relationship(back_populates="credentials")
