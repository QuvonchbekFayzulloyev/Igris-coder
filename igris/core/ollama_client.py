"""
igris.core.ollama_client
-------------------------
Async wrapper around a local Ollama server's /api/chat endpoint, plus the
bounded tool-calling loop that wires model tool_calls to an MCPManager.
qwen3 is the recommended model for reliable native tool-calling; the
JSON-text fallback (see llm_common) recovers qwen2.5-coder-style output.

ChatResult and _extract_fallback_tool_calls are re-exported here for
backward compatibility with existing imports/tests -- the real
definitions now live in llm_common so every provider (LM Studio,
OpenRouter, ...) shares the same shape instead of duplicating it.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

import httpx

from .llm_common import ChatResult, _extract_fallback_tool_calls  # noqa: F401  (re-export)

__all__ = ["OllamaClient", "ChatResult", "_extract_fallback_tool_calls"]


class OllamaClient:
    def __init__(self, config):
        self.host = config.get("ollama.host")
        self.model = config.get("ollama.model")
        self.temperature = config.get("ollama.temperature", 0.4)
        self.keep_alive = config.get("ollama.keep_alive", "10m")
        self.timeout = config.get("ollama.timeout_seconds", 120)
        self.enable_json_fallback = config.get("ollama.enable_json_tool_call_fallback", True)

    async def _chat_once(self, messages: list[dict], tools: list[dict] | None) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
            "keep_alive": self.keep_alive,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.host}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatResult:
        """Single round-trip, no tool execution -- caller handles tool_calls itself."""
        data = await self._chat_once(messages, tools)
        msg = data.get("message", {})
        return ChatResult(
            content=msg.get("content", ""),
            tool_calls=msg.get("tool_calls", []) or [],
            raw_messages=messages + [msg],
            prompt_tokens=data.get("prompt_eval_count", 0) or 0,
            completion_tokens=data.get("eval_count", 0) or 0,
        )

    async def run_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        mcp_manager,
        max_iterations: int = 12,
        on_tool_call: Callable[[str, dict, str], Awaitable[None]] | None = None,
    ) -> ChatResult:
        """
        Runs the standard agent loop: send messages -> if the model returns
        tool_calls (real or JSON-text-fallback), execute each via
        mcp_manager and feed results back -> repeat until the model answers
        with plain content or the iteration budget runs out.
        """
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        tools = mcp_manager.tool_schemas() if mcp_manager else None

        iterations = 0
        used_fallback = False
        prompt_tokens = 0
        completion_tokens = 0
        while iterations < max_iterations:
            iterations += 1
            data = await self._chat_once(messages, tools)
            msg = data.get("message", {})
            messages.append(msg)
            # Ollama reports counts per-call, not cumulatively -- each
            # iteration re-sends the growing message history, so summing
            # every call's counts gives the loop's true total token spend.
            prompt_tokens += data.get("prompt_eval_count", 0) or 0
            completion_tokens += data.get("eval_count", 0) or 0

            tool_calls = msg.get("tool_calls", []) or []
            if not tool_calls and self.enable_json_fallback and tools:
                fallback = _extract_fallback_tool_calls(msg.get("content", ""))
                if fallback:
                    tool_calls = fallback
                    used_fallback = True

            if not tool_calls:
                return ChatResult(
                    content=msg.get("content", ""),
                    tool_calls=[],
                    raw_messages=messages,
                    tool_iterations=iterations,
                    used_fallback_parsing=used_fallback,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                if mcp_manager is None:
                    tool_result = f"ERROR: no MCP manager available to run '{name}'"
                else:
                    tool_result = await mcp_manager.call(name, args)

                if on_tool_call:
                    await on_tool_call(name, args, tool_result)

                messages.append({
                    "role": "tool",
                    "content": tool_result,
                    "name": name,
                })

        # Iteration budget exhausted -- return whatever the model last said.
        return ChatResult(
            content=messages[-1].get("content", "(tool iteration budget exhausted)"),
            tool_calls=[],
            raw_messages=messages,
            tool_iterations=iterations,
            used_fallback_parsing=used_fallback,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
