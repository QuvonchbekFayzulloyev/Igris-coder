"""
IGRIS BRAIN — Formal State Machine (Phase 1: Foundation)
=========================================================
Arxitektura audit plani §1 + §17 natijasi: agent holatlari avval 3 darajada
tarqoq edi (PIPELINE_SPECS stages / executor status / NodeStatus). Bu modul
BIR yagona, deterministik state machine beradi.

Qoidalar (audit §17):
  - State transition'lari 100% DETERMINISTIK — LLM bu yerga kirmaydi.
  - Har bir transition guard funksiyasi orqali o'tadi (invalid transition
    bloklanadi + logga yoziladi).
  - Har bir o'tish history'ga yoziladi (§16 observability uchun asos).

Pipeline bosqichlari (nominal, §1.3 dizayni):

    INPUT -> UNDERSTAND -> PLAN -> EXECUTE -> OBSERVE -> VERIFY -> UPDATE_STATE
              ^                                                      |
              |                    CONTINUE <------------------------+
              |                      |
              +----------------------+  (keyingi iteratsiya PLAN'dan)

    Yakun: COMPLETE (faqat VERIFIED) | FAIL | ESCALATE
    Repair: VERIFY -> EXECUTE (FAILED + retry < max_retries)

Run: python state_machine.py   (o'z-o'zini tekshiruv)
"""

from __future__ import annotations

import json
import os
import time
from enum import Enum
from typing import Any, Callable, Optional


# ------------------------------------------------------------------ #
# Enum'lar
# ------------------------------------------------------------------ #

class AgentState(str, Enum):
    """Agentning operational holatlari (§1)."""
    INPUT = "INPUT"
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    VERIFY = "VERIFY"
    UPDATE_STATE = "UPDATE_STATE"
    CONTINUE = "CONTINUE"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"


class VerificationStatus(str, Enum):
    """Verify bosqichi natijasi (§10 bilan bog'lanadi).

    COMPLETE state'ga o'tish uchun FAQAT VERIFIED qabul qilinadi —
    "tool success != real-world success" qoidasi shu yerda mustahkamlanadi.
    """
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class TaskStatus(str, Enum):
    """Task/subtask holati (§2) — task_supervisor.NodeStatus bilan bir ma'noda.

    task_supervisor o'z NodeStatus'ini saqlaydi (backwards-compat); yangi kod
    shu enum'ni ishlatadi. Qiymatlar bir xil — serializatsiya mos.
    """
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_MORE_STEPS = "needs_more_steps"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ------------------------------------------------------------------ #
# Guard funksiyalari
# ------------------------------------------------------------------ #
# Har bir guard: (ctx: dict) -> (ok: bool, reason: str)
# ctx — transition konteksti. Majburiy kalit yetishmasa — BLOKLANADI
# (deterministik xavfsizlik: noma'lum holatda o'tkazmaymiz).

def _need(ctx: dict, key: str, expected_true: bool = True) -> tuple[bool, str]:
    val = ctx.get(key)
    if val is None:
        return False, f"missing context: {key}"
    if expected_true and not val:
        return False, f"context {key} falsy"
    return True, ""


def g_input_validated(ctx: dict) -> tuple[bool, str]:
    return _need(ctx, "input_validated")


def g_requirements_ready(ctx: dict) -> tuple[bool, str]:
    return _need(ctx, "requirements_ready")


def g_plan_valid(ctx: dict) -> tuple[bool, str]:
    """PLAN -> EXECUTE: kamida 1 qadam VA barcha tool nomlari mavjud."""
    steps = ctx.get("plan_steps")
    if steps is None:
        return False, "missing context: plan_steps"
    if not isinstance(steps, list) or len(steps) < 1:
        return False, "plan has no steps"
    allowed = ctx.get("allowed_tools")
    if allowed is None:
        return False, "missing context: allowed_tools"
    plan_tools: set[str] = set()
    for s in steps:
        if isinstance(s, dict):
            plan_tools |= {str(t) for t in (s.get("tools") or [])}
    unknown = plan_tools - set(allowed)
    if unknown:
        return False, f"unknown tools in plan: {sorted(unknown)[:5]}"
    return True, ""


