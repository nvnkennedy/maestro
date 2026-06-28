"""Create / refresh a Windows desktop shortcut for Maestro.

Run on every launch, so after a ``pip install -U`` the shortcut automatically
points at the current interpreter and shows the new version. The shortcut starts
Maestro **windowless** (``pythonw.exe``) — no cmd window pops up; watch activity
on the in-app **Console** page instead.

Opt out by setting ``MAESTRO_NO_SHORTCUT=1``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def ensure_desktop_shortcut() -> Path | None:
    """Best-effort create/update of ``Desktop\\Maestro.lnk``. Never raises."""
    if os.name != "nt" or os.environ.get("MAESTRO_NO_SHORTCUT"):
        return None
    try:
        from backend import __version__

        # Prefer a windowless launch (no cmd window); fall back to python.exe.
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        target = str(pythonw if pythonw.exists() else sys.executable)
        workdir = str(Path(sys.executable).parent)

        # The Maestro mark (same design as the app/favicon), bundled in the wheel.
        icon_line = ""
        try:
            from backend.config import FRONTEND_DIST

            ico = FRONTEND_DIST / "maestro.ico"
            if ico.exists():
                icon_line = f"$s.IconLocation = '{ico}'; "
        except Exception:
            icon_line = ""

        # Let WScript resolve the real Desktop folder — this handles OneDrive
        # redirection (where %USERPROFILE%\Desktop may not exist) and then prints
        # the .lnk path back so we can confirm it was written.
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            "$lnk = Join-Path $ws.SpecialFolders('Desktop') 'Maestro.lnk'; "
            "$s = $ws.CreateShortcut($lnk); "
            f"$s.TargetPath = '{target}'; "
            "$s.Arguments = '-m backend.cli'; "
            f"$s.WorkingDirectory = '{workdir}'; "
            f"{icon_line}"
            f"$s.Description = 'Maestro v{__version__} - Automotive Test Automation'; "
            "$s.Save(); Write-Output $lnk"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        out = (result.stdout or "").strip().splitlines()
        link = Path(out[-1]) if out else None
        return link if link and link.exists() else None
    except Exception:
        return None
