"""Regression tests for the hardening added around auth and the sandbox."""

from __future__ import annotations

import os

import pytest

from backend.api.websocket import _origin_allowed
from backend.security.auth import token_ok
from backend.services.execution_sandbox import run_sandboxed


# ---- sandbox interpreter gating ------------------------------------------------


@pytest.mark.asyncio
async def test_sandbox_blocks_shell_by_default(monkeypatch):
    monkeypatch.delenv("MAESTRO_ALLOW_SHELL", raising=False)
    result = await run_sandboxed("echo hi", interpreter="bash")
    assert not result.success
    assert "disabled" in result.error.lower()


@pytest.mark.asyncio
async def test_sandbox_allows_python_without_flag(monkeypatch):
    monkeypatch.delenv("MAESTRO_ALLOW_SHELL", raising=False)
    result = await run_sandboxed("print('sandbox-ok')", interpreter="python", timeout=90)
    assert result.success, result.error
    assert "sandbox-ok" in result.output


# ---- token comparison ----------------------------------------------------------


def test_token_ok_disabled_when_empty():
    # No token configured -> auth is off, anything passes.
    assert token_ok(None, "")
    assert token_ok("whatever", "")


def test_token_ok_requires_exact_match():
    assert token_ok("s3cret", "s3cret")
    assert not token_ok("wrong", "s3cret")
    assert not token_ok(None, "s3cret")


# ---- websocket origin check ----------------------------------------------------


def test_origin_allowed():
    allowed = ["http://localhost:5173", "http://localhost:8000"]
    assert _origin_allowed(None, allowed)  # non-browser client
    assert _origin_allowed("http://localhost:5173", allowed)
    # Loopback on any port is trusted (auto-port fallback, 127.0.0.1 vs localhost).
    assert _origin_allowed("http://localhost:58121", allowed)
    assert _origin_allowed("http://127.0.0.1:8000", allowed)
    # Same-origin as the request host is trusted even if not in the list.
    assert _origin_allowed("http://192.168.1.5:8000", allowed, host="192.168.1.5:8000")
    # A genuine cross-site origin is still rejected.
    assert not _origin_allowed("http://evil.example", allowed)
    assert not _origin_allowed("http://evil.example", allowed, host="192.168.1.5:8000")


# ---- token enforcement end to end ----------------------------------------------


def test_token_auth_enforced_on_api(monkeypatch):
    import backend.config as config

    monkeypatch.setenv("MAESTRO_API_TOKEN", "topsecret")
    config.get_settings.cache_clear()
    try:
        from fastapi.testclient import TestClient

        from backend.main import create_app

        with TestClient(create_app(serve_frontend=False)) as client:
            # Open bootstrap path stays reachable without a token.
            assert client.get("/api/health").status_code == 200
            # Protected route rejects missing/wrong token, accepts the right one.
            assert client.get("/api/projects").status_code == 401
            assert (
                client.get(
                    "/api/projects", headers={"X-Maestro-Token": "wrong"}
                ).status_code
                == 401
            )
            assert (
                client.get(
                    "/api/projects", headers={"Authorization": "Bearer topsecret"}
                ).status_code
                == 200
            )
    finally:
        monkeypatch.delenv("MAESTRO_API_TOKEN", raising=False)
        config.get_settings.cache_clear()
        assert os.getenv("MAESTRO_API_TOKEN") is None
