"""
igris.core.gateway
--------------------
The "LLM Gateway" from the architecture plan: one factory function that
picks a provider by config so the rest of igris (RepromptLoop, the
server, the CLI) never imports a specific provider directly. Every
provider exposes the same two async methods -- chat() and
run_with_tools() -- returning the shared ChatResult, so swapping
gateway.provider in config.yaml is the only change needed to switch
between a fully local setup (Ollama, LM Studio) and a hosted one
(OpenRouter).

Currently wired: ollama, lmstudio, openrouter. Adding a fourth provider
means one new file in core/providers/ plus one line here -- nothing else
in the codebase needs to change, since everything downstream only talks
to the ChatResult-shaped interface.
"""
from __future__ import annotations

from .ollama_client import OllamaClient
from .providers.lmstudio_provider import build_lmstudio_client
from .providers.openrouter_provider import build_openrouter_client

SUPPORTED_PROVIDERS = ("ollama", "lmstudio", "openrouter")


def build_llm(config):
    provider = config.get("gateway.provider", "ollama")

    if provider == "ollama":
        return OllamaClient(config)
    if provider == "lmstudio":
        return build_lmstudio_client(config)
    if provider == "openrouter":
        return build_openrouter_client(config)

    raise ValueError(
        f"Unknown gateway.provider '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
    )
