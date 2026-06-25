"""Load user-supplied (third-party) plugins from ``data/plugins``.

A custom plugin is a directory containing ``manifest.json`` plus the Python
module referenced by its ``entry_point``. The class must subclass
``BaseAdapter``.
"""

from __future__ import annotations

import importlib.util
import json
import sys

from backend.adapters.base_adapter import BaseAdapter
from backend.config import DATA_DIR
from backend.utils.logger import get_logger

logger = get_logger("maestro.plugins.custom")

PLUGINS_DIR = DATA_DIR / "plugins"


def load_custom_plugins(registry) -> int:
    """Discover and register plugins under data/plugins. Returns count loaded."""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    loaded = 0
    for manifest_path in sorted(PLUGINS_DIR.glob("*/manifest.json")):
        plugin_dir = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            module_name, _, class_name = manifest["entry_point"].partition(":")
            module_file = plugin_dir / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(
                f"maestro_custom_{plugin_dir.name}_{module_name}", module_file
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load {module_file}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            adapter_cls = getattr(module, class_name)
            if not issubclass(adapter_cls, BaseAdapter):
                raise TypeError(f"{class_name} must subclass BaseAdapter")
            registry.register(adapter_cls(), manifest)
            loaded += 1
            logger.info("custom_plugin_loaded", plugin=manifest["name"])
        except Exception as exc:
            logger.error("custom_plugin_failed", plugin=plugin_dir.name, error=str(exc))
    return loaded
