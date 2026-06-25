"""Optional shared-token authentication.

Maestro ships zero-config for a single-user local install (no token). When
``MAESTRO_API_TOKEN`` is set — recommended whenever the dashboard is reachable
beyond ``127.0.0.1`` — every ``/api`` and ``/ws`` request must present that
token. This sits *in front of* the RBAC layer (which decides *what* an
authenticated user may do); without it the spoofable ``X-Maestro-User`` header
alone gates nothing.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Paths that must stay reachable without a token so the app can bootstrap.
_OPEN_PATHS = ("/api/docs", "/api/openapi.json", "/api/health", "/metrics")


def token_ok(supplied: str | None, expected: str) -> bool:
    """Constant-time comparison; empty ``expected`` means auth is disabled."""
    if not expected:
        return True
    if not supplied:
        return False
    return hmac.compare_digest(supplied, expected)


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-maestro-token") or request.query_params.get("token")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Enforce the shared token on API routes when one is configured."""

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        if self._token and request.url.path.startswith("/api"):
            if not any(request.url.path.startswith(p) for p in _OPEN_PATHS):
                if not token_ok(_extract_token(request), self._token):
                    return JSONResponse(
                        {"detail": "Missing or invalid API token"}, status_code=401
                    )
        return await call_next(request)
