"""Live camera / desktop feed — an MJPEG stream you can watch in the browser.

ffmpeg is run with the **mpjpeg** muxer (a stream of JPEG frames with multipart
boundaries on stdout) and piped straight to the client as
``multipart/x-mixed-replace`` — which a plain ``<img>`` renders as a live video
feed, no plugins.

Two local sources:
  * **webcam** — the machine's connected camera (ffmpeg dshow).
  * **desktop** — the whole screen (ffmpeg gdigrab); point an RDP client window at
    your remote/RDP host and you can watch that session live.

The feed is produced on the host running Maestro (your bench PC), so it captures
that machine's camera/desktop. Auth (when a token is set) is handled by the global
token middleware, which also accepts ``?token=`` — the UI appends it to the URL.
"""

from __future__ import annotations

import asyncio
import sys

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse

from backend.adapters.windows_camera_adapter.adapter import _find_ffmpeg

router = APIRouter(prefix="/camera", tags=["camera"])

# ffmpeg's mpjpeg muxer separates frames with this boundary token.
_BOUNDARY = "ffmpeg"


async def _list_webcams(ffmpeg: str) -> list[str]:
    """Names of the dshow video devices ffmpeg can see on this machine."""
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    names: list[str] = []
    for line in out.decode(errors="replace").splitlines():
        if "(video)" in line and '"' in line:
            name = line.split('"')[1]
            if name and name not in names:
                names.append(name)
    return names


def _ffmpeg_cmd(ffmpeg: str, source: str, camera: str, fps: int, width: int) -> list[str]:
    """Build the ffmpeg command that emits an MJPEG stream on stdout."""
    out_opts = [
        "-an",                       # no audio
        "-vf", f"scale={width}:-2",  # downscale, keep aspect (even height)
        "-r", str(fps),
        "-q:v", "7",                 # JPEG quality (lower = better)
        "-f", "mpjpeg",
        "pipe:1",
    ]
    if source == "desktop":
        return [ffmpeg, "-f", "gdigrab", "-framerate", str(fps), "-i", "desktop", *out_opts]
    device = camera if camera.lower().startswith("video=") else f"video={camera}"
    return [ffmpeg, "-f", "dshow", "-i", device, *out_opts]


@router.get("/sources")
async def camera_sources() -> dict:
    """What live sources are available on this host (for the UI picker)."""
    ffmpeg = _find_ffmpeg({})
    cameras = await _list_webcams(ffmpeg) if ffmpeg else []
    return {
        "ffmpeg": bool(ffmpeg),
        "cameras": cameras,
        "desktop": sys.platform.startswith("win"),
    }


@router.get("/live")
async def camera_live(
    source: str = Query("webcam", description="webcam | desktop"),
    camera: str = Query("", description="dshow device name (blank = first webcam)"),
    fps: int = Query(12, ge=1, le=30),
    width: int = Query(640, ge=160, le=1920),
):
    """Stream a live MJPEG feed an ``<img>`` can display directly."""
    ffmpeg = _find_ffmpeg({})
    if not ffmpeg:
        return JSONResponse(
            {"error": "ffmpeg not found — drop ffmpeg.exe in the app's bin/ folder."},
            status_code=503,
        )
    if source != "desktop" and not camera:
        cams = await _list_webcams(ffmpeg)
        camera = cams[0] if cams else "Integrated Camera"

    proc = await asyncio.create_subprocess_exec(
        *_ffmpeg_cmd(ffmpeg, source, camera, fps, width),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def frames():
        try:
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            # Client closed the <img> (navigated away) — stop ffmpeg.
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.wait()

    return StreamingResponse(
        frames(),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"},
    )
