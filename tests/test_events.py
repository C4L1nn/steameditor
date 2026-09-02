"""Tests for EventBus — stable ID, thread-safety, unsubscribe."""
import threading

from steameditor.events import EventBus, get_event_bus


def test_subscribe_and_emit():
    bus = EventBus()
    bus.clear()
    calls = []
    bus.subscribe("test.evt", lambda e: calls.append(e.data))
    bus.emit("test.evt", 42)
    assert calls == [42]
    bus.clear()


def test_subscribe_returns_stable_id():
    bus = EventBus()
    bus.clear()
    id1 = bus.subscribe("a", lambda e: None)
    id2 = bus.subscribe("a", lambda e: None)
    assert id1 != id2
    assert id2 == id1 + 1
    bus.clear()


def test_unsubscribe_by_id_stable():
    bus = EventBus()
    bus.clear()
    calls = []
    id1 = bus.subscribe("evt", lambda e: calls.append(1))
    id2 = bus.subscribe("evt", lambda e: calls.append(2))
    id3 = bus.subscribe("evt", lambda e: calls.append(3))
    # Remove middle — other IDs must remain valid
    assert bus.unsubscribe("evt", id2) is True
    bus.emit("evt")
    assert calls == [1, 3]
    # Remove first
    assert bus.unsubscribe("evt", id1) is True
    calls.clear()
    bus.emit("evt")
    assert calls == [3]
    # Invalid id returns False
    assert bus.unsubscribe("evt", 9999) is False
    bus.clear()


def test_unsubscribe_wrong_event_returns_false():
    bus = EventBus()
    bus.clear()
    sid = bus.subscribe("a", lambda e: None)
    assert bus.unsubscribe("b", sid) is False
    bus.clear()


def test_emit_does_not_break_on_exception():
    bus = EventBus()
    bus.clear()
    calls = []

    def bad(e):
        raise RuntimeError("boom")

    def good(e):
        calls.append(e.data)

    bus.subscribe("x", bad)
    bus.subscribe("x", good)
    bus.emit("x", 99)
    assert calls == [99]
    bus.clear()


def test_emit_async():
    bus = EventBus()
    bus.clear()
    calls = []
    bus.subscribe("async.evt", lambda e: calls.append(e.data))
    bus.emit_async("async.evt", 123)
    # Wait a bit for thread
    import time
    time.sleep(0.2)
    assert 123 in calls
    bus.clear()


def test_clear_specific_event():
    bus = EventBus()
    bus.clear()
    bus.subscribe("a", lambda e: None)
    bus.subscribe("b", lambda e: None)
    bus.clear("a")
    assert bus._subscribers.get("a") is None
    assert "b" in bus._subscribers
    bus.clear()


def test_thread_safety():
    bus = EventBus()
    bus.clear()
    calls = []
    lock = threading.Lock()

    def cb(e):
        with lock:
            calls.append(e.data)

    for _ in range(5):
        bus.subscribe("thr", cb)

    threads = [threading.Thread(target=lambda: bus.emit("thr", 1)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 5 subscribers * 20 emits = 100 calls
    assert len(calls) == 100
    bus.clear()


def test_singleton():
    b1 = EventBus()
    b2 = EventBus()
    assert b1 is b2
    assert get_event_bus() is b1
