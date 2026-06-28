"""Plugin lifecycle management backed by the adapter registry + DB state."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.adapters.adapter_registry import get_registry
from backend.models.artifact import PluginRegistryEntry
from backend.utils.logger import get_logger

logger = get_logger("maestro.plugin_manager")


def sync_plugins_to_db(db: Session) -> list[dict]:
    """Reconcile discovered plugins with the plugin_registry table."""
    registry = get_registry()
    discovered = {p["name"]: p for p in registry.list_plugins()}

    rows = {row.plugin_name: row for row in db.query(PluginRegistryEntry).all()}
    for name, info in discovered.items():
        if name in rows:
            row = rows[name]
            row.version = info.get("version", row.version)
            row.manifest = json.dumps(info, default=str)
            # Apply persisted enabled state to the in-memory registry.
            registry.set_enabled(name, row.enabled)
        else:
            db.add(
                PluginRegistryEntry(
                    plugin_name=name,
                    plugin_type=info.get("type", "adapter"),
                    version=info.get("version", "1.0.0"),
                    manifest=json.dumps(info, default=str),
                    enabled=True,
                )
            )
    db.flush()
    return list_plugins_with_state(db)


def _resolve_tool_version(info: dict) -> None:
    """Annotate a plugin with the live version of the tool it's powered by.

    e.g. the ``adb`` adapter's ``powered_by.module = "turboadb"`` resolves to the
    installed turboadb version, so the Plugins page can show "turboadb 1.0.5".
    """
    powered_by = info.get("powered_by")
    module = powered_by.get("module") if isinstance(powered_by, dict) else None
    if not module:
        return
    version: str | None = None
    # Prefer the installed package version (this evolves every time the tool is
    # upgraded, e.g. turbossh 1.2.24), falling back to the module's __version__.
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as pkg_version

        try:
            version = pkg_version(module)
        except PackageNotFoundError:
            version = None
    except Exception:
        version = None
    if version is None:
        try:
            import importlib

            version = getattr(importlib.import_module(module), "__version__", None)
        except Exception:
            version = None
    info["tool_version"] = version


def list_plugins_with_state(db: Session) -> list[dict]:
    registry = get_registry()
    rows = {row.plugin_name: row for row in db.query(PluginRegistryEntry).all()}
    plugins = []
    for info in registry.list_plugins():
        row = rows.get(info["name"])
        if row is not None:
            info["enabled"] = row.enabled
        _resolve_tool_version(info)
        plugins.append(info)
    return plugins


def set_plugin_enabled(db: Session, name: str, enabled: bool) -> bool:
    registry = get_registry()
    if not registry.set_enabled(name, enabled):
        return False
    row = (
        db.query(PluginRegistryEntry)
        .filter(PluginRegistryEntry.plugin_name == name)
        .first()
    )
    if row is not None:
        row.enabled = enabled
    logger.info("plugin_toggled", plugin=name, enabled=enabled)
    return True


def hot_reload(db: Session) -> list[dict]:
    """Reload all plugins from disk without restarting the server."""
    get_registry().reload()
    from backend.adapters.custom_script_loader import load_custom_plugins

    load_custom_plugins(get_registry())
    return sync_plugins_to_db(db)