def g_tool_result_ready(ctx: dict) -> tuple[bool, str]:
    return _need(ctx, "tool_result")


def g_observation_flagged(ctx: dict) -> tuple[bool, str]:
    """OBSERVE -> VERIFY: observation confirmed/assumed flag bilan belgilangan."""
    flags = ctx.get("observation_flags")
    if flags is None:
        return False, "missing context: observation_flags"
    if not isinstance(flags, (list, tuple, set)) or not flags:
        return False, "observation not flagged (confirmed/assumed)"
    if not ({"confirmed", "assumed"} & set(flags)):
        return False, "observation flag must be 'confirmed' or 'assumed'"
    return True, ""


def g_verify_status(ctx: dict) -> tuple[bool, str]:
    """VERIFY -> UPDATE_STATE: verification status majburiy."""
    status = ctx.get("verify_status")
    if status is None:
        return False, "missing context: verify_status"
    try:
        VerificationStatus(str(status))
    except ValueError:
        return False, f"invalid verify_status: {status}"
    return True, ""


def g_continue(ctx: dict) -> tuple[bool, str]:
    """UPDATE_STATE -> CONTINUE: qolgan qadam bor VA iteration limit ichida."""
    remaining = ctx.get("remaining_steps")
    if remaining is None:
        return False, "missing context: remaining_steps"
    iteration = ctx.get("iteration", 0)
    max_iter = ctx.get("max_iter", 50)
    if not isinstance(iteration, int) or not isinstance(max_iter, int):
        return False, "iteration/max_iter must be int"
    if iteration >= max_iter:
        return False, f"iteration limit reached ({iteration}/{max_iter})"
    if remaining <= 0:
        return False, "no remaining steps"
    return True, ""


def g_complete(ctx: dict) -> tuple[bool, str]:
    """UPDATE_STATE -> COMPLETE: FAQAT VERIFIED + qolgan qadam yo'q.

    Bu agentning eng muhim deterministik kafoli: 'bajardim' da'vosi
    verification'siz COMPLETE bo'la olmaydi (§10, §17).

    R1.2 (Roadmap v3): context'da `completion` berilgan bo'lsa (requirement
    matrix formal statusi) — u HAM 'complete' bo'lishi SHART (bir manba —
    executor _build_requirement_matrix bilan). Matrix FAIL/PARTIAL/BLOCKED
    bo'lsa COMPLETE mumkin emas, hatto VERIFIED bo'lsa ham.
    """
    status = str(ctx.get("verify_status") or "")
    if status != VerificationStatus.VERIFIED.value:
        return False, f"completion requires VERIFIED, got {status or 'none'}"
    # R1.2: requirement matrix formal contract — SM bilan BIR MANBA.
    completion = ctx.get("completion")
    if completion is not None and str(completion) != "complete":
        return False, f"requirement matrix not complete: {completion}"
    remaining = ctx.get("remaining_steps")
    if remaining is None:
        return False, "missing context: remaining_steps"
    if remaining > 0:
        return False, f"still {remaining} steps remaining"
    return True, ""


def g_fail(ctx: dict) -> tuple[bool, str]:
    """UPDATE_STATE -> FAIL: retry limiti tugagan yoki hal qilinmaydigan xato."""
    if ctx.get("retry_limit_reached"):
        return True, ""
    if ctx.get("fatal_error"):
        return True, ""
    return False, "fail requires retry_limit_reached or fatal_error"


def g_repair(ctx: dict) -> tuple[bool, str]:
    """VERIFY -> EXECUTE: FAILED + retry < max_retries (repair pass)."""
    status = str(ctx.get("verify_status") or "")
    if status != VerificationStatus.FAILED.value:
        return False, f"repair requires FAILED, got {status or 'none'}"
    retries = ctx.get("retries", 0)
    max_retries = ctx.get("max_retries", 2)
    if not isinstance(retries, int) or not isinstance(max_retries, int):
        return False, "retries/max_retries must be int"
    if retries >= max_retries:
        return False, f"retry limit reached ({retries}/{max_retries})"
    return True, ""


