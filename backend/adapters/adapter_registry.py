"""Plugin discovery and registry.

Scans ``backend/adapters/*/manifest.json``, imports each adapter module and
instantiates the class declared in the manifest ``entry_point``. Supports
enable/disable and hot reload without restarting the server.
"""

from __future__ import annotations

import importlib
import json
from typing import Optional

from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.config import ADAPTERS_DIR
from backend.utils.logger import get_logger

logger = get_logger("maestro.plugins")

# ADAPTERS_DIR is resolved in config for source / frozen / pip-installed modes.


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}
        self._manifests: dict[str, dict] = {}
        self._disabled: set[str] = set()

    # ---- discovery ---------------------------------------------------------

    def discover(self) -> None:
        """Scan adapter packages and (re)load every plugin with a manifest."""
        for manifest_path in sorted(ADAPTERS_DIR.glob("*/manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._load_from_manifest(manifest, manifest_path.parent.name)
            except Exception as exc:
                logger.error(
                    "plugin_load_failed", plugin=manifest_path.parent.name, error=str(exc)
                )

    def _load_from_manifest(self, manifest: dict, package_name: str) -> None:
        name = manifest["name"]
        module_name, _, class_name = manifest["entry_point"].partition(":")
        module = importlib.import_module(f"backend.adapters.{package_name}.{module_name}")
        importlib.reload(module)
        adapter_cls = getattr(module, class_name)
        self._adapters[name] = adapter_cls()
        self._manifests[name] = manifest
        logger.info("plugin_loaded", plugin=name, version=manifest.get("version"))

    def register(self, adapter: BaseAdapter, manifest: dict | None = None) -> None:
        """Register a programmatically-created adapter (custom plugins)."""
        self._adapters[adapter.name] = adapter
        self._manifests[adapter.name] = manifest or {
            "name": adapter.name,
            "version": "0.0.0",
            "type": "adapter",
        }

    def reload(self) -> None:
        """Hot reload: drop and rediscover all manifest-based plugins."""
        self._adapters.clear()
        self._manifests.clear()
        self.discover()

    # ---- access -------------------------------------------------------------

    def get(self, name: str) -> Optional[BaseAdapter]:
        if name in self._disabled:
            return None
        return self._adapters.get(name)

    def list_plugins(self) -> list[dict]:
        plugins = []
        for name, adapter in sorted(self._adapters.items()):
            info = dict(self._manifests.get(name, {}))
            info.update(adapter.get_capabilities())
            info["enabled"] = name not in self._disabled
            plugins.append(info)
        return plugins

    def set_enabled(self, name: str, enabled: bool) -> bool:
        if name not in self._adapters:
            return False
        if enabled:
            self._disabled.discard(name)
        else:
            self._disabled.add(name)
        return True

    async def health_check_all(self) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for name, adapter in self._adapters.items():
            if name in self._disabled:
                results[name] = {"success": False, "output": "", "error": "disabled"}
                continue
            try:
                result = await adapter.health_check()
            except Exception as exc:
                result = AdapterResult(success=False, error=str(exc))
            results[name] = result.to_dict()
        return results

    async def cleanup_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                await adapter.cleanup()
            except Exception:
                pass


_registry: AdapterRegistry | None = None


def get_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
        _registry.discover()
        # Load user-supplied plugins from data/plugins as well.
        try:
            from backend.adapters.custom_script_loader import load_custom_plugins

            load_custom_plugins(_registry)
        except Exception as exc:
            logger.error("custom_plugins_failed", error=str(exc))
    return _registry
