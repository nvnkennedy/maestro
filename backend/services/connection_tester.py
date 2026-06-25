"""Device connection testing — validates configs before tests run."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.adapters.adapter_registry import get_registry
from backend.adapters.base_adapter import AdapterResult
from backend.models.device_config import DeviceConfig
from backend.security.credential_manager import resolve_device, resolve_target
from backend.services.observability import metrics
from backend.utils.helpers import utcnow

# Per config type: (adapter_name, action, params) used as a connectivity probe.
# SSH actually logs in (turbossh) and reports the resolved user/host so you know
# auth works. ADB lists devices via turboadb. The power probe only *validates the
# script* (the non-executing 'check' action) — a connection test must never
# actually toggle bench power. ETFW reports its last known state.
_PROBES: dict[str, tuple[str, str, dict]] = {
    "ssh": ("ssh", "execute_command", {"command": "echo MAESTRO_LOGIN_OK; uname -n"}),
    "adb": ("adb", "list_devices", {}),
    "power": ("power", "check", {}),
    "etfw": ("etfw", "get_state", {}),
    "camera": ("camera", "screenshot", {}),
    "serial": ("serial", "list_ports", {}),
    "system": ("system", "echo", {"message": "maestro-ok"}),
}


async def test_device_connection(db: Session, config_id: int) -> dict:
    """Run the connectivity probe for a device config and persist the outcome."""
    config = db.get(DeviceConfig, config_id)
    if config is None:
        raise ValueError(f"Device config {config_id} not found")

    # Run Targets: validate where tests will run (local tooling, or remote login).
    if config.config_type == "target":
        result = await _probe_target(db, config_id)
    # DLT is file-based now — there's nothing to "connect" to.
    elif config.config_type == "dlt":
        result = AdapterResult(
            success=True,
            output="DLT is file-based — point steps at your DLT file; no live check needed.",
        )
    else:
        probe = _PROBES.get(config.config_type)
        if probe is None:
            result = AdapterResult(
                success=False, error=f"No connection probe for type '{config.config_type}'"
            )
        else:
            adapter_name, action, base_params = probe
            adapter = get_registry().get(adapter_name)
            if adapter is None:
                result = AdapterResult(
                    success=False, error=f"Adapter '{adapter_name}' unavailable"
                )
            else:
                device = resolve_device(db, config_id)
                params = {k: v for k, v in device.items() if not k.startswith("_")}
                params.update(base_params)
                result = await adapter.execute(action, params, timeout=20)
                # If the login marker came back, the session works — even if the
                # host returned a non-zero exit (e.g. QNX's missing-home warning).
                if config.config_type == "ssh" and "MAESTRO_LOGIN_OK" in (result.output or ""):
                    result.success = True
                    result.error = ""
                    node = next(
                        (
                            ln.strip()
                            for ln in result.output.splitlines()
                            if ln.strip() and ln.strip() != "MAESTRO_LOGIN_OK"
                        ),
                        "",
                    )
                    who = params.get("username", "?")
                    host = params.get("host", "?")
                    result.output = f"Logged in as {who}@{host}" + (f" ({node})" if node else "")

    config.last_tested_at = utcnow()
    config.last_test_ok = result.success
    metrics.set_adapter_health(config.config_type, result.success)
    return {
        "config_id": config_id,
        "config_type": config.config_type,
        "label": config.label,
        **result.to_dict(),
    }


def _probe_local_tooling() -> AdapterResult:
    """Report whether adb/ffmpeg are available on this (local) machine."""
    import shutil

    from backend.adapters.adb_adapter.capabilities import find_adb

    adb = find_adb()
    ffmpeg = shutil.which("ffmpeg")
    parts = [
        f"adb: {('found — ' + adb) if adb else 'NOT found (Android steps will fail)'}",
        f"ffmpeg: {'found' if ffmpeg else 'NOT found (webcam capture needs it)'}",
    ]
    return AdapterResult(success=True, output="Local target ready. " + "; ".join(parts))


async def _probe_target(db: Session, config_id: int) -> AdapterResult:
    """Validate a Run Target: local tooling, or a remote SSH login + tooling."""
    target = resolve_target(db, config_id)
    if target["kind"] == "local":
        return _probe_local_tooling()

    if not target.get("host"):
        return AdapterResult(success=False, error="Remote target has no hostname set")
    ssh = get_registry().get("ssh")
    if ssh is None:
        return AdapterResult(success=False, error="SSH adapter unavailable")

    is_win = target.get("os") == "windows"
    sep = " & " if is_win else "; "
    # Login marker + a best-effort adb presence check (works on both OSes).
    adb_check = "adb version" if is_win else "adb version 2>/dev/null || echo 'adb: NOT found'"
    command = sep.join(["echo MAESTRO_LOGIN_OK", adb_check])
    params = {
        "host": target["host"],
        "port": target["port"],
        "username": target["username"],
        "domain": target["domain"],
        "domain_format": target["domain_format"],
        "password": target["password"],
        "key_file": target["key_file"],
        "command": command,
    }
    if is_win:
        params["raw_command"] = True
    result = await ssh.execute("execute_command", params, timeout=20)
    if "MAESTRO_LOGIN_OK" in (result.output or ""):
        result.success = True
        result.error = ""
        who = target["username"] or "?"
        adb_ok = "adb found" if "Android Debug Bridge" in result.output else "adb NOT found"
        result.output = f"Logged in to {who}@{target['host']} ({adb_ok})"
    return result
