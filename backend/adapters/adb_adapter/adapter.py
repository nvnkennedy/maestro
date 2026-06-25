"""ADB adapter — Android device control via the ``turboadb`` library.

Drives the device through ``turboadb.ADBHandler`` (the current turboadb API)
instead of shelling out to a raw ``adb`` binary. turboadb is imported lazily so
the adapter still loads for test design on a machine without it; missing tools /
no device surface as clear runtime errors rather than crashes.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from backend.adapters.adb_adapter.capabilities import find_adb
from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.config import ARTIFACTS_DIR
from backend.utils.matching import check_expectations


class ADBAdapter(BaseAdapter):
    name = "adb"
    description = (
        "Android device control via turboadb: shell, push/pull, install, "
        "logcat, screenshot, screenrecord, wireless connect"
    )

    def _register_actions(self) -> None:
        self.actions = {
            "list_devices": self._list_devices,
            "shell": self._shell,
            "push": self._push,
            "pull": self._pull,
            "install_apk": self._install_apk,
            "uninstall_apk": self._uninstall_apk,
            "logcat_dump": self._logcat_dump,
            "logcat_clear": self._logcat_clear,
            "screenshot": self._screenshot,
            "screenrecord": self._screenrecord,
            "reboot": self._reboot,
            "wait_for_device": self._wait_for_device,
            "connect_wireless": self._connect_wireless,
            "device_info": self._device_info,
        }

    # ---- turboadb plumbing -------------------------------------------------

    @staticmethod
    def _turboadb():
        import turboadb  # lazy: adapter still loads if turboadb is absent

        return turboadb

    async def _run_blocking(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    def _adb_path(self, params: dict) -> str | None:
        return params.get("adb_path") or find_adb()

    def _handler(self, params: dict):
        """Build an ADBHandler from step/device params (cheap; no I/O)."""
        turboadb = self._turboadb()
        cfg = turboadb.ADBConfig(
            serial=params.get("serial") or params.get("device") or None,
            adb_path=self._adb_path(params),
            command_timeout=(
                float(params["command_timeout"]) if params.get("command_timeout") else None
            ),
        )
        host = params.get("host")
        if host:  # network / wireless target
            cfg.host = host
            if params.get("port"):
                cfg.port = int(params["port"])
        return turboadb.ADBHandler(cfg, quiet=True)

    @staticmethod
    def _from_command(cr) -> AdapterResult:
        """Map a turboadb CommandResult to an AdapterResult."""
        out = getattr(cr, "text", None)
        if out is None:
            out = getattr(cr, "stdout", "") or ""
        ok = bool(getattr(cr, "ok", getattr(cr, "exit_code", 0) == 0))
        stderr = getattr(cr, "stderr", "") or ""
        return AdapterResult(
            success=ok,
            output=out,
            error="" if ok else (stderr or out),
            data={"exit_code": getattr(cr, "exit_code", None), "stderr": stderr},
        )

    @staticmethod
    def _adb_error(exc: Exception) -> AdapterResult:
        return AdapterResult(success=False, error=f"{type(exc).__name__}: {exc}")

    async def execute(self, action, params=None, timeout=30):
        """Verify a usable adb before any action (clearer than a deep stack)."""
        params = params or {}
        turboadb = None
        try:
            turboadb = self._turboadb()
        except Exception:
            return AdapterResult(
                success=False,
                error="turboadb is not installed (pip install turboadb).",
            )
        if not (params.get("adb_path") or find_adb() or turboadb.adb_available()):
            return AdapterResult(
                success=False,
                error="adb not found — install Android platform-tools, set "
                "ANDROID_HOME / adb_path, run `turboadb fetch-tools`, or use a "
                "Maestro build with adb bundled in bin/platform-tools.",
            )
        return await super().execute(action, params, timeout=timeout)

    # ---- actions -----------------------------------------------------------

    async def _list_devices(self, params: dict) -> AdapterResult:
        turboadb = self._turboadb()
        try:
            devices = await self._run_blocking(
                lambda: turboadb.list_devices(adb_path=self._adb_path(params))
            )
        except Exception as exc:
            return self._adb_error(exc)
        items = []
        for d in devices:
            items.append(
                {
                    "serial": getattr(d, "serial", None) or (d.get("serial") if isinstance(d, dict) else str(d)),
                    "state": getattr(d, "state", None) or (d.get("state") if isinstance(d, dict) else ""),
                    "model": getattr(d, "model", "") or (d.get("model", "") if isinstance(d, dict) else ""),
                }
            )
        listing = "\n".join(f"{i['serial']}\t{i['state']}\t{i['model']}".rstrip() for i in items)
        return AdapterResult(
            success=True,
            output=listing or "No devices connected",
            data={"devices": items, "count": len(items)},
        )

    async def _shell(self, params: dict) -> AdapterResult:
        command = params.get("command", "")
        if not command:
            return AdapterResult(success=False, error="Missing 'command' parameter")

        def work():
            return self._handler(params).shell(
                command,
                timeout=float(params.get("command_timeout", 30)),
                su=bool(params.get("su")),
            )

        try:
            cr = await self._run_blocking(work)
        except Exception as exc:
            return self._adb_error(exc)
        result = self._from_command(cr)
        if result.success:
            ok, message = check_expectations(result.output, params)
            if not ok:
                result.success = False
                result.error = message
        if params.get("attach_output") and result.output:
            result.data["artifact_path"] = self.save_text_artifact(
                params.get("attach_name", "adb_output"), result.output
            )
            result.data["artifact_type"] = "log"
        return result

    async def _push(self, params: dict) -> AdapterResult:
        local, remote = params.get("local_path", ""), params.get("remote_path", "")
        if not local or not remote:
            return AdapterResult(
                success=False, error="Both 'local_path' and 'remote_path' are required"
            )
        try:
            tr = await self._run_blocking(lambda: self._handler(params).push(local, remote))
        except Exception as exc:
            return self._adb_error(exc)
        return AdapterResult(
            success=True,
            output=f"Pushed {local} -> {remote} ({getattr(tr, 'human_size', '')})".strip(),
            data={"size_bytes": getattr(tr, "size_bytes", None)},
        )

    async def _pull(self, params: dict) -> AdapterResult:
        local, remote = params.get("local_path", ""), params.get("remote_path", "")
        if not local or not remote:
            return AdapterResult(
                success=False, error="Both 'local_path' and 'remote_path' are required"
            )
        try:
            tr = await self._run_blocking(lambda: self._handler(params).pull(remote, local))
        except Exception as exc:
            return self._adb_error(exc)
        return AdapterResult(
            success=True,
            output=f"Pulled {remote} -> {local} ({getattr(tr, 'human_size', '')})".strip(),
            data={"artifact_path": local, "artifact_type": "log", "size_bytes": getattr(tr, "size_bytes", None)},
        )

    async def _install_apk(self, params: dict) -> AdapterResult:
        apk = params.get("apk_path", "")
        if not apk:
            return AdapterResult(success=False, error="Missing 'apk_path' parameter")
        try:
            cr = await self._run_blocking(
                lambda: self._handler(params).install(apk, replace=bool(params.get("reinstall", True)))
            )
        except Exception as exc:
            return self._adb_error(exc)
        return self._from_command(cr)

    async def _uninstall_apk(self, params: dict) -> AdapterResult:
        package = params.get("package", "")
        if not package:
            return AdapterResult(success=False, error="Missing 'package' parameter")
        try:
            cr = await self._run_blocking(
                lambda: self._handler(params).uninstall(package, keep_data=bool(params.get("keep_data")))
            )
        except Exception as exc:
            return self._adb_error(exc)
        return self._from_command(cr)

    async def _logcat_clear(self, params: dict) -> AdapterResult:
        try:
            cr = await self._run_blocking(lambda: self._handler(params).logcat_clear())
        except Exception as exc:
            return self._adb_error(exc)
        res = self._from_command(cr)
        if res.success and not res.output:
            res.output = "logcat buffers cleared"
        return res

    async def _logcat_dump(self, params: dict) -> AdapterResult:
        save_to = str(ARTIFACTS_DIR / f"logcat_{int(time.time())}.txt")
        tag = params.get("filter") or params.get("tag") or None

        def work():
            self._handler(params).logcat(dump=True, tag=tag, save_to=save_to, clean=True)
            return save_to

        try:
            path = await self._run_blocking(work)
        except Exception as exc:
            return self._adb_error(exc)
        text = ""
        if Path(path).exists():
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        lines = int(params.get("lines", 500))
        tail = "\n".join(text.splitlines()[-lines:])
        return AdapterResult(
            success=True,
            output=f"Captured logcat -> attached {path}\n\n{tail}",
            data={"artifact_path": path, "artifact_type": "log"},
        )

    async def _screenshot(self, params: dict) -> AdapterResult:
        local = params.get("local_path") or str(ARTIFACTS_DIR / f"adb_screenshot_{int(time.time())}.png")
        Path(local).parent.mkdir(parents=True, exist_ok=True)

        def work():
            self._handler(params).screenshot(local)
            return local

        try:
            await self._run_blocking(work)
        except Exception as exc:
            return self._adb_error(exc)
        if not Path(local).exists():
            return AdapterResult(success=False, error="Screenshot was not produced")
        return AdapterResult(
            success=True,
            output=f"Screenshot saved to {local}",
            data={"artifact_path": local, "artifact_type": "screenshot"},
        )

    async def _screenrecord(self, params: dict) -> AdapterResult:
        duration = int(params.get("duration", 10))
        local = params.get("local_path") or str(ARTIFACTS_DIR / f"adb_record_{int(time.time())}.mp4")
        Path(local).parent.mkdir(parents=True, exist_ok=True)

        def work():
            self._handler(params).screen_record(local, time_limit=duration)
            return local

        try:
            await self._run_blocking(work)
        except Exception as exc:
            return self._adb_error(exc)
        if not Path(local).exists():
            return AdapterResult(success=False, error="Screen recording was not produced")
        return AdapterResult(
            success=True,
            output=f"Screen recording ({duration}s) saved to {local}",
            data={"artifact_path": local, "artifact_type": "video"},
        )

    async def _reboot(self, params: dict) -> AdapterResult:
        mode = params.get("mode") or None  # None, bootloader, recovery, sideload
        try:
            cr = await self._run_blocking(lambda: self._handler(params).reboot(mode))
        except Exception as exc:
            return self._adb_error(exc)
        res = self._from_command(cr)
        if not res.output:
            res.output = f"Reboot issued ({mode or 'normal'})"
        return res

    async def _wait_for_device(self, params: dict) -> AdapterResult:
        timeout = float(params.get("wait_timeout", 120))
        try:
            await self._run_blocking(lambda: self._handler(params).wait_for_device(timeout=timeout))
        except Exception as exc:
            return self._adb_error(exc)
        return AdapterResult(success=True, output="Device is online")

    async def _connect_wireless(self, params: dict) -> AdapterResult:
        """Connect to a device over TCP/IP (wireless adb)."""
        host = params.get("host")
        if not host:
            return AdapterResult(success=False, error="Missing 'host' for wireless connect")
        port = int(params.get("port", 5555))

        def work():
            return self._handler(params).connect_tcp(host, port)

        try:
            await self._run_blocking(work)
        except Exception as exc:
            return self._adb_error(exc)
        return AdapterResult(success=True, output=f"Connected to {host}:{port}")

    async def _device_info(self, params: dict) -> AdapterResult:
        """Identity / build info for the target device."""
        try:
            info = await self._run_blocking(lambda: self._handler(params).device_info())
        except Exception as exc:
            return self._adb_error(exc)
        data = info if isinstance(info, dict) else {"info": str(info)}
        lines = "\n".join(f"{k}: {v}" for k, v in data.items())
        return AdapterResult(success=True, output=lines or str(info), data={"device_info": data})

    async def health_check(self) -> AdapterResult:
        try:
            turboadb = self._turboadb()
        except Exception:
            return AdapterResult(success=False, error="turboadb is not installed")
        adb = self._adb_path({}) or (turboadb.find_adb() if hasattr(turboadb, "find_adb") else None)
        if not adb:
            return AdapterResult(
                success=False,
                error="adb executable not found (try `turboadb fetch-tools`)",
            )
        try:
            version = await self._run_blocking(turboadb.adb_version)
        except Exception as exc:
            return self._adb_error(exc)
        return AdapterResult(success=True, output=f"turboadb {turboadb.__version__}; {version}")
