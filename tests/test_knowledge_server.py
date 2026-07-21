"""
Tests for igris.mcp_servers.knowledge_server's tool functions, called
directly (FastMCP's @mcp.tool() decorator leaves them plain callables).
Monkeypatches the module's global _EMBEDDER so no live Ollama is needed.

The connection-failure tests are a regression guard for a real bug found
via live smoke-testing: an unhandled httpx.ConnectError inside the tool
crashed the whole MCP call instead of returning a clean "ERROR: ..."
string the model could read and act on (see tool-call-reliability skill).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import igris.mcp_servers.knowledge_server as ks
from igris.config import Config
from igris.core.knowledge_base import KnowledgeStore


class _FakeEmbedder:
    """Deterministic fake -- same text always yields the same vector, so similarity is testable."""

    def __init__(self, host="http://fake:11434", model="fake-embed"):
        self.host = host
        self.model = model
        self.calls: list[str] = []

    async def embed_one(self, text: str) -> list[float]:
        self.calls.append(text)
        # crude but deterministic: vector position encodes text length parity
        return [1.0, 0.0] if len(text) % 2 == 0 else [0.0, 1.0]


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)
    monkeypatch.setattr(ks, "_STORE", store)
    monkeypatch.setattr(ks, "_CONFIG", config)
    return store


@pytest.fixture
def fake_embedder(monkeypatch):
    embedder = _FakeEmbedder()
    monkeypatch.setattr(ks, "_EMBEDDER", embedder)
    return embedder


def test_knowledge_add_then_search_roundtrip(isolated_store, fake_embedder):
    result = asyncio.run(ks.knowledge_add("even length text", module="backend", kind="rule"))
    assert result.startswith("OK:")

    search_result = asyncio.run(ks.knowledge_search("also even", module="backend"))
    assert "even length text" in search_result


def test_knowledge_add_rejects_invalid_kind(isolated_store, fake_embedder):
    result = asyncio.run(ks.knowledge_add("text", kind="not_a_real_kind"))
    assert result.startswith("ERROR")
    assert fake_embedder.calls == []  # validated before ever calling the embedder


def test_knowledge_add_rejects_invalid_source(isolated_store, fake_embedder):
    result = asyncio.run(ks.knowledge_add("text", source="not_a_real_source"))
    assert result.startswith("ERROR")


def test_knowledge_list_modules_reflects_additions(isolated_store, fake_embedder):
    asyncio.run(ks.knowledge_add("x", module="backend.core"))
    asyncio.run(ks.knowledge_add("y", module="frontend"))
    result = ks.knowledge_list_modules()
    assert "backend.core" in result
    assert "frontend" in result


def test_knowledge_search_auto_routes_when_module_not_given(isolated_store, fake_embedder):
    asyncio.run(ks.knowledge_add("reprompt loop rule", module="backend.core"))
    result = asyncio.run(ks.knowledge_search("tell me about the reprompt loop"))
    assert "[scope searched: backend.core]" in result


# --- tool-call-reliability regression: connection failures must not crash ---

def test_knowledge_add_connect_error_returns_clean_message(isolated_store, monkeypatch):
    class _BrokenEmbedder:
        host = "http://localhost:11434"
        model = "nomic-embed-text"

        async def embed_one(self, text):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(ks, "_EMBEDDER", _BrokenEmbedder())
    result = asyncio.run(ks.knowledge_add("some text"))
    assert result.startswith("ERROR")
    assert "Ollama" in result


def test_knowledge_search_connect_error_returns_clean_message(isolated_store, monkeypatch):
    class _BrokenEmbedder:
        host = "http://localhost:11434"
        model = "nomic-embed-text"

        async def embed_one(self, text):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(ks, "_EMBEDDER", _BrokenEmbedder())
    result = asyncio.run(ks.knowledge_search("anything"))
    assert result.startswith("ERROR")


def test_timeout_returns_clean_message_not_raw_exception(isolated_store, monkeypatch):
    class _SlowEmbedder:
        host = "http://localhost:11434"
        model = "nomic-embed-text"

        async def embed_one(self, text):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(ks, "_EMBEDDER", _SlowEmbedder())
    result = asyncio.run(ks.knowledge_add("text"))
    assert result.startswith("ERROR")
    assert "timed out" in result.lower()


def test_no_entries_message_when_scope_is_empty(isolated_store, fake_embedder):
    result = asyncio.run(ks.knowledge_search("nothing indexed yet", module="backend.providers"))
    assert "no knowledge entries found" in result


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
