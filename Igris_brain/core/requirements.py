"""
IGRIS BRAIN — RequirementExtractor (semantik talab tushunish)
=============================================================
User xabaridan struktur talab modelini chiqaradi — LLM orqali (semantik,
CAG-keshlangan) yoki LLM yo'q/offline bo'lsa deterministik fallback orqali.

Bu qatlam Igris javobini "qotib qolgan pattern"dan (kalit-so'z router +
canned matnlar) real moslashuvchanlikka o'tkazish uchun ASOS:
task o'zgarsa talab modeli ham o'zgaradi va javob shakllanishi (til,
chuqurlik, format, natija shakli, cheklovlar) shunga moslanadi.

Talab modeli (Requirement):
  intent           : ochiq to'plam ('answer','code','file','draw',
                     'summarize','research','compose_ui','execute',...)
  language         : 'uz' | 'en' | ... (aniqlangan til)
  output_format    : text | code | file | list | table | steps | image | html
  verbosity        : concise | balanced | detailed
  constraints      : [str, ...] — aniq cheklovlar (format, muddat, bosqichlar...)
  deliverable_name : Optional[str] — foydalanuvchi nomlagan fayl
  domain           : str (erkin)
  needs_tools      : bool — fayl/web/ijro tool'lar haqiqatan kerakmi
  confidence       : 0..1
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Requirement:
    """User talabining struktur modeli — javob shakllanishini boshqaradi."""

    intent: str = "answer"
    language: str = ""
    output_format: str = "text"
    verbosity: str = "balanced"
    constraints: list = field(default_factory=list)
    deliverable_name: Optional[str] = None
    domain: str = ""
    needs_tools: bool = False
    confidence: float = 0.0

    @classmethod
    def from_json(cls, obj: dict) -> "Requirement":
        return cls(
            intent=str(obj.get("intent") or "answer").strip(),
            language=str(obj.get("language") or "").strip(),
            output_format=str(obj.get("output_format") or "text").strip(),
            verbosity=str(obj.get("verbosity") or "balanced").strip(),
            constraints=[str(c).strip() for c in (obj.get("constraints") or []) if str(c).strip()][:8],
            deliverable_name=(
                str(obj["deliverable_name"]).strip()
                if obj.get("deliverable_name") else None
            ),
            domain=str(obj.get("domain") or "").strip(),
            needs_tools=bool(obj.get("needs_tools", False)),
            confidence=min(1.0, max(0.0, float(obj.get("confidence") or 0.0))),
        )

    def to_block(self) -> str:
        """System prompt'ga qo'shiladigan ixcham talab bloki (model bajaradi)."""
        lines = ["USER REQUIREMENTS (follow exactly):"]
        lines.append(f"- intent: {self.intent}")
        lines.append(f"- output format: {self.output_format}")
        lines.append(f"- verbosity: {self.verbosity}")
        if self.language:
            lines.append(f"- language: {self.language}")
        if self.domain:
            lines.append(f"- domain: {self.domain}")
        if self.deliverable_name:
            lines.append(f"- deliverable file: {self.deliverable_name}")
        if self.constraints:
            lines.append("- constraints: " + "; ".join(self.constraints))
        if self.needs_tools:
            lines.append("- this task requires tools (file/web/execution)")
        return "\n".join(lines)


EXTRACT_SYSTEM = """You are an intent/requirement extractor for a local AI agent.
Read the user's latest message (and any conversation history) and extract a
structured task requirement. Respond with ONLY valid JSON:
{"intent": "...", "language": "uz|en|...", "output_format": "text|code|file|list|table|steps|image|html",
 "verbosity": "concise|balanced|detailed", "constraints": ["..."], "deliverable_name": null,
 "domain": "...", "needs_tools": true|false, "confidence": 0.0-1.0}

Rules:
- intent is an OPEN set: answer, code, file, draw, summarize, research, compose_ui,
  execute, explain, translate, fix, compare, list_items, ...
