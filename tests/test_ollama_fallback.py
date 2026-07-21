"""
Regression test for the exact failure observed with qwen2.5-coder:7b:
Ollama's /api/chat returned the tool call as plain JSON text in
`message.content` instead of populating `message.tool_calls`. Before the
fix, run_with_tools() treated that JSON text as the final answer and never
executed the tool. This test drives OllamaClient.run_with_tools() against
a fake httpx transport that replays exactly that response shape.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.ollama_client import OllamaClient, _extract_fallback_tool_calls


def test_extract_fallback_tool_calls_parses_bare_json():
    content = '''
    {
      "name": "terminal__run_command",
      "arguments": {
        "command": "dir /b",
        "cwd": ".",
        "shell": "cmd"
      }
    }
    '''
    calls = _extract_fallback_tool_calls(content)
    assert calls is not None
    assert calls[0]["function"]["name"] == "terminal__run_command"
    assert calls[0]["function"]["arguments"]["command"] == "dir /b"


def test_extract_fallback_tool_calls_ignores_normal_prose():
    assert _extract_fallback_tool_calls("Here are the files: a.txt, b.txt") is None


def test_extract_fallback_tool_calls_handles_fenced_json():
    content = '```json\n{"name": "filesystem__list_dir", "arguments": {"path": "."}}\n```'
    calls = _extract_fallback_tool_calls(content)
    assert calls is not None
    assert calls[0]["function"]["name"] == "filesystem__list_dir"


class _FakeMCPManager:
    """Records calls; returns a canned result for the exact tool used in the bug report."""

    def __init__(self):
        self.calls = []

    def tool_schemas(self):
        return [{"type": "function", "function": {"name": "terminal__run_command", "parameters": {}}}]

    def describe_tools(self):
        return "- terminal.run_command: run a shell command"

    async def call(self, name, args):
        self.calls.append((name, args))
        return "file1.txt\nfile2.txt"


def _fake_ollama_transport(responses: list[dict]):
    """Replays canned /api/chat responses in order, last one repeats."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return httpx.Response(200, json=responses[idx])

    return httpx.MockTransport(handler)


def test_run_with_tools_recovers_qwen25coder_style_json_response(monkeypatch):
    """
    Reproduces the bug report verbatim: first response is the JSON-as-text
    tool call qwen2.5-coder:7b actually produced, second response is a
    normal final answer after the tool result is fed back.
    """
    config = Config.load(project_root=Path("/tmp"))
    client = OllamaClient(config)

    first_response = {
        "message": {
            "role": "assistant",
            "content": '{\n  "name": "terminal__run_command",\n  "arguments": {\n    "command": "dir /b",\n    "cwd": ".",\n    "shell": "cmd"\n  }\n}',
            # tool_calls deliberately absent/empty -- this is the observed bug
        }
    }
    second_response = {
        "message": {
            "role": "assistant",
            "content": "The directory contains: file1.txt, file2.txt",
        }
    }

    transport = _fake_ollama_transport([first_response, second_response])

    async def fake_chat_once(messages, tools):
        async with httpx.AsyncClient(transport=transport) as ac:
            resp = await ac.post("http://fake/api/chat", json={"messages": messages})
            return resp.json()

    monkeypatch.setattr(client, "_chat_once", fake_chat_once)

    mcp = _FakeMCPManager()
    result = asyncio.run(client.run_with_tools("system", "list files", mcp, max_iterations=5))

    assert mcp.calls == [("terminal__run_command", {"command": "dir /b", "cwd": ".", "shell": "cmd"})]
    assert result.used_fallback_parsing is True
    assert "file1.txt" in result.content
    assert result.tool_iterations == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
