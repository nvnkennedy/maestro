"""General utility functions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    Drop-in for the deprecated ``datetime.utcnow()``: same naive-UTC value
    (which matches the timezone-less DateTime columns and existing rows) but
    built from the non-deprecated ``datetime.now(timezone.utc)``.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_iso() -> str:
    return utcnow().isoformat()


def safe_json_loads(raw: str, default=None):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default if default is not None else {}


def truncate(text: str, limit: int = 10_000) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"
