from __future__ import annotations

import queue
import threading


class TerminalSession:
    def __init__(self) -> None:
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()

    def emit(self, kind: str, text: str = "") -> None:
        self._q.put((kind, text))

    def get_item(self, timeout: float = 20) -> tuple[str, str]:
        return self._q.get(timeout=timeout)


_active: TerminalSession | None = None
_lock = threading.Lock()


def new_session() -> TerminalSession:
    global _active
    with _lock:
        _active = TerminalSession()
    return _active


def get_active() -> TerminalSession | None:
    with _lock:
        return _active
