"""
IGRIS BRAIN — LLM Output Schema (Roadmap v2 §14, band 10)
==========================================================
Alohida LLM output schema — Decision dan meros olmaydi,
mustaqil validate qilinadi.

Qaytish shakli:
  {"ok": bool, "errors": [str], "output": LLMOutput|None, "source": stage}

§7 tool contract'i ({ok, error, code}) bilan ruhandosh.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Intent(str, Enum):
    """LLM niyat tasnifi."""
    CODE = "code"
    DRAW = "draw"
    UI_BUILD = "ui_build"
    WEB = "web"
    RESEARCH = "research"
    CHAT = "chat"
    COMPOSITION = "composition"
    FILE_TASK = "file_task"
    UNKNOWN = "unknown"


@dataclass
class LLMOutput:
    """LLM chiqarishi uchun alohida schema.

    Decision dan farqli o'laroq, bu schema:
      - Intent aniqlaydi (qaysi oila/turga kiradi)
      - Reasoning (ni uchun shunday qaror)
      - Confidence (0.0-1.0)
      - Action (qaysi tool ishlatish kerak)
    """
    intent: Intent = Intent.UNKNOWN
    reasoning: str = ""
    confidence: float = 1.0
    action_name: Optional[str] = None
    action_args: Optional[dict] = field(default_factory=dict)
    raw_text: str = ""
    source: str = "llm"  # "llm" | "fallback" | "rule"

    def validate(self) -> list[str]:
        """Schema tekshiruvi — xatoliklar ro'yxatini qaytaradi."""
        errors = []
        if not isinstance(self.intent, Intent):
            try:
                self.intent = Intent(self.intent)
            except (ValueError, TypeError):
                errors.append(f"Invalid intent: {self.intent!r}")
                self.intent = Intent.UNKNOWN
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"Confidence out of range: {self.confidence}")
            self.confidence = max(0.0, min(1.0, self.confidence))
        if self.action_name and not isinstance(self.action_name, str):
            errors.append(f"action_name must be str, got {type(self.action_name)}")
        if self.action_args and not isinstance(self.action_args, dict):
            errors.append(f"action_args must be dict, got {type(self.action_args)}")
            self.action_args = {}
        return errors

    def to_dict(self) -> dict:
        """Serializatsiya — JSON serializable dict."""
        d = asdict(self)
        d["intent"] = self.intent.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "LLMOutput":
        """Deserializatsiya — dict'dan yaratish."""
        intent_raw = data.get("intent", "unknown")
        try:
            intent = Intent(intent_raw)
        except (ValueError, TypeError):
            intent = Intent.UNKNOWN
        return cls(
            intent=intent,
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 1.0)),
            action_name=data.get("action_name"),
            action_args=data.get("action_args") or {},
            raw_text=data.get("raw_text", ""),
            source=data.get("source", "llm"),
        )


def validate_llm_output(output: LLMOutput) -> dict:
    """LLMOutput ni to'liq tekshirish.

    Natija: {"ok": bool, "errors": [str], "output": LLMOutput}
    """
    errors = output.validate()
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "output": output,
    }


def parse_llm_output(raw: str) -> dict:
    """Raw LLM matnidan LLMOutput parse qilish.

    JSON parse → schema validate → tool-exists check.
    Natija: {"ok": bool, "errors": [str], "output": LLMOutput|None, "source": stage}
    """
    import json as _json

    # 1. JSON parse
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = _json.loads(text)
    except _json.JSONDecodeError as exc:
        return {"ok": False, "errors": [f"JSON parse: {exc}"], "output": None, "source": "parse"}

    # 2. Schema validate
    output = LLMOutput.from_dict(data)
    validation = validate_llm_output(output)
    if not validation["ok"]:
        return {"ok": False, "errors": validation["errors"], "output": output, "source": "schema"}

    return {"ok": True, "errors": [], "output": output, "source": "ok"}


__all__ = [
    "Intent", "LLMOutput",
    "validate_llm_output", "parse_llm_output",
]
