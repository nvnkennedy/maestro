"""SSH adapter — command execution, SFTP transfer, log capture, plus webcam and
remote-desktop (RDP) capture, all driven by the ``turbossh`` library.

turbossh owns the connection details (domain logins, legacy/embedded algorithms,
host-key policy, jump hosts, passwordless/QNX auth), so this adapter no longer
hand-rolls paramiko. It is imported lazily so the adapter still loads for test
design without it installed.

Camera / RDP capture
--------------------
turbossh's camera API is webcam-only (DirectShow over ffmpeg). So:
  * local webcam  -> local ffmpeg dshow capture (turbossh resolves/fetches ffmpeg)
  * remote webcam -> ``SSHHandler.webcam_channel`` (turbossh native, MJPEG stream)
  * remote RDP screen -> ffmpeg ``gdigrab`` run on the remote box over the same
    SSH connection, then pulled back (turbossh has no native screen grab, but it
    runs commands + pushes ffmpeg to that box, which is what makes it possible).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.adapters.ssh_adapter.capabilities import check_turbossh_available
from backend.config import ARTIFACTS_DIR
from backend.utils.matching import check_expectations


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


# A broad PATH covering Linux + QNX/embedded layouts. A non-interactive SSH exec
# gets a bare PATH, so plain commands like `uname` aren't found; we prepend these
# so commands resolve like an interactive (MobaXterm) login shell.
_EMBEDDED_PATH = (
    "/bin:/usr/bin:/sbin:/usr/sbin:/usr/local/bin:/usr/local/sbin:"
    "/proc/boot:/system/bin:/system/xbin:"
    "/ifs/bin:/ifs/usr/bin:/ifs/sbin:/mnt/bin:/mnt/usr/bin:/mnt/sbin:/opt/bin"
)


def _wrap_command(command: str, params: dict) -> str:
    """Run ``command`` with a sane PATH (and optionally a sourced profile).

    Disable with ``raw_command: true`` (required for Windows hosts). Add
    device-specific dirs with ``path`` (a colon list); source ``/etc/profile``
    first with ``source_profile: true``.
    """
    if _truthy(params.get("raw_command")):
        return command
    extra = str(params.get("path") or "").strip().strip(":")
    full = (extra + ":" if extra else "") + _EMBEDDED_PATH
    prefix = f'export PATH="{full}:$PATH" 2>/dev/null'
    if _truthy(params.get("source_profile")):
        prefix = ". /etc/profile 2>/dev/null; " + prefix
    return f"{prefix}; {command}"


class SSHAdapter(BaseAdapter):
    name = "ssh"
    description = (
        "SSH command execution, SFTP transfer, log capture, webcam capture, and "
        "remote-desktop (RDP) screenshot/recording via turbossh"
    )

    def _register_actions(self) -> None:
        self.actions = {
            "execute_command": self._execute_command,
            "upload_file": lambda p: self._transfer(p, "put"),
            "download_file": lambda p: self._transfer(p, "get"),
            "remount_rw": self._remount_rw,
            "file_exists": self._file_exists,
            "list_dir": self._list_dir,
            "tail_file": self._tail_file,
            "process_status": self._process_status,
            "reboot": self._reboot,
            "capture_journal": self._capture_journal,
            "capture_slog2info": self._capture_slog2info,
            # webcam + remote-desktop capture
            "camera_list": self._camera_list,
            "camera_screenshot": self._camera_screenshot,
            "camera_record": self._camera_record,
            "remote_camera_capture": self._remote_camera_capture,
            "rdp_screenshot": self._rdp_screenshot,
            "rdp_record": self._rdp_record,
        }

    # ---- turbossh plumbing -------------------------------------------------

    @staticmethod
    def _turbossh():
        import turbossh  # lazy: adapter still loads if turbossh is absent

        return turbossh

    async def _run_blocking(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    def _config(self, params: dict):
        """Build an SSHConfig from step/device params."""
        turbossh = self._turbossh()
        username = params.get("username", "root")
        domain = str(params.get("domain", "") or "").strip() or None
        # UPN form (user@domain) vs the default down-level DOMAIN\user.
        if domain and str(params.get("domain_format", "")).lower() == "upn":
            username = f"{username}@{domain}"
            domain = None
        policy = "reject" if _truthy(params.get("strict_host_key")) else str(
            params.get("host_key_policy", "auto")
        )
        return turbossh.SSHConfig(
            host=params.get("host", "127.0.0.1"),
            port=int(params.get("port", 22)),
            username=username,
            domain=domain,
            password=params.get("password") or None,
            key_filename=params.get("key_file") or None,
            connect_timeout=float(params.get("connect_timeout", 10)),
            command_timeout=(
                float(params["command_timeout"]) if params.get("command_timeout") else None
            ),
            enable_legacy_algorithms=_truthy(
                params.get("enable_legacy_algorithms") or params.get("legacy_algorithms")
            ),
            host_key_policy=policy,
            # Fail fast by default (responsive connection tests); benches on flaky
            # links can bump 'max_retries' on the target/step.
            max_retries=int(params.get("max_retries", 1)),
        )

    def _open(self, params: dict, *, windows: bool = False):
        """Open a connected SSHHandler (caller must close it)."""
        turbossh = self._turbossh()
        cfg = self._config(params)
        if windows:
            cfg.remote_os = "windows"
        handler = turbossh.SSHHandler(cfg, quiet=True)
        handler.connect()
        return handler

    @staticmethod
    def _err(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    # ---- command actions ---------------------------------------------------

    def _run_blocking_command(self, params: dict, command: str, *, strict_exit=None) -> AdapterResult:
        """Open a connection, run one command, and map it to an AdapterResult.

        Runs in a worker thread (turbossh is blocking). QNX/embedded sshd's benign
        'could not chdir to home directory' warning is dropped and not treated as a
        failure (matching how MobaXterm shows then ignores it).
        """
        try:
            handler = self._open(params)
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        try:
            wrapped = command if _truthy(params.get("raw_command")) else _wrap_command(command, params)
            cr = handler.run(wrapped, timeout=float(params.get("command_timeout", 30)))
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        finally:
            try:
                handler.close()
            except Exception:
                pass

        out = getattr(cr, "text", None)
        if out is None:
            out = getattr(cr, "stdout", "") or ""
        err = getattr(cr, "stderr", "") or ""
        exit_code = getattr(cr, "exit_code", 0)

        chdir_only = False
        if "could not chdir to home directory" in err.lower():
            err = "\n".join(
                ln for ln in err.splitlines() if "could not chdir to home directory" not in ln.lower()
            ).strip()
            chdir_only = not err

        strict = _truthy(params.get("strict_exit_code")) if strict_exit is None else strict_exit
        success = exit_code == 0 or (chdir_only and not strict)
        return AdapterResult(
            success=success,
            output=out,
            error=err if not success else "",
            data={"exit_code": exit_code, "stderr": err},
        )

    async def _command(self, params: dict, command: str, *, strict_exit=None) -> AdapterResult:
        return await self._run_blocking(
            lambda: self._run_blocking_command(params, command, strict_exit=strict_exit)
        )

    async def _execute_command(self, params: dict) -> AdapterResult:
        command = params.get("command", "")
        if not command:
            return AdapterResult(success=False, error="Missing 'command' parameter")
        result = await self._command(params, command)
        if result.success:
            ok, message = check_expectations(result.output, params)
            if not ok:
                result.success = False
                result.error = message
        if params.get("attach_output") and result.output:
            result.data["artifact_path"] = self.save_text_artifact(
                params.get("attach_name", "ssh_output"), result.output
            )
            result.data["artifact_type"] = "log"
        return result

    async def _transfer(self, params: dict, direction: str) -> AdapterResult:
        local = params.get("local_path", "")
        remote = params.get("remote_path", "")
        if not remote or (direction == "put" and not local):
            return AdapterResult(
                success=False, error="Both 'local_path' and 'remote_path' are required"
            )
        if direction == "get" and not local:
            from pathlib import PurePosixPath

            local = str(ARTIFACTS_DIR / f"{int(time.time())}_{PurePosixPath(remote).name}")

        def work():
            handler = self._open(params)
            try:
                if direction == "put":
                    handler.push(local, remote, make_dirs=True)
                    return ("put", None)
                handler.pull(remote, local, make_dirs=True)
                return ("get", None)
            finally:
                try:
                    handler.close()
                except Exception:
                    pass

        try:
            await self._run_blocking(work)
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        if direction == "put":
            return AdapterResult(success=True, output=f"Uploaded {local} -> {remote}")
        return AdapterResult(
            success=True,
            output=f"Downloaded {remote} -> {local}",
            data={"artifact_path": local, "artifact_type": "log"},
        )

    async def _remount_rw(self, params: dict) -> AdapterResult:
        mount_point = params.get("mount_point", "/")
        return await self._command(params, f"mount -o remount,rw {mount_point}")

    async def _file_exists(self, params: dict) -> AdapterResult:
        path = params.get("path", "")
        if not path:
            return AdapterResult(success=False, error="Missing 'path' parameter")
        result = await self._command(params, f'test -e "{path}" && echo EXISTS || echo MISSING')
        exists = "EXISTS" in (result.output or "")
        return AdapterResult(
            success=exists,
            output=f"{path} {'exists' if exists else 'does NOT exist'}",
            error="" if exists else f"Path not found on target: {path}",
        )

    async def _list_dir(self, params: dict) -> AdapterResult:
        path = params.get("path", ".")
        return await self._command(params, f'ls -la "{path}"')

    async def _tail_file(self, params: dict) -> AdapterResult:
        path = params.get("path", "")
        if not path:
            return AdapterResult(success=False, error="Missing 'path' parameter")
        lines = int(params.get("lines", 200))
        return self._attach_output(await self._command(params, f'tail -n {lines} "{path}"'), "tail")

    async def _process_status(self, params: dict) -> AdapterResult:
        name = params.get("name") or params.get("process") or ""
        if not name:
            return AdapterResult(success=False, error="Missing 'name' parameter")
        result = await self._command(params, f'pgrep -fl "{name}" || echo NOT_RUNNING')
        running = "NOT_RUNNING" not in (result.output or "") and bool((result.output or "").strip())
        return AdapterResult(
            success=running,
            output=result.output or "",
            error="" if running else f"No running process matches '{name}'",
        )

    async def _reboot(self, params: dict) -> AdapterResult:
        # A reboot drops the connection — don't fail solely on a dropped channel.
        result = await self._command(
            params, params.get("reboot_command", "reboot"), strict_exit=False
        )
        return AdapterResult(success=True, output=result.output or "Reboot issued")

    def _attach_output(self, result: AdapterResult, prefix: str) -> AdapterResult:
        if result.success and result.output:
            result.data["artifact_path"] = self.save_text_artifact(prefix, result.output)
            result.data["artifact_type"] = "log"
        return result

    async def _capture_journal(self, params: dict) -> AdapterResult:
        lines = int(params.get("lines", 200))
        return self._attach_output(
            await self._command(params, f"journalctl -n {lines} --no-pager"), "journalctl"
        )

    async def _capture_slog2info(self, params: dict) -> AdapterResult:
        return self._attach_output(
            await self._command(params, params.get("slog_command", "slog2info -b last")),
            "slog2info",
        )

    # ---- webcam + remote-desktop (RDP) capture -----------------------------

    @staticmethod
    def _ffmpeg_tools():
        from turbossh.gui import ffmpeg_tools  # importable without PyQt

        return ffmpeg_tools

    def _local_ffmpeg(self, params: dict) -> str | None:
        """Resolve a local ffmpeg: explicit path, turbossh cache/download, or PATH."""
        explicit = params.get("ffmpeg_path")
        if explicit and Path(explicit).exists():
            return explicit
        try:
            ft = self._ffmpeg_tools()
            return ft.cached_ffmpeg() or ft.ensure_local_ffmpeg()
        except Exception:
            import shutil

            return shutil.which("ffmpeg")

    @staticmethod
    def _ffmpeg_missing() -> AdapterResult:
        return AdapterResult(
            success=False,
            error="ffmpeg not found. Set 'ffmpeg_path' on the step, install ffmpeg "
            "(so it's on PATH), or let turbossh fetch it on first use.",
        )

    async def _camera_list(self, params: dict) -> AdapterResult:
        ffmpeg = self._local_ffmpeg(params)
        if not ffmpeg:
            return self._ffmpeg_missing()
        cams = await self._run_blocking(lambda: self._ffmpeg_tools().list_local_cameras(ffmpeg))
        return AdapterResult(
            success=True,
            output="\n".join(cams) if cams else "No local cameras detected",
            data={"cameras": cams},
        )

    async def _resolve_local_camera(self, ffmpeg: str, params: dict) -> str | None:
        cam = str(params.get("camera") or params.get("camera_name") or "").strip()
        if cam:
            return cam
        cams = await self._run_blocking(lambda: self._ffmpeg_tools().list_local_cameras(ffmpeg))
        return cams[0] if cams else None

    async def _camera_screenshot(self, params: dict) -> AdapterResult:
        """Single still from a LOCAL webcam."""
        ffmpeg = self._local_ffmpeg(params)
        if not ffmpeg:
            return self._ffmpeg_missing()
        cam = await self._resolve_local_camera(ffmpeg, params)
        if not cam:
            return AdapterResult(success=False, error="No local camera found; set 'camera'")
        out = params.get("output_path") or str(ARTIFACTS_DIR / f"camera_{int(time.time())}.png")
        cmd = [ffmpeg, "-y", "-f", "dshow", "-i", f"video={cam}", "-frames:v", "1", out]
        result = await self._run_subprocess(cmd, timeout=int(params.get("timeout", 30)))
        if result.success or Path(out).exists():
            result.success = True
            result.output = f"Local camera image saved to {out}"
            result.data["artifact_path"] = out
            result.data["artifact_type"] = "screenshot"
        return result

    async def _camera_record(self, params: dict) -> AdapterResult:
        """Video clip from a LOCAL webcam."""
        ffmpeg = self._local_ffmpeg(params)
        if not ffmpeg:
            return self._ffmpeg_missing()
        cam = await self._resolve_local_camera(ffmpeg, params)
        if not cam:
            return AdapterResult(success=False, error="No local camera found; set 'camera'")
        duration = int(params.get("duration", 10))
        out = params.get("output_path") or str(ARTIFACTS_DIR / f"camera_{int(time.time())}.mp4")
        cmd = [
            ffmpeg, "-y", "-f", "dshow", "-i", f"video={cam}",
            "-t", str(duration), "-pix_fmt", "yuv420p", out,
        ]
        result = await self._run_subprocess(cmd, timeout=duration + 30)
        if result.success or Path(out).exists():
            result.success = True
            result.output = f"Local camera video ({duration}s) saved to {out}"
            result.data["artifact_path"] = out
            result.data["artifact_type"] = "video"
        return result

    def _remote_ffmpeg(self, handler, params: dict) -> str:
        """ffmpeg path on the remote box (push it via turbossh if needed)."""
        override = params.get("remote_ffmpeg")
        if override:
            return override
        ft = self._ffmpeg_tools()
        local = self._local_ffmpeg(params) or "ffmpeg"
        return ft.ensure_remote_ffmpeg(handler, local)

    async def _remote_camera_capture(self, params: dict) -> AdapterResult:
        """Snapshot from a webcam attached to the REMOTE host (turbossh native)."""
        def work():
            handler = self._open(params, windows=True)
            try:
                rff = self._remote_ffmpeg(handler, params)
                cam = str(params.get("camera") or "").strip()
                if not cam:
                    cams = handler.list_cameras(ffmpeg=rff)
                    cam = cams[0] if cams else None
                if not cam:
                    raise RuntimeError("No camera detected on the remote host")
                chan = handler.webcam_channel(
                    cam, ffmpeg=rff,
                    width=int(params.get("width", 640)),
                    height=int(params.get("height", 480)),
                    fps=int(params.get("fps", 15)),
                    force=True,
                )
                buf = b""
                jpg = None
                deadline = time.time() + float(params.get("timeout", 20))
                while time.time() < deadline:
                    data = chan.recv(65536)
                    if not data:
                        break
                    buf += data
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                    if start >= 0 and end > 0:
                        jpg = buf[start : end + 2]
                        break
                try:
                    chan.close()
                finally:
                    try:
                        handler.webcam_release()
                    except Exception:
                        pass
                return (cam, jpg)
            finally:
                try:
                    handler.close()
                except Exception:
                    pass

        try:
            cam, jpg = await self._run_blocking(work)
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        if not jpg:
            return AdapterResult(success=False, error="No frame received from the remote camera")
        out = params.get("output_path") or str(ARTIFACTS_DIR / f"remote_cam_{int(time.time())}.jpg")
        Path(out).write_bytes(jpg)
        return AdapterResult(
            success=True,
            output=f"Remote camera ({cam}) snapshot saved to {out}",
            data={"artifact_path": out, "artifact_type": "screenshot"},
        )

    def _rdp_capture(self, params: dict, *, record: bool):
        """Capture the remote machine's desktop with ffmpeg gdigrab over SSH."""
        duration = int(params.get("duration", 10)) if record else 0
        suffix = "mp4" if record else "png"
        remote_tmp = params.get("remote_temp") or f"C:/Windows/Temp/maestro_rdp_{int(time.time())}.{suffix}"
        local = params.get("output_path") or str(
            ARTIFACTS_DIR / f"rdp_{int(time.time())}.{suffix}"
        )
        handler = self._open(params, windows=True)
        try:
            try:
                rff = self._remote_ffmpeg(handler, params)
            except Exception:
                rff = params.get("remote_ffmpeg") or "ffmpeg"
            fps = int(params.get("fps", 15)) if record else 1
            if record:
                cmd = (
                    f'"{rff}" -y -f gdigrab -framerate {fps} -i desktop -t {duration} '
                    f'-pix_fmt yuv420p "{remote_tmp}"'
                )
                run_timeout = float(duration + 40)
            else:
                cmd = f'"{rff}" -y -f gdigrab -framerate 1 -i desktop -frames:v 1 "{remote_tmp}"'
                run_timeout = float(params.get("timeout", 40))
            cr = handler.run(cmd, timeout=run_timeout)
            handler.pull(remote_tmp, local, make_dirs=True)
            try:
                handler.run(f'cmd /c del /q "{remote_tmp}"', timeout=15)
            except Exception:
                pass
            return (cr, local)
        finally:
            try:
                handler.close()
            except Exception:
                pass

    async def _rdp_screenshot(self, params: dict) -> AdapterResult:
        try:
            cr, local = await self._run_blocking(lambda: self._rdp_capture(params, record=False))
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        if Path(local).exists():
            return AdapterResult(
                success=True,
                output=f"RDP desktop screenshot saved to {local}",
                data={"artifact_path": local, "artifact_type": "screenshot"},
            )
        detail = getattr(cr, "stderr", "") or getattr(cr, "text", "")
        return AdapterResult(success=False, error=f"RDP screen capture failed: {detail}".strip())

    async def _rdp_record(self, params: dict) -> AdapterResult:
        try:
            cr, local = await self._run_blocking(lambda: self._rdp_capture(params, record=True))
        except Exception as exc:
            return AdapterResult(success=False, error=self._err(exc))
        if Path(local).exists():
            duration = int(params.get("duration", 10))
            return AdapterResult(
                success=True,
                output=f"RDP desktop recording ({duration}s) saved to {local}",
                data={"artifact_path": local, "artifact_type": "video"},
            )
        detail = getattr(cr, "stderr", "") or getattr(cr, "text", "")
        return AdapterResult(success=False, error=f"RDP screen recording failed: {detail}".strip())

    async def health_check(self) -> AdapterResult:
        return check_turbossh_available()
