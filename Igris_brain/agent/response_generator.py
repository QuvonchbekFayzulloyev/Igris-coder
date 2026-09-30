"""
IGRIS BRAIN — ResponseGenerator (Roadmap §13)
=============================================
Javob generatsiya qilish moduli — verified results + progress + questions
formatida foydalanuvchiga tushunarli javob yaratadi.

Voice policy:
  - voice=true  → qisqa, ixcham javoblar (≤50 so'z)
  - voice=false → to'liq format (batafsil)

Fasad: IgrisAgent._ask_final_summary() o'rniga ishlatiladi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------ #
# Voice Policy
# ------------------------------------------------------------------ #

VOICE_MAX_WORDS = 50


@dataclass
class VoicePolicy:
    """Voice mode siyosati — qisqa yoki to'liq javob."""
    voice_mode: bool = False  # True = qisqa, False = to'liq
    max_words: int = VOICE_MAX_WORDS

    def apply(self, text: str) -> str:
        """Voice mode bo'lsa matnni qisqartiradi."""
        if not self.voice_mode:
            return text
        words = text.split()
        if len(words) <= self.max_words:
            return text
        short = " ".join(words[:self.max_words])
        if not short.endswith((".", "!", "?")):
            short += "..."
        return short


# ------------------------------------------------------------------ #
# Response Formats
# ------------------------------------------------------------------ #

def format_progress(step: int, total: int, title: str = "") -> str:
    """Step N of M formatida progress javobi."""
    header = f"Step {step} of {total}"
    if title:
        header += f": {title}"
    return header


def format_completion(result: dict, matrix: Optional[dict] = None) -> str:
    """To'liq bajarilish javobi — natija + requirement matrix."""
    parts = []
    status = result.get("status", "completed")
    if status == "completed":
        parts.append("Task completed successfully.")
    elif status == "partial":
        parts.append("Task partially completed.")
    else:
        parts.append(f"Task finished with status: {status}")

    # Tool calls summary
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        parts.append(f"Executed {len(tool_calls)} step(s).")

    # Requirement matrix
    if matrix:
        passed = sum(1 for v in matrix.values() if v.get("pass", False))
        total = len(matrix)
        if total > 0:
            parts.append(f"Requirements: {passed}/{total} passed.")

    # Errors
    errors = result.get("errors", [])
    if errors:
        parts.append(f"Encountered {len(errors)} error(s).")

    return " ".join(parts)


def format_failure(error: str, recovery: Optional[str] = None) -> str:
    """Xato javobi — xato + qayta urinish."""
    parts = [f"Task failed: {error}"]
    if recovery:
        parts.append(f"Recovery: {recovery}")
    return " ".join(parts)


def format_step_result(step_idx: int, total: int, step_result: dict) -> str:
    """Bir qadam natijasi."""
    title = step_result.get("title", "")
    ok = step_result.get("ok", False)
    status = "done" if ok else "failed"
    return format_progress(step_idx + 1, total, title) + f" [{status}]"


# ------------------------------------------------------------------ #
# ResponseGenerator
# ------------------------------------------------------------------ #

class ResponseGenerator:
    """Javob generatsiya qilish — verified results + voice policy.

    IgrisAgent ichida ishlatiladi:
        rg = ResponseGenerator(voice_mode=args.voice)
        response = rg.generate(task, result, progress)
    """

    def __init__(self, voice_mode: bool = False):
        self.voice_policy = VoicePolicy(voice_mode=voice_mode)
        self._history: list[dict] = []

    def generate(
        self,
        task: str,
        result: dict,
        progress: Optional[list[dict]] = None,
        matrix: Optional[dict] = None,
    ) -> str:
        """Asosiy javob generatsiyasi — task + result + progress."""
        parts = []

        # 1. Progress
        if progress:
            for i, step in enumerate(progress):
                parts.append(format_step_result(i, len(progress), step))

        # 2. Completion
        parts.append(format_completion(result, matrix))

        # 3. Failure recovery
        if result.get("status") == "failed":
            error = result.get("error", "Unknown error")
            recovery = result.get("recovery")
            parts.append(format_failure(error, recovery))

        text = "\n".join(parts)
        text = self.voice_policy.apply(text)

        # History
        self._history.append({
            "task": task,
            "result_status": result.get("status"),
            "text": text,
        })

        return text

    def generate_summary(self, result: dict) -> str:
        """Qisqa oxirgi javob — agent chat uchun."""
        status = result.get("status", "completed")
        if status == "completed":
            text = "Done! "
        elif status == "partial":
            text = "Partially done. "
        else:
            text = f"Finished ({status}). "

        # Tool calls
        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            last = tool_calls[-1]
            output = last.get("output", {})
            if output.get("ok") and output.get("output"):
                text += str(output["output"])[:200]
            else:
                text += f"{len(tool_calls)} step(s) executed."

        return self.voice_policy.apply(text)

    @property
    def history(self) -> list[dict]:
        return list(self._history)


__all__ = [
    "VoicePolicy", "ResponseGenerator",
    "format_progress", "format_completion", "format_failure",
    "format_step_result",
]
