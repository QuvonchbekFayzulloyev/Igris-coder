"""
Tests for igris.core.cost -- deliberately conservative: local providers
are always free, OpenRouter cost is only computed from rates the user
explicitly configured, never a hardcoded/guessed price table.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.cost import estimate_cost_usd


def test_ollama_is_always_free():
    config = Config.load(project_root=Path("/tmp"))
    assert estimate_cost_usd("ollama", 100000, 50000, config) == 0.0


def test_lmstudio_is_always_free():
    config = Config.load(project_root=Path("/tmp"))
    assert estimate_cost_usd("lmstudio", 100000, 50000, config) == 0.0


def test_openrouter_defaults_to_zero_when_unconfigured():
    config = Config.load(project_root=Path("/tmp"))
    assert estimate_cost_usd("openrouter", 100000, 50000, config) == 0.0


def test_openrouter_computes_from_configured_rates():
    config = Config.load(project_root=Path("/tmp"))
    config.data["openrouter"]["price_per_1k_prompt_tokens"] = 0.003
    config.data["openrouter"]["price_per_1k_completion_tokens"] = 0.015

    cost = estimate_cost_usd("openrouter", 1000, 1000, config)
    assert cost == 0.003 + 0.015


def test_openrouter_zero_tokens_is_zero_cost():
    config = Config.load(project_root=Path("/tmp"))
    config.data["openrouter"]["price_per_1k_prompt_tokens"] = 0.003
    assert estimate_cost_usd("openrouter", 0, 0, config) == 0.0
