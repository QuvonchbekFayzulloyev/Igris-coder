"""
IGRIS BRAIN — Decision Model (Roadmap v2 B2, §14)
===================================================
LLM qarorining RASMIY, tipga ega ko'rinishi (§14 band 2, 4, 6).

v1 auditda plan JSON faqat {goal, steps, engine} edi; reasoning/confidence
B2'da ixtiyoriy qo'shildi (Phase 5). Bu modul ularni rasmiylashtiradi:

    Decision
      ├── intent      — nima uchun (chat|code|web|draw|...) — ixtiyoriy
      ├── decision    — qaror matni (task/goal bilan bir xil ma'noda)
      ├── reasoning   — nega bu reja (1-2 gap)
      ├── confidence  — 0..1 (fallback reja: 1.0 — deterministik)
      ├── steps[]     — PlanStep (id/title/tools/detail)
      └── engine      — "llm" | "fallback"

KONTRAKT: `Decision.from_plan()` hech qachon exception IRMAYDI —
noto'g'ri maydonlar jim tushiriladi yoki defaultga tushadi (§14 band 7
invalid-output handling planner'da allaqachon bor; bu yerda ikkinchi
himoya qatlami). `to_dict()` esa plan dict shaklini TO'LIQ saqlaydi —
mavjud executor/server kodi o'zgarmasdan ishlaydi (backward-compatible).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Ma'lum intent'lar (request_classifier.py oilalari bilan mos bo'lgan)
KNOWN_INTENTS = {
    "chat", "code", "web", "draw", "math", "weather", "creative",
    "structure", "research", "file", "task", "general",
}

_STEP_ID_RE = re.compile(r"^\d+$")


# ============================================================
# PlanStep — bitta reja qadami
# ============================================================

@dataclass
class PlanStep:
    """Reja qadami: id, title, tools, detail — §14 Action schema'ning
    plan-darajadagi ko'rinishi."""

    id: int
    title: str
    tools: list[str] = field(default_factory=list)
    detail: str = ""

    @classmethod
    def from_dict(cls, raw: Any, fallback_id: int = 1) -> "PlanStep":
        """Dict'dan yaratadi — xavfsiz (invalid maydonlar defaultga tushadi)."""
        if not isinstance(raw, dict):
            return cls(id=fallback_id, title=str(raw or "Step")[:200])
        try:
            step_id = int(raw.get("id", fallback_id))
        except (TypeError, ValueError):
            step_id = fallback_id
        title = str(raw.get("title", "Step")).strip()[:200] or "Step"
        tools_raw = raw.get("tools") or []
        tools = [str(t).strip() for t in tools_raw
                 if isinstance(t, (str, int)) and str(t).strip()][:8]
        detail = str(raw.get("detail", "")).strip()[:2000]
        return cls(id=step_id, title=title, tools=tools, detail=detail)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title,
                "tools": list(self.tools), "detail": self.detail}

    def validate(self) -> list[str]:
        """Xatolar ro'yxati (bo'sh = to'g'ri)."""
        errors: list[str] = []
        if not isinstance(self.id, int) or self.id < 1:
            errors.append(f"step.id invalid: {self.id!r}")
        if not self.title:
            errors.append("step.title bo'sh")
        for t in self.tools:
            if not re.match(r"^[a-zA-Z_][\w.\-]*$", t):
                errors.append(f"step.tools nom formati xato: {t!r}")
        return errors


# ============================================================
# Decision — rasmiy qaror modeli
# ============================================================

