"""
igris.core.cost
-----------------
Cost estimation for a completed run. Deliberately conservative: local
providers (Ollama, LM Studio) are genuinely free, so they always report
0.0. OpenRouter is the only paid provider igris talks to, and its
per-model pricing varies and changes over time -- rather than hardcoding
a price table that will silently go stale, cost is computed only from
rates the user explicitly configured (openrouter.price_per_1k_*_tokens),
defaulting to 0.0 ("unknown/not configured") when they haven't. An
honest "$0.00 (unset)" is better than a fabricated number that looks
precise but is wrong.
"""
from __future__ import annotations


def estimate_cost_usd(provider: str, prompt_tokens: int, completion_tokens: int, config) -> float:
    if provider != "openrouter":
        return 0.0  # local providers are genuinely free

    prompt_rate = config.get("openrouter.price_per_1k_prompt_tokens", 0.0) or 0.0
    completion_rate = config.get("openrouter.price_per_1k_completion_tokens", 0.0) or 0.0

    cost = (prompt_tokens / 1000.0) * prompt_rate + (completion_tokens / 1000.0) * completion_rate
    return round(cost, 6)
