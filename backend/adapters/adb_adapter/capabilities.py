"""ADB adapter capability probes."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def find_adb() -> str | None:
    """Locate adb: bundled platform-tools → PATH → common SDK locations."""
    # Prefer the copy bundled with Maestro (ships in the wheel / installer).
    # Try the canonical platform-tools layout first, then a recursive search
    # (handles adb living inside e.g. a scrcpy folder).
    try:
        from backend.config import find_bundled_binary, find_bundled_executable

        for exe in ("adb.exe", "adb"):
            bundled = find_bundled_binary("platform-tools", exe) or find_bundled_executable(exe)
            if bundled:
                return str(bundled)
    except Exception:
        pass

    # turboadb's own resolver (also knows ~/.turboadb/tools and can fetch-tools).
    try:
        import turboadb

        resolved = turboadb.find_adb()
        if resolved:
            return str(resolved)
    except Exception:
        pass

    found = shutil.which("adb")
    if found:
        return found
    candidates = []
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(env)
        if root:
            candidates.append(Path(root) / "platform-tools" / "adb")
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Android" / "Sdk" / "platform-tools" / "adb")
    candidates.append(Path("C:/platform-tools/adb.exe"))
    # Common manual extraction spots for platform-tools-latest-windows.zip
    for drive in ("C:", "D:", "E:"):
        candidates.append(
            Path(f"{drive}/platform-tools-latest-windows/platform-tools/adb.exe")
        )
    for candidate in candidates:
        for suffix in ("", ".exe"):
            path = Path(str(candidate) + suffix)
            if path.exists():
                return str(path)
    return None
