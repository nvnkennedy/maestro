"""Live-log bridge so adapters can stream output to the Execution console.

Adapters are decoupled from the executor, so we pass the *current execution id*
through a context variable. The executor sets it for the duration of a run; any
adapter running inside that run can call :func:`emit_line` to push a line to the
live logs in real time (e.g. a long PowerShell/Python script printing progress).
"""

from __future__ import annotations

import contextvars

from backend.services.ws_manager import ws_manager
from backend.utils.helpers import utcnow

_current_execution: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "maestro_execution_id", default=None
)


def set_execution(execution_id: int | None) -> None:
    """Bind the current async context to an execution (or clear with None)."""
    _current_execution.set(execution_id)


def current_execution() -> int | None:
    return _current_execution.get()


async def emit_line(message: str, level: str = "info") -> None:
    """Stream one log line to the live console for the current execution."""
    execution_id = _current_execution.get()
    if execution_id is None:
        return  # not inside a run (e.g. a unit test) — no-op
    await ws_manager.broadcast(
        {
            "type": "log",
            "execution_id": execution_id,
            "level": level,
            "message": message,
            "timestamp": utcnow().isoformat(),
        }
    )
