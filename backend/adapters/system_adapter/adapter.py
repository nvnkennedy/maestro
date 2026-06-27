"""System adapter — waits, echoes, assertions, and running your own scripts.

This built-in adapter needs no hardware. Besides the inline sandboxed
``run_script``, it can run **any existing script or executable as-is**
(``run_file``) or an arbitrary command line (``run_command``) — PowerShell,
batch, cmd, Python, shell or .exe — with your own arguments, working directory
and environment. Those run with the full environment (not sandboxed) because
they are your trusted bench scripts.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import sys
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.utils.matching import check_expectations, text_matches


def _as_args(value) -> list[str]:
    """Normalise step args to a list.

    A list is used as-is. A string is split respecting quotes (``posix=False``
    keeps Windows backslashes intact), so a quoted path with spaces stays one
    argument instead of being broken on whitespace.
    """
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(a) for a in value]
    try:
        return shlex.split(str(value), posix=False)
    except ValueError:
        return str(value).split()


def _build_command(path: Path, args: list[str], python_path: str | None) -> list[str]:
    """Pick the interpreter from the file extension and run the file verbatim."""
    ext = path.suffix.lower()
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(path), *args]
    if ext in (".bat", ".cmd"):
        return ["cmd", "/c", str(path), *args]
    if ext == ".py":
        return [python_path or sys.executable, str(path), *args]
    if ext == ".sh":
        return ["bash", str(path), *args]
    # .exe or anything else directly executable
    return [str(path), *args]


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _artifact_type_for(path) -> str:
    return "screenshot" if Path(str(path)).suffix.lower() in _IMAGE_EXTS else "log"


async def _exec_local(
    cmd, cwd: str | None, env: dict | None, timeout: float, shell: bool = False
) -> AdapterResult:
    """Run a local process, STREAMING each output line to the live log.

    stderr is merged into stdout so lines stream in the order your script
    prints them — adapt your script to print progress and it shows live in the
    Execution console.
    """
    from backend.services.live_log import emit_line

    try:
        if shell:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, cwd=cwd, env=env,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, cwd=cwd, env=env,
            )
    except FileNotFoundError:
        target = cmd if shell else cmd[0]
        return AdapterResult(success=False, error=f"Not found: {target}")

    lines: list[str] = []

    async def _pump() -> None:
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            text = raw.decode(errors="replace").rstrip("\r\n")
            lines.append(text)
            await emit_line(text)
        await proc.wait()

    try:
        await asyncio.wait_for(_pump(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return AdapterResult(
            success=False,
            output="\n".join(lines),
            error=f"Timed out after {timeout}s",
            data={"returncode": None},
        )
    rc = proc.returncode
    output = "\n".join(lines)
    return AdapterResult(
        success=rc == 0,
        output=output,
        error="" if rc == 0 else (output[-500:] or f"Exited with code {rc}"),
        data={"returncode": rc},
    )


class SystemAdapter(BaseAdapter):
    name = "system"
    description = "Local steps: wait, echo, assert, and run your own scripts/commands"

    def _register_actions(self) -> None:
        self.actions = {
            "wait": self._wait,
            "echo": self._echo,
            "assert_contains": self._assert_contains,
            "run_script": self._run_script,
            "run_file": self._run_file,
            "run_registered": self._run_registered,
            "run_command": self._run_command,
            "fail": self._fail,
        }

    async def _wait(self, params: dict) -> AdapterResult:
        seconds = float(params.get("seconds", 1))
        await asyncio.sleep(seconds)
        return AdapterResult(success=True, output=f"Waited {seconds}s")

    async def _echo(self, params: dict) -> AdapterResult:
        message = str(params.get("message", ""))
        return AdapterResult(success=True, output=message)

    async def _assert_contains(self, params: dict) -> AdapterResult:
        text = str(params.get("text", ""))
        expected = str(params.get("expected", ""))
        mode = str(params.get("match_mode", "contains"))
        ok = text_matches(text, expected, mode)
        return AdapterResult(
            success=ok,
            output=f"'{expected}' ({mode}) {'matched' if ok else 'NOT matched'} in input",
            error="" if ok else f"Assertion failed: '{expected}' ({mode}) not in '{text[:200]}'",
        )

    async def _run_script(self, params: dict) -> AdapterResult:
        from backend.services.execution_sandbox import run_sandboxed

        script = params.get("script", "")
        if not script:
            return AdapterResult(success=False, error="Missing 'script' parameter")
        return await run_sandboxed(
            script,
            interpreter=params.get("interpreter", "python"),
            timeout=float(params.get("script_timeout", 60)),
        )

    def _finish(self, result: AdapterResult, params: dict) -> AdapterResult:
        """Apply matching + attachments to a finished run.

        Two DLT-style modes (work for any produced file/log):
          * **Match** — set ``match_file`` (e.g. your ``.dlt``) + ``match_pattern``
            (regex). The step passes only if the pattern is found (unless
            ``match_required=false``), and the file is attached on match.
          * **Logging** — no ``match_pattern``: just attach with ``attach_file`` /
            ``attach_files`` / ``attach_output``.
        """
        # 1. Pass/fail on the script's stdout (supports multiple expectations).
        if result.success:
            ok, message = check_expectations(result.output, params)
            if not ok:
                result.success = False
                result.error = message

        # 2. Match a regex inside a produced file (the DLT "match" mode).
        match_file = params.get("match_file")
        match_pattern = params.get("match_pattern")
        matched: bool | None = None
        if match_file and match_pattern:
            try:
                content = Path(str(match_file)).read_text(errors="replace")
            except OSError:
                content = ""
            count = len(re.findall(str(match_pattern), content))
            matched = count > 0
            result.data["match_count"] = count
            note = f"[match] '{match_pattern}' found {count}x in {Path(str(match_file)).name}"
            result.output = (result.output + "\n" + note) if result.output else note
            if result.success and params.get("match_required", True) and not matched:
                result.success = False
                result.error = f"Pattern '{match_pattern}' not found in {match_file}"

        # 3. Attachments (step/report). Matched files attach on match.
        paths: list[dict] = list(result.data.get("artifact_paths") or [])
        if params.get("attach_output") and result.output:
            paths.append({
                "path": self.save_text_artifact(
                    str(params.get("attach_name", "script_output")), result.output
                ),
                "artifact_type": "log",
            })
        attach: list = []
        if params.get("attach_file"):
            attach.append(params["attach_file"])
        attach.extend(params.get("attach_files") or [])
        if match_file and (matched or params.get("attach_unmatched")):
            attach.append(match_file)
        seen = set()
        for item in attach:
            key = str(item)
            if item and key not in seen:
                seen.add(key)
                paths.append({"path": key, "artifact_type": _artifact_type_for(item)})
        if paths:
            result.data["artifact_paths"] = paths
        return result

    async def _run_file(self, params: dict) -> AdapterResult:
        """Run ANY existing script/executable as-is, with your own arguments.

        ``path`` → a .ps1/.bat/.cmd/.py/.sh/.exe file (interpreter auto-detected
        from the extension). ``args`` (list or string), ``cwd``, ``env`` (dict),
        ``timeout``, ``expect_contains``, ``attach_output`` are all optional.
        """
        raw = str(
            params.get("path") or params.get("script_path") or params.get("file") or ""
        ).strip()
        if not raw:
            return AdapterResult(
                success=False,
                error="No script selected — set 'path' to your script or .exe "
                "(type the path, or use the File button to upload one).",
            )
        path = Path(raw)
        if not path.exists():
            return AdapterResult(success=False, error=f"File not found: {raw}")
        cmd = _build_command(path, _as_args(params.get("args")), params.get("python_path"))
        cwd = str(params.get("cwd") or path.parent)
        env = {**os.environ, **{str(k): str(v) for k, v in (params.get("env") or {}).items()}}
        timeout = float(params.get("timeout", params.get("script_timeout", 120)))
        result = await _exec_local(cmd, cwd, env, timeout)
        return self._finish(result, params)

    async def _run_registered(self, params: dict) -> AdapterResult:
        """Run a registered script with an argument list: ``<interp> <path> <args…>``.

        ``script_id`` + ``args`` come from the palette template (each registered
        command is just an args list). The script path + interpreter are resolved
        from the registry at run time, so moving a script only needs a one-place
        edit. Matching/attachment knobs behave like ``run_file``.
        """
        from backend.services.script_registry import get_script

        script = get_script(params.get("script_id"))
        if script is None:
            return AdapterResult(
                success=False,
                error=f"Registered script '{params.get('script_id')}' not found — "
                "register it under Templates → Scripts.",
            )
        raw = str(script.get("path") or "").strip()
        if not raw:
            return AdapterResult(success=False, error=f"Script '{script['id']}' has no path set")
        path = Path(raw)
        if not path.exists():
            return AdapterResult(success=False, error=f"Script file not found: {raw}")
        args = _as_args(params.get("args"))
        cmd = _build_command(
            path, args, script.get("interpreter") or params.get("python_path")
        )
        cwd = str(params.get("cwd") or path.parent)
        env = {**os.environ, **{str(k): str(v) for k, v in (params.get("env") or {}).items()}}
        timeout = float(params.get("timeout", params.get("script_timeout", 120)))
        result = await _exec_local(cmd, cwd, env, timeout)
        return self._finish(result, params)

    async def _run_command(self, params: dict) -> AdapterResult:
        """Run an arbitrary command line through the shell (cmd on Windows)."""
        command = str(params.get("command", "")).strip()
        if not command:
            return AdapterResult(success=False, error="Missing 'command'")
        cwd = params.get("cwd") or None
        env = {**os.environ, **{str(k): str(v) for k, v in (params.get("env") or {}).items()}}
        timeout = float(params.get("timeout", params.get("script_timeout", 120)))
        result = await _exec_local(command, cwd, env, timeout, shell=True)
        return self._finish(result, params)

    async def _fail(self, params: dict) -> AdapterResult:
        return AdapterResult(
            success=False, error=str(params.get("message", "Intentional failure"))
        )
