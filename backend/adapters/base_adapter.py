"""Abstract base class every Maestro adapter implements."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class AdapterResult:
    """Uniform result returned by every adapter action."""

    success: bool
    output: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "data": self.data,
            "duration_seconds": self.duration_seconds,
        }


class BaseAdapter(ABC):
    """Contract for all adapters (SSH, ADB, power, DLT, ...).

    Subclasses register actions in ``self.actions`` mapping an action name to
    an async callable ``(params: dict) -> AdapterResult``.
    """

    name: str = "base"
    description: str = ""

    def __init__(self) -> None:
        self.actions: dict[str, Callable[[dict], Awaitable[AdapterResult]]] = {}
        self._register_actions()

    @abstractmethod
    def _register_actions(self) -> None:
        """Populate ``self.actions``."""

    async def execute(
        self, action: str, params: dict | None = None, timeout: float = 30
    ) -> AdapterResult:
        """Run an action with timing and timeout handling."""
        params = params or {}
        handler = self.actions.get(action)
        if handler is None:
            return AdapterResult(
                success=False,
                error=f"Adapter '{self.name}' has no action '{action}'. "
                f"Available: {sorted(self.actions)}",
            )
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(handler(params), timeout=timeout)
        except asyncio.TimeoutError:
            result = AdapterResult(
                success=False, error=f"Action '{action}' timed out after {timeout}s"
            )
        except Exception as exc:  # adapters must never crash the executor
            result = AdapterResult(success=False, error=f"{type(exc).__name__}: {exc}")
        result.duration_seconds = round(time.monotonic() - start, 3)
        return result

    async def health_check(self) -> AdapterResult:
        """Default health check: adapter is loadable. Subclasses override."""
        return AdapterResult(success=True, output=f"{self.name} adapter loaded")

    def get_capabilities(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "actions": sorted(self.actions.keys()),
        }

    async def cleanup(self) -> None:
        """Release held resources (connections, processes). Optional."""

    # ---- helpers shared by subclasses -------------------------------------

    @staticmethod
    def save_text_artifact(prefix: str, text: str, suffix: str = ".txt") -> str:
        """Persist captured text as a report attachment file; returns its path."""
        import time as _time

        from backend.config import ARTIFACTS_DIR

        path = ARTIFACTS_DIR / f"{prefix}_{int(_time.time() * 1000)}{suffix}"
        path.write_text(text, encoding="utf-8", errors="replace")
        return str(path)

    @staticmethod
    async def _run_subprocess(cmd: list[str], timeout: float = 30) -> AdapterResult:
        """Run a local subprocess and capture output."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except FileNotFoundError:
            return AdapterResult(success=False, error=f"Executable not found: {cmd[0]}")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return AdapterResult(success=False, error=f"Command timed out: {' '.join(cmd)}")
        out = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        return AdapterResult(
            success=proc.returncode == 0,
            output=out,
            error=err if proc.returncode != 0 else "",
            data={"returncode": proc.returncode, "stderr": err},
        )
