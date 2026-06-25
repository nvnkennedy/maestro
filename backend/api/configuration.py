"""Device configuration endpoints (credentials stored encrypted)."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.device_config import DeviceConfig
from backend.security.audit import record_audit
from backend.security.credential_manager import set_credentials
from backend.security.rbac import require_role
from backend.services.connection_tester import test_device_connection

router = APIRouter(prefix="/configs", tags=["configuration"])


class DeviceConfigIn(BaseModel):
    project_id: int
    config_type: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=200)
    settings: dict = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)
    is_active: bool = True


@router.get("")
def list_configs(
    project_id: Optional[int] = Query(default=None),
    config_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    query = db.query(DeviceConfig)
    if project_id:
        query = query.filter(DeviceConfig.project_id == project_id)
    if config_type:
        query = query.filter(DeviceConfig.config_type == config_type)
    return [c.to_dict() for c in query.order_by(DeviceConfig.id).all()]


@router.post("", status_code=201)
def create_config(
    body: DeviceConfigIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("configure")),
):
    config = DeviceConfig(
        project_id=body.project_id,
        config_type=body.config_type,
        label=body.label,
        settings_json=json.dumps(body.settings),
        is_active=body.is_active,
    )
    db.add(config)
    db.flush()
    set_credentials(db, config.id, body.credentials)
    record_audit(
        db, user, "create", "device_config", config.id,
        {"label": body.label, "type": body.config_type},
    )
    db.commit()
    return config.to_dict()


@router.put("/{config_id}")
def update_config(
    config_id: int,
    body: DeviceConfigIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("configure")),
):
    config = db.get(DeviceConfig, config_id)
    if config is None:
        raise HTTPException(404, "Device config not found")
    config.config_type = body.config_type
    config.label = body.label
    config.settings_json = json.dumps(body.settings)
    config.is_active = body.is_active
    set_credentials(db, config_id, body.credentials)
    record_audit(db, user, "update", "device_config", config_id, {"label": body.label})
    db.commit()
    return config.to_dict()


@router.delete("/{config_id}", status_code=204)
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("configure")),
):
    config = db.get(DeviceConfig, config_id)
    if config is None:
        raise HTTPException(404, "Device config not found")
    db.delete(config)
    record_audit(db, user, "delete", "device_config", config_id)
    db.commit()


class BulkDeleteIn(BaseModel):
    ids: list[int]


@router.post("/bulk-delete")
def bulk_delete_configs(
    body: BulkDeleteIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("configure")),
):
    deleted = 0
    for config_id in body.ids:
        config = db.get(DeviceConfig, config_id)
        if config is not None:
            db.delete(config)
            deleted += 1
    record_audit(db, user, "delete", "device_config", None, {"bulk_ids": body.ids})
    db.commit()
    return {"deleted": deleted}


@router.post("/{config_id}/test")
async def test_connection(
    config_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("configure")),
):
    try:
        result = await test_device_connection(db, config_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    record_audit(
        db, user, "run", "device_config", config_id,
        {"test": "connection", "success": result["success"]},
    )
    db.commit()
    return result
