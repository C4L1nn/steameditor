"""steameditor.services.worker_pool — Thread pool for background processing."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Callable, TypeVar, Any

T = TypeVar("T")


@dataclass
class TaskResult:
    """Result of a background task."""
    success: bool
    result: Any = None
    error: Exception | None = None

    @classmethod
    def ok(cls, result: Any = None) -> TaskResult:
        return cls(success=True, result=result)

    @classmethod
    def err(cls, error: Exception) -> TaskResult:
        return cls(success=False, error=error)


class WorkerPool:
    """Thread pool for CPU-intensive background tasks."""

    _instance: WorkerPool | None = None
    _lock = threading.Lock()

    def __new__(cls, max_workers: int | None = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(max_workers)
            elif max_workers is not None:
                cls._instance._resize(max_workers)
            return cls._instance

    def _init(self, max_workers: int | None):
        self.max_workers = max_workers or min(4, (threading.cpu_count() or 2))
        self._executor: ThreadPoolExecutor | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown = False

    def _resize(self, max_workers: int):
        if self._executor:
            self._executor.shutdown(wait=False)
        self.max_workers = max_workers
        self._executor = None
        self.start()

    def start(self):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="steameditor-worker"
            )
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()

    def shutdown(self, wait: bool = True):
        self._shutdown = True
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def submit(self, fn: Callable[..., T], *args, **kwargs) -> Future[TaskResult]:
        """Submit a task to the pool."""
        if not self._executor:
            self.start()

        def wrapped():
            try:
                return TaskResult.ok(fn(*args, **kwargs))
            except Exception as e:
                return TaskResult.err(e)

        return self._executor.submit(wrapped)

    async def run_async(self, fn: Callable[..., T], *args, **kwargs) -> TaskResult:
        """Run a blocking function asynchronously."""
        if not self._loop:
            self.start()
        return await self._loop.run_in_executor(self._executor, fn, *args, **kwargs)

    def map(self, fn: Callable[[Any], T], items: list[Any]) -> list[TaskResult]:
        """Map function over items in parallel."""
        if not self._executor:
            self.start()
        futures = [self._executor.submit(lambda x=item: TaskResult.ok(fn(x)) or TaskResult.err(Exception("error")), item) for item in items]
        # Wait for all
        results = []
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                results.append(TaskResult.err(e))
        return results


# ════════════════════════════════════════════════════════════════════
# Task Queue with Progress
# ════════════════════════════════════════════════════════════════════

from dataclasses import field
from collections import deque
import time


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
        self._running: dict[str, Future] = {}
        self._lock = threading.RLock()
        self._cancelled = set()
        self._paused = False
        self._callbacks: list[Callable[[QueuedTask], None]] = []

    def enqueue(self, fn: Callable, *args, priority: int = 0, task_id: str | None = None, **kwargs) -> str:
        """Add task to queue. Returns task ID."""
        import uuid
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
            # Cancel running
            if task_id in self._running:
                self._running[task_id].cancel()
                del self._running[task_id]
            # Remove from queue
            self._queue = deque(t for t in self._queue if t.id != task_id)
            return True

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def on_task_complete(self, callback: Callable[[QueuedTask], None]):
        self._callbacks.append(callback)

    def process(self, max_concurrent: int = 1) -> list[QueuedTask]:
        """Process queued tasks. Call repeatedly or in a loop."""
        completed = []
        with self._lock:
            # Check for cancellations
            self._queue = deque(t for t in self._queue if t.id not in self._cancelled)
            self._cancelled.clear()

            # Start new tasks up to max_concurrent
            while len(self._running) < max_concurrent and self._queue and not self._paused:
                task = self._queue.popleft()
                if task.id in self._cancelled:
                    continue
                task.started_at = time.time()
                future = self._pool.submit(task.fn, *task.args, **task.kwargs)
                self._running[task.id] = future

            # Check completed
            done_ids = []
            for tid, future in list(self._running.items()):
                if future.done():
                    done_ids.append(tid)

            for tid in done_ids:
                future = self._running.pop(tid)
                # Find task (we need to track it)
                # For simplicity, we don't track task objects in running
                # In a real implementation, you'd keep a reference
                pass

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
            self._cancelled.update(self._running.keys())
            for f in self._running.values():
                f.cancel()
            self._running.clear()


# Global accessor
_pool: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool