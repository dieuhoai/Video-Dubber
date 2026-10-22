"""Trạng thái dùng chung của server: job đang chạy + phát sự kiện tới các WebSocket."""
from __future__ import annotations

import asyncio
import threading
from typing import Any


class AppState:
    def __init__(self) -> None:
        self.token = ""
        self.port = 0
        self._lock = threading.Lock()
        self._clients: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self.job: dict[str, Any] = {"status": "idle", "done": 0, "total": 0, "items": []}
        self.stop_flag = threading.Event()

    def add_client(self, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._clients.append((loop, q))
        return q

    def remove_client(self, loop: asyncio.AbstractEventLoop, q: asyncio.Queue) -> None:
        with self._lock:
            self._clients = [c for c in self._clients if c[1] is not q]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"job": dict(self.job)}

    def emit(self, event: dict[str, Any]) -> None:
        """An toàn khi gọi từ thread worker."""
        with self._lock:
            clients = list(self._clients)
        for loop, q in clients:
            try:
                loop.call_soon_threadsafe(q.put_nowait, event)
            except RuntimeError:  # loop đã đóng
                pass

    def update_job(self, **kw: Any) -> None:
        with self._lock:
            self.job.update(kw)
            job = dict(self.job)
        self.emit({"type": "job", "job": job})


STATE = AppState()
