"""
Tests for OpenAICompatibleClient (shared by LM Studio and OpenRouter) and
the gateway provider factory. Uses httpx.MockTransport -- no real LM
Studio/OpenRouter server needed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.gateway import build_llm
from igris.core.providers.openai_compatible import OpenAICompatibleClient
from igris.core.providers.lmstudio_provider import build_lmstudio_client
from igris.core.providers.openrouter_provider import build_openrouter_client


class _FakeMCPManager:
    def __init__(self):
        self.calls = []

    def tool_schemas(self):
        return [{"type": "function", "function": {"name": "filesystem__list_dir", "parameters": {}}}]

    def describe_tools(self):
        return "- filesystem.list_dir: list a directory"

    async def call(self, name, args):
        self.calls.append((name, args))
        return "a.txt\nb.txt"


def _mock_transport(responses):
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(state["n"], len(responses) - 1)
        state["n"] += 1
        return httpx.Response(200, json=responses[idx])

    return httpx.MockTransport(handler)


def test_openai_compatible_chat_single_turn(monkeypatch):
    client = OpenAICompatibleClient(base_url="http://fake/v1", model="test-model")
    transport = _mock_transport([{"choices": [{"message": {"role": "assistant", "content": "hello"}}]}])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/v1/chat/completions", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)
    result = asyncio.run(client.chat([{"role": "user", "content": "hi"}]))
    assert result.content == "hello"


def test_openai_compatible_run_with_tools_uses_tool_call_id(monkeypatch):
    """OpenAI's protocol requires echoing tool_calls[i].id back as tool_call_id."""
    client = OpenAICompatibleClient(base_url="http://fake/v1", model="test-model")

    first = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_abc123",
                    "type": "function",
                    "function": {"name": "filesystem__list_dir", "arguments": '{"path": "."}'},
                }],
            }
        }]
    }
    second = {"choices": [{"message": {"role": "assistant", "content": "Files: a.txt, b.txt"}}]}
    transport = _mock_transport([first, second])

    captured_messages = []

    async def fake_chat_once(messages, tools):
        captured_messages.append([dict(m) for m in messages])
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/v1/chat/completions", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)

    mcp = _FakeMCPManager()
    result = asyncio.run(client.run_with_tools("sys", "list files", mcp, max_iterations=5))

    assert mcp.calls == [("filesystem__list_dir", {"path": "."})]
    assert "Files: a.txt" in result.content
    # the second _chat_once call's messages must include a tool message
    # carrying tool_call_id="call_abc123"
    second_call_messages = captured_messages[1]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert tool_msgs and tool_msgs[0]["tool_call_id"] == "call_abc123"


def test_gateway_builds_ollama_by_default():
    config = Config.load(project_root=Path("/tmp"))
    llm = build_llm(config)
    assert type(llm).__name__ == "OllamaClient"


def test_gateway_builds_lmstudio_client():
    config = Config.load(project_root=Path("/tmp"))
    config.data["gateway"]["provider"] = "lmstudio"
    llm = build_llm(config)
    assert isinstance(llm, OpenAICompatibleClient)
    assert llm.base_url == "http://localhost:1234/v1"


def test_gateway_builds_openrouter_client_with_api_key():
    config = Config.load(project_root=Path("/tmp"))
    config.data["gateway"]["provider"] = "openrouter"
    config.data["openrouter"]["api_key"] = "sk-test-key"
    llm = build_llm(config)
    assert isinstance(llm, OpenAICompatibleClient)
    assert llm.api_key == "sk-test-key"


def test_gateway_openrouter_without_key_raises():
    config = Config.load(project_root=Path("/tmp"))
    config.data["gateway"]["provider"] = "openrouter"
    config.data["openrouter"]["api_key"] = ""
    import os
    saved = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        with pytest.raises(ValueError):
            build_llm(config)
    finally:
        if saved is not None:
            os.environ["OPENROUTER_API_KEY"] = saved


def test_gateway_unknown_provider_raises():
    config = Config.load(project_root=Path("/tmp"))
    config.data["gateway"]["provider"] = "not-a-real-provider"
    with pytest.raises(ValueError):
        build_llm(config)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
