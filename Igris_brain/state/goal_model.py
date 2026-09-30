"""
IGRIS BRAIN — Goal Hierarchy modeli (Phase 1: Foundation)
=========================================================
Arxitektura audit plani §2 natijasi: user goal avval `plan["goal"]` sifatida
mutable saqlangan edi — re-plan paytida o'zgarishi mumkin edi (goal loss
xavfi). Bu modul GOAL PRESERVATION kafolini beradi:

    Goal (frozen)  →  Objective (mutable, goal_id reference)  →  Task  →  Action

Qoidalar (audit §2.2):
  1. Goal immutable — hech qachon o'zgartirilmaydi (frozen dataclass).
  2. Objective/Task mutable, lekin goal_id doim original Goal'ga ishora qiladi.
  3. Re-plan faqat Task darajasida o'zgaradi — goal_id hech qachon.
  4. Har bir LLM prompt'ga goal text PIN qilinadi (prompt_pin()).
  5. Resume: to_dict/from_dict — goal disk'dan tiklanadi.

Run: python goal_model.py   (o'z-o'zini tekshiruv)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.state_machine import TaskStatus

MAX_GOAL_TEXT = 2000      # prompt pin xavfsiz chegarasi
MAX_NOTE_TEXT = 500


def _now() -> float:
    return round(time.time(), 3)


def _clip(text: str, limit: int) -> str:
    return (text or "")[:limit]


# ------------------------------------------------------------------ #
# Goal — immutable
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class Goal:
    """User'ning ORIGINAL maqsadi — immutable, never modified (§12).

    Yangi Goal yaratish kerak bo'lsa `replace()` bilan yangi obyekt
    yaratiladi (asl nusxa saqlanadi) — dataclass(frozen=True) buni majburlaydi.
    """
    id: str
    text: str
    created_at: float

    @staticmethod
    def create(text: str) -> "Goal":
        clean = _clip(str(text or "").strip(), MAX_GOAL_TEXT)
        if not clean:
            raise ValueError("goal text is required (empty after strip)")
        return Goal(id=f"goal-{uuid.uuid4().hex[:12]}", text=clean, created_at=_now())

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        if not d.get("id") or not d.get("text"):
            raise ValueError("goal dict requires id and text")
        return cls(id=str(d["id"]), text=str(d["text"]),
                   created_at=float(d.get("created_at") or _now()))


# ------------------------------------------------------------------ #
# Action — eng kichik birlik
# ------------------------------------------------------------------ #

@dataclass
class Action:
    """Bitta tool chaqiruv (§2 Subtask → Action darajasi)."""
    id: str
    tool: str
    args: dict = field(default_factory=dict)
    result: dict | None = None
    status: str = "pending"            # pending | done | failed
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tool": self.tool, "args": self.args,
            "result": self.result, "status": self.status,
            "started_at": self.started_at, "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(id=str(d.get("id") or f"act-{uuid.uuid4().hex[:8]}"),
                   tool=str(d.get("tool") or ""),
                   args=dict(d.get("args") or {}),
                   result=d.get("result"),
                   status=str(d.get("status") or "pending"),
                   started_at=d.get("started_at"),
                   finished_at=d.get("finished_at"))


# ------------------------------------------------------------------ #
# Task — subtask daraxti
# ------------------------------------------------------------------ #

@dataclass
class Task:
    """Objective ichidagi bitta task/subtask (§2).

    Parent Objective'ga `objective_id` bilan bog'lanadi — subtask
    bajarilganda parent maqsad YO'QOLMAYDI (har bir Task o'z goal_id'ni
    o'zida saqlaydi — §2 'Subtask bajarilganda parent objective yo'qolmasligi').
    """
    id: str
    title: str
    objective_id: str
    goal_id: str                    # original goal'ga immutable ishora
    detail: str = ""
    status: TaskStatus = TaskStatus.PENDING
    parent_task_id: str | None = None
    subtasks: list["Task"] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    priority: int = 0               # katta = yuqori ustuvorlik (§2 priority)
    dependencies: list[str] = field(default_factory=list)   # boshqa Task id
    created_at: float = field(default_factory=_now)
    finished_at: float | None = None

    # ---------------- holat o'zgarishlari ---------------- #

    def set_status(self, new: TaskStatus) -> TaskStatus:
        """Deterministik status o'zgarishi (LLM ishlovi yo'q).

        Ruxsat etilgan o'tishlar (state machine §1 bilan mos):
          PENDING -> RUNNING | FAILED
          RUNNING -> COMPLETED | FAILED | PARTIAL | NEEDS_MORE_STEPS | PENDING (reset)
          NEEDS_MORE_STEPS -> RUNNING | FAILED
          PARTIAL -> RUNNING | COMPLETED | FAILED
        """
        allowed: dict[TaskStatus, set[TaskStatus]] = {
            TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED},
            TaskStatus.RUNNING: {
                TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PARTIAL,
                TaskStatus.NEEDS_MORE_STEPS, TaskStatus.PENDING,
            },
            TaskStatus.NEEDS_MORE_STEPS: {TaskStatus.RUNNING, TaskStatus.FAILED},
            TaskStatus.PARTIAL: {TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED},
            TaskStatus.COMPLETED: set(),
            TaskStatus.FAILED: {TaskStatus.PENDING},   # qayta urinish uchun reset
        }
        new = TaskStatus(new)
        if new not in allowed.get(self.status, set()):
            raise ValueError(
                f"invalid task status transition {self.status.value} -> {new.value}")
        self.status = new
        if new in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self.finished_at = _now()
        return self.status

    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    # ---------------- serializatsiya ---------------- #

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title,
            "objective_id": self.objective_id, "goal_id": self.goal_id,
            "detail": self.detail, "status": self.status.value,
            "parent_task_id": self.parent_task_id,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "actions": [a.to_dict() for a in self.actions],
            "priority": self.priority, "dependencies": list(self.dependencies),
            "created_at": self.created_at, "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=str(d["id"]), title=str(d.get("title") or ""),
            objective_id=str(d.get("objective_id") or ""),
            goal_id=str(d.get("goal_id") or ""),
            detail=str(d.get("detail") or ""),
            status=TaskStatus(d.get("status") or "pending"),
            parent_task_id=d.get("parent_task_id"),
            subtasks=[Task.from_dict(st) for st in (d.get("subtasks") or [])],
            actions=[Action.from_dict(a) for a in (d.get("actions") or [])],
            priority=int(d.get("priority") or 0),
            dependencies=list(d.get("dependencies") or []),
            created_at=float(d.get("created_at") or _now()),
            finished_at=d.get("finished_at"),
        )


# ------------------------------------------------------------------ #
# Objective — mutable, goal'ga ishora qiladi
# ------------------------------------------------------------------ #

@dataclass
class Objective:
    """Hozirgi bajarilayotgan maqsad — Goal'ga immutable reference bilan.

    Objective o'zgarishi mumkin (re-plan), lekin goal_id HECH QACHON
    o'zgartirilmaydi — `replan()` buni majburlaydi.
    """
    id: str
    goal_id: str
    current: str                    # hozirgi maqsad bayoni (mutable)
    tasks: list[Task] = field(default_factory=list)
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    # ---------------- task boshqaruvi ---------------- #

    def add_task(self, title: str, detail: str = "", priority: int = 0,
                 dependencies: list[str] | None = None,
                 parent_task_id: str | None = None) -> Task:
        task = Task(
            id=f"task-{uuid.uuid4().hex[:10]}",
            title=_clip(title, 200),
            objective_id=self.id,
            goal_id=self.goal_id,
            detail=_clip(detail, MAX_NOTE_TEXT),
            priority=priority,
            dependencies=list(dependencies or []),
            parent_task_id=parent_task_id,
        )
        if parent_task_id:
            parent = self.find_task(parent_task_id)
            if parent is None:
                raise ValueError(f"parent task not found: {parent_task_id}")
            parent.subtasks.append(task)
        else:
            self.tasks.append(task)
        self.updated_at = _now()
        return task

    def find_task(self, task_id: str) -> Task | None:
        def _search(tasks: list[Task]) -> Task | None:
            for t in tasks:
                if t.id == task_id:
                    return t
                found = _search(t.subtasks)
                if found:
                    return found
            return None
        return _search(self.tasks)

    def replan(self, new_current: str, new_tasks: list[Task]) -> None:
        """Re-plan: current + tasks yangilanadi, goal_id SAQLANADI (§12).

        Yangi tasklar goal_id'ni objective'dan meros qilib oladi —
        original goal hech qachon yo'qolmaydi.
        """
        self.current = _clip(new_current, MAX_NOTE_TEXT)
        self.tasks = list(new_tasks)
        for t in self.tasks:
            if t.goal_id != self.goal_id:
                t.goal_id = self.goal_id      # majburiy sinxron (immutable Goal)
        self.updated_at = _now()

    # ---------------- serializatsiya ---------------- #

    def to_dict(self) -> dict:
        return {
            "id": self.id, "goal_id": self.goal_id, "current": self.current,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Objective":
        obj = cls(id=str(d["id"]), goal_id=str(d["goal_id"]),
                  current=str(d.get("current") or ""),
                  created_at=float(d.get("created_at") or _now()),
                  updated_at=float(d.get("updated_at") or _now()))
        obj.tasks = [Task.from_dict(t) for t in (d.get("tasks") or [])]
        return obj


# ------------------------------------------------------------------ #
# GoalContext — goal pin (context compression'da saqlanadi, §6/§12)
# ------------------------------------------------------------------ #

class GoalContext:
    """Run davomida goal'ni PIN qilib turadi.

    `prompt_pin()` har bir LLM prompt'ining boshiga qo'shiladi — context
    compression/summarization paytida ham original goal doim contextda
    qoladi (audit §2 'Current objective doim saqlanishi' + §12).
    """

    def __init__(self, goal: Goal, objective: Objective | None = None):
        self.goal = goal
        self.objective = objective

    def prompt_pin(self, objective_text: str | None = None) -> str:
        """LLM prompt'ga qo'shiladigan ixcham goal bloki."""
        obj = objective_text or (self.objective.current if self.objective else "")
        pin = f"[ORIGINAL GOAL] {self.goal.text}"
        if obj and obj != self.goal.text:
            pin += f"\n[CURRENT OBJECTIVE] {obj}"
        return pin

    def bind(self, objective: Objective) -> None:
        """Objective'ni goal'ga bog'laydi — goal_id mos kelishi MAJBURIY."""
        if objective.goal_id != self.goal.id:
            raise ValueError(
                f"objective goal_id mismatch: {objective.goal_id} != {self.goal.id}")
        self.objective = objective

    def to_dict(self) -> dict:
        return {
            "goal": self.goal.to_dict(),
            "objective": self.objective.to_dict() if self.objective else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GoalContext":
        goal = Goal.from_dict(d["goal"])
        obj = Objective.from_dict(d["objective"]) if d.get("objective") else None
        return cls(goal, obj)


def save_goal_context(ctx: GoalContext, path: str) -> str:
    """GoalContext'ni JSON faylga yozadi (resume uchun, §12)."""
    import json
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ctx.to_dict(), fh, ensure_ascii=False, indent=2)
    return path


