"""Input validation helpers."""

from __future__ import annotations

import re

_CRON_FIELD = r"[0-9A-Za-z*,\-/]+"
_CRON_RE = re.compile(rf"^{_CRON_FIELD}(\s+{_CRON_FIELD}){{4}}$")

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9\-\.]{1,253}(?<!-)$"
)


def is_valid_cron(expression: str) -> bool:
    """Validate a 5-field cron expression (minute hour day month weekday)."""
    return bool(_CRON_RE.match(expression.strip()))


def is_valid_hostname(host: str) -> bool:
    return bool(_HOSTNAME_RE.match(host))


def is_valid_port(port) -> bool:
    try:
        return 0 < int(port) < 65536
    except (TypeError, ValueError):
        return False


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a file name."""
    return re.sub(r"[^\w\-. ]", "_", name).strip() or "unnamed"
