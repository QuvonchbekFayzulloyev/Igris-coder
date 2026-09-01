"""
IGRIS BRAIN — 2.2 Logical-Mathematical Intelligence — core/logic
================================================================
Pattern, formal reasoning, kod mantig'i.

Implementatsiya yo'nalishi (qo'llanma 2.2): chain-of-thought + tool-use
(kalkulyator, kod ijrochisi) orqali kuchaytiriladi — model o'zining "ichki"
reasoning'iga to'liq tayanmaydi. Mavjud `senior-software-engineer` va
`architecture-expert` skill qatlami bilan bog'lanadi.

Bu modul:
  - reja/CoT yo'naltirishlarini beradi (system prompt uchun)
  - strukturani tekshiradi (kod, JSON) — mantiqiy xatolarni aniqlash
  - oddiy arifmetik tekshiruv (tool-use o'rnini bosuvchi yordamchi)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StructureCheck:
    """Struktura tekshiruvi natijasi (kod/JSON mantiqiyligi)."""

    ok: bool
    kind: str = ""                     # json | python_block | plain
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "kind": self.kind, "errors": list(self.errors)}


def extract_balanced_json(text: str) -> Optional[str]:
    """Matn ichidagi birinchi muvozanatli va to'g'ri {...} / [...] blokini topadi.

    Model JSON'ni matn ichiga o'rab yozsa ("Natija: { ... }" kabi) —
    to'g'ri blokni ajratib olishga urinamiz. Qaytaradi: yaroqli JSON satri
    yoki None.
    """
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    block = text[start:i + 1]
                    try:
                        json.loads(block)
                        return block
                    except (ValueError, TypeError):
                        break
    return None


# CoT yo'naltirish — modelga "ichki reasoning"ni tashqi tekshiruv bilan
# mustahkamlashni buyuradi (qo'llanma 2.2)
COT_DIRECTIVE = (
    "For logic/code tasks: think step by step, then verify your solution "
    "before answering. Use tools (python_exec / run_command) to check "
    "complex calculations instead of relying only on mental math."
)


class LogicLayer:
    """2.2 Mantiqiy-matematik qatlam.

    Usullar:
      - reasoning_directive() -> CoT system prompt qo'shimchasi
      - check_structure(output) -> JSON/kod struktura mantiqiyligi
      - safe_math(expr) -> oddiy arifmetikani xavfsiz hisoblash
    """

    def __init__(self):
        self._checks: int = 0

    # ------------------------------------------------------------ #

    def reasoning_directive(self) -> str:
        return COT_DIRECTIVE

    def check_structure(self, output: Optional[str]) -> StructureCheck:
        """Chiqish strukturasi mantiqiy to'g'rimi?

        - JSON bo'lsa: parse qilishga urinadi
        - python fenced block bo'lsa: ochilish/yopilish muvozanatini tekshiradi
        - oddiy matn: ok (struktura talab qilinmagan)
        """
        self._checks += 1
        text = (output or "").strip()
        if not text:
            return StructureCheck(ok=False, kind="plain", errors=["empty output"])

        # JSON?
        if text.startswith("{") or text.startswith("["):
            try:
                json.loads(text)
                return StructureCheck(ok=True, kind="json")
            except json.JSONDecodeError as exc:
                return StructureCheck(ok=False, kind="json",
                                      errors=[f"invalid JSON: {exc.msg}"])

        # JSON matn ichiga o'ralgan bo'lishi mumkin ("Natija: { ... }") —
        # to'g'ri blokni ajratib olishga urinamiz (mantiqiy tekshiruv chuqurroq).
        if "{" in text or "[" in text:
            block = extract_balanced_json(text)
            if block:
                try:
                    json.loads(block)
                    return StructureCheck(ok=True, kind="json")
                except json.JSONDecodeError as exc:
                    return StructureCheck(ok=False, kind="json",
                                          errors=[f"invalid JSON: {exc.msg}"])

        # python fenced block?
        fence = re.search(r"```(?:python|py)?\n(.*?)```", text, re.DOTALL)
        if fence:
            body = fence.group(1)
            if body.count("```") > 0 or not body.strip():
                return StructureCheck(ok=False, kind="python_block",
                                      errors=["malformed fenced block"])
            return StructureCheck(ok=True, kind="python_block")

        return StructureCheck(ok=True, kind="plain")

    def safe_math(self, expr: str) -> Optional[float]:
        """Oddiy arifmetik ifodani xavfsiz hisoblaydi (eval EMAS).

        Faqat raqamlar va + - * / ( ) . ishtirok etgan ifodalar.
        Murakkab ifodalar uchun python_exec tool ishlatilishi kerak.
        """
        if not expr or not re.fullmatch(r"[\d\s+\-*/().]+", expr):
            return None
        try:
            # Eval xavfi: whitelist — faqat sonli tokenlar qolganini
            # tekshiramiz (funksiya chaqiruvlari yo'q).
            if re.search(r"[A-Za-z_]", expr):
                return None
            return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307
        except (ZeroDivisionError, SyntaxError, ValueError, TypeError):
            return None

    # ------------------------------------------------------------ #

    def stats(self) -> dict:
        return {"structure_checks": self._checks}
