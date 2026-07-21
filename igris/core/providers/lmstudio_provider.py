"""
igris.core.providers.lmstudio_provider
-----------------------------------------
LM Studio runs a local OpenAI-compatible server (Developer -> Local
Server in the LM Studio app). No API key needed -- it's local, like
Ollama, just a different wire protocol.
"""
from __future__ import annotations

from .openai_compatible import OpenAICompatibleClient


def build_lmstudio_client(config) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=config.get("lmstudio.host", "http://localhost:1234/v1"),
        model=config.get("lmstudio.model", "local-model"),
        api_key=None,
        temperature=config.get("lmstudio.temperature", 0.4),
        timeout_seconds=config.get("lmstudio.timeout_seconds", 120),
        enable_json_fallback=config.get("lmstudio.enable_json_tool_call_fallback", True),
    )
