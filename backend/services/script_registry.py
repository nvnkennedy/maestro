"""Registered custom scripts (power / etfw / dlt bench scripts).

Many bench scripts run as ``python power_control.py <args…>`` (e.g.
``normal_power_cycle``, or ``--mode edl --retries 3``). Registering such a script
once — its path, interpreter and a list of named *commands*, each with its own
**argument list** — lets the designer offer every command as a ready-to-drop
palette item, instead of making users hand-type a raw ``script`` argument.

Storage is a single JSON file under the writable data dir so it survives across
restarts and ships with no DB migration. Each entry:

    {
      "id": "power",                # stable slug
      "name": "Power control",
      "path": "C:/bench/power_control.py",
      "interpreter": "python",      # or a full path to a python.exe; "" = auto
      "description": "...",
      "commands": [
        {"label": "Normal power cycle", "args": ["normal_power_cycle"]},
        {"label": "EDL power cycle",    "args": ["edl_power_cycle"]},
        ...
      ]
    }
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from backend.config import DATA_DIR

_STORE = DATA_DIR / "registered_scripts.json"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return slug or "script"


def _read() -> list[dict]:
    if not _STORE.exists():
        return []
    try:
        data = json.loads(_STORE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(scripts: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(scripts, indent=2), encoding="utf-8")


def list_scripts() -> list[dict]:
    return _read()


def get_script(script_id: Any) -> Optional[dict]:
    sid = str(script_id or "")
    return next((s for s in _read() if str(s.get("id")) == sid), None)


def _coerce_args(value) -> list[str]:
    """Normalise an args value to a list of strings (accepts a list or a string)."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(a) for a in value]
    return [a for a in str(value).split() if a]


def _normalise(body: dict, existing_id: str | None = None) -> dict:
    commands = []
    # Accept the new "commands" (label + args) and the legacy "subcommands".
    for cmd in body.get("commands") or []:
        if isinstance(cmd, dict) and (cmd.get("label") or cmd.get("args")):
            args = _coerce_args(cmd.get("args"))
            commands.append(
                {
                    "label": str(cmd.get("label") or " ".join(args) or "run"),
                    "args": args,
                }
            )
    for sub in body.get("subcommands") or []:
        name = sub if isinstance(sub, str) else sub.get("name", "")
        if name:
            commands.append({"label": str(name), "args": [str(name)]})
    return {
        "id": existing_id or _slugify(body.get("id") or body.get("name") or "script"),
        "name": str(body.get("name") or body.get("id") or "Script"),
        "path": str(body.get("path") or ""),
        "interpreter": str(body.get("interpreter") or ""),
        "description": str(body.get("description") or ""),
        "commands": commands,
    }


def save_script(body: dict) -> dict:
    """Create or update a registered script (keyed by id). Returns the stored entry."""
    scripts = _read()
    entry = _normalise(body, existing_id=str(body["id"]) if body.get("id") else None)
    # Ensure a unique id on create.
    ids = {s["id"] for s in scripts}
    if not body.get("id"):
        base, i = entry["id"], 2
        while entry["id"] in ids:
            entry["id"] = f"{base}_{i}"
            i += 1
    replaced = False
    for index, existing in enumerate(scripts):
        if existing.get("id") == entry["id"]:
            scripts[index] = entry
            replaced = True
            break
    if not replaced:
        scripts.append(entry)
    _write(scripts)
    return entry


def delete_script(script_id: str) -> bool:
    scripts = _read()
    remaining = [s for s in scripts if str(s.get("id")) != str(script_id)]
    if len(remaining) == len(scripts):
        return False
    _write(remaining)
    return True


def as_templates() -> list[dict]:
    """Expose each registered command as a designer palette template.

    Dropping one creates a ``system.run_registered`` step bound to the script id
    with the command's argument list, run as ``<interpreter> <path> <args…>``.
    """
    templates: list[dict] = []
    for script in _read():
        if not script.get("path"):
            continue
        commands = script.get("commands") or [{"label": "run", "args": []}]
        for cmd in commands:
            label = f"{script['name']}: {cmd.get('label') or ' '.join(cmd.get('args', [])) or 'run'}"
            templates.append(
                {
                    "label": label,
                    "action": "system.run_registered",
                    "parameters": {
                        "script_id": script["id"],
                        "args": cmd.get("args", []),
                    },
                    "timeout_seconds": 120,
                }
            )
    return templates
