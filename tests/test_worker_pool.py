"""Tests for WorkerPool and TaskQueue."""
import time

from steameditor.services.worker_pool import TaskQueue, WorkerPool


def test_worker_pool_map_preserves_order():
    pool = WorkerPool(max_workers=2)
    pool.start()
    results = pool.map(lambda x: x * 2, [1, 2, 3, 4, 5])
    assert [r.result for r in results] == [2, 4, 6, 8, 10]
    assert all(r.success for r in results)


def test_worker_pool_map_handles_exception():
    pool = WorkerPool(max_workers=2)

    def may_fail(x):
        if x == 3:
            raise ValueError("fail on 3")
        return x

    results = pool.map(may_fail, [1, 2, 3, 4])
    assert results[0].success and results[0].result == 1
    assert not results[2].success
    assert isinstance(results[2].error, ValueError)


def test_worker_pool_submit():
    pool = WorkerPool(max_workers=2)
    fut = pool.submit(lambda a, b: a + b, 5, 7)
    res = fut.result(timeout=2)
    assert res.success and res.result == 12

    fut2 = pool.submit(lambda: 1 / 0)
    res2 = fut2.result(timeout=2)
    assert not res2.success
    assert isinstance(res2.error, ZeroDivisionError)


def test_task_queue_priority_and_process():
    pool = WorkerPool(max_workers=2)
    q = TaskQueue(pool)
    # Enqueue with priorities
    q.enqueue(lambda: 1, priority=1, task_id="low")
    q.enqueue(lambda: 2, priority=10, task_id="high")
    q.enqueue(lambda: 3, priority=5, task_id="mid")
    # Queue order should be high, mid, low (dequeue pops left)
    assert [t.id for t in q._queue] == ["high", "mid", "low"]
    # Process all
    completed = []
    for _ in range(5):
        c = q.process(max_concurrent=2)
        completed.extend(c)
        time.sleep(0.05)
        if q.get_status()["queued"] == 0 and q.get_status()["running"] == 0:
            break
    # All 3 should complete
    assert len(completed) == 3
    # Results should be present
    id_to_result = {t.id: t.result.result for t in completed}
    assert id_to_result["high"] == 2
    assert id_to_result["low"] == 1


def test_task_queue_cancel_pending():
    pool = WorkerPool(max_workers=1)
    q = TaskQueue(pool)
    q.pause()
    q.enqueue(lambda: 1, task_id="t1")
    q.enqueue(lambda: 2, task_id="t2")
    assert q.cancel("t1") is True
    assert q.get_status()["queued"] == 1
    assert q._queue[0].id == "t2"
    q.resume()


def test_task_queue_pause_resume():
    pool = WorkerPool(max_workers=1)
    q = TaskQueue(pool)
    q.pause()
    q.enqueue(lambda: 42, task_id="t1")
    c = q.process(max_concurrent=1)
    assert len(c) == 0  # paused, nothing started
    assert q.get_status()["queued"] == 1
    q.resume()
    # Now it should start
    c = q.process(max_concurrent=1)
    # May need second tick to collect
    time.sleep(0.1)
    c2 = q.process(max_concurrent=1)
    assert len(c) + len(c2) >= 1


def test_task_queue_on_complete_callback():
    pool = WorkerPool(max_workers=1)
    q = TaskQueue(pool)
    calls = []
    q.on_task_complete(lambda t: calls.append(t.id))
    q.enqueue(lambda: 99, task_id="cb1")
    for _ in range(5):
        q.process(max_concurrent=1)
        time.sleep(0.05)
        if calls:
            break
    assert "cb1" in calls


def test_task_queue_clear():
    pool = WorkerPool(max_workers=1)
    q = TaskQueue(pool)
    q.enqueue(lambda: 1, task_id="a")
    q.enqueue(lambda: 2, task_id="b")
    q.clear()
    assert q.get_status()["queued"] == 0
    assert q.get_status()["running"] == 0
