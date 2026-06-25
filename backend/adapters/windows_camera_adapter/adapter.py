"""Windows camera adapter — desktop screenshot and camera/video capture.

Screenshot uses PowerShell + System.Drawing (no extra dependencies). Camera
video capture shells out to ffmpeg (DirectShow) when available.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from backend.adapters.base_adapter import AdapterResult, BaseAdapter
from backend.config import ARTIFACTS_DIR


def _find_ffmpeg(params: dict) -> str | None:
    """Locate ffmpeg: explicit param → bundled bin/ → PATH → common installs."""
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    explicit = params.get("ffmpeg_path")
    if explicit and Path(explicit).exists():
        return explicit
    # Prefer the copy bundled with Maestro (ships in the wheel / installer),
    # searching every bin location recursively (ffmpeg often lives in a
    # versioned subfolder like bin/ffmpeg-8.1.2/bin/ffmpeg.exe).
    from backend.config import find_bundled_executable

    bundled = find_bundled_executable(exe)
    if bundled:
        return str(bundled)
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Common Windows install locations (winget / choco / scoop / manual).
    home = Path.home()
    candidates = [
        Path(r"C:\ffmpeg\bin") / exe,
        Path(r"C:\Program Files\ffmpeg\bin") / exe,
        Path(r"C:\ProgramData\chocolatey\bin") / exe,
        home / "scoop" / "shims" / exe,
    ]
    winget = Path(os.getenv("LOCALAPPDATA", str(home))) / "Microsoft" / "WinGet" / "Packages"
    if winget.exists():
        candidates += list(winget.glob(f"**/{exe}"))
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _ffmpeg_error() -> AdapterResult:
    return AdapterResult(
        success=False,
        error=(
            "ffmpeg not found. Quickest: download ffmpeg.exe from "
            "https://www.gyan.dev/ffmpeg/builds/ and drop it in the app's bin\\ "
            "folder (no setup). Or install it (winget install Gyan.FFmpeg) / set "
            "'ffmpeg_path' on the step."
        ),
    )

_PS_SCREENSHOT = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$bmp.Save('{path}', [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
"""


class WindowsCameraAdapter(BaseAdapter):
    name = "camera"
    description = "Desktop screenshots and camera video recording (Windows)"

    def _register_actions(self) -> None:
        self.actions = {
            "screenshot": self._screenshot,
            "capture": self._capture,
            "capture_webcam": self._capture_webcam,
            "record_video": self._record_video,
            "list_devices": self._list_devices,
            "detect": self._detect,
        }

    async def _capture(self, params: dict) -> AdapterResult:
        """One webcam step that takes a photo OR records a video.

        ``mode``: ``photo`` (default) grabs a single still; ``video`` records for
        ``duration`` seconds. Lets a single designer step do either without
        switching actions.
        """
        mode = str(params.get("mode", "photo")).lower()
        if mode in ("video", "record", "mp4"):
            return await self._record_video(params)
        return await self._capture_webcam(params)

    async def _dshow_device(self, ffmpeg: str, params: dict) -> str:
        """Resolve the ffmpeg dshow input for the webcam.

        Uses ``camera_name`` when given; otherwise auto-detects the first video
        device ffmpeg reports, so a step works without the exact dshow name.
        """
        name = str(params.get("camera_name") or "").strip()
        if not name:
            probe = await self._run_subprocess(
                [ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=20
            )
            listing = probe.data.get("stderr", "") if probe.data else ""
            for line in listing.splitlines():
                if "(video)" in line and '"' in line:
                    name = line.split('"')[1]
                    break
            if not name:
                name = "Integrated Camera"  # last-resort default
        return name if name.lower().startswith("video=") else f"video={name}"

    async def _capture_webcam(self, params: dict) -> AdapterResult:
        """Grab a single still frame from the webcam (not the desktop)."""
        ffmpeg = _find_ffmpeg(params)
        if not ffmpeg:
            return _ffmpeg_error()
        device = await self._dshow_device(ffmpeg, params)
        path = params.get(
            "output_path", str(ARTIFACTS_DIR / f"webcam_{int(time.time())}.png")
        )
        cmd = [ffmpeg, "-y", "-f", "dshow", "-i", device, "-frames:v", "1", path]
        result = await self._run_subprocess(cmd, timeout=int(params.get("timeout", 30)))
        if result.success or Path(path).exists():
            result.success = True
            result.output = f"Webcam image saved to {path}"
            result.data["artifact_path"] = path
            result.data["artifact_type"] = "screenshot"
        return result

    async def _detect(self, params: dict) -> AdapterResult:
        """Detect cameras attached to this machine (no manual config needed)."""
        if not sys.platform.startswith("win"):
            return AdapterResult(success=False, error="Camera detection requires Windows")
        script = (
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.PNPClass -in @('Camera','Image') -and $_.Status -eq 'OK' } | "
            "Select-Object -ExpandProperty Name"
        )
        result = await self._run_subprocess(
            ["powershell", "-NoProfile", "-Command", script], timeout=30
        )
        devices = [
            {"name": line.strip(), "kind": "camera"}
            for line in result.output.splitlines()
            if line.strip()
        ]
        return AdapterResult(
            success=True,
            output="\n".join(d["name"] for d in devices) or "No cameras detected",
            data={"devices": devices},
        )

    async def _screenshot(self, params: dict) -> AdapterResult:
        if not sys.platform.startswith("win"):
            return AdapterResult(
                success=False, error="Desktop screenshot requires Windows"
            )
        path = params.get(
            "output_path", str(ARTIFACTS_DIR / f"screenshot_{int(time.time())}.png")
        )
        script = _PS_SCREENSHOT.format(path=path.replace("'", "''"))
        result = await self._run_subprocess(
            ["powershell", "-NoProfile", "-Command", script], timeout=30
        )
        if result.success:
            result.output = f"Screenshot saved to {path}"
            result.data["artifact_path"] = path
            result.data["artifact_type"] = "screenshot"
        return result

    async def _record_video(self, params: dict) -> AdapterResult:
        ffmpeg = _find_ffmpeg(params)
        if not ffmpeg:
            return _ffmpeg_error()
        duration = int(params.get("duration", 10))
        device = await self._dshow_device(ffmpeg, params)
        path = params.get(
            "output_path", str(ARTIFACTS_DIR / f"video_{int(time.time())}.mp4")
        )
        cmd = [
            ffmpeg, "-y", "-f", "dshow", "-i", device,
            "-t", str(duration), "-pix_fmt", "yuv420p", path,
        ]
        result = await self._run_subprocess(cmd, timeout=duration + 30)
        if result.success:
            result.output = f"Video ({duration}s) saved to {path}"
            result.data["artifact_path"] = path
            result.data["artifact_type"] = "video"
        return result

    async def _list_devices(self, params: dict) -> AdapterResult:
        ffmpeg = _find_ffmpeg(params)
        if not ffmpeg:
            return _ffmpeg_error()
        result = await self._run_subprocess(
            [ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=20
        )
        # ffmpeg prints device list to stderr and exits non-zero by design.
        listing = result.data.get("stderr", "") or result.error
        return AdapterResult(success=True, output=listing)

    async def health_check(self) -> AdapterResult:
        if not sys.platform.startswith("win"):
            return AdapterResult(
                success=False, error="camera adapter is Windows-only on this host"
            )
        return AdapterResult(success=True, output="camera adapter ready")
