"""WebSocket connection manager — broadcasts execution events to the UI."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket

from backend.utils.logger import get_logger

logger = get_logger("maestro.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        self.loop = asyncio.get_running_loop()

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        async with self._lock:
            connections = list(self._connections)
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    def broadcast_threadsafe(self, event: dict[str, Any]) -> None:
        """Broadcast from a non-async context (scheduler thread)."""
        if self.loop is not None and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self.loop)

    @property
    def client_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
