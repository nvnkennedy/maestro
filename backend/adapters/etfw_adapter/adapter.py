"""ETFW adapter — bus sleep control and ECU state management.

Wraps the bench ETFW script (configured via ``script_path``, or the legacy
``etfw_path``). Subcommands mirror the bench etfw.py verbs::

    etfw.py bus_sleep_on
    etfw.py set_state normal_operation
    etfw.py get_state

The last known state is tracked so steps can assert on it. With no script
configured the transition is *simulated* so test design works without bench
hardware attached.
"""

from __future__ import annotations

import sys
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter


class ETFWAdapter(BaseAdapter):
    name = "etfw"
    description = "ETFW bus sleep control and ECU state management via a configurable script"

    def __init__(self) -> None:
        super().__init__()
        self._last_state: str = "unknown"

    def _register_actions(self) -> None:
        self.actions = {
            "bus_sleep_on": lambda p: self._set_state(p, "bus_sleep_on"),
            "bus_sleep_off": lambda p: self._set_state(p, "bus_sleep_off"),
            "set_state": self._set_custom_state,
            "get_state": self._get_state,
        }

    def _script_base(self, params: dict) -> list[str] | None | AdapterResult:
        script = params.get("script_path") or params.get("etfw_path")
        if not script:
            return None
        path = Path(script)
        if not path.exists():
            return AdapterResult(success=False, error=f"ETFW script not found: {script}")
        if path.suffix.lower() == ".ps1":
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
        if path.suffix.lower() == ".py":
            return [params.get("python_path", sys.executable), str(path)]
        return [str(path)]

    async def _invoke(self, params: dict, *args: str) -> AdapterResult | None:
        """Run the script with ``args``. Returns None when no script is configured
        (caller falls back to simulation)."""
        base = self._script_base(params)
        if base is None:
            return None
        if isinstance(base, AdapterResult):
            return base
        return await self._run_subprocess(
            base + list(args), timeout=float(params.get("etfw_timeout", 60))
        )

    async def _set_state(self, params: dict, state: str) -> AdapterResult:
        # ETFW verbs use the subcommand directly (set_state takes the state arg).
        if state.startswith("set_state:"):
            result = await self._invoke(params, "set_state", state.split(":", 1)[1])
        else:
            result = await self._invoke(params, state)
        if result is None:  # simulated
            self._last_state = state.replace("set_state:", "")
            return AdapterResult(
                success=True,
                output=f"[simulated] ETFW {state.replace(':', ' ')} "
                "(set 'script_path' on the device config to drive real hardware)",
                data={"state": self._last_state, "simulated": True},
            )
        if result.success:
            self._last_state = state.replace("set_state:", "")
            result.data["state"] = self._last_state
        return result

    async def _set_custom_state(self, params: dict) -> AdapterResult:
        state = params.get("state", "")
        if not state:
            return AdapterResult(success=False, error="Missing 'state' parameter")
        return await self._set_state(params, f"set_state:{state}")

    async def _get_state(self, params: dict) -> AdapterResult:
        result = await self._invoke(params, "get_state")
        if result is None:  # simulated / no script
            return AdapterResult(
                success=True, output=self._last_state, data={"state": self._last_state}
            )
        if result.success and result.output.strip():
            self._last_state = result.output.strip().splitlines()[-1].strip()
            result.data["state"] = self._last_state
        return result

    async def health_check(self) -> AdapterResult:
        return AdapterResult(success=True, output="etfw adapter loaded")
