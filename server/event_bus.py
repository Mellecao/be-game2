from __future__ import annotations
import json
import queue
import threading

_subscribers: list[queue.Queue[str]] = []
_lock = threading.Lock()


def subscribe() -> queue.Queue[str]:
    q: queue.Queue[str] = queue.Queue()
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue[str]) -> None:
    with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


def emit(event_type: str, data: str) -> None:
    payload = json.dumps({"type": event_type, "data": data})
    with _lock:
        for q in list(_subscribers):
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass
