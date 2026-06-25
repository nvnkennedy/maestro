#!/usr/bin/env python3
"""Build the Maestro PyPI wheel — slim, no bundled binaries.

    python scripts/build_pypi.py [--no-frontend]

Steps:
  1. Build the React UI (frontend/dist) unless --no-frontend.
  2. Stage it into backend/_bundled/frontend/dist so the UI ships inside the wheel.
  3. python -m build --wheel  ->  dist/*.whl
  4. Remove the staged copy.

adb / ffmpeg / scrcpy are deliberately NOT bundled: turboadb and turbossh fetch
their own tools at runtime, and ffmpeg can be on PATH or set per-step. This keeps
the wheel small enough for PyPI (well under the 100 MB file limit).

Then upload (never commit the token):
    python -m twine upload dist/*
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_ROOT = ROOT / "backend" / "_bundled"
BUNDLED = BUNDLED_ROOT / "frontend" / "dist"


def build_frontend() -> None:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    fe = ROOT / "frontend"
    if not (fe / "node_modules").exists():
        subprocess.check_call([npm, "install"], cwd=str(fe))
    subprocess.check_call([npm, "run", "build"], cwd=str(fe))


def main() -> None:
    if "--no-frontend" not in sys.argv:
        print("Building frontend…")
        build_frontend()

    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").exists():
        sys.exit("frontend/dist not found — run without --no-frontend first.")

    print("Staging UI into the package…")
    if BUNDLED.exists():
        shutil.rmtree(BUNDLED)
    shutil.copytree(dist, BUNDLED)

    try:
        # Clean any stale build/ tree so nothing leaks into the wheel.
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        print("Building wheel…")
        subprocess.check_call([sys.executable, "-m", "build", "--wheel"], cwd=str(ROOT))
    finally:
        shutil.rmtree(BUNDLED_ROOT, ignore_errors=True)

    print("\n  Wheel in:", ROOT / "dist")
    print("  Install:  pip install dist/maestro_automation-<ver>-py3-none-any.whl")


if __name__ == "__main__":
    main()
