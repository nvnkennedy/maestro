"""Resource locking — prevents two executions from driving the same device.

Locks are keyed by device config id (or adapter name when a step has no
device binding). Async-native, fair (FIFO via asyncio.Lock) and in-process,
which matches Maestro's single-server execution model.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class ResourceLockManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._holders: dict[str, int] = {}  # resource -> execution_id
        self._guard = asyncio.Lock()

    async def _get_lock(self, resource: str) -> asyncio.Lock:
        async with self._guard:
            if resource not in self._locks:
                self._locks[resource] = asyncio.Lock()
            return self._locks[resource]

    @asynccontextmanager
    async def acquire(self, resource: str, execution_id: int, timeout: float = 300):
        """Acquire a device lock, waiting up to ``timeout`` seconds."""
        lock = await self._get_lock(resource)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            holder = self._holders.get(resource)
            raise TimeoutError(
                f"Resource '{resource}' is locked by execution #{holder} "
                f"(waited {timeout}s)"
            )
        self._holders[resource] = execution_id
        try:
            yield
        finally:
            self._holders.pop(resource, None)
            lock.release()

    def status(self) -> dict[str, int]:
        """Currently held locks: resource -> execution id."""
        return dict(self._holders)


lock_manager = ResourceLockManager()
