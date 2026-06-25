"""Subprocess execution of user-supplied scripts.

Scripts run in a child process with their own temporary working directory, a
trimmed environment and a hard timeout. This contains *accidents* (a runaway
loop, a wrong path) but is **not** a security sandbox: the child runs as the
same OS user as Maestro, with full filesystem and network access — it can read
``data/maestro.db`` and the vault key. Treat ``run_script`` as "run code on
this host" and protect it with authentication (``MAESTRO_API_TOKEN``).

Non-Python interpreters (bash/cmd/powershell) are therefore disabled unless
``MAESTRO_ALLOW_SHELL`` is explicitly enabled.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult

_SAFE_ENV_KEYS = ("SYSTEMROOT", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT", "LANG", "HOME")
_SHELL_INTERPRETERS = ("powershell", "bash", "cmd")


def _shell_allowed() -> bool:
    return os.getenv("MAESTRO_ALLOW_SHELL", "false").lower() in ("1", "true", "yes")


async def run_sandboxed(
    script: str, interpreter: str = "python", timeout: float = 60
) -> AdapterResult:
    """Run a script body in a child subprocess and capture its output."""
    if interpreter in _SHELL_INTERPRETERS and not _shell_allowed():
        return AdapterResult(
            success=False,
            error=(
                f"Interpreter '{interpreter}' is disabled. Set MAESTRO_ALLOW_SHELL=true "
                "to permit shell scripts (they run with full host privileges)."
            ),
        )
    suffix = {"python": ".py", "powershell": ".ps1", "bash": ".sh", "cmd": ".bat"}.get(
        interpreter, ".txt"
    )
    env = {k: v for k, v in os.environ.items() if k.upper() in _SAFE_ENV_KEYS}

    with tempfile.TemporaryDirectory(prefix="maestro_sandbox_") as workdir:
        script_path = Path(workdir) / f"user_script{suffix}"
        script_path.write_text(script, encoding="utf-8")

        if interpreter == "python":
            cmd = [sys.executable, "-I", str(script_path)]  # -I = isolated mode
        elif interpreter == "powershell":
            cmd = [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
            ]
        elif interpreter == "bash":
            cmd = ["bash", str(script_path)]
        elif interpreter == "cmd":
            cmd = ["cmd", "/c", str(script_path)]
        else:
            return AdapterResult(
                success=False, error=f"Unsupported interpreter: {interpreter}"
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except FileNotFoundError:
            return AdapterResult(success=False, error=f"Interpreter not found: {cmd[0]}")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return AdapterResult(
                success=False, error=f"Sandboxed script timed out after {timeout}s"
            )

        out = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        return AdapterResult(
            success=proc.returncode == 0,
            output=out,
            error=err if proc.returncode != 0 else "",
            data={"returncode": proc.returncode, "stderr": err},
        )
