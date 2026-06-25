"""SQLAlchemy setup and session management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    echo=False,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _auto_add_columns() -> None:
    """Lightweight migration: ADD COLUMN for model columns missing in the DB.

    create_all only creates new tables; when a model gains a column, existing
    SQLite files need an ALTER. Covers additive changes — anything more needs
    a real Alembic migration.
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    inspector = sa_inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            default = column.default.arg if column.default is not None else None
            if isinstance(default, (str, int, float, bool)):
                value = f"'{default}'" if isinstance(default, str) else (
                    int(default) if isinstance(default, bool) else default
                )
                ddl += f" DEFAULT {value}"
            with engine.begin() as conn:
                conn.execute(text(ddl))


def init_db() -> None:
    """Create all tables and apply additive column migrations (idempotent)."""
    # Import models so they are registered with Base.metadata.
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _auto_add_columns()


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for non-request code paths (executor, scheduler)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
