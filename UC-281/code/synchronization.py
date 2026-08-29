"""Thread-safe event bus, idempotency cache and synchronization barrier."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List


class EventBus:
    def __init__(self) -> None:
        self._events: List[dict] = []
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, run_id: str, payload: dict) -> dict:
        event = {"type": event_type, "run_id": run_id, "payload": payload, "timestamp": time.time()}
        with self._lock:
            self._events.append(event)
            subscribers = list(self._subscribers[event_type])
        for callback in subscribers:
            callback(event)
        return event

    def events(self, run_id: str | None = None) -> List[dict]:
        with self._lock:
            return [dict(event) for event in self._events if run_id is None or event["run_id"] == run_id]


class IdempotencyCache:
    def __init__(self) -> None:
        self._values: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any:
        with self._lock:
            return self._values.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value