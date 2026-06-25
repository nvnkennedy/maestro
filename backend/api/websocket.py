"""WebSocket endpoint for real-time execution updates and log streaming."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from backend.config import get_settings
from backend.security.auth import token_ok
from backend.services.ws_manager import ws_manager

router = APIRouter()

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _origin_allowed(origin: str | None, allowed: list[str], host: str | None = None) -> bool:
    """Reject cross-site WebSocket connections (CSWSH) without breaking local use.

    Browsers always send an ``Origin`` header on WS handshakes, so a missing
    origin means a non-browser client (curl, tests, native tooling) — allowed.
    A present origin is accepted when it is:
      * in the configured CORS allow-list, or
      * a loopback host on any port (Maestro is a local-first dashboard, and
        ``app.py`` may pick an auto-port like :58121), or
      * exactly same-origin as the request's own Host header.
    Anything else (e.g. https://evil.example) is rejected.
    """
    if origin is None:
        return True
    if origin in allowed:
        return True
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.hostname in _LOOPBACK_HOSTS:
        return True
    if host and parsed.netloc == host:
        return True
    return False


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    if not _origin_allowed(origin, settings.cors_origins, websocket.headers.get("host")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    # When an API token is configured, require it (?token=… or X-Maestro-Token).
    if settings.api_token:
        supplied = websocket.query_params.get("token") or websocket.headers.get(
            "x-maestro-token"
        )
        if not token_ok(supplied, settings.api_token):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    await ws_manager.connect(websocket)
    try:
        while True:
            # Client messages are currently ping/keepalive only.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)
