"""Power script adapter capability probes."""

from __future__ import annotations

from pathlib import Path

from backend.adapters.base_adapter import AdapterResult


def check_script(script_path: str) -> AdapterResult:
    path = Path(script_path)
    if not path.exists():
        return AdapterResult(success=False, error=f"Script not found: {script_path}")
    return AdapterResult(success=True, output=f"Script available: {script_path}")