def g_escalate(ctx: dict) -> tuple[bool, str]:
    """* -> ESCALATE: user intervention talab qilinadi (§11)."""
    return _need(ctx, "needs_human")


# ------------------------------------------------------------------ #
# Transition jadvali
# ------------------------------------------------------------------ #

GuardFn = Callable[[dict], tuple[bool, str]]

TRANSITIONS: dict[AgentState, dict[AgentState, GuardFn]] = {
    AgentState.INPUT: {
        AgentState.UNDERSTAND: g_input_validated,
    },
    AgentState.UNDERSTAND: {
        AgentState.PLAN: g_requirements_ready,
        AgentState.ESCALATE: g_escalate,
    },
    AgentState.PLAN: {
        AgentState.EXECUTE: g_plan_valid,
        AgentState.ESCALATE: g_escalate,
    },
    AgentState.EXECUTE: {
        AgentState.OBSERVE: g_tool_result_ready,
        AgentState.FAIL: g_fail,
    },
    AgentState.OBSERVE: {
        AgentState.VERIFY: g_observation_flagged,
    },
    AgentState.VERIFY: {
        AgentState.UPDATE_STATE: g_verify_status,
        AgentState.EXECUTE: g_repair,
    },
    AgentState.UPDATE_STATE: {
        AgentState.CONTINUE: g_continue,
        AgentState.COMPLETE: g_complete,
        AgentState.FAIL: g_fail,
        AgentState.ESCALATE: g_escalate,
    },
    AgentState.CONTINUE: {
        AgentState.PLAN: lambda ctx: (True, ""),   # keyingi iteratsiya
    },
    AgentState.FAIL: {
        AgentState.ESCALATE: g_escalate,
    },
}


class StateTransitionError(Exception):
    """Invalid transition — guard rad etdi yoki yo'l umuman mavjud emas."""

    def __init__(self, from_state: AgentState, to_state: AgentState, reason: str):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"invalid transition {from_state.value} -> {to_state.value}: {reason}")


# ------------------------------------------------------------------ #
# StateMachine
# ------------------------------------------------------------------ #

class StateMachine:
    """Bitta task/run uchun formal holat mashinasi (deterministik).

    - `transition()` guard'dan o'tmasa StateTransitionError ko'taradi
      (xato hech qachon jim o'tmaydi — audit talabi).
    - Har bir urinish (muvaffaqiyatli/yiqilgan) history'ga yoziladi.
    - `history()` / `dump_history()` — §16 observability uchun.
    """

    def __init__(self, initial: AgentState = AgentState.INPUT,
                 task_id: str = "", max_iter: int = 50, max_retries: int = 2):
        self.task_id = task_id
        self.max_iter = max_iter
        self.max_retries = max_retries
        self._state = AgentState(initial)
        self._history: list[dict] = []
        self._iteration = 0
        self._retries = 0
        self._log("init", None, self._state, True, "initial state")

    # ---------------- xususiyatlar ---------------- #

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def iteration(self) -> int:
        return self._iteration

    @property
    def retries(self) -> int:
        return self._retries

    # ---------------- asosiy API ---------------- #

    def can(self, to_state: AgentState | str, ctx: Optional[dict] = None) -> tuple[bool, str]:
        """O'tish mumkinmi — guard'ni bajarmasdan BEKOR... bajarmasdan TEKSHIRADI."""
        to_state = AgentState(to_state)
        ctx = self._full_ctx(ctx or {})
        table = TRANSITIONS.get(self._state, {})
        guard = table.get(to_state)
        if guard is None:
            return False, f"no transition {self._state.value} -> {to_state.value}"
        return guard(ctx)

    def transition(self, to_state: AgentState | str, ctx: Optional[dict] = None,
                   trigger: str = "") -> AgentState:
        """Guard'dan o'tkazib holatni o'zgartiradi. Rad etilsa — exception."""
        to_state = AgentState(to_state)
        ctx = self._full_ctx(ctx or {})
        ok, reason = self.can(to_state, ctx)
        self._log("transition", self._state, to_state, ok,
                  reason or trigger or "ok")
        if not ok:
            raise StateTransitionError(self._state, to_state, reason)
        # iteratsiya/retry hisoblagichlari (deterministik)
        if to_state == AgentState.EXECUTE and self._state == AgentState.VERIFY:
            self._retries += 1                      # repair pass
        if to_state == AgentState.CONTINUE:
            self._iteration += 1
        if to_state == AgentState.PLAN and self._state == AgentState.CONTINUE:
            pass  # yangi iteratsiya PLAN bilan boshlanadi
        self._state = to_state
        return self._state

    def reset_iteration(self) -> None:
        """Yangi iteratsiya boshlanishida retry hisoblagichini tozalaydi."""
        self._retries = 0

    # ---------------- history / observability ---------------- #

    def history(self) -> list[dict]:
        return list(self._history)

    def dump_history(self, path: str) -> str:
        """History'ni JSONL faylga yozadi (§16 state transition log)."""
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for rec in self._history:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return path

    # ---------------- ichki ---------------- #

    def _full_ctx(self, ctx: dict) -> dict:
        """Umumiy kontekst (iteration/max_iter/retries) — guard'larga uzatiladi."""
        full = {
            "iteration": self._iteration,
            "max_iter": self.max_iter,
            "retries": self._retries,
            "max_retries": self.max_retries,
        }
        full.update(ctx)
        return full

    def _log(self, kind: str, frm: Optional[AgentState], to: AgentState,
             ok: bool, note: str) -> None:
        self._history.append({
            "ts": round(time.time(), 3),
            "task_id": self.task_id,
            "kind": kind,
            "from": frm.value if frm is not None else None,
            "to": to.value,
            "ok": ok,
            "note": note[:200],
        })


# ------------------------------------------------------------------ #
# Yordamchi: plan tool validatsiyasi (§7/§17 — deterministik)
# ------------------------------------------------------------------ #

def validate_plan_tools(steps: list[dict], allowed_tools: list[str]) -> tuple[bool, str]:
    """Reja qadamlaridagi tool nomlari registry/MCP ro'yxatida bormi —
    PLAN -> EXECUTE guard'idan tashqaridan ham ishlatish uchun."""
    return g_plan_valid({"plan_steps": steps, "allowed_tools": allowed_tools})


# ------------------------------------------------------------------ #
# O'z-o'zini tekshiruv
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    sm = StateMachine(task_id="selftest")
    happy = {
        "input_validated": True,
        "requirements_ready": True,
        "plan_steps": [{"id": 1, "tools": ["read_file"]}],
        "allowed_tools": ["read_file"],
        "tool_result": {"ok": True},
        "observation_flags": ["confirmed"],
        "verify_status": "VERIFIED",
        "remaining_steps": 0,
    }
    for st in ["UNDERSTAND", "PLAN", "EXECUTE", "OBSERVE", "VERIFY",
               "UPDATE_STATE", "COMPLETE"]:
        sm.transition(st, happy, trigger="selftest")
    assert sm.state == AgentState.COMPLETE
    print("PASS | state machine happy path -> COMPLETE")

    # invalid: COMPLETE only after VERIFIED
    sm2 = StateMachine(task_id="selftest2")
    bad = dict(happy, verify_status="UNKNOWN")
    for st in ["UNDERSTAND", "PLAN", "EXECUTE", "OBSERVE", "VERIFY", "UPDATE_STATE"]:
        sm2.transition(st, bad)
    try:
        sm2.transition("COMPLETE", bad)
        raise SystemExit("FAIL | COMPLETE accepted without VERIFIED")
    except StateTransitionError:
        print("PASS | COMPLETE blocked without VERIFIED")

    # invalid: skipped state
    sm3 = StateMachine(task_id="selftest3")
    try:
        sm3.transition("EXECUTE", happy)
        raise SystemExit("FAIL | INPUT -> EXECUTE accepted")
    except StateTransitionError:
        print("PASS | INPUT -> EXECUTE blocked")

    print("OK | state_machine selftest")
