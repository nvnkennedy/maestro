"""User-defined step templates (create / manage your own palette items).

Built-in templates live read-only in ``backend/templates/*_templates.json``.
This store holds the user's own templates in one writable JSON list under the
data dir, each tagged with the palette ``group`` it should appear under. They
are merged on top of the built-ins by the ``/test-cases/templates`` endpoint,
and managed from the Template Manager page.

Each entry:
    {"id": "t_ab12", "group": "My scripts", "label": "Reset bench",
     "action": "system.run_command", "parameters": {...}, "timeout_seconds": 120}
"""

from __future__ import annotations

import json
import uuid
from typing import Optional

from backend.config import DATA_DIR

_STORE = DATA_DIR / "user_templates.json"


def _read() -> list[dict]:
    if not _STORE.exists():
        return []
    try:
        data = json.loads(_STORE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def list_templates() -> list[dict]:
    return _read()


def _normalise(body: dict, existing_id: str | None = None) -> dict:
    return {
        "id": existing_id or f"t_{uuid.uuid4().hex[:8]}",
        "group": str(body.get("group") or "Custom"),
        "label": str(body.get("label") or "Untitled step"),
        "action": str(body.get("action") or "system.echo"),
        "parameters": body.get("parameters") if isinstance(body.get("parameters"), dict) else {},
        "timeout_seconds": int(body.get("timeout_seconds") or 30),
    }


def save_template(body: dict) -> dict:
    items = _read()
    entry = _normalise(body, existing_id=body.get("id") or None)
    for index, existing in enumerate(items):
        if existing.get("id") == entry["id"]:
            items[index] = entry
            _write(items)
            return entry
    items.append(entry)
    _write(items)
    return entry


def delete_template(template_id: str) -> bool:
    items = _read()
    remaining = [t for t in items if t.get("id") != template_id]
    if len(remaining) == len(items):
        return False
    _write(remaining)
    return True


def grouped() -> dict[str, list[dict]]:
    """User templates bucketed by their palette group (for the templates feed)."""
    buckets: dict[str, list[dict]] = {}
    for t in _read():
        buckets.setdefault(t.get("group") or "Custom", []).append(
            {
                "label": t["label"],
                "action": t["action"],
                "parameters": t.get("parameters", {}),
                "timeout_seconds": t.get("timeout_seconds", 30),
            }
        )
    return buckets


def get_template(template_id: str) -> Optional[dict]:
    return next((t for t in _read() if t.get("id") == template_id), None)
