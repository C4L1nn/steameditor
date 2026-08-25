"""steameditor.events — Simple pub/sub event bus for decoupled communication."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Event:
    name: str
    data: Any = None
    source: Any = None


class EventBus:
    """Thread-safe singleton event bus for pub/sub communication."""

    _instance: EventBus | None = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
                cls._instance._sub_lock = threading.RLock()
            return cls._instance

    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> int:
        """Subscribe to an event. Returns subscription ID for unsubscribing."""
        with self._sub_lock:
            self._subscribers[event_name].append(callback)
            return len(self._subscribers[event_name]) - 1

    def unsubscribe(self, event_name: str, sub_id: int) -> bool:
        with self._sub_lock:
            if 0 <= sub_id < len(self._subscribers.get(event_name, [])):
                self._subscribers[event_name].pop(sub_id)
                return True
        return False

    def emit(self, event_name: str, data: Any = None, source: Any = None) -> None:
        """Emit an event to all subscribers (synchronous)."""
        event = Event(event_name, data, source)
        with self._sub_lock:
            callbacks = list(self._subscribers.get(event_name, []))
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                # Log but don't break other subscribers
                pass

    def emit_async(self, event_name: str, data: Any = None, source: Any = None) -> None:
        """Emit event in a background thread (fire and forget)."""
        import threading
        threading.Thread(target=self.emit, args=(event_name, data, source), daemon=True).start()

    def clear(self, event_name: str | None = None) -> None:
        """Clear all subscribers for an event, or all events if None."""
        with self._sub_lock:
            if event_name:
                self._subscribers.pop(event_name, None)
            else:
                self._subscribers.clear()


# Global instance
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


# Convenience functions
def subscribe(event_name: str, callback: Callable[[Event], None]) -> int:
    return get_event_bus().subscribe(event_name, callback)


def unsubscribe(event_name: str, sub_id: int) -> bool:
    return get_event_bus().unsubscribe(event_name, sub_id)


def emit(event_name: str, data: Any = None, source: Any = None) -> None:
    get_event_bus().emit(event_name, data, source)


def emit_async(event_name: str, data: Any = None, source: Any = None) -> None:
    get_event_bus().emit_async(event_name, data, source)