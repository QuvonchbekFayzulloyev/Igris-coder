"""
IGRIS BRAIN — Task Queue (Roadmap §15)
======================================
FIFO navbat tizimi + ustuvorlik (priority) qo'llab-quvvatlash.

TaskQueue:
  - submit(task, priority="normal") → task_id
  - cancel(task_id) → bool
  - queue_info() → dict
  - Priority: high > normal > low

Server RunManager bilan integratsiya:
  POST /api/agent/run → queue'ga qo'shish
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskPriority(str, Enum):
    """Navbat ustuvorligi."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# Priority tartib raqami (yuqori = ustuvor)
_PRIORITY_ORDER = {
    TaskPriority.HIGH: 0,
    TaskPriority.NORMAL: 1,
    TaskPriority.LOW: 2,
}


class TaskStatus(str, Enum):
    """Task holati."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueTask:
    """Navbatdagi task."""
    task_id: str
    payload: dict
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """FIFO navbat + ustuvorlik.

    max_concurrent=1 bo'lsa — yagona task ketma-ket ishlaydi.
    max_concurrent>1 bo'lsa — parallel bajariladi.
    """

    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent
        self._queue: deque[QueueTask] = deque()
        self._active: dict[str, QueueTask] = {}
        self._completed: list[QueueTask] = []
        self._lock = threading.Lock()
        self._task_counter = 0

    def submit(self, payload: dict, priority: str = "normal") -> str:
        """Task navbatga qo'shish — task_id qaytaradi."""
        try:
            pri = TaskPriority(priority)
        except ValueError:
            pri = TaskPriority.NORMAL

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = QueueTask(
            task_id=task_id,
            payload=payload,
            priority=pri,
        )

        with self._lock:
            self._queue.append(task)
            self._task_counter += 1
            # Priority bo'yicha saralash
            self._sort_queue()

        return task_id

    def cancel(self, task_id: str) -> bool:
        """Taskni navbatdan o'chirish."""
        with self._lock:
            # Navbatdan topish
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    task.status = TaskStatus.CANCELLED
                    self._queue.remove(task)
                    self._completed.append(task)
                    return True
            # Active tasklarni tekshirish (to'xtatib bo'lmaydi, lekin belgilaymiz)
            if task_id in self._active:
                self._active[task_id].status = TaskStatus.CANCELLED
                return True
        return False

    def queue_info(self) -> dict:
        """Navbat holati."""
        with self._lock:
            return {
                "queued": len(self._queue),
                "active": len(self._active),
                "completed": len(self._completed),
                "max_concurrent": self.max_concurrent,
                "tasks": [t.to_dict() for t in list(self._queue)[:10]],
                "active_tasks": [t.to_dict() for t in self._active.values()],
            }

    def next_task(self) -> Optional[QueueTask]:
        """Keyingi taskni olish (bajarish uchun)."""
        with self._lock:
            if len(self._active) >= self.max_concurrent:
                return None
            if not self._queue:
                return None
            task = self._queue.popleft()
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self._active[task.task_id] = task
            return task

    def complete_task(self, task_id: str, result: Optional[dict] = None, error: Optional[str] = None):
        """Task bajarilganini belgilash."""
        with self._lock:
            task = self._active.pop(task_id, None)
            if task is None:
                return
            task.completed_at = time.time()
            if error:
                task.status = TaskStatus.FAILED
                task.error = error
            else:
                task.status = TaskStatus.COMPLETED
            task.result = result
            self._completed.append(task)

    def _sort_queue(self):
        """Navbatni ustuvorlik bo'yicha saralash (high → normal → low)."""
        items = list(self._queue)
        items.sort(key=lambda t: _PRIORITY_ORDER.get(t.priority, 1))
        self._queue.clear()
        self._queue.extend(items)

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def completed_count(self) -> int:
        return len(self._completed)


__all__ = [
    "TaskPriority", "TaskStatus", "QueueTask", "TaskQueue",
]
