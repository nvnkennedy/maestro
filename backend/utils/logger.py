"""Structured JSON logging.

Uses ``structlog`` when available, otherwise falls back to a small built-in
JSON formatter so Maestro has zero hard logging dependencies.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from backend.config import LOGS_DIR, get_settings

try:
    import structlog

    _HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover - depends on environment
    _HAS_STRUCTLOG = False

_configured = False

# In-memory ring buffer of recent log lines, surfaced by the in-app Console
# page (/api/logs) so you don't need the external cmd window to see activity.
_LOG_BUFFER: "deque[dict]" = deque(maxlen=1000)


def _record_line(level: str, logger_name: str, message: str, ts: str | None = None) -> None:
    _LOG_BUFFER.append(
        {
            "ts": ts or datetime.now(timezone.utc).isoformat(),
            "level": (level or "info").lower(),
            "logger": logger_name or "",
            "message": message or "",
        }
    )


def recent_logs(limit: int = 300) -> list[dict]:
    """The most recent buffered log lines (newest last)."""
    items = list(_LOG_BUFFER)
    return items[-limit:] if limit else items


class _BufferHandler(logging.Handler):
    """Mirror stdlib log records (uvicorn, apscheduler, …) into the console buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _record_line(record.levelname, record.name, record.getMessage())
        except Exception:
            pass


def _buffer_processor(logger, method_name, event_dict):
    """structlog processor: mirror Maestro's own events into the console buffer."""
    try:
        _record_line(
            str(event_dict.get("level", method_name)),
            str(event_dict.get("logger", "")),
            str(event_dict.get("event", "")),
            ts=event_dict.get("timestamp"),
        )
    except Exception:
        pass
    return event_dict


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


class _FallbackLogger:
    """structlog-like keyword-argument logging on top of stdlib logging."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, event: str, **kwargs) -> None:
        self._logger.log(level, event, extra={"context": kwargs})

    def debug(self, event: str, **kwargs) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def exception(self, event: str, **kwargs) -> None:
        self._logger.error(event, exc_info=True, extra={"context": kwargs})


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    level = getattr(logging, settings.log_level, logging.INFO)

    log_file: Path = LOGS_DIR / "maestro.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(_JsonFormatter())
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root.addHandler(_BufferHandler())

    if _HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                _buffer_processor,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    _configured = True


def get_logger(name: str = "maestro"):
    setup_logging()
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return _FallbackLogger(logging.getLogger(name))
