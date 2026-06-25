"""DLT adapter — capture DLT logs and verify patterns.

Two capture modes:
  * **Script mode** (preferred when ``script_path`` is set): drives your bench
    ``dlt.py`` flow — ``start --host H --port P`` / ``stop`` / ``capture --out F``.
  * **Built-in TCP mode** (no script configured): connects to a DLT daemon
    (default port 3490) and streams the raw payload to a file under
    ``data/artifacts`` — so capture works even without your script present.

``verify_pattern`` / ``tail`` / ``save_file`` operate on whichever ``.dlt`` file
the chosen mode produced (or an explicit ``file_path``).
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.config import ARTIFACTS_DIR


class DLTAdapter(BaseAdapter):
    name = "dlt"
    description = "DLT log capture (bench script or built-in TCP) with pattern verification"

    def __init__(self) -> None:
        super().__init__()
        self._capture_task: asyncio.Task | None = None
        self._capture_file: Path | None = None
        self._stop_event: asyncio.Event | None = None

    def _register_actions(self) -> None:
        self.actions = {
            "start_capture": self._start_capture,
            "stop_capture": self._stop_capture,
            "capture": self._capture_once,
            "save_file": self._save_file,
            "verify_pattern": self._verify_pattern,
            "tail": self._tail,
        }

    # ---- script-mode plumbing ---------------------------------------------

    def _script_base(self, params: dict) -> list[str] | None | AdapterResult:
        script = params.get("script_path") or params.get("dlt_script")
        if not script:
            return None
        path = Path(script)
        if not path.exists():
            return AdapterResult(success=False, error=f"DLT script not found: {script}")
        if path.suffix.lower() == ".ps1":
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
        if path.suffix.lower() == ".py":
            return [params.get("python_path", sys.executable), str(path)]
        return [str(path)]

    # ---- capture actions ---------------------------------------------------

    async def _start_capture(self, params: dict) -> AdapterResult:
        base = self._script_base(params)
        if isinstance(base, AdapterResult):
            return base
        if base is not None:  # script mode
            args = base + ["start", "--host", params.get("host", "127.0.0.1"),
                           "--port", str(params.get("port", 3490))]
            if params.get("out_file"):
                self._capture_file = Path(params["out_file"])
                args += ["--out", params["out_file"]]
            result = await self._run_subprocess(args, timeout=float(params.get("script_timeout", 60)))
            if result.success and not result.output:
                result.output = "DLT capture started (script mode)"
            return result

        # built-in TCP mode
        if self._capture_task is not None and not self._capture_task.done():
            return AdapterResult(success=False, error="A DLT capture is already running")
        host = params.get("host", "127.0.0.1")
        port = int(params.get("port", 3490))
        self._capture_file = ARTIFACTS_DIR / f"dlt_capture_{int(time.time())}.dlt"
        self._stop_event = asyncio.Event()
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close()
        except (OSError, asyncio.TimeoutError) as exc:
            return AdapterResult(
                success=False, error=f"Cannot reach DLT daemon at {host}:{port} — {exc}"
            )
        self._capture_task = asyncio.create_task(self._capture_loop(host, port, self._capture_file))
        return AdapterResult(
            success=True,
            output=f"DLT capture started -> {self._capture_file}",
            data={"artifact_path": str(self._capture_file), "artifact_type": "log"},
        )

    async def _stop_capture(self, params: dict) -> AdapterResult:
        base = self._script_base(params)
        if isinstance(base, AdapterResult):
            return base
        if base is not None:  # script mode
            result = await self._run_subprocess(
                base + ["stop"], timeout=float(params.get("script_timeout", 60))
            )
            if self._capture_file and self._capture_file.exists():
                result.data["artifact_path"] = str(self._capture_file)
                result.data["artifact_type"] = "log"
            if result.success and not result.output:
                result.output = "DLT capture stopped (script mode)"
            return result

        # built-in TCP mode
        if self._capture_task is None:
            return AdapterResult(success=False, error="No DLT capture is running")
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            await asyncio.wait_for(self._capture_task, timeout=5)
        except asyncio.TimeoutError:
            self._capture_task.cancel()
        path = self._capture_file
        self._capture_task = None
        size = path.stat().st_size if path and path.exists() else 0
        return AdapterResult(
            success=True,
            output=f"DLT capture stopped ({size} bytes) -> {path}",
            data={"artifact_path": str(path), "artifact_type": "log", "bytes": size},
        )

    async def _capture_once(self, params: dict) -> AdapterResult:
        """One-shot capture via the bench script (``dlt.py capture --out FILE``)."""
        base = self._script_base(params)
        if base is None:
            return AdapterResult(
                success=True,
                output="[simulated] DLT capture (set 'script_path' to your dlt.py to run a real capture)",
                data={"simulated": True},
            )
        if isinstance(base, AdapterResult):
            return base
        out = params.get("out_file") or str(ARTIFACTS_DIR / f"dlt_{int(time.time())}.dlt")
        args = base + ["capture", "--out", out]
        if params.get("host"):
            args += ["--host", params["host"], "--port", str(params.get("port", 3490))]
        result = await self._run_subprocess(args, timeout=float(params.get("script_timeout", 300)))
        if Path(out).exists():
            self._capture_file = Path(out)
            result.success = True
            result.data["artifact_path"] = out
            result.data["artifact_type"] = "log"
            if not result.output:
                result.output = f"DLT capture saved -> {out}"
        return result

    async def _capture_loop(self, host: str, port: int, path: Path) -> None:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            with path.open("ab") as fh:
                while self._stop_event is not None and not self._stop_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(reader.read(65536), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    if not chunk:
                        break
                    fh.write(chunk)
                    fh.flush()
        finally:
            writer.close()

    # ---- file utilities ----------------------------------------------------

    def _resolved_file(self, params: dict) -> Path | None:
        raw = params.get("file_path") or (str(self._capture_file) if self._capture_file else "")
        if not raw or raw == ".":
            return None
        path = Path(raw)
        return path if path.exists() else None

    async def _save_file(self, params: dict) -> AdapterResult:
        import shutil

        source = self._resolved_file(params)
        if source is None:
            return AdapterResult(
                success=False,
                error="No DLT file found — set 'file_path' to your capture output, "
                "or run a capture first",
            )
        dest = ARTIFACTS_DIR / f"dlt_{int(time.time())}_{source.name}"
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)
        size_kb = dest.stat().st_size // 1024
        return AdapterResult(
            success=True,
            output=f"DLT file attached: {dest.name} ({size_kb} KB)",
            data={"artifact_path": str(dest), "artifact_type": "log"},
        )

    def _read_capture_text(self, params: dict) -> str | None:
        path = self._resolved_file(params)
        if path is None:
            return None
        return path.read_bytes().decode("utf-8", errors="replace")

    async def _verify_pattern(self, params: dict) -> AdapterResult:
        pattern = params.get("pattern", "")
        if not pattern:
            return AdapterResult(success=False, error="Missing 'pattern' parameter")
        text = self._read_capture_text(params)
        if text is None:
            return AdapterResult(success=False, error="No DLT capture file available")
        matches = re.findall(pattern, text)
        return AdapterResult(
            success=len(matches) > 0,
            output=f"Pattern '{pattern}' matched {len(matches)} time(s)",
            error="" if matches else f"Pattern '{pattern}' not found in capture",
            data={"match_count": len(matches), "matches": matches[:50]},
        )

    async def _tail(self, params: dict) -> AdapterResult:
        text = self._read_capture_text(params)
        if text is None:
            return AdapterResult(success=False, error="No DLT capture file available")
        lines = text.splitlines()[-int(params.get("lines", 100)):]
        return AdapterResult(success=True, output="\n".join(lines))

    async def health_check(self) -> AdapterResult:
        running = self._capture_task is not None and not self._capture_task.done()
        return AdapterResult(
            success=True,
            output=f"dlt adapter loaded (capture {'running' if running else 'idle'})",
        )

    async def cleanup(self) -> None:
        if self._capture_task is not None and not self._capture_task.done():
            if self._stop_event is not None:
                self._stop_event.set()
            self._capture_task.cancel()
