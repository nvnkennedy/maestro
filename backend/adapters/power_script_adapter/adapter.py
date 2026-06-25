"""Power script adapter — wraps the bench power-control script.

The script path is configured per device (``script_path``) and lives on the
bench machine. Actions map to the script's subcommands, e.g.::

    power_control.py normal_power_cycle
    power_control.py power_on_edl_on  --port COM5 --channel 1

The adapter only knows how to invoke the script; the script owns the relay/PSU
logic. With no ``script_path`` configured the action is *simulated* so test
design and dry-runs work without a bench attached.
"""

from __future__ import annotations

import sys
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter

# Logical action -> the script subcommand it invokes. These mirror the bench
# power_control.py verbs. ``extra_subcommand`` on the step overrides for any
# verb the script grows later.
_SUBCOMMANDS = {
    "normal_power_cycle": "normal_power_cycle",
    "edl_power_cycle": "edl_power_cycle",
    "power_off_edl_off": "power_off_edl_off",
    "power_on_edl_off": "power_on_edl_off",
    "power_on_edl_on": "power_on_edl_on",
    "power_on": "on",
    "power_off": "off",
    "status": "status",
}


class PowerScriptAdapter(BaseAdapter):
    name = "power"
    description = "Bench power control via a configurable power_control.py / .ps1 script"

    def _register_actions(self) -> None:
        self.actions = {name: self._make(name) for name in _SUBCOMMANDS}
        # Convenience alias + generic runner + non-executing connectivity probe.
        self.actions["power_cycle"] = self._make("normal_power_cycle")
        self.actions["run"] = self._run_custom
        self.actions["check"] = self._check

    def _make(self, action: str):
        async def handler(params: dict) -> AdapterResult:
            return await self._invoke(params, _SUBCOMMANDS[action])

        return handler

    def _build_command(self, params: dict, subcommand: str) -> list[str] | AdapterResult:
        script = params.get("script_path", "")
        if not script:
            return AdapterResult(success=False, error="__simulate__")  # sentinel
        path = Path(script)
        if not path.exists():
            return AdapterResult(success=False, error=f"Power script not found: {script}")
        if path.suffix.lower() == ".ps1":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
        elif path.suffix.lower() == ".py":
            cmd = [params.get("python_path", sys.executable), str(path)]
        else:
            cmd = [str(path)]
        cmd.append(subcommand)
        if params.get("com_port") or params.get("port"):
            cmd += ["--port", str(params.get("com_port") or params.get("port"))]
        if params.get("channel") is not None and str(params.get("channel")) != "":
            cmd += ["--channel", str(params["channel"])]
        cmd += [str(a) for a in params.get("extra_args", [])]
        return cmd

    async def _invoke(self, params: dict, subcommand: str) -> AdapterResult:
        cmd = self._build_command(params, subcommand)
        if isinstance(cmd, AdapterResult):
            if cmd.error == "__simulate__":
                return AdapterResult(
                    success=True,
                    output=f"[simulated] power {subcommand} "
                    "(set 'script_path' on the power device config to drive real hardware)",
                    data={"simulated": True, "subcommand": subcommand},
                )
            return cmd
        return await self._run_subprocess(cmd, timeout=float(params.get("script_timeout", 60)))

    async def _run_custom(self, params: dict) -> AdapterResult:
        sub = params.get("subcommand") or params.get("command")
        if not sub:
            return AdapterResult(success=False, error="Missing 'subcommand' parameter")
        return await self._invoke(params, str(sub))

    async def _check(self, params: dict) -> AdapterResult:
        """Connectivity probe: validate the script WITHOUT executing it (a test
        connection must never actually toggle bench power)."""
        script = params.get("script_path", "")
        if not script:
            return AdapterResult(
                success=True,
                output="[simulated] power adapter ready (no script_path configured)",
                data={"simulated": True},
            )
        if not Path(script).exists():
            return AdapterResult(success=False, error=f"Power script not found: {script}")
        return AdapterResult(success=True, output=f"Power script present: {script}")

    async def health_check(self) -> AdapterResult:
        return AdapterResult(
            success=True,
            output="power adapter ready (script_path validated per device config)",
        )
