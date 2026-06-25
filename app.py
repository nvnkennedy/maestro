#!/usr/bin/env python3
"""Maestro single-command launcher.

    python app.py

1. Verifies the Python version
2. Installs Python dependencies if missing
3. Builds the React frontend if needed (requires Node.js)
4. Starts the FastAPI backend serving both API and frontend
5. Opens your browser at http://localhost:8000
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_python() -> None:
    if sys.version_info < (3, 10):
        sys.exit("Maestro requires Python 3.10 or newer (3.11.9 recommended).")


def ensure_backend_deps() -> None:
    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
        import uvicorn  # noqa: F401
        import cryptography  # noqa: F401
        import apscheduler  # noqa: F401
    except ImportError:
        print("Installing Python dependencies (first run only)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
        )


def _frontend_is_stale(dist: Path, frontend: Path) -> bool:
    """True if any frontend source is newer than the built bundle.

    Without this check the dashboard would silently serve an old bundle after
    you edit the UI — the classic "my changes/DnD aren't showing" trap, since a
    plain ``python app.py`` never rebuilds once ``dist`` exists.
    """
    if not dist.exists():
        return True
    built_at = dist.stat().st_mtime
    # Watch the sources plus the build inputs that change output.
    watched = [frontend / "src", frontend / "index.html", frontend / "package.json"]
    watched += list(frontend.glob("vite.config.*"))
    watched += list(frontend.glob("tailwind.config.*"))
    for path in watched:
        if not path.exists():
            continue
        if path.is_file():
            if path.stat().st_mtime > built_at:
                return True
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.stat().st_mtime > built_at:
                return True
    return False


def ensure_frontend_built() -> bool:
    dist = ROOT / "frontend" / "dist" / "index.html"
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").exists():
        # No sources to build from — only the prebuilt bundle (if any) is usable.
        if dist.exists():
            return True
        print("WARNING: frontend sources not found; API-only mode.")
        return False
    if dist.exists() and not _frontend_is_stale(dist, frontend):
        return True
    npm = "npm.cmd" if os.name == "nt" else "npm"
    try:
        if not (frontend / "node_modules").exists():
            print("Installing frontend dependencies (first run only)...")
            subprocess.check_call([npm, "install"], cwd=str(frontend))
        print("Building frontend (sources changed since last build)..."
              if dist.exists() else "Building frontend...")
        subprocess.check_call([npm, "run", "build"], cwd=str(frontend))
        return dist.exists()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"WARNING: frontend build failed ({exc}); starting API-only.")
        print("Install Node.js 18+ and re-run 'python app.py' for the full dashboard.")
        return dist.exists()


def resolve_port(host: str, preferred: int) -> int:
    """Return ``preferred`` if free, otherwise the next available port.

    Prevents the cryptic WinError 10048 when another Maestro (or any app)
    already holds the port — e.g. a forgotten terminal or a debugger session.
    """
    import socket

    for candidate in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
            except OSError:
                continue
        if candidate != preferred:
            print(f"  NOTE: port {preferred} is already in use (another Maestro "
                  f"or app is running there) — using port {candidate} instead.")
        return candidate
    sys.exit(
        f"Ports {preferred}-{preferred + 19} are all busy. Stop the other "
        f"process or set MAESTRO_PORT in .env to a free port."
    )


def open_browser_later(url: str, port: int, host: str) -> None:
    """Open the dashboard in exactly one tab, once the server is actually up.

    Waiting for the port to accept connections (instead of a fixed sleep)
    avoids the "blank/error tab, then a second working tab" double-open: we
    only launch the browser when the page will load, and only once.
    """
    import socket

    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host

    def _open() -> None:
        for _ in range(100):  # up to ~10s
            try:
                with socket.create_connection((probe_host, port), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.1)
        try:
            # On Windows, os.startfile() hands the URL to the shell's default
            # handler, which opens it as a single tab in the existing browser
            # window — cleaner than webbrowser (which can spawn an extra window).
            # Note: if the browser is fully closed, it cold-starts and shows its
            # own configured start page too; that extra tab is the browser's, not
            # Maestro's (set MAESTRO_OPEN_BROWSER=false to skip auto-open).
            if os.name == "nt":
                os.startfile(url)  # noqa: S606 - local dashboard URL
            else:
                webbrowser.open(url, new=0, autoraise=True)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    check_python()
    frozen = getattr(sys, "frozen", False)
    if not frozen:
        # Source checkout: install deps / build the UI on demand.
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        ensure_backend_deps()
        ensure_frontend_built()
    # In a PyInstaller build, deps and the built UI are already bundled.

    from backend.config import get_settings
    from backend.main import create_app

    settings = get_settings()

    # Loud warning if the dashboard is exposed beyond localhost without a token:
    # RBAC alone trusts a spoofable header, so an open bind = anyone can drive it.
    loopback = settings.host in ("127.0.0.1", "localhost", "::1")
    if not loopback and not settings.api_token:
        print(
            "  WARNING: binding to a non-loopback host without MAESTRO_API_TOKEN.\n"
            "           Anyone who can reach this port has full control. Set\n"
            "           MAESTRO_API_TOKEN in .env, or bind MAESTRO_HOST=127.0.0.1."
        )

    app = create_app(serve_frontend=True)

    port = resolve_port(settings.host, settings.port)
    url = f"http://localhost:{port}"
    print()
    print("  __  __                _              ")
    print(" |  \\/  | __ _  ___ ___| |_ _ __ ___   ")
    print(" | |\\/| |/ _` |/ _ Y __| __| '__/ _ \\  ")
    print(" | |  | | (_| |  __|__ \\ |_| | | (_) | ")
    print(" |_|  |_|\\__,_|\\___|___/\\__|_|  \\___/  ")
    print()
    print(f"  Maestro dashboard : {url}")
    print(f"  API documentation : {url}/api/docs")
    print(f"  Metrics           : {url}/metrics")
    print()

    if settings.open_browser:
        open_browser_later(url, port, settings.host)

    # Keep the console readable: drop access-log noise for static assets.
    import logging

    class _QuietAssets(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                message = record.getMessage()
            except Exception:
                return True
            return not ("/assets/" in message or "favicon" in message)

    logging.getLogger("uvicorn.access").addFilter(_QuietAssets())

    import uvicorn

    uvicorn.run(app, host=settings.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
