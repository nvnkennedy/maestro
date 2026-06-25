"""SSH adapter health checks and capability probes."""

from __future__ import annotations

from backend.adapters.base_adapter import AdapterResult


def check_turbossh_available() -> AdapterResult:
    """Report whether turbossh (and its ffmpeg-based camera helpers) are usable."""
    try:
        import turbossh
    except ImportError:
        return AdapterResult(
            success=False, error="turbossh is not installed (pip install turbossh)"
        )
    camera = "unavailable"
    try:
        from turbossh.gui import ffmpeg_tools

        camera = "ready" if ffmpeg_tools.cached_ffmpeg() else "needs ffmpeg (fetched on first use)"
    except Exception:
        pass
    return AdapterResult(
        success=True,
        output=f"turbossh {turbossh.__version__} available (camera: {camera})",
    )


def check_paramiko_available() -> AdapterResult:
    """Legacy probe kept for compatibility — turbossh bundles paramiko."""
    try:
        import paramiko

        return AdapterResult(success=True, output=f"paramiko {paramiko.__version__} available")
    except ImportError:
        return AdapterResult(success=False, error="paramiko is not installed")
