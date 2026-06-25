"""Audit logging for compliance — every mutating action is recorded."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.models.user import AuditLog
from backend.utils.logger import get_logger

logger = get_logger("maestro.audit")


def record_audit(
    db: Session,
    username: str,
    action: str,
    resource_type: str = "",
    resource_id: int | None = None,
    changes: dict[str, Any] | None = None,
    ip_address: str = "",
) -> None:
    entry = AuditLog(
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=json.dumps(changes or {}, default=str),
        ip_address=ip_address,
    )
    db.add(entry)
    logger.info(
        "audit",
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