def load_goal_context(path: str) -> GoalContext:
    """GoalContext'ni disk'dan tiklaydi (resume: original goal + progress)."""
    import json
    with open(path, "r", encoding="utf-8") as fh:
        return GoalContext.from_dict(json.load(fh))


# ------------------------------------------------------------------ #
# O'z-o'zini tekshiruv
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    goal = Goal.create("Mini ilon o'yinini yasab ber")
    obj = Objective(id=f"obj-{uuid.uuid4().hex[:8]}", goal_id=goal.id,
                    current="o'yin kodini yozish")
    gctx = GoalContext(goal, obj)

    t1 = obj.add_task("snake klassini yoz", detail="grid + move logic")
    t2 = obj.add_task("o'yin tsiklini yoz", dependencies=[t1.id])

    # replan — goal saqlanishi
    old_goal_id = obj.goal_id
    obj.replan("qayta: pygame bilan yozish", [Task(id="task-x", title="yangi reja",
                                                    objective_id=obj.id,
                                                    goal_id="XATO-GOAL")])
    assert obj.goal_id == old_goal_id, "replan goal_id ni o'zgartirmasligi kerak"
    assert obj.tasks[0].goal_id == old_goal_id, "task goal_id majburiy sinxron"
    print("PASS | replan preserves goal_id")

    # frozen goal — o'zgartirib bo'lmaydi
    try:
        goal.text = "hack"
        raise SystemExit("FAIL | frozen Goal o'zgartirildi")
    except Exception:
        print("PASS | Goal is frozen")

    # invalid status transition
    try:
        t2.set_status(TaskStatus.COMPLETED)   # PENDING -> COMPLETED taqiqlangan
        raise SystemExit("FAIL | PENDING -> COMPLETED o'tdi")
    except ValueError:
        print("PASS | invalid task status transition blocked")

    # round-trip
    d = gctx.to_dict()
    gctx2 = GoalContext.from_dict(d)
    assert gctx2.goal.text == goal.text and gctx2.objective.current == obj.current
    print("PASS | GoalContext round-trip")

    # prompt pin
    pin = gctx.prompt_pin()
    assert pin.startswith("[ORIGINAL GOAL]") and "Mini ilon" in pin
    print("PASS | prompt_pin")

    print("OK | goal_model selftest")
