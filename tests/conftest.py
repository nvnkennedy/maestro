"""Test fixtures — isolated database and vault key per test session."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="maestro_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["MAESTRO_VAULT_KEY_FILE"] = str(Path(_TMP, ".vault.key"))
os.environ["MAESTRO_OPEN_BROWSER"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture(scope="session")
def app():
    from backend.main import create_app

    return create_app(serve_frontend=False)


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session():
    from backend.database import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
