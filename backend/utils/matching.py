"""Flexible text matching for step assertions (expect_contains / expected result).

Modes:
  * ``contains`` (default) — substring is present anywhere.
  * ``wildcard``           — shell-style globbing (``systemctl*``, ``*active*``,
                             ``?`` single char). Bare text is wrapped as ``*text*``.
  * ``regex``              — Python regular expression search.
  * ``exact``              — the whole (stripped) output equals the pattern.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any


def text_matches(text: str | None, pattern: str | None, mode: str = "contains") -> bool:
    text = text or ""
    pattern = pattern or ""
    mode = (mode or "contains").lower()

    if mode == "exact":
        return text.strip() == pattern.strip()
    if mode == "regex":
        try:
            return re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None
        except re.error:
            return False
    if mode == "wildcard":
        glob = pattern if any(c in pattern for c in "*?[") else f"*{pattern}*"
        # match per line and across the whole blob so multi-line output works
        if fnmatch.fnmatch(text, glob):
            return True
        return any(fnmatch.fnmatch(line, glob) for line in text.splitlines())
    # default: substring
    return pattern in text


def expectation_rules(params: dict) -> list[dict[str, str]]:
    """Normalise a step's expectations into a list of {text, mode} rules.

    Supports, in order:
      * ``expect_rules``: ``[{"text": ..., "mode": ...}, ...]`` (the new
        multi-expectation form — every rule must pass).
      * ``expect_contains``: a single string, or a list of strings, paired
        with the legacy ``match_mode`` (back-compatible).
      * ``expected``: legacy single-string assertion.
    """
    default_mode = str(params.get("match_mode", "contains"))
    rules: list[dict[str, str]] = []

    raw_rules = params.get("expect_rules")
    if isinstance(raw_rules, list):
        for item in raw_rules:
            if isinstance(item, dict) and str(item.get("text", "")).strip():
                rules.append(
                    {"text": str(item["text"]), "mode": str(item.get("mode", "contains"))}
                )

    raw: Any = params.get("expect_contains")
    if isinstance(raw, list):
        for item in raw:
            if str(item).strip():
                rules.append({"text": str(item), "mode": default_mode})
    elif raw not in (None, ""):
        rules.append({"text": str(raw), "mode": default_mode})

    legacy = params.get("expected")
    if legacy not in (None, ""):
        rules.append({"text": str(legacy), "mode": default_mode})

    return rules


def check_expectations(output: str | None, params: dict) -> tuple[bool, str]:
    """Check every expectation rule against ``output``.

    Returns ``(passed, message)``. ``passed`` is True when there are no rules
    or all of them match; otherwise ``message`` lists the failed rules.
    """
    rules = expectation_rules(params)
    failures = [
        f"({r['mode']}) '{r['text']}'"
        for r in rules
        if not text_matches(output, r["text"], r["mode"])
    ]
    if failures:
        return False, "Expected output to match " + ", ".join(failures)
    return True, ""
