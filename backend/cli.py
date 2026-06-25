"""Console entry point for the pip-installed package: the ``maestro`` command.

Unlike ``app.py`` (the source-checkout launcher), this does not install deps or
build the frontend — both are provided by pip / bundled in the wheel.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser


def _resolve_port(host: str, preferred: int) -> int:
    for candidate in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, candidate))
            except OSError:
                continue
        return candidate
    sys.exit(f"Ports {preferred}-{preferred + 19} are busy; set MAESTRO_PORT.")


def _open_browser_later(url: str, port: int, host: str) -> None:
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host

    def _open() -> None:
        for _ in range(100):
            try:
                with socket.create_connection((probe_host, port), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.1)
        try:
            if os.name == "nt":
                os.startfile(url)  # noqa: S606 - local dashboard URL
            else:
                webbrowser.open(url, new=0, autoraise=True)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


def _banner(url: str, host: str, port: int) -> str:
    from backend import __version__

    # ASCII-only (legacy Windows consoles use cp1252 and choke on box-drawing).
    cyan, dim, bold, reset = "\033[36m", "\033[2m", "\033[1m", "\033[0m"
    if os.name == "nt" and not os.environ.get("WT_SESSION"):
        # Older consoles may not render ANSI — keep it plain there.
        cyan = dim = bold = reset = ""
    bar = "=" * 50
    lines = [
        "",
        f"{cyan}  {bar}{reset}",
        f"   {bold}MAESTRO{reset}  -  Automotive Test Automation  {dim}v{__version__}{reset}",
        f"{cyan}  {bar}{reset}",
        "",
        f"   {bold}Dashboard{reset}   {url}",
        f"   {dim}API docs {reset}   {url}/api/docs",
        f"   {dim}Listening{reset}   {host}:{port}",
        "",
        f"   {dim}Tip: run 'maestro setup' to install into a dedicated folder.{reset}",
        f"   {dim}Press Ctrl+C to stop.{reset}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    # `maestro setup` / `maestro --setup`: provision a dedicated install folder
    # (own venv + data + launcher) instead of running in this Python env.
    if any(arg in ("setup", "--setup", "install", "--install") for arg in sys.argv[1:]):
        from backend.installer import run_setup

        run_setup()
        return

    import uvicorn

    from backend.config import get_settings
    from backend.main import create_app

    settings = get_settings()
    app = create_app(serve_frontend=True)
    port = _resolve_port(settings.host, settings.port)
    url = f"http://localhost:{port}"

    print(_banner(url, settings.host, port))

    if settings.open_browser:
        _open_browser_later(url, port, settings.host)

    # Quieter console: show warnings/errors, not every request line.
    uvicorn.run(app, host=settings.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
