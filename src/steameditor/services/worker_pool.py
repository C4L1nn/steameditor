"""steameditor.services.worker_pool — Thread pool for background processing."""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass
class TaskResult:
    """Result of a background task."""
    success: bool
    result: Any = None
    error: Exception | None = None

    @classmethod
    def ok(cls, result: Any = None) -> "TaskResult":
        return cls(success=True, result=result)

    @classmethod
    def err(cls, error: Exception) -> "TaskResult":
        return cls(success=False, error=error)


class WorkerPool:
    """Thread pool for CPU-intensive background tasks."""

    _instance: "WorkerPool | None" = None
    _lock = threading.Lock()

    def __new__(cls, max_workers: int | None = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(max_workers)
            elif max_workers is not None and max_workers != cls._instance.max_workers:
                cls._instance._resize(max_workers)
            return cls._instance

    def _init(self, max_workers: int | None):
        self.max_workers = max_workers or min(4, (threading.active_count() or 2) * 2)
        # clamp to sensible range 2..8
        self.max_workers = max(2, min(8, self.max_workers))
        self._executor: ThreadPoolExecutor | None = None
        self._shutdown = False

    def _resize(self, max_workers: int):
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        self.max_workers = max(2, min(8, max_workers))
        self.start()

    def start(self):
        if self._executor is None and not self._shutdown:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="steameditor-worker",
            )

    def shutdown(self, wait: bool = True):
        self._shutdown = True
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def submit(self, fn: Callable[..., T], *args, **kwargs) -> Future[TaskResult]:
        """Submit a task to the pool. Returns Future[TaskResult]."""
        if self._executor is None or self._shutdown:
            self._shutdown = False
            self.start()

        def wrapped() -> TaskResult:
            try:
                return TaskResult.ok(fn(*args, **kwargs))
            except Exception as e:
                return TaskResult.err(e)

        assert self._executor is not None
        return self._executor.submit(wrapped)

    async def run_async(self, fn: Callable[..., T], *args, **kwargs) -> TaskResult:
        """Run a blocking function asynchronously (asyncio)."""
        import asyncio
        try:
            # Use to_thread if available (py 3.9+)
            result = await asyncio.to_thread(fn, *args, **kwargs)
            return TaskResult.ok(result)
        except Exception as e:
            return TaskResult.err(e)

    def map(self, fn: Callable[[Any], T], items: list[Any]) -> list[TaskResult]:
        """Map function over items in parallel. Preserves order."""
        if not self._executor:
            self.start()
        assert self._executor is not None
        # Proper closure capture via default arg
        futures: list[Future[TaskResult]] = []
        for item in items:
            # capture item by value
            def _task(x=item):  # type: ignore
                try:
                    return TaskResult.ok(fn(x))
                except Exception as e:
                    return TaskResult.err(e)
            futures.append(self._executor.submit(_task))

        results: list[TaskResult] = []
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                # Should not happen because _task catches, but just in case
                results.append(TaskResult.err(e))
        return results


# ════════════════════════════════════════════════════════════════════
# Task Queue with Progress
# ════════════════════════════════════════════════════════════════════

@dataclass
class QueuedTask:
    id: str
    fn: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: int = 0  # higher = first
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: TaskResult | None = None


class TaskQueue:
    """Priority task queue with progress tracking and cancellation."""

    def __init__(self, worker_pool: WorkerPool | None = None):
        self._pool = worker_pool or WorkerPool()
        self._queue: deque[QueuedTask] = deque()
        self._running: dict[str, Future[TaskResult]] = {}
        self._running_tasks: dict[str, QueuedTask] = {}  # id -> task
        self._lock = threading.RLock()
        self._cancelled: set[str] = set()
        self._paused = False
        self._callbacks: list[Callable[[QueuedTask], None]] = []

    def enqueue(self, fn: Callable, *args, priority: int = 0, task_id: str | None = None, **kwargs) -> str:
        """Add task to queue. Returns task ID."""
        tid = task_id or str(uuid.uuid4())[:8]
        task = QueuedTask(id=tid, fn=fn, args=args, kwargs=kwargs, priority=priority)
        with self._lock:
            # Insert by priority (higher first)
            inserted = False
            for i, t in enumerate(self._queue):
                if task.priority > t.priority:
                    self._queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self._queue.append(task)
        return tid

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        with self._lock:
            if task_id in self._cancelled:
                return False
            self._cancelled.add(task_id)
            # Cancel running future if possible
            fut = self._running.get(task_id)
            if fut is not None:
                fut.cancel()
                self._running.pop(task_id, None)
                self._running_tasks.pop(task_id, None)
            # Remove from pending queue
            original_len = len(self._queue)
            self._queue = deque(t for t in self._queue if t.id != task_id)
            # Also remove if it was already considered cancelled before start
            return len(self._queue) != original_len or task_id in self._running or task_id in self._cancelled

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def on_task_complete(self, callback: Callable[[QueuedTask], None]):
        with self._lock:
            self._callbacks.append(callback)

    def process(self, max_concurrent: int = 1) -> list[QueuedTask]:
        """Start queued tasks up to max_concurrent and collect completed.

        Call repeatedly or in a loop. Returns list of tasks that just completed.
        Thread-safe.
        """
        completed: list[QueuedTask] = []
        callbacks: list[Callable[[QueuedTask], None]] = []
        with self._lock:
            # Filter out cancelled pending
            if self._cancelled:
                self._queue = deque(t for t in self._queue if t.id not in self._cancelled)
                # cancelled running already handled in cancel(); clear for pending
                # keep cancelled set for tasks that were cancelled before start
                # remove ids that are not running/queued anymore
                still_pending = {t.id for t in self._queue} | set(self._running.keys())
                self._cancelled = {cid for cid in self._cancelled if cid in still_pending}

            # Start new tasks up to max_concurrent
            while len(self._running) < max_concurrent and self._queue and not self._paused:
                task = self._queue.popleft()
                if task.id in self._cancelled:
                    self._cancelled.discard(task.id)
                    continue
                task.started_at = time.time()
                future = self._pool.submit(task.fn, *task.args, **task.kwargs)
                self._running[task.id] = future
                self._running_tasks[task.id] = task

            # Check completed futures
            done_ids: list[str] = []
            for tid, fut in list(self._running.items()):
                if fut.done():
                    done_ids.append(tid)

            for tid in done_ids:
                fut = self._running.pop(tid, None)
                task = self._running_tasks.pop(tid, None)
                if task is None or fut is None:
                    continue
                try:
                    # Future returns TaskResult (pool always wraps)
                    tr: TaskResult = fut.result()
                except Exception as e:
                    tr = TaskResult.err(e)
                task.result = tr
                task.completed_at = time.time()
                completed.append(task)

            # Copy callbacks outside lock to call without holding
            if completed:
                callbacks = list(self._callbacks)

        # Invoke callbacks outside lock
        for task in completed:
            for cb in callbacks:
                try:
                    cb(task)
                except Exception:
                    import logging
                    logging.getLogger("steameditor.worker_pool").exception("on_task_complete callback failed")

        return completed

    def get_status(self) -> dict:
        with self._lock:
            return {
                "queued": len(self._queue),
                "running": len(self._running),
                "paused": self._paused,
            }

    def clear(self):
        with self._lock:
            self._queue.clear()
            # Mark running as cancelled (best effort)
            self._cancelled.update(self._running.keys())
            for f in self._running.values():
                try:
                    f.cancel()
                except Exception:
                    pass
            self._running.clear()
            self._running_tasks.clear()


# Global accessor
_pool: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool
