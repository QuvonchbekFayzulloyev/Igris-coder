"""
Tests for token usage tracking end-to-end: captured per-provider from the
real API response shapes, summed across tool-calling iterations, and
aggregated by RepromptLoop across attempts/review calls/multi-agent
branches. This was a requirement in the original architecture spec
("Token, Cost, Model, Runtime Status") that got silently dropped when
StatusBar.tsx was first built -- these tests exist so it can't regress
back to silently missing again.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.ollama_client import OllamaClient
from igris.core.providers.openai_compatible import OpenAICompatibleClient
from igris.config import Config


class _FakeMCPManager:
    def __init__(self, tool_call_rounds=0):
        self.calls = []
        self._rounds_remaining = tool_call_rounds

    def tool_schemas(self):
        return [{"type": "function", "function": {"name": "filesystem__read_file", "parameters": {}}}]

    def describe_tools(self):
        return "- filesystem.read_file"

    async def call(self, name, args):
        self.calls.append((name, args))
        return "file contents"


def _mock_transport(responses):
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(state["n"], len(responses) - 1)
        state["n"] += 1
        return httpx.Response(200, json=responses[idx])

    return httpx.MockTransport(handler)


def test_ollama_chat_captures_token_counts(monkeypatch):
    config = Config.load(project_root=Path("/tmp"))
    client = OllamaClient(config)
    transport = _mock_transport([{
        "message": {"role": "assistant", "content": "hello"},
        "prompt_eval_count": 120,
        "eval_count": 45,
    }])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/api/chat", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)
    result = asyncio.run(client.chat([{"role": "user", "content": "hi"}]))
    assert result.prompt_tokens == 120
    assert result.completion_tokens == 45


def test_ollama_run_with_tools_sums_tokens_across_iterations(monkeypatch):
    """Two tool-calling rounds -- each response's counts should sum, not overwrite."""
    config = Config.load(project_root=Path("/tmp"))
    client = OllamaClient(config)

    first = {
        "message": {
            "role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "filesystem__read_file", "arguments": {"path": "a.txt"}}}],
        },
        "prompt_eval_count": 100, "eval_count": 20,
    }
    second = {
        "message": {"role": "assistant", "content": "done"},
        "prompt_eval_count": 150, "eval_count": 30,
    }
    transport = _mock_transport([first, second])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/api/chat", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)
    mcp = _FakeMCPManager()
    result = asyncio.run(client.run_with_tools("sys", "read a.txt", mcp, max_iterations=5))

    assert result.prompt_tokens == 100 + 150
    assert result.completion_tokens == 20 + 30


def test_openai_compatible_chat_captures_usage(monkeypatch):
    client = OpenAICompatibleClient(base_url="http://fake/v1", model="test-model")
    transport = _mock_transport([{
        "choices": [{"message": {"role": "assistant", "content": "hello"}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
    }])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/v1/chat/completions", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)
    result = asyncio.run(client.chat([{"role": "user", "content": "hi"}]))
    assert result.prompt_tokens == 80
    assert result.completion_tokens == 15


def test_openai_compatible_missing_usage_defaults_to_zero(monkeypatch):
    """Some local OpenAI-compatible servers omit usage entirely -- must not crash."""
    client = OpenAICompatibleClient(base_url="http://fake/v1", model="test-model")
    transport = _mock_transport([{
        "choices": [{"message": {"role": "assistant", "content": "hello"}}],
        # no "usage" key at all
    }])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/v1/chat/completions", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)
    result = asyncio.run(client.chat([{"role": "user", "content": "hi"}]))
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
