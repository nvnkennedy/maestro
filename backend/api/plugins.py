"""Plugin management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.plugin_manager import (
    hot_reload,
    list_plugins_with_state,
    set_plugin_enabled,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
def list_plugins(db: Session = Depends(get_db), _: str = Depends(require_role("read"))):
    return list_plugins_with_state(db)


@router.post("/{plugin_name}/enable")
def enable_plugin(
    plugin_name: str,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("admin")),
):
    if not set_plugin_enabled(db, plugin_name, True):
        raise HTTPException(404, f"Plugin '{plugin_name}' not found")
    record_audit(db, user, "update", "plugin", None, {"plugin": plugin_name, "enabled": True})
    return {"plugin": plugin_name, "enabled": True}


@router.post("/{plugin_name}/disable")
def disable_plugin(
    plugin_name: str,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("admin")),
):
    if not set_plugin_enabled(db, plugin_name, False):
        raise HTTPException(404, f"Plugin '{plugin_name}' not found")
    record_audit(db, user, "update", "plugin", None, {"plugin": plugin_name, "enabled": False})
    return {"plugin": plugin_name, "enabled": False}


@router.post("/reload")
def reload_plugins(
    db: Session = Depends(get_db), user: str = Depends(require_role("admin"))
):
    plugins = hot_reload(db)
    record_audit(db, user, "update", "plugin", None, {"action": "hot_reload"})
    return plugins
