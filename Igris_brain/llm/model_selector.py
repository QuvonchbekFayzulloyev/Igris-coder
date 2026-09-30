"""
IGRIS BRAIN — Model Selector
==============================
Task turiga qarab model tanlash.
OmniRoute orqali barcha modellarga kirish.

Usage:
  from llm.model_selector import ModelSelector
  selector = ModelSelector()
  model = selector.select("code_generation")
  print(model.model_id)  # "openai/gpt-4o"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------ #
# Model Profile
# ------------------------------------------------------------------ #

@dataclass
class ModelProfile:
    """Model profili — task turi uchun optimal model."""
    name: str
    provider: str  # "openai" | "anthropic" | "google" | "ollama" | "deepseek"
    model_id: str  # OmniRoute format: "openai/gpt-4o"
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_tokens: int = 128000
    strengths: list[str] = field(default_factory=list)

    @property
    def is_free(self) -> bool:
        return self.cost_per_1k_input == 0 and self.cost_per_1k_output == 0

    @property
    def is_local(self) -> bool:
        return self.provider == "ollama"


# ------------------------------------------------------------------ #
# Predefined Profiles
# ------------------------------------------------------------------ #

PROFILES: dict[str, ModelProfile] = {
    # OpenAI
    "gpt-4o": ModelProfile(
        name="GPT-4o",
        provider="openai",
        model_id="openai/gpt-4o",
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
        max_tokens=128000,
        strengths=["code", "reasoning", "creative"],
    ),
    "gpt-4o-mini": ModelProfile(
        name="GPT-4o Mini",
        provider="openai",
        model_id="openai/gpt-4o-mini",
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        max_tokens=128000,
        strengths=["fast", "code", "simple"],
    ),
    "o3-mini": ModelProfile(
        name="o3-mini",
        provider="openai",
        model_id="openai/o3-mini",
        cost_per_1k_input=0.0011,
        cost_per_1k_output=0.0044,
        max_tokens=128000,
        strengths=["reasoning", "code", "math"],
    ),

    # Anthropic
    "claude-3-5-sonnet": ModelProfile(
        name="Claude 3.5 Sonnet",
        provider="anthropic",
        model_id="anthropic/claude-3-5-sonnet-20241022",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        max_tokens=200000,
        strengths=["code", "reasoning", "long_context"],
    ),
    "claude-3-opus": ModelProfile(
        name="Claude 3 Opus",
        provider="anthropic",
        model_id="anthropic/claude-3-opus-20240229",
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        max_tokens=200000,
        strengths=["complex_reasoning", "code", "creative"],
    ),
    "claude-3-haiku": ModelProfile(
        name="Claude 3 Haiku",
        provider="anthropic",
        model_id="anthropic/claude-3-haiku-20240307",
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        max_tokens=200000,
        strengths=["fast", "simple", "cheap"],
    ),

    # Google
    "gemini-1.5-pro": ModelProfile(
        name="Gemini 1.5 Pro",
        provider="google",
        model_id="google/gemini-1.5-pro",
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.005,
        max_tokens=2000000,
        strengths=["long_context", "code", "multimodal"],
    ),
    "gemini-1.5-flash": ModelProfile(
        name="Gemini 1.5 Flash",
        provider="google",
        model_id="google/gemini-1.5-flash",
        cost_per_1k_input=0.000075,
        cost_per_1k_output=0.0003,
        max_tokens=1000000,
        strengths=["fast", "cheap", "code"],
    ),

    # DeepSeek
    "deepseek-v3": ModelProfile(
        name="DeepSeek V3",
        provider="deepseek",
        model_id="deepseek/deepseek-chat",
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        max_tokens=64000,
        strengths=["code", "reasoning", "cheap"],
    ),
    "deepseek-coder": ModelProfile(
        name="DeepSeek Coder",
        provider="deepseek",
        model_id="deepseek/deepseek-coder",
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        max_tokens=64000,
        strengths=["code", "cheap"],
    ),

    # Local (Ollama)
    "qwen3-8b": ModelProfile(
        name="Qwen3 8B (Local)",
        provider="ollama",
        model_id="ollama/qwen3:8b",
        cost_per_1k_input=0,
        cost_per_1k_output=0,
        max_tokens=32768,
        strengths=["fast", "free", "privacy"],
    ),
    "qwen3-4b": ModelProfile(
        name="Qwen3 4B (Local)",
        provider="ollama",
        model_id="ollama/qwen3:4b",
        cost_per_1k_input=0,
        cost_per_1k_output=0,
        max_tokens=32768,
        strengths=["fast", "free", "low_ram"],
    ),
}


# ------------------------------------------------------------------ #
# Task Rules
# ------------------------------------------------------------------ #

TASK_RULES: dict[str, dict] = {
    "code_generation": {
        "preferred": ["gpt-4o", "claude-3-5-sonnet", "deepseek-coder"],
        "fallback": ["gpt-4o-mini", "qwen3-8b"],
        "prefer_local": False,
    },
    "code_review": {
        "preferred": ["claude-3-5-sonnet", "gpt-4o"],
        "fallback": ["gpt-4o-mini", "deepseek-v3"],
        "prefer_local": False,
    },
    "quick_qa": {
        "preferred": ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash"],
        "fallback": ["qwen3-8b", "deepseek-v3"],
        "prefer_local": True,
    },
    "complex_reasoning": {
        "preferred": ["claude-3-opus", "gpt-4o", "o3-mini"],
        "fallback": ["claude-3-5-sonnet", "deepseek-v3"],
        "prefer_local": False,
    },
    "simple_task": {
        "preferred": ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash"],
        "fallback": ["qwen3-8b", "qwen3-4b"],
        "prefer_local": True,
    },
    "long_context": {
        "preferred": ["gemini-1.5-pro", "claude-3-5-sonnet"],
        "fallback": ["gpt-4o"],
        "prefer_local": False,
    },
    "refactoring": {
        "preferred": ["claude-3-5-sonnet", "gpt-4o"],
        "fallback": ["deepseek-v3", "gpt-4o-mini"],
        "prefer_local": False,
    },
    "creative": {
        "preferred": ["claude-3-opus", "gpt-4o"],
        "fallback": ["claude-3-5-sonnet"],
        "prefer_local": False,
    },
    "math": {
        "preferred": ["o3-mini", "gpt-4o"],
        "fallback": ["deepseek-v3"],
        "prefer_local": False,
    },
}


# ------------------------------------------------------------------ #
# Model Selector
# ------------------------------------------------------------------ #

class ModelSelector:
    """Task turiga qarab model tanlaydi."""

    def __init__(self, available_models: Optional[list[str]] = None):
        self.available = available_models or list(PROFILES.keys())

    def select(
        self,
        task_type: str,
        prefer_local: bool = False,
        max_cost: Optional[float] = None,
        exclude: Optional[list[str]] = None,
    ) -> ModelProfile:
        """Task uchun eng mos modelni tanlash."""
        rules = TASK_RULES.get(task_type, TASK_RULES["simple_task"])
        exclude = set(exclude or [])

        # Local model afzallik berilgan bo'lsa
        if prefer_local or rules.get("prefer_local"):
            for name in rules["preferred"]:
                if name in exclude:
                    continue
                profile = PROFILES.get(name)
                if profile and name in self.available and profile.is_local:
                    return profile

        # Preferred modellar
        for name in rules["preferred"]:
            if name in exclude:
                continue
            profile = PROFILES.get(name)
            if profile and name in self.available:
                if max_cost is None or profile.cost_per_1k_input <= max_cost:
                    return profile

        # Fallback modellar
        for name in rules["fallback"]:
            if name in exclude:
                continue
            profile = PROFILES.get(name)
            if profile and name in self.available:
                return profile

        # Default — eng arzon
        return PROFILES["gpt-4o-mini"]

    def classify_task(self, message: str) -> str:
        """Xabardan task turini aniqlash (rule-based, LLM kerak emas)."""
        msg = message.lower()

        # Math (code_generation dan oldin tekshiramiz)
        if any(w in msg for w in ["hisobla", "calculate", "math", "son", "qiymat", "formula", "bo'l", "qo'sh", "ayir", "ko'paytir"]):
            return "math"

        # Code generation
        if any(w in msg for w in ["yoz", "create", "write", "generate", "qil", "build", "make"]):
            if any(w in msg for w in ["code", "function", "class", "file", "script", "module", "api"]):
                return "code_generation"

        # Code review
        if any(w in msg for w in ["review", "tekshir", "check", "analyze", "sharh", "audit"]):
            return "code_review"

        # Refactoring
        if any(w in msg for w in ["refactor", "o'zgartir", "tuzat", "optimize", "yaxshilash", "clean"]):
            return "refactoring"

        # Complex reasoning (uzun savollar)
        if any(w in msg for w in ["nima", "qanday", "nega", "tushuntir", "explain", "why", "how", "farq"]):
            if len(message.split()) > 20:
                return "complex_reasoning"

        # Creative
        if any(w in msg for w in ["yarat", "creative", "design", "tus", "rang", "style"]):
            return "creative"

        # Long context
        if any(w in msg for w in ["barcha", "all", "to'liq", "complete", "summary", "xulosa"]):
            return "long_context"

        return "simple_task"

    def estimate_cost(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Taxminiy xarajatni hisoblash (USD)."""
        profile = PROFILES.get(model_name)
        if not profile:
            return 0.0
        return (
            input_tokens * profile.cost_per_1k_input
            + output_tokens * profile.cost_per_1k_output
        ) / 1000

    def rank_models(
        self,
        task_type: str,
        top_n: int = 3,
    ) -> list[tuple[ModelProfile, str]]:
        """Barcha modellarni task uchun reytingga qo'yish."""
        rules = TASK_RULES.get(task_type, TASK_RULES["simple_task"])
        results: list[tuple[ModelProfile, str]] = []

        for name in rules["preferred"] + rules["fallback"]:
            profile = PROFILES.get(name)
            if profile and name in self.available:
                reason = "preferred" if name in rules["preferred"] else "fallback"
                results.append((profile, reason))

        # Free modellarni ustunlik berish
        results.sort(key=lambda x: (not x[0].is_free, x[0].cost_per_1k_input))

        return results[:top_n]


__all__ = [
    "ModelProfile",
    "PROFILES",
    "TASK_RULES",
    "ModelSelector",
]