- needs_tools=true ONLY when the task actually requires file/web/execution tools.
- deliverable_name: ONLY if the user explicitly names a file (e.g. "app.py", "hisobot.md").
- constraints: capture explicit constraints (format, deadline, step count, restrictions, tone).
- language: 'uz' for Uzbek (o'zbekcha), 'en' for English, else the detected code.
- output_format 'text' unless the user clearly asks for code/list/table/steps/file/image/html.
- verbosity from explicit words: "qisqa/concise/brief" -> concise, "batafsil/detailed/ilova" -> detailed.
- If anything is unclear use defaults (intent=answer, output_format=text, verbosity=balanced,
  needs_tools=false, confidence=0.5)."""


# ---- Deterministik yordamchilar (LLM yo'q/offline fallback uchun) ----

_UZ_CHARS = re.compile(r"[ʻ’‘`]?[oO]ʻ|[gG]ʻ|ў|қ|ғ|ҳ|ж|нг", re.IGNORECASE)
_UZ_WORDS = re.compile(
    r"\b(boʻl|uchun|bilan|kerak|yoz|yarat|ber|qil|qaysi|qanday|nimadur|"
    r"hisobot|ilova|dastur|fayl|natija|javob|savol|oʻzbek)\b", re.IGNORECASE)
_EN_WORDS = re.compile(
    r"\b(the|and|write|create|file|code|function|explain|what|how|"
    r"please|report|summarize|list|table|steps)\b", re.IGNORECASE)
_FILE_NAME_RE = re.compile(r"[\w\-]+\.(py|ts|js|tsx|jsx|md|txt|html|css|json|go|rs|cpp|c|java)")
_CODE_WORDS = ("kod", "code", "dastur", "script", "function", "class", "python",
               "javascript", "html", "css", "sql", "api", "function", "fix", "tuzat")
_DRAW_WORDS = ("rasm", "chiz", "draw", "image", "picture", "svg", "icon", "logo", "grafika")
_WEB_WORDS = ("http", "url", "sayt", "site", "web", "brauzer", "browser", "internet", "yangilik")
_FILE_WORDS = ("fayl", "file", "write", "yarat", "create", "saqla", "save")
_SUM_WORDS = ("xulosa", "summarize", "qisqacha bayon", "umumlashtir")
_STEP_WORDS = ("bosqichma-bosqich", "step by step", "bosqichlari", "qadamlari", "qadamlar")
_LIST_WORDS = ("roʻyxat", "ro'yxat", "list", "ro'yhat")
_TABLE_WORDS = ("jadval", "table")
_DETAIL_WORDS = ("batafsil", "detailed", "ilova", "toʻliq", "to'liq", "chuqur", "in-depth")
_CONCISE_WORDS = ("qisqa", "concise", "brief", "tez", "kalta")
_MATH_RE = re.compile(r"^\s*[\d\s+\-*/().^%]+\s*$")


class RequirementExtractor:
    """LLM orqali semantik, aks holda deterministik talab chiqaruvchi."""

    def __init__(self, llm=None, cache=None):
        self.llm = llm
        self.cache = cache  # CagCache — kalit "req:<message>"

    # ------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------ #

    def extract_fast(self, message: str) -> Requirement:
        """Deterministik TEZ talab (LLM YO'Q) — draw kabi oddiy so'rovlar uchun.

        Chizish/tezkor yo'llarda LLM extractor keraksiz kechikish beradi va
        kuchsiz model noto'g'ri chiqarishi mumkin — to'g'ridan-to'g'ri qoida.
        """
        return self._deterministic(message)

    def extract(self, message: str, history: Optional[list] = None) -> Requirement:
        """Talab modelini chiqaradi. Hech qachon exception bermaydi.

        LLM bor bo'lsa — CAG keshlangan semantik ekstraksiya; yo'q/offline
        bo'lsa — deterministik fallback (eski kalit-so'z mantiqidan xavfsiz).
        """
        req = self._deterministic(message)
        if self.llm is None:
            return req
        try:
            cached = None
            if self.cache is not None:
                cached = self.cache.get("req", message)
            if cached is not None:
                parsed = self._parse(cached)
                if parsed is not None:
                    return parsed
            prompt = self._build_prompt(message, history)
            text = self.llm.complete(system=EXTRACT_SYSTEM, prompt=prompt)
            if not text:
                return req
            parsed = self._parse(text)
            if parsed is None:
                return req
            if self.cache is not None:
                self.cache.put("req", message, text)
            return parsed
        except Exception:
            return req

    # ------------------------------------------------------------ #
    # LLM path helpers
    # ------------------------------------------------------------ #

    def _build_prompt(self, message: str, history: Optional[list]) -> str:
        ctx = ""
        if history:
            last = []
            for h in (history or [])[-6:]:
                r = h.get("role")
                c = str(h.get("content") or "")
                if r in ("user", "assistant") and c:
                    last.append(f"{r}: {c[:400]}")
            if last:
                ctx = "\nConversation history (for context only):\n" + "\n".join(last) + "\n\n"
        return f"{ctx}User message: {message}"

    def _parse(self, text: str) -> Optional[Requirement]:
        try:
            obj = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            obj = None
        if obj is None:
            from core.intelligence.logic import extract_balanced_json
            raw = extract_balanced_json(text)
            if not raw:
                return None
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        if not isinstance(obj, dict):
            return None
        try:
            return Requirement.from_json(obj)
        except Exception:
            return None

    # ------------------------------------------------------------ #
    # Deterministic fallback (LLM yo'q / offline / xatolik)
    # ------------------------------------------------------------ #

    def _deterministic(self, message: str) -> Requirement:
        low = (message or "").lower()
        req = Requirement(confidence=0.4)

        # Til
        if _UZ_CHARS.search(message) or _UZ_WORDS.search(low):
            req.language = "uz"
        elif _EN_WORDS.search(low) or re.search(r"[a-zA-Z]{4,}", low):
            req.language = "en"

        # Intent (kalit-so'z, lekin FAKAT fallback sifatida ishlatiladi)
        if _MATH_RE.fullmatch(low):
            req.intent, req.output_format, req.needs_tools = "math", "text", False
        elif any(w in low for w in ("havo", "weather", "ob-havo", "harorat")):
            req.intent, req.output_format, req.needs_tools = "weather", "text", False
        elif any(w in low for w in _DRAW_WORDS):
            req.intent, req.output_format, req.needs_tools = "draw", "image", True
        elif any(w in low for w in _WEB_WORDS) or "://" in low:
            req.intent, req.output_format, req.needs_tools = "web", "text", True
        elif any(w in low for w in _SUM_WORDS):
            req.intent, req.output_format, req.needs_tools = "summarize", "text", False
        elif any(w in low for w in _CODE_WORDS) or any(
                w in low for w in ("backend", "frontend", "yoz", "qur", "dastur")):
            req.intent, req.output_format, req.needs_tools = "code", "code", True
        elif any(w in low for w in _FILE_WORDS):
            req.intent, req.output_format, req.needs_tools = "file", "file", True
        elif "uy" in low or "ilova" in low or "app" in low:
            req.intent, req.needs_tools = "compose_ui", True

        # Format (an'anaviy routerdan ko'ra xushmuomala — so'zlar bilan aytilgani)
        if any(w in low for w in _TABLE_WORDS):
            req.output_format = "table"
        elif any(w in low for w in _LIST_WORDS):
            req.output_format = "list"
        elif any(w in low for w in _STEP_WORDS):
            req.output_format = "steps"

        # Chuqurlik
        if any(w in low for w in _DETAIL_WORDS):
            req.verbosity = "detailed"
        elif any(w in low for w in _CONCISE_WORDS):
            req.verbosity = "concise"

        # Fayl nomi
        m = _FILE_NAME_RE.search(message)
        if m:
            req.deliverable_name = m.group(0)

        return req


__all__ = ["Requirement", "RequirementExtractor"]