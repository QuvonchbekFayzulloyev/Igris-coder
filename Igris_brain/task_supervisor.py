"""
IGRIS BRAIN — Task Supervisor (§9 Scaling to Complex Tasks)
=============================================================

Murakkab, ko'p qismli vazifalarni boshqarish uchun Supervisor + Planner +
DAG arxitekturasi. Bitta so'rov 1+ ta Loop talab qilsa — Supervisor
VAZIFANI bo'laklarga ajratadi, ularni bog'liqlik grafigi (DAG) orqali
bajaradi va natijalarni yig'adi.

Asosiy tushunchalar:
  - TaskNode: bitta sub-vazifa (pending/running/completed/failed)
  - TaskDAG: bog'liqlik grafigi (topological order)
  - TaskSupervisor: scheduler — ready nodlarni dispatch qiladi
  - WorkingContext: context rot ni oldini olish (compact old observations)
  - Checkpoint: crash dan qayta tiklash (2 ta fayl: task + execution)
  - Budget: umumiy max_iter barcha nodlar orasida bo'linadi

O'lcham: solo local tool uchun — multiprocessing, distributed queue,
per-user isolation kerak emas.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Optional


# ------------------------------------------------------------------ #
# TaskNode — bitta sub-vazifa
# ------------------------------------------------------------------ #

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_MORE_STEPS = "needs_more_steps"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskNode:
    """Bitta sub-vazifa — DAG ichidagi node.

    Each node = 1 Loop (§3.2). Har bir node o'ziga xos context oladi
    — faqat o'zi + predecessors natijalari, butun task tarixi emas.
    """
    id: str
    description: str
    need: str  # pipeline type: chat/code/draw/ui_build/...
    predecessors: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    # Node-scoped context: faqat bu node uchun kerakli ma'lumotlar
    context: dict = field(default_factory=dict)
    # Tool calls log (operation log — rollback uchun)
    tool_calls: list[dict] = field(default_factory=list)
    # Files changed (rollback uchun git commit)
    files_changed: list[str] = field(default_factory=list)
    # Iteration tracking
    iterations_used: int = 0
    repairs_used: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TaskNode":
        d = dict(d)
        d["status"] = NodeStatus(d.get("status", "pending"))
        return cls(**d)


# ------------------------------------------------------------------ #
# TaskDAG — bog'liqlik grafigi
# ------------------------------------------------------------------ #

class TaskDAG:
    """Bog'liqlik grafigi — topological order + readiness check.

    Planner tomonidan quriladi, Supervisor tomonidan ishlatiladi.
    """

    def __init__(self, nodes: list[TaskNode] | None = None):
        self.nodes: dict[str, TaskNode] = {}
        if nodes:
            for n in nodes:
                self.nodes[n.id] = n

    def add_node(self, node: TaskNode):
        self.nodes[node.id] = node

    def get_ready(self) -> list[TaskNode]:
        """Hozir bajarilishi mumkin bo'lgan nodlar — barcha predecessors completed."""
        ready = []
        for node in self.nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            preds_ok = all(
                self.nodes[p].status == NodeStatus.COMPLETED
                for p in node.predecessors
                if p in self.nodes
            )
            if preds_ok:
                ready.append(node)
        return ready

    def is_complete(self) -> bool:
        """Barcha nodlar completed yoki failed."""
        return all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.FAILED)
            for n in self.nodes.values()
        )

    def has_failures(self) -> bool:
        return any(n.status == NodeStatus.FAILED for n in self.nodes.values())

    def predecessor_results(self, node_id: str) -> dict[str, str]:
        """Bir node uchun barcha predecessor natijalari."""
        node = self.nodes.get(node_id)
        if not node:
            return {}
        results = {}
        for pred_id in node.predecessors:
            pred = self.nodes.get(pred_id)
            if pred and pred.result:
                results[pred_id] = pred.result
        return results

    def topological_order(self) -> list[str]:
        """DAG ning topological tartibi — qayta ishlash uchun."""
        visited: set[str] = set()
        order: list[str] = []

        def _visit(nid: str):
            if nid in visited:
                return
            visited.add(nid)
            node = self.nodes.get(nid)
            if node:
                for pred in node.predecessors:
                    _visit(pred)
            order.append(nid)

        for nid in self.nodes:
            _visit(nid)
        return order

    def to_dict(self) -> dict:
        return {nid: n.to_dict() for nid, n in self.nodes.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "TaskDAG":
        dag = cls()
        for nid, nd in d.items():
            dag.nodes[nid] = TaskNode.from_dict(nd)
        return dag


# ------------------------------------------------------------------ #
# WorkingContext — context rot oldini olish (§9.2)
# ------------------------------------------------------------------ #

class WorkingContext:
    """Stack-style working set — eski observations ni qisqartiradi.

    Har bir loop iteration'da:
      1. Joriy sub-goal + live plan to'liq saqlanadi
      2. Eskiroq tool observations qisqa summaryga siqiladi
      3. Open dependency state ("node B blocked on node A") saqlanadi

    Bu "context rot" ni oldini oladi — 10-subtask task'da subtask #8
    reasoning'i subtask #2 irrelevant detail'dan buzilmaydi.
    """

    def __init__(self, max_context_chars: int = 12000):
        self.max_context_chars = max_context_chars
        self.current_goal: str = ""
        self.live_plan: list[str] = []
        self.observations: list[dict] = []  # [{role, content, age}]
        self.dependencies: dict[str, str] = {}  # node_id -> status
        self._age_counter: int = 0

    def set_goal(self, goal: str):
        self.current_goal = goal

    def set_plan(self, plan: list[str]):
        self.live_plan = list(plan)

    def add_observation(self, role: str, content: str):
        """Yangi observation qo'shadi — eskilari avtomatik siqiladi."""
        self._age_counter += 1
        self.observations.append({
            "role": role,
            "content": content[:500],  # cheklash
            "age": self._age_counter,
        })
        self._compact()

    def update_dependency(self, node_id: str, status: str):
        self.dependencies[node_id] = status

    def _compact(self):
        """Eski observations ni qisqa summaryga siqadi.

        Faqat eng yangi 3 ta observation to'liq saqlanadi;
        qolganlari 1 qator summaryga siqiladi. Open dependency
        state saqlanadi (default summarizer tashlab ketadigan detallar).
        """
        total = sum(len(o["content"]) for o in self.observations)
        if total <= self.max_context_chars:
            return

        # Eng yangi 3 ni saqla, qolganlarini summaryga siq
        if len(self.observations) <= 3:
            return

        recent = self.observations[-3:]
        old = self.observations[:-3]

        # Summary: nechta observation bo'lgan va ularning umumiy mazmuni
        summary_parts = []
        for o in old[:2]:  # faqat eng eski 2 tasini qisqacha aytish
            text = o["content"][:80]
            summary_parts.append(f"[old] {o['role']}: {text}...")

        summary_content = " | ".join(summary_parts) if summary_parts else "[compacted]"

        self.observations = [{"role": "system", "content": summary_content, "age": 0}] + recent

    def build_context_block(self) -> str:
        """Context blokini quradi — LLM system prompt'ga qo'shiladi."""
        parts = []
        if self.current_goal:
            parts.append(f"Goal: {self.current_goal}")
        if self.live_plan:
            parts.append("Plan: " + " → ".join(self.live_plan))
        if self.dependencies:
            deps = ", ".join(f"{k}={v}" for k, v in self.dependencies.items())
            parts.append(f"Dependencies: {deps}")
        for obs in self.observations:
            parts.append(f"[{obs['role']}] {obs['content']}")
        return "\n".join(parts)

    def total_chars(self) -> int:
        return sum(len(o["content"]) for o in self.observations)


# ------------------------------------------------------------------ #
# Checkpoint — crash dan qayta tiklash (§9.3)
# ------------------------------------------------------------------ #

@dataclass
class TaskCheckpoint:
    """Task-continuity + execution-continuity — 2 ta fayl.

    Task-continuity: goal, DAG, node statuslari
    Execution-continuity: qaysi loop active, qaysi stage, oxirgi completed step

    Har bir pipeline stage tugagandan keyin yoziladi.
    """
    task_id: str
    goal: str
    dag: dict  # TaskDAG.to_dict()
    active_node_id: Optional[str] = None
    active_stage: Optional[str] = None
    last_completed_step: Optional[str] = None
    timestamp: float = 0.0
    # Budget tracking
    total_iterations_used: int = 0
    total_repairs_used: int = 0
    budget_remaining: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskCheckpoint":
        return cls(**d)


class CheckpointManager:
    """Checkpoint yozish/o'qish — 2 ta JSON fayl.

    Fayllar:
      - task_{task_id}.json — task-continuity (goal, DAG, status)
      - exec_{task_id}.json — execution-continuity (active loop, stage)

    Qayta tiklash: ikkala faylni o'qib, DAG dan davom etish.
    """

    def __init__(self, checkpoint_dir: str):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _task_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"task_{task_id}.json")

    def _exec_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"exec_{task_id}.json")

    def save(self, checkpoint: TaskCheckpoint):
        """Checkpoint ni 2 ta faylga saqlaydi."""
        checkpoint.timestamp = time.time()
        data = checkpoint.to_dict()

        # Task-continuity
        task_data = {
            "task_id": data["task_id"],
            "goal": data["goal"],
            "dag": data["dag"],
            "total_iterations_used": data["total_iterations_used"],
            "total_repairs_used": data["total_repairs_used"],
            "budget_remaining": data["budget_remaining"],
            "timestamp": data["timestamp"],
        }
        with open(self._task_path(checkpoint.task_id), "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)

        # Execution-continuity
        exec_data = {
            "task_id": data["task_id"],
            "active_node_id": data["active_node_id"],
            "active_stage": data["active_stage"],
            "last_completed_step": data["last_completed_step"],
            "timestamp": data["timestamp"],
        }
        with open(self._exec_path(checkpoint.task_id), "w", encoding="utf-8") as f:
            json.dump(exec_data, f, ensure_ascii=False, indent=2)

    def load(self, task_id: str) -> Optional[TaskCheckpoint]:
        """Checkpoint ni qayta yuklaydi — mavjud bo'lmasa None."""
        task_path = self._task_path(task_id)
        exec_path = self._exec_path(task_id)
        if not os.path.exists(task_path):
            return None

        with open(task_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        exec_data = {}
        if os.path.exists(exec_path):
            with open(exec_path, "r", encoding="utf-8") as f:
                exec_data = json.load(f)

        return TaskCheckpoint(
            task_id=task_data["task_id"],
            goal=task_data["goal"],
            dag=task_data["dag"],
            active_node_id=exec_data.get("active_node_id"),
            active_stage=exec_data.get("active_stage"),
            last_completed_step=exec_data.get("last_completed_step"),
            total_iterations_used=task_data.get("total_iterations_used", 0),
            total_repairs_used=task_data.get("total_repairs_used", 0),
            budget_remaining=task_data.get("budget_remaining", 0),
            timestamp=task_data.get("timestamp", 0),
        )

    def clear(self, task_id: str):
        """Checkpoint fayllarini o'chiradi."""
        for path in (self._task_path(task_id), self._exec_path(task_id)):
            if os.path.exists(path):
                os.remove(path)


# ------------------------------------------------------------------ #
# TaskSupervisor — scheduler + orchestrator (§9.1 + §9.4)
# ------------------------------------------------------------------ #

# Default budgets
DEFAULT_TOTAL_BUDGET = 40  # umumiy max_iter (barcha nodlar orasida)
DEFAULT_NODE_MAX_ITER = 8  # bitta loop uchun max_iter
DEFAULT_NODE_MAX_REPAIR = 3  # bitta review uchun max_repair


class TaskSupervisor:
    """Murakkab vazifalarni boshqaruvchi — DAG scheduler.

    Flow:
      1. is_atomic() — atomic bo'lsa → bir loop dispatch
      2. build_dag() — non-atomic → DAG quradi
      3. run() — topological scheduling, ready nodlarni dispatch
      4. on failure → self_revise (Planner DAG'ni tuzatadi)
      5. aggregate() — natijalarni yig'adi
      6. checkpoint → crash dan qayta tiklash

    Budget: umumiy max_iter barcha nodlar orasida bo'linadi.
    """

    def __init__(
        self,
        agent=None,
        total_budget: int = DEFAULT_TOTAL_BUDGET,
        checkpoint_dir: Optional[str] = None,
    ):
        self.agent = agent
        self.total_budget = total_budget
        self.budget_remaining = total_budget
        self.checkpoint_mgr = (
            CheckpointManager(checkpoint_dir) if checkpoint_dir else None
        )
        self.dag: Optional[TaskDAG] = None
        self.context = WorkingContext()
        self._task_id: str = ""

    def is_atomic(self, message: str, pipeline: dict) -> bool:
        """So'rov atomic (bitta loop) yoki complex (1+ loop) ekanini aniqlaydi.

        Atomic: oddiy chat, matematika, ob-havo, bitta chizma, bitta kod.
        Non-atomic: "rasm chiz va kod yoz", "UI qur va test yoz", etc.
        """
        # Agar sub_pipelines bo'lsa — non-atomic
        subs = pipeline.get("sub_pipelines", [])
        if subs and len(subs) > 0:
            return False
        # Agar loop_shape plan_then_execute va 5+ stages bo'lsa — hali atomic
        # (bitta loop ichida bajariladi)
        return True

    def build_dag(self, message: str, pipeline: dict) -> TaskDAG:
        """So'rovni DAG ga ajratadi — Planner.

        Har bir pipeline type = bitta TaskNode.
        Sub-pipelines = qo'shimcha nodlar.
        Bog'liqliklar: "kod yoz" -> "test yoz" kabi.
        """
        dag = TaskDAG()
        need = pipeline.get("need", "chat")
        label = pipeline.get("label", need)

        # Asosiy node
        main_node = TaskNode(
            id="main",
            description=label,
            need=need,
            predecessors=[],
        )
        # Node-scoped context: clarified + subject
        main_node.context["clarified"] = pipeline.get("clarified", "")
        main_node.context["subject"] = pipeline.get("subject", "")
        main_node.context["loop_shape"] = pipeline.get("loop_shape", "straight_through")
        main_node.context["max_iter"] = pipeline.get("max_iter", 8)
        main_node.context["max_repair"] = pipeline.get("max_repair", 0)
        dag.add_node(main_node)

        # Sub-pipelines → qo'shimcha nodlar
        for i, sub in enumerate(pipeline.get("sub_pipelines", [])):
            sub_need = sub.get("need", "code")
            sub_id = f"sub_{i}_{sub_need}"
            sub_node = TaskNode(
                id=sub_id,
                description=sub.get("label", sub_need),
                need=sub_need,
                predecessors=["main"],  # asosiy pipeline dan keyin
            )
            sub_node.context["loop_shape"] = sub.get("loop_shape", "straight_through")
            sub_node.context["max_iter"] = sub.get("max_iter", 8)
            sub_node.context["max_repair"] = sub.get("max_repair", 0)
            dag.add_node(sub_node)

        # Bog'liqliklarni aniqlash
        self._infer_dependencies(dag, message)

        return dag

    def _infer_dependencies(self, dag: TaskDAG, message: str):
        """Avtomatik bog'liqliklarni aniqlaydi.

        Masalan: "react ilova qurib ber va test yoz" ->
          main(ui_build) -> sub_code(code) test yozish kod yozishga bog'liq.
        """
        nodes = list(dag.nodes.values())
        for node in nodes:
            if node.id == "main":
                continue
            # Agar predecessors bo'sh bo'lsa — main ga bog'la
            if not node.predecessors:
                node.predecessors = ["main"]

    def run(
        self,
        message: str,
        pipeline: dict,
        progress_cb: Optional[Callable] = None,
    ) -> dict:
        """DAG ni topological tartibda bajaradi.

        Returns: {"status": "ok"|"partial"|"failed", "results": {...}, "summary": str}
        """
        self._task_id = f"task_{int(time.time() * 1000)}"
        self.dag = self.build_dag(message, pipeline)

        # Context setup
        self.context.set_goal(message)
        self.context.set_plan(self.dag.topological_order())

        # Budget calculation
        node_count = len(self.dag.nodes)
        per_node_budget = max(
            DEFAULT_NODE_MAX_ITER,
            self.total_budget // max(node_count, 1),
        )
        self.budget_remaining = self.total_budget

        # Checkpoint: initial save
        self._save_checkpoint()

        results: dict[str, str] = {}
        status = "ok"

        while not self.dag.is_complete():
            ready = self.dag.get_ready()
            if not ready:
                if self.dag.has_failures():
                    status = "partial"
                    break
                # Deadlock — all remaining nodes have unmet deps from failed nodes
                status = "partial"
                break

            # Budget check
            if self.budget_remaining <= 0:
                status = "partial"
                break

            for node in ready:
                # Per-node budget cap
                node_budget = min(per_node_budget, self.budget_remaining)
                if node_budget <= 0:
                    node.status = NodeStatus.FAILED
                    node.error = "Budget exhausted"
                    continue

                node.status = NodeStatus.RUNNING

                if progress_cb:
                    try:
                        progress_cb("supervisor", f"Running: {node.description}")
                    except Exception:
                        pass

                # Node-scoped context build
                pred_results = self.dag.predecessor_results(node.id)
                ctx = self.context.build_context_block()
                if pred_results:
                    ctx += "\n\nPredecessor results:\n"
                    for pid, pres in pred_results.items():
                        ctx += f"  [{pid}]: {pres[:200]}\n"

                # Execute node = run one loop
                try:
                    result = self._execute_node(node, ctx, node_budget)
                    node.result = result
                    node.status = NodeStatus.COMPLETED
                    results[node.id] = result
                    self.budget_remaining -= node.iterations_used

                    # Update working context
                    self.context.add_observation("result", f"{node.id}: {result[:200]}")
                    self.context.update_dependency(node.id, "completed")

                except Exception as exc:
                    node.status = NodeStatus.FAILED
                    node.error = str(exc)[:300]
                    self.context.update_dependency(node.id, "failed")

                    # Self-revision: Planner DAG'ni tuzatadi
                    self._self_revise(node)

                # Checkpoint after each completed node
                self._save_checkpoint(active_node_id=node.id)

        # Aggregation
        summary = self._aggregate(results)

        return {
            "status": status,
            "results": results,
            "summary": summary,
            "iterations_used": self.total_budget - self.budget_remaining,
            "nodes": {nid: n.to_dict() for nid, n in self.dag.nodes.items()},
        }

    def _execute_node(
        self, node: TaskNode, context: str, budget: int
    ) -> str:
        """Bitta node ni bajaradi — bitta Loop (§3.2).

        Agar agent mavjud bo'lsa — agent.chat() chaqiradi.
        Aks holda — placeholder (testing uchun).
        """
        # Build a focused message with node-scoped context
        focused_msg = (
            f"Task: {node.description}\n"
            f"Context:\n{context}\n\n"
            f"Complete this specific sub-task."
        )

        if self.agent is not None:
            try:
                data = self.agent.chat(
                    focused_msg,
                    use_memory=True,
                )
                result = data.get("content", "")
                node.iterations_used = 1  # simplified
                node.tool_calls = data.get("tool_calls", [])
                return result
            except Exception as exc:
                raise RuntimeError(f"Node {node.id} failed: {exc}")

        # Testing placeholder
        node.iterations_used = 1
        return f"[placeholder] Completed: {node.description}"

    def _self_revise(self, failed_node: TaskNode):
        """Self-Revision: Planner DAG'ni tuzatadi (§9.1).

        LLM bo'lsa — LLM orqali DAG'ni tuzatish (qo'shimcha node,
        alternative yo'l, yoki description tuzatish).
        LLM bo'lmasa — retry (max 1 marta) yoki skip.
        """
        if failed_node.status != NodeStatus.FAILED:
            return

        # Strategy 1: LLM-based revision
        if self.agent is not None and hasattr(self.agent, "llm_available"):
            if self.agent.llm_available():
                revised = self._llm_self_revise(failed_node)
                if revised:
                    return

        # Strategy 2: Simple retry (max 1 marta)
        if failed_node.error and "retry" not in str(failed_node.error).lower():
            failed_node.status = NodeStatus.PENDING
            failed_node.error = None
            self.context.add_observation(
                "revision",
                f"Retrying failed node: {failed_node.id}"
            )
        else:
            # Strategy 3: Skip permanently failed node
            failed_node.status = NodeStatus.COMPLETED
            failed_node.result = f"[skipped] {failed_node.description}"
            self.context.add_observation(
                "revision",
                f"Skipping permanently failed node: {failed_node.id}"
            )

    def _llm_self_revise(self, failed_node: TaskNode) -> bool:
        """LLM orqali DAG'ni tuzatish — qo'shimcha node yoki description."""
        try:
            llm = getattr(self.agent, "llm", None)
            if llm is None or not hasattr(llm, "complete"):
                return False

            # DAG holatini LLM ga beramiz
            dag_desc = []
            for nid, node in self.dag.nodes.items():
                status = node.status.value
                dag_desc.append(f"  {nid}: {node.description} [{status}]")

            prompt = (
                f"A task node failed: {failed_node.id} ({failed_node.description})\n"
                f"Error: {failed_node.error}\n\n"
                f"Current DAG:\n" + "\n".join(dag_desc) + "\n\n"
                "How to fix this? Respond with ONLY one of:\n"
                '1. {"action": "retry", "new_description": "..."} — fix the description and retry\n'
                '2. {"action": "skip"} — skip this node entirely\n'
                '3. {"action": "add_fix_node", "id": "fix_...", "description": "...", "need": "code", "predecessors": ["..."]} — add a fix-up node before retrying'
            )

            system = (
                "You are a task recovery planner. A sub-task failed. "
                "Suggest the simplest fix. Respond with ONLY valid JSON."
            )

            response = llm.complete(prompt, system=system)
            if not response:
                return False

            # Parse JSON
            import json as _json
            import re
            text = response.strip()
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if m:
                text = m.group(1)
            elif not text.startswith("{"):
                s = text.find("{")
                e = text.rfind("}")
                if s >= 0 and e > s:
                    text = text[s:e + 1]

            data = _json.loads(text)
            action = data.get("action", "skip")

            if action == "retry":
                new_desc = data.get("new_description", failed_node.description)
                failed_node.description = new_desc
                failed_node.status = NodeStatus.PENDING
                failed_node.error = None
                self.context.add_observation(
                    "llm_revision",
                    f"LLM revised: {failed_node.id} → {new_desc[:80]}"
                )
                return True

            elif action == "add_fix_node":
                fix_id = data.get("id", f"fix_{failed_node.id}")
                fix_desc = data.get("description", f"Fix {failed_node.description}")
                fix_need = data.get("need", "code")
                fix_preds = data.get("predecessors", [])

                # Add fix node to DAG
                fix_node = TaskNode(
                    id=fix_id,
                    description=fix_desc,
                    need=fix_need,
                    predecessors=[p for p in fix_preds if p in self.dag.nodes],
                )
                self.dag.add_node(fix_node)

                # Mark original as pending again
                failed_node.status = NodeStatus.PENDING
                failed_node.error = None
                failed_node.predecessors.append(fix_id)

                self.context.add_observation(
                    "llm_revision",
                    f"LLM added fix node: {fix_id} before {failed_node.id}"
                )
                return True

            elif action == "skip":
                failed_node.status = NodeStatus.COMPLETED
                failed_node.result = f"[skipped by LLM] {failed_node.description}"
                self.context.add_observation(
                    "llm_revision",
                    f"LLM skipped: {failed_node.id}"
                )
                return True

        except Exception:
            pass

        return False

    def _aggregate(self, results: dict[str, str]) -> str:
        """Barcha completed node natijalarini yig'adi — synthesis (§3.3.f)."""
        parts = []
        order = self.dag.topological_order() if self.dag else list(results.keys())
        for nid in order:
            if nid in results:
                parts.append(f"**{nid}**: {results[nid]}")
        return "\n\n".join(parts) if parts else "No results."

    def _save_checkpoint(self, active_node_id: Optional[str] = None):
        """Checkpoint saqlaydi — crash dan qayta tiklash uchun."""
        if not self.checkpoint_mgr or not self.dag:
            return

        cp = TaskCheckpoint(
            task_id=self._task_id,
            goal=self.context.current_goal,
            dag=self.dag.to_dict(),
            active_node_id=active_node_id,
            active_stage=None,
            last_completed_step=active_node_id,
            total_iterations_used=self.total_budget - self.budget_remaining,
            total_repairs_used=0,
            budget_remaining=self.budget_remaining,
        )
        self.checkpoint_mgr.save(cp)

    def resume(self, task_id: str) -> Optional[dict]:
        """Checkpoint dan qayta tiklash — DAG ni qayta yuklaydi va davom ettiradi."""
        if not self.checkpoint_mgr:
            return None

        cp = self.checkpoint_mgr.load(task_id)
        if cp is None:
            return None

        self._task_id = task_id
        self.dag = TaskDAG.from_dict(cp.dag)
        self.budget_remaining = cp.budget_remaining
        self.context.set_goal(cp.goal)

        # Pending nodlarni qayta ishga tushirish
        results: dict[str, str] = {}
        for nid, node in self.dag.nodes.items():
            if node.status == NodeStatus.COMPLETED and node.result:
                results[nid] = node.result

        # Resume: ready nodlarni bajarish
        while not self.dag.is_complete():
            ready = self.dag.get_ready()
            if not ready:
                break
            for node in ready:
                node.status = NodeStatus.RUNNING
                try:
                    result = self._execute_node(
                        node, "", min(DEFAULT_NODE_MAX_ITER, self.budget_remaining)
                    )
                    node.result = result
                    node.status = NodeStatus.COMPLETED
                    results[node.id] = result
                    self.budget_remaining -= node.iterations_used
                except Exception:
                    node.status = NodeStatus.FAILED
                    self._self_revise(node)
            self._save_checkpoint()

        return {
            "status": "ok" if not self.dag.has_failures() else "partial",
            "results": results,
            "summary": self._aggregate(results),
            "resumed_from": task_id,
        }


# ------------------------------------------------------------------ #
# LLMDAGPlanner — LLM orqali so'rovni sub-task'larga ajratish (§9.1)
# ------------------------------------------------------------------ #

DAG_PLAN_SYSTEM = (
    "You are a task decomposition planner for a coding agent. "
    "Break the user's complex request into a dependency graph (DAG) of "
    "concrete sub-tasks. Each sub-task needs a pipeline type from: "
    "chat, code, draw, ui_build, web, composition, file_task.\n\n"
    "Rules:\n"
    "- Each sub-task has an id, description, need (pipeline type), "
    "and a list of predecessor ids (tasks that must complete first).\n"
    "- If tasks are independent, they can have no predecessors or share the same predecessor.\n"
    "- Keep it to 2-5 sub-tasks max. Simpler is better.\n"
    "- If the request is simple enough for a single pipeline, return just one task.\n\n"
    "Respond with ONLY valid JSON:\n"
    '{"tasks": [{"id": "t1", "description": "...", "need": "code", "predecessors": []}, ...]}'
)


class LLMDAGPlanner:
    """LLM orqali so'rovni sub-task'larga ajratadi.

    Fallback: LLM bo'lmasa yoki noto'g'ri JSON qaytarsa —
    oddiy main + sub_pipelines DAG qaytariladi.
    """

    def __init__(self, llm=None):
        self.llm = llm

    def plan(self, message: str, pipeline: dict) -> Optional[TaskDAG]:
        """So'rovni DAG ga ajratadi.

        Returns: TaskDAG yoki None (LLM mavjud emas / noto'g'ri natija).
        """
        if self.llm is None:
            return None

        # Try LLM-based planning
        try:
            dag = self._llm_plan(message, pipeline)
            if dag is not None and len(dag.nodes) >= 1:
                return dag
        except Exception:
            pass

        return None

    def _llm_plan(self, message: str, pipeline: dict) -> Optional[TaskDAG]:
        """LLM chaqiruvi — JSON DAG plan olish."""
        # Pipeline context — LLM ga mavjud pipeline turini tushuntirish
        need = pipeline.get("need", "chat")
        label = pipeline.get("label", need)
        subs = pipeline.get("sub_pipelines", [])
        subs_info = ", ".join(s.get("need", "?") for s in subs) if subs else "none"

        prompt = (
            f"User request: {message}\n"
            f"Detected pipeline: {label} ({need})\n"
            f"Sub-pipelines detected: {subs_info}\n\n"
            "Decompose this into a DAG of sub-tasks. "
            "If it's already simple enough for one pipeline, return just one task."
        )

        response = self.llm.complete(prompt, system=DAG_PLAN_SYSTEM)
        if not response:
            return None

        return self._parse_dag_json(response)

    def _parse_dag_json(self, text: str) -> Optional[TaskDAG]:
        """LLM javobidan DAG quradi — JSON parsing + xavfsiz fallback."""
        text = text.strip()

        # JSON blokni topish (```json ... ``` yoki to'g'ridan-to'g'ri)
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        elif not text.startswith("{"):
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end + 1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        tasks = data.get("tasks", [])
        if not tasks:
            return None

        dag = TaskDAG()
        valid_needs = {"chat", "code", "draw", "ui_build", "web",
                       "composition", "file_task", "math", "weather"}

        for t in tasks:
            nid = str(t.get("id", "")).strip()
            if not nid:
                continue
            need = t.get("need", "chat")
            if need not in valid_needs:
                need = "chat"

            node = TaskNode(
                id=nid,
                description=str(t.get("description", ""))[:200],
                need=need,
                predecessors=[str(p) for p in t.get("predecessors", [])],
            )
            dag.add_node(node)

        # Validate: all predecessors must exist
        for node in list(dag.nodes.values()):
            node.predecessors = [
                p for p in node.predecessors if p in dag.nodes
            ]

        return dag if dag.nodes else None


# ------------------------------------------------------------------ #
# GitCheckpointManager — git commit at checkpoint (§9.3)
# ------------------------------------------------------------------ #

import subprocess  # noqa: E402


class GitCheckpointManager(CheckpointManager):
    """Checkpoint + git commit — rollback support.

    Har bir checkpoint'da git commit qilinadi:
      1. Checkpoint fayllarini yozadi (otadan)
      2. O'zgargan fayllarni staging qiladi
      3. Git commit qiladi ("checkpoint: {task_id}")

    Rollback: git revert yoki git reset orqali.
    """

    def __init__(self, checkpoint_dir: str, repo_dir: Optional[str] = None):
        super().__init__(checkpoint_dir)
        self.repo_dir = repo_dir or os.path.dirname(checkpoint_dir)
        self._git_available = self._check_git()

    def _check_git(self) -> bool:
        """Git mavjudligini tekshiradi."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5,
                cwd=self.repo_dir,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def save(self, checkpoint: TaskCheckpoint):
        """Checkpoint saqlaydi + git commit."""
        # Parent: checkpoint fayllarini yozish
        super().save(checkpoint)

        # Git commit
        if self._git_available:
            self._git_commit(checkpoint.task_id)

    def _git_commit(self, task_id: str):
        """Git add + commit — checkpoint fayllarini saqlaydi."""
        try:
            # Add checkpoint files
            task_file = self._task_path(task_id)
            exec_file = self._exec_path(task_id)

            for fpath in (task_file, exec_file):
                if os.path.exists(fpath):
                    subprocess.run(
                        ["git", "add", fpath],
                        capture_output=True, timeout=5,
                        cwd=self.repo_dir,
                    )

            # Commit
            subprocess.run(
                ["git", "commit", "-m", f"checkpoint: {task_id}", "--allow-empty"],
                capture_output=True, timeout=10,
                cwd=self.repo_dir,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # Git xatosi — checkpoint fayllari saqlanib qoladi

    def get_last_checkpoint_commit(self, task_id: str) -> Optional[str]:
        """Oxirgi checkpoint commit'ini topadi — rollback uchun."""
        if not self._git_available:
            return None
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1",
                 "--grep", f"checkpoint: {task_id}"],
                capture_output=True, text=True, timeout=5,
                cwd=self.repo_dir,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split()[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def rollback(self, task_id: str) -> bool:
        """Checkpoint ga qaytaradi — git reset --hard + checkpoint restore."""
        if not self._git_available:
            return False
        commit = self.get_last_checkpoint_commit(task_id)
        if not commit:
            return False
        try:
            # Git reset to checkpoint commit
            subprocess.run(
                ["git", "reset", "--hard", commit],
                capture_output=True, timeout=10,
                cwd=self.repo_dir,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_checkpoints(self) -> list[str]:
        """Barcha checkpoint commit'larini ro'yxatlaydi."""
        if not self._git_available:
            return []
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--grep", "checkpoint:", "--all"],
                capture_output=True, text=True, timeout=5,
                cwd=self.repo_dir,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                return [ln.strip() for ln in lines if ln.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return []
