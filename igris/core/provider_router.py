"""
igris.core.provider_router
---------------------------
Decision architecture for "when to choose which" provider.

Principles:
  1. Static capability registry — defined once, never re-queried from AI.
  2. Cached health — rate_limited/down is remembered, not re-checked each time.
  3. Fallback chain — first healthy provider gets the task; on failure, next.
  4. Capability is re-checked ONLY when a provider is newly registered or
     its capabilities explicitly change — never on every query.

Flow:
  query → query_to_capability() → CAPABILITY_MAP → get_healthy_providers()
  → pick first → execute → if fail → mark unhealthy → pick next
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

# ---------------------------------------------------------------------------
# Static Capability Registry — defined once, never re-queried
# ---------------------------------------------------------------------------

PROVIDER_CAPABILITIES: dict[str, dict[str, Any]] = {
    "chatgpt": {
        "capabilities": {"image_gen", "coding", "reasoning", "research", "conversation"},
        "needs_login": True,
        "limits": {"free": {"image_gen": 2, "messages": 50}},
        "priority": 1,
        "description": "OpenAI ChatGPT — image gen (DALL-E), coding, reasoning",
    },
    "claude": {
        "capabilities": {"coding", "reasoning", "research", "long_context", "conversation"},
        "needs_login": True,
        "limits": {"free": {"messages": 20}},
        "priority": 2,
        "description": "Anthropic Claude — reasoning, coding, long context",
    },
    "kimi": {
        "capabilities": {"image_gen", "reasoning", "research", "long_context", "conversation"},
        "needs_login": True,
        "limits": {"free": {"image_gen": 5, "messages": 50}},
        "priority": 3,
        "description": "Kimi (Moonshot) — image gen, long context, reasoning",
    },
    "perplexity": {
        "capabilities": {"research", "sources", "conversation"},
        "needs_login": False,
        "limits": {"free": {"searches": 5}},
        "priority": 1,
        "description": "Perplexity — web-grounded research with sources",
    },
    "deepseek": {
        "capabilities": {"coding", "reasoning", "research", "conversation"},
        "needs_login": False,
        "limits": {"free": {"messages": 50}},
        "priority": 2,
        "description": "DeepSeek — coding, reasoning, free tier available",
    },
    "gemini": {
        "capabilities": {"image_gen", "reasoning", "research", "long_context", "conversation"},
        "needs_login": True,
        "limits": {"free": {"image_gen": 10, "messages": 60}},
        "priority": 4,
        "description": "Google Gemini — image gen, long context, research",
    },
    "grok": {
        "capabilities": {"research", "sources", "conversation"},
        "needs_login": True,
        "limits": {"free": {"messages": 15}},
        "priority": 3,
        "description": "xAI Grok — research with X/Twitter sources",
    },
}

# Query intent → capability label (cheap regex, no AI)
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "image_gen": [r"\b(image|picture|photo|rasm\w*|surat|dalle|draw|illustrat|rasm yarat|rasm kerak|tasvir)\b"],
    "coding":    [r"\b(code|implement|function|script|debug|fix|refactor|build|create|write|yoz|tuzat|yangi|dastur)\b"],
    "research":  [r"\b(architecture|design|system|platform|microservice|pipeline|diagram|arxitektura|tizim|what is|what are|who is|tell me about)\b"],
    "reasoning": [r"\b(explain|analyze|compare|why|reason|think|logic|argument|nima|kim|qanday|haqida|farq|sabab)\b"],
    "sources":   [r"\b(source|citation|reference|according to|research|find|news|recent|manba|iqtibos|sayt)\b"],
}

CAPABILITY_PROVIDERS: dict[str, list[str]] = {
    "image_gen":    ["chatgpt", "kimi", "gemini"],
    "coding":       ["chatgpt", "claude", "deepseek"],
    "reasoning":    ["claude", "chatgpt", "kimi"],
    "research":     ["perplexity", "deepseek", "grok", "chatgpt"],
    "sources":      ["perplexity", "grok"],
    "long_context": ["kimi", "claude", "gemini"],
    "conversation": ["chatgpt", "claude", "kimi", "perplexity", "deepseek", "gemini", "grok"],
}

# ---------------------------------------------------------------------------
# Cached health — remembers rate_limited/down per provider
# ---------------------------------------------------------------------------

_ProviderHealth = dict[str, dict[str, Any]]  # provider -> {status, reason, since}

_health: _ProviderHealth = {}


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Decision API
# ---------------------------------------------------------------------------


def query_to_capability(query: str) -> str:
    """Map user query to a capability label — cheap regex, no AI call."""
    q = query.lower()
    for cap, patterns in CAPABILITY_KEYWORDS.items():
        for p in patterns:
            if re.search(p, q):
                return cap
    return "research"


def get_healthy_providers(capability: str) -> list[str]:
    """Return providers supporting a capability, skipping unhealthy ones.

    Only checks cached health — never asks the AI.
    """
    providers = CAPABILITY_PROVIDERS.get(capability, [])
    return [p for p in providers if _get_health(p) == "available"]


def select(capability: str, prefer_no_login: bool = False) -> str | None:
    """Pick the best healthy provider for a capability.

    Returns provider name or None if all are unhealthy.
    Falls back through the chain automatically.
    """
    healthy = get_healthy_providers(capability)
    if prefer_no_login:
        no_login = [p for p in healthy if not PROVIDER_CAPABILITIES.get(p, {}).get("needs_login", True)]
        if no_login:
            return no_login[0]
    return healthy[0] if healthy else None


def select_multi(capability: str, count: int = 2, prefer_no_login: bool = False) -> list[str]:
    """Pick multiple healthy providers for parallel querying.

    Returns up to `count` providers. Fewer if not enough healthy ones.
    """
    healthy = get_healthy_providers(capability)
    if prefer_no_login:
        healthy.sort(key=lambda p: PROVIDER_CAPABILITIES.get(p, {}).get("needs_login", True))
    return healthy[:count]


def get_decision_path(query: str, prefer_no_login: bool = False) -> dict:
    """Full decision trace: query → capability → candidates → winner.

    Useful for debugging and logging the "when to choose which" logic.
    """
    cap = query_to_capability(query)
    candidates = CAPABILITY_PROVIDERS.get(cap, [])
    healthy = get_healthy_providers(cap)
    winner = select(cap, prefer_no_login)
    return {
        "query": query[:100],
        "capability": cap,
        "all_candidates": candidates,
        "health": {p: _get_health(p) for p in candidates},
        "healthy": healthy,
        "winner": winner,
        "fallback_chain": healthy[1:] if winner else [],
        "no_login_options": [p for p in candidates if not PROVIDER_CAPABILITIES.get(p, {}).get("needs_login", True)],
        "decision": f"capability={cap} → winner={winner}" if winner else f"capability={cap} → NO HEALTHY PROVIDER",
    }


def _get_health(provider: str) -> str:
    entry = _health.get(provider)
    if entry is None:
        return "available"
    return entry["status"]


def mark_failure(provider: str, reason: str = "rate_limited") -> None:
    """Mark provider as temporarily unavailable.

    Called when we detect rate_limited, down, or consecutive errors
    during a real interaction. Provider stays unhealthy until:
      - clear_health() is called
      - a successful interaction occurs (mark_success)
    """
    _health[provider] = {"status": reason, "reason": reason, "since": _now()}


def mark_success(provider: str) -> None:
    """Mark provider as healthy again after a successful interaction."""
    _health.pop(provider, None)


def clear_health(provider: str | None = None) -> None:
    """Reset health for one or all providers."""
    if provider:
        _health.pop(provider, None)
    else:
        _health.clear()


def get_health_summary() -> dict:
    """Return health status of all providers."""
    return {
        p: _get_health(p)
        for p in PROVIDER_CAPABILITIES
    }


def get_capabilities(provider: str | None = None) -> dict:
    """Return capability registry.

    If provider is specified, return only that provider's capabilities.
    """
    if provider:
        info = PROVIDER_CAPABILITIES.get(provider)
        if not info:
            return {"error": f"Unknown provider: {provider}"}
        return {
            "capabilities": list(info["capabilities"]),
            "health": _get_health(provider),
            "needs_login": info.get("needs_login", True),
            "priority": info.get("priority", 99),
            "limits": info.get("limits", {}),
        }
    return {
        name: {
            "capabilities": list(info["capabilities"]),
            "health": _get_health(name),
            "needs_login": info.get("needs_login", True),
            "priority": info.get("priority", 99),
        }
        for name, info in PROVIDER_CAPABILITIES.items()
    }


def is_capability_recheck_needed(provider: str) -> bool:
    """Should we re-check this provider's capabilities?

    Returns True only if the provider is not in the registry — meaning
    it was newly added and capabilities need to be discovered.
    Once in the registry, capabilities are never re-checked.
    """
    return provider not in PROVIDER_CAPABILITIES


# ---------------------------------------------------------------------------
# Decision trace (human-readable)
# ---------------------------------------------------------------------------


def format_decision(query: str) -> str:
    """Return a human-readable decision trace for a query."""
    trace = get_decision_path(query)
    lines = [
        f"Query: {trace['query']}",
        f"Capability: {trace['capability']}",
        f"Candidates: {', '.join(trace['all_candidates'])}",
    ]
    for p, status in trace["health"].items():
        lines.append(f"  {p}: {status}")
    lines.append(f"Winner: {trace['winner'] or 'NONE (all unhealthy)'}")
    if trace.get("fallback_chain"):
        lines.append(f"Fallback chain: {', '.join(trace['fallback_chain'])}")
    return "\n".join(lines)