@dataclass
class Decision:
    """LLM (yoki fallback) qarorining to'liq, validatsiya qilingan ko'rinishi."""

    decision: str                      # qaror/task matni (majburiy)
    goal: str = ""                     # reja maqsadi (decision bilan bir xil bo'lishi mumkin)
    intent: str = ""                   # ixtiyoriy: chat|code|web|...
    reasoning: str = ""                # ixtiyoriy: nega bu reja
    confidence: float = 0.5            # 0..1
    steps: list[PlanStep] = field(default_factory=list)
    engine: str = "llm"                # "llm" | "fallback"
    source: str = "planner"            # qayerdan kelgan (tracing)

    # ---------- konstruktörler ----------

    @classmethod
    def from_plan(cls, plan: dict, task: str = "") -> "Decision":
        """Plan dict (planner._normalize chiqishi) → Decision.

        HECH QACHON EXCEPTION IRMAYDI. Invalid qiymatlar defaultga tushadi.
        """
        if not isinstance(plan, dict):
            plan = {}
        task = (task or plan.get("goal") or "").strip()
        decision_text = str(plan.get("decision") or plan.get("goal") or task)[:2000]

        # intent: valid bo'lsa olamiz, aks holda bo'sh (suhbatdagi classifier boshqacha)
        intent = str(plan.get("intent", "")).strip().lower()
        if intent not in KNOWN_INTENTS:
            intent = ""

        reasoning = str(plan.get("reasoning", "")).strip()[:500]

        try:
            confidence = float(plan.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        steps: list[PlanStep] = []
        raw_steps = plan.get("steps")
        if isinstance(raw_steps, list):
            for i, s in enumerate(raw_steps[:32], start=1):
                steps.append(PlanStep.from_dict(s, fallback_id=i))

        engine = str(plan.get("engine", "llm")).strip().lower()
        if engine not in ("llm", "fallback"):
            engine = "llm"

        return cls(
            decision=decision_text,
            goal=str(plan.get("goal", "")).strip()[:2000],
            intent=intent,
            reasoning=reasoning,
            confidence=round(confidence, 2),
            steps=steps,
            engine=engine,
            source=str(plan.get("source", "planner"))[:50],
        )

    # ---------- eksport ----------

    def to_dict(self) -> dict:
        """Plan dict shakliga qaytaradi (backward-compatible: goal/steps/engine
        mavjud kod bilan bir xil; yangi maydonlar faqat bo'lsa qo'shiladi)."""
        d: dict = {
            "goal": self.goal or self.decision,
            "steps": [s.to_dict() for s in self.steps],
            "engine": self.engine,
        }
        if self.reasoning:
            d["reasoning"] = self.reasoning
        d["confidence"] = self.confidence
        if self.intent:
            d["intent"] = self.intent
        if self.source != "planner":
            d["source"] = self.source
        d["decision"] = self.decision
        return d

    # ---------- validatsiya ----------

    def validate(self) -> list[str]:
        """To'liq validatsiya — xatolar ro'yxati (bo'sh = OK). §14 band 10."""
        errors: list[str] = []
        if not self.decision.strip():
            errors.append("decision matni bo'sh")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence oraliqdan tashqari: {self.confidence}")
        if self.engine not in ("llm", "fallback"):
            errors.append(f"engine noma'lum: {self.engine!r}")
        if self.intent and self.intent not in KNOWN_INTENTS:
            errors.append(f"intent noma'lum: {self.intent!r}")
        if self.engine == "llm" and not self.steps:
            # LLM rejasida bo'sh steps — fallback bo'lishi kerak edi
            errors.append("engine=llm lekin steps bo'sh")
        for s in self.steps:
            errors.extend(s.validate())
        # id'lar unique bo'lishi kerak
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            errors.append("step.id lar takrorlangan")
        return errors

    # ---------- statistika ----------

    @property
    def is_confident(self) -> bool:
        """Confidence >= 0.5 — yuqori ishonch (§14 threshold)."""
        return self.confidence >= 0.5

    def tool_names(self) -> list[str]:
        """Rejadagi barcha tool nomlari (unique, tartib saqlangan)."""
        seen: set[str] = set()
        out: list[str] = []
        for s in self.steps:
            for t in s.tools:
                if t not in seen:
                    seen.add(t)
                    out.append(t)
        return out

    def summary(self) -> str:
        """Ixcham inson-o'qiydigan xulosa (log/observability uchun)."""
        return (f"Decision(intent={self.intent or '-'}, conf={self.confidence}, "
                f"engine={self.engine}, steps={len(self.steps)})")


__all__ = ["Decision", "PlanStep", "KNOWN_INTENTS"]
