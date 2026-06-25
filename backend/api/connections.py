"""Ad-hoc connection testing and adapter health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.adapters.adapter_registry import get_registry
from backend.database import get_db
from backend.models.device_config import DeviceConfig
from backend.security.rbac import require_role
from backend.services.observability import metrics
from backend.services.resource_lock_mgr import lock_manager

router = APIRouter(prefix="/connections", tags=["connections"])


class AdHocTestIn(BaseModel):
    adapter: str
    action: str
    params: dict = Field(default_factory=dict)
    timeout: float = 20


@router.post("/test")
async def adhoc_test(
    body: AdHocTestIn, _: str = Depends(require_role("configure"))
):
    """Run any adapter action directly (used by the configuration panel)."""
    adapter = get_registry().get(body.adapter)
    if adapter is None:
        return {"success": False, "error": f"Adapter '{body.adapter}' unavailable"}
    result = await adapter.execute(body.action, body.params, timeout=body.timeout)
    return result.to_dict()


@router.get("/health")
async def adapters_health(_: str = Depends(require_role("read"))):
    results = await get_registry().health_check_all()
    for name, result in results.items():
        metrics.set_adapter_health(name, bool(result.get("success")))
    return results


@router.get("/locks")
def resource_locks(_: str = Depends(require_role("read"))):
    return {"held_locks": lock_manager.status()}


# Which adapter action answers "what devices are attached to this machine?"
_DETECTORS: dict[str, tuple[str, str]] = {
    "adb": ("adb", "list_devices"),
    "camera": ("camera", "detect"),
    "serial": ("serial", "list_ports"),
}


@router.get("/detect/{kind}")
async def detect_devices(
    kind: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Auto-detect locally attached devices (ADB devices, cameras, COM ports).

    If a target of this type is already configured (e.g. an adb_path), its
    settings are used for the scan.
    """
    probe = _DETECTORS.get(kind)
    if probe is None:
        return {"success": False, "error": f"No detector for '{kind}'", "devices": []}
    adapter_name, action = probe
    adapter = get_registry().get(adapter_name)
    if adapter is None:
        return {"success": False, "error": f"Adapter '{adapter_name}' unavailable", "devices": []}

    params: dict = {}
    config = (
        db.query(DeviceConfig)
        .filter(DeviceConfig.config_type == kind, DeviceConfig.is_active)
        .order_by(DeviceConfig.id.desc())
        .first()
    )
    if config is not None:
        import json as _json

        try:
            params = _json.loads(config.settings_json or "{}")
        except ValueError:
            params = {}
        params.pop("serial", None)  # scan all devices, not just the saved one

    result = await adapter.execute(action, params, timeout=30)
    data = result.to_dict()
    data["devices"] = result.data.get("devices") or result.data.get("ports") or []
    return data
