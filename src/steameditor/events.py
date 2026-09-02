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
                cls._instance._subscribers: dict[str, dict[int, Callable[[Event], None]]] = defaultdict(dict)
                cls._instance._next_id: int = 0
                cls._instance._sub_lock = threading.RLock()
            return cls._instance

    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> int:
        """Subscribe to an event. Returns stable subscription ID for unsubscribing."""
        with self._sub_lock:
            sub_id = self._next_id
            self._next_id += 1
            self._subscribers[event_name][sub_id] = callback
            return sub_id

    def unsubscribe(self, event_name: str, sub_id: int) -> bool:
        with self._sub_lock:
            subs = self._subscribers.get(event_name)
            if subs is not None and sub_id in subs:
                del subs[sub_id]
                if not subs:
                    self._subscribers.pop(event_name, None)
                return True
        return False

    def emit(self, event_name: str, data: Any = None, source: Any = None) -> None:
        """Emit an event to all subscribers (synchronous)."""
        event = Event(event_name, data, source)
        with self._sub_lock:
            callbacks = list(self._subscribers.get(event_name, {}).values())
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                # Log but don't break other subscribers
                import logging
                logging.getLogger("steameditor.events").exception("Event callback failed")
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