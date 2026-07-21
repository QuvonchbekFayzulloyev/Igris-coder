"""
igris.core.providers.openrouter_provider
-------------------------------------------
OpenRouter is a hosted (non-local) OpenAI-compatible gateway to many
cloud models. Requires an API key -- read from config first, then the
OPENROUTER_API_KEY environment variable so the key never has to live in
.igris/config.yaml if the user prefers an env var.
"""
from __future__ import annotations

import os

from .openai_compatible import OpenAICompatibleClient


def build_openrouter_client(config) -> OpenAICompatibleClient:
    api_key = config.get("openrouter.api_key") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenRouter selected as gateway.provider but no API key found. "
            "Set openrouter.api_key in .igris/config.yaml or the OPENROUTER_API_KEY "
            "environment variable."
        )
    return OpenAICompatibleClient(
        base_url=config.get("openrouter.host", "https://openrouter.ai/api/v1"),
        model=config.get("openrouter.model", "openrouter/auto"),
        api_key=api_key,
        temperature=config.get("openrouter.temperature", 0.4),
        timeout_seconds=config.get("openrouter.timeout_seconds", 120),
        extra_headers={
            "HTTP-Referer": "https://github.com/igris-cli",
            "X-Title": "igris-cli",
        },
        enable_json_fallback=config.get("openrouter.enable_json_tool_call_fallback", True),
    )
