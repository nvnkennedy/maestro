"""Observability: metrics counters with Prometheus text exposition.

Uses ``prometheus_client`` when installed; otherwise falls back to an
internal registry that renders the same exposition format, so the
``/metrics`` endpoint always works.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

try:
    from prometheus_client import (  # type: ignore
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        generate_latest,
    )

    _HAS_PROM = True
except ImportError:  # pragma: no cover - depends on environment
    _HAS_PROM = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class _Metrics:
    """Thread-safe metric store with optional prometheus_client backing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple], float] = {}
        self._help: dict[str, str] = {}
        self.started_at = time.time()

        if _HAS_PROM:
            self._prom_executions = Counter(
                "test_executions_total", "Total test executions", ["status"]
            )
            self._prom_duration = Counter(
                "test_duration_seconds_total", "Cumulative test execution seconds"
            )
            self._prom_adapter_health = Gauge(
                "adapter_health_status", "Adapter health (1=ok)", ["adapter"]
            )
            self._prom_queue = Gauge("queue_length", "Executions currently running")

    # ---- generic primitives -------------------------------------------------

    def inc(self, name: str, labels: dict | None = None, value: float = 1.0,
            help_text: str = "") -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._counters[key] += value
            if help_text:
                self._help[name] = help_text

    def set_gauge(self, name: str, value: float, labels: dict | None = None,
                  help_text: str = "") -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._gauges[key] = value
            if help_text:
                self._help[name] = help_text

    # ---- domain helpers -----------------------------------------------------

    def record_execution(self, status: str, duration: float) -> None:
        self.inc("test_executions_total", {"status": status},
                 help_text="Total test executions")
        self.inc("test_duration_seconds_total", value=duration,
                 help_text="Cumulative execution seconds")
        if _HAS_PROM:
            self._prom_executions.labels(status=status).inc()
            self._prom_duration.inc(duration)

    def set_queue_length(self, value: int) -> None:
        self.set_gauge("queue_length", value, help_text="Executions currently running")
        if _HAS_PROM:
            self._prom_queue.set(value)

    def set_adapter_health(self, adapter: str, healthy: bool) -> None:
        self.set_gauge("adapter_health_status", 1.0 if healthy else 0.0,
                       {"adapter": adapter}, help_text="Adapter health (1=ok)")
        if _HAS_PROM:
            self._prom_adapter_health.labels(adapter=adapter).set(1 if healthy else 0)

    # ---- exposition ----------------------------------------------------------

    def render(self) -> tuple[bytes, str]:
        if _HAS_PROM:
            return generate_latest(), CONTENT_TYPE_LATEST
        lines: list[str] = []
        with self._lock:
            seen: set[str] = set()
            for (name, labels), value in list(self._counters.items()) + list(
                self._gauges.items()
            ):
                if name not in seen:
                    seen.add(name)
                    if name in self._help:
                        lines.append(f"# HELP {name} {self._help[name]}")
                    kind = "counter" if (name, labels) in self._counters else "gauge"
                    lines.append(f"# TYPE {name} {kind}")
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                suffix = f"{{{label_str}}}" if label_str else ""
                lines.append(f"{name}{suffix} {value}")
            uptime = time.time() - self.started_at
            lines.append("# TYPE maestro_uptime_seconds gauge")
            lines.append(f"maestro_uptime_seconds {uptime:.1f}")
        return ("\n".join(lines) + "\n").encode(), CONTENT_TYPE_LATEST


metrics = _Metrics()
