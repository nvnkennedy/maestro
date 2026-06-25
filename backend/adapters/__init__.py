"""Adapter (plugin) layer — device/tool integrations behind a common interface."""

from backend.adapters.adapter_registry import AdapterRegistry, get_registry
from backend.adapters.base_adapter import AdapterResult, BaseAdapter

__all__ = ["AdapterResult", "BaseAdapter", "AdapterRegistry", "get_registry"]
