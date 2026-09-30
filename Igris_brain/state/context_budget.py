"""
CONTEXT BUDGET (§6) — token budget + prioritet qatlamlar + graceful degradation.

Muammo (Phase 3 audit §6): config'da max_context_tokens=4096 bor edi, lekin
HECH QAYERDA ishlatilmaydi — faqat char kesish bor; limit oshsa transport
xato yoki jim kesish (graceful degradation YO'Q).

Yechim — deterministik budget assembler:
  - Token estimatsiya: chars/4 (standart evristika, deterministik — §17)
  - Qatlam prioriteti (inclusion): goal_pin > base_system > req > memory > history
  - Drop tartibi (overflow'da): memory → history (eskilari) → req (truncate) →
    base (truncate, faqat ekstremal) — goal_pin va user HECH QACHON tashlanmaydi
  - Har qaror report'ga yoziladi (tracing, §16)

Foydalanish:
    budget = ContextBudget(max_tokens=4096)
    system, kept_history, report = budget.fit_prompt(
        base_system=..., req_block=..., goal_pin=...,
        memory_block=..., history=[...], user_message=...)
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4          # evristika: 1 token ~= 4 belgi
MIN_BLOCK_TOKENS = 50        # bundan kichik qoldiqqa blok qo'shilmaydi
DEFAULT_MAX_TOKENS = 4096
DEFAULT_RESERVE = 512        # javob uchun zaxira


def estimate_tokens(text: str) -> int:
    """Deterministik token estimatsiya (LLM'siz, §17)."""
    if not text:
        return 0
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _truncate_to_tokens(text: str, tokens: int) -> str:
    """Matnni taxminan `tokens` token sig'adigan bosh qismigacha kesish."""
    if tokens <= 0:
        return ""
    max_chars = tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


class ContextBudget:
    """Prompt qatlamlarini token budget ichida sig'diradi (deterministik).

    max_tokens      — model context oynasi (config'dagi max_context_tokens)
    reserve_response— javob uchun ajratilgan tokenlar
    """

    def __init__(self, max_tokens: int = DEFAULT_MAX_TOKENS,
                 reserve_response: int = DEFAULT_RESERVE):
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = DEFAULT_MAX_TOKENS
        try:
            reserve_response = int(reserve_response)
        except (TypeError, ValueError):
            reserve_response = DEFAULT_RESERVE
        self.max_tokens = max(max_tokens, 512)
        self.reserve_response = min(max(reserve_response, 0), self.max_tokens // 2)
        self.prompt_budget = max(256, self.max_tokens - self.reserve_response)

    # ------------------------------------------------------------------
    def fit_prompt(
        self,
        *,
        base_system: str = "",
        req_block: str = "",
        goal_pin: str = "",
        memory_block: str = "",
        history: list[dict] | None = None,
        user_message: str = "",
        max_history: int = 12,
    ) -> tuple[str, list[dict], dict]:
        """System prompt + history'ni budget bilan yig'adi.

        Qaytaradi: (system_text, kept_history, report)
        report: {budget, estimated, history_kept, history_total,
                 dropped: [..], truncated: [..]}
        """
        report: dict = {
            "budget": self.prompt_budget,
            "estimated": 0,
            "history_kept": 0,
            "history_total": 0,
            "dropped": [],
            "truncated": [],
        }

        # 1) HIMoyalangan qatlamlar: goal_pin + user + base_system
        #    (goal va user HECH QACHON tashlanmaydi).
        goal_tok = estimate_tokens(goal_pin)
        user_tok = estimate_tokens(user_message)
        base_tok = estimate_tokens(base_system)
        remaining = self.prompt_budget - goal_tok - user_tok

        base_final = base_system
        if remaining <= 0:
            # Ekstremal overflow: base ham sig'maydi — boshidan kesamiz.
            base_final = _truncate_to_tokens(base_system, max(0, self.prompt_budget - goal_tok - user_tok))
            if base_final != base_system:
                report["truncated"].append("base_system")
            remaining = 0
        else:
            remaining -= base_tok
            if remaining < 0:
                base_final = _truncate_to_tokens(base_system, base_tok + remaining)
                if base_final != base_system:
                    report["truncated"].append("base_system")
                remaining = 0

        # 2) req_block: sig'masa — boshidan kesish; juda kichik qoldiqda tashlash
        req_final = ""
        if req_block:
            req_tok = estimate_tokens(req_block)
            if req_tok <= remaining:
                req_final = req_block
                remaining -= req_tok
            elif remaining >= MIN_BLOCK_TOKENS:
                req_final = _truncate_to_tokens(req_block, remaining)
                report["truncated"].append("req_block")
                remaining = 0
            else:
                report["dropped"].append("req_block")

        # 3) memory_block: BIRINCHI tashlanadigan qatlam (ixtiyoriy kontekst)
        mem_final = ""
        if memory_block:
            mem_tok = estimate_tokens(memory_block)
            if mem_tok <= remaining:
                mem_final = memory_block
                remaining -= mem_tok
            elif remaining >= MIN_BLOCK_TOKENS:
                mem_final = _truncate_to_tokens(memory_block, remaining)
                report["truncated"].append("memory_block")
                remaining = 0
            else:
                report["dropped"].append("memory_block")

        # 4) Yig'ish (prompt tartibi saqlanadi: base + memory + req + goal)
        parts = [p for p in (base_final, mem_final, req_final, goal_pin) if p]
        system = "\n\n".join(parts)

        # 5) history: eng yangilardan boshlab sig'migacha (eskilari tashlanadi)
        hist = [h for h in (history or []) if h]
        report["history_total"] = len(hist)
        kept: list[dict] = []
        used = estimate_tokens(system) + user_tok
        for h in reversed(hist[-max_history:]):
            cost = estimate_tokens(str(h.get("content", "")))
            if used + cost > self.prompt_budget:
                continue  # bu xabar sig'madi — davom etamiz (kichikroq keyingi sig'ishi mumkin)
            used += cost
            kept.append(h)
        kept.reverse()
        report["history_kept"] = len(kept)
        if len(kept) < min(len(hist), max_history):
            report["dropped"].append(f"history({len(hist) - len(kept)})")

        report["estimated"] = used
        return system, kept, report
