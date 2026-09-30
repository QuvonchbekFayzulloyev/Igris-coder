"""
IGRIS BRAIN — LLM OUTPUT VALIDATION LAYER (Roadmap v2 B2, §14 band 10)
=======================================================================
§14 band 10: "LLM output validation layer" — parse → schema → tool-exists
zanjirini BITTA modulda jamlagan fasad.

Bu yerda yangi mantiq YO'Q — mavjud deterministik tekshiruvlar (hech biri
LLM emas) bir joydan chaqiriladi:

  1. parse        → planner.PlanParser._extract_json (direct→fenced→balanced)
  2. schema       → decision.Decision.validate() (§14 maydonlar kontrakti)
  3. tool-exists  → state_machine.validate_plan_tools (PLAN→EXECUTE guard'i
                    bilan BIR XIL funksiya — double-source-of-truth yo'q)

Qaytish shakli barcha tekshiruvlar uchun bir xil:
  {"ok": bool, "errors": [str], "decision": Decision|None, "source": stage}
Bu §7 tool contract'i ({ok, error, code}) bilan ruhandosh — xato har doim
strukturada.
"""

from __future__ import annotations

import os
import sys

_brain = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain not in sys.path:
    sys.path.insert(0, _brain)

from typing import Optional

from planning.decision import Decision
from state.state_machine import validate_plan_tools

__all__ = ["ValidationResult", "validate_llm_output", "validate_plan_json"]


class ValidationResult(dict):
    """Result dict — .ok/.source/.errors qisqartmalari bilan."""

    @property
    def ok(self) -> bool:
        return bool(self.get("ok"))

    @property
    def source(self) -> str:
        return str(self.get("source", ""))

    @property
    def errors(self) -> list:
        return self.get("errors") or []

    @property
    def decision(self) -> Optional[Decision]:
        return self.get("decision")


def validate_llm_output(
    text: str,
    task: str = "",
    allowed_tools: Optional[list[str]] = None,
    check_tools: bool = True,
) -> ValidationResult:
    """LLM chiqishini to'liq zanjir bo'ylab tekshiradi.

    Bosqichlar:
      parse  — JSON ajratib olish (3 daraja: direct → fenced → balanced)
      schema — Decision.validate() (maydonlar, confidence, steps, id'lar)
      tools  — reja tool nomlari registry/MCP ro'yxatida bormi

    allowed_tools berilmasa tool bosqichi o'tkazib yuboriladi.
    """
    # 1) PARSE (TaskPlanner._extract_json — staticmethod, instansiyasiz)
    try:
        from planning.planner import TaskPlanner
        parsed = TaskPlanner._extract_json(text or "")
    except Exception:
        parsed = None

    if parsed is None:
        return ValidationResult({
            "ok": False, "errors": ["parse: JSON ajratib olinmadi"],
            "decision": None, "source": "parse",
        })

    # 2) SCHEMA
    decision = Decision.from_plan(parsed, task=task)
    errors = decision.validate()
    if errors:
        return ValidationResult({
            "ok": False, "errors": errors,
            "decision": decision, "source": "schema",
        })

    # 3) TOOL-EXISTS (SM PLAN→EXECUTE guard'i bilan bir xil funksiya)
    if check_tools and allowed_tools is not None:
        plan_steps = [s.to_dict() for s in decision.steps]
        _, msg = validate_plan_tools(plan_steps, sorted(set(allowed_tools)))
        if msg:
            return ValidationResult({
                "ok": False,
                "errors": [f"tools: {msg}"],
                "decision": decision, "source": "tools",
            })

    return ValidationResult({"ok": True, "errors": [], "decision": decision,
                             "source": "ok"})


def validate_plan_json(
    plan: dict,
    task: str = "",
    allowed_tools: Optional[list[str]] = None,
) -> ValidationResult:
    """Allaqachon parse qilingan plan dict uchun (schema + tools bosqichlari)."""
    decision = Decision.from_plan(plan, task=task)
    errors = decision.validate()
    if errors:
        return ValidationResult({"ok": False, "errors": errors,
                                 "decision": decision, "source": "schema"})
    if allowed_tools is not None:
        plan_steps = [s.to_dict() for s in decision.steps]
        _, msg = validate_plan_tools(plan_steps, sorted(set(allowed_tools)))
        if msg:
            return ValidationResult({"ok": False, "errors": [f"tools: {msg}"],
                                     "decision": decision, "source": "tools"})
    return ValidationResult({"ok": True, "errors": [], "decision": decision,
                             "source": "ok"})
