"""
igris.core.providers.openai_compatible
-----------------------------------------
A single client for any server that speaks the OpenAI /chat/completions
protocol -- which covers both LM Studio's local server and OpenRouter's
hosted API. Only base_url, model, and auth differ between them; that
config lives in lmstudio_provider.py / openrouter_provider.py.

Shape differences from Ollama's /api/chat handled here:
- request:  POST {base_url}/chat/completions, body has "messages"/"tools"
  the same as Ollama, but no "keep_alive".
- response: choices[0].message instead of message directly.
- tool calls: OpenAI's tool_calls each carry an "id" that must be echoed
  back on the corresponding "tool" role message as "tool_call_id" --
  Ollama doesn't require this, so it's handled only here.
- tool call arguments are *always* a JSON string in OpenAI's format
  (Ollama sometimes returns a dict) -- both are handled defensively.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

import httpx

from ..llm_common import ChatResult, _extract_fallback_tool_calls


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.4,
        timeout_seconds: int = 120,
        extra_headers: dict | None = None,
        enable_json_fallback: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout_seconds
        self.extra_headers = extra_headers or {}
        self.enable_json_fallback = enable_json_fallback

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _chat_once(self, messages: list[dict], tools: list[dict] | None) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
            )
            resp.raise_for_status()
            return resp.json()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatResult:
        data = await self._chat_once(messages, tools)
        msg = data["choices"][0]["message"]
        usage = data.get("usage") or {}
        return ChatResult(
            content=msg.get("content") or "",
            tool_calls=msg.get("tool_calls", []) or [],
            raw_messages=messages + [msg],
            prompt_tokens=usage.get("prompt_tokens", 0) or 0,
            completion_tokens=usage.get("completion_tokens", 0) or 0,
        )

    async def run_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        mcp_manager,
        max_iterations: int = 12,
        on_tool_call: Callable[[str, dict, str], Awaitable[None]] | None = None,
    ) -> ChatResult:
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
            msg = data["choices"][0]["message"]
            messages.append(msg)
            # usage is top-level per response, not per-message; not every
            # OpenAI-compatible server sends it (some local servers omit
            # it), so this defensively defaults to 0 rather than failing.
            usage = data.get("usage") or {}
            prompt_tokens += usage.get("prompt_tokens", 0) or 0
            completion_tokens += usage.get("completion_tokens", 0) or 0

            tool_calls = msg.get("tool_calls", []) or []
            if not tool_calls and self.enable_json_fallback and tools:
                fallback = _extract_fallback_tool_calls(msg.get("content") or "")
                if fallback:
                    tool_calls = fallback
                    used_fallback = True

            if not tool_calls:
                return ChatResult(
                    content=msg.get("content") or "",
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
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}

                if mcp_manager is None:
                    tool_result = f"ERROR: no MCP manager available to run '{name}'"
                else:
                    tool_result = await mcp_manager.call(name, args)

                if on_tool_call:
                    await on_tool_call(name, args, tool_result)

                tool_message = {"role": "tool", "content": tool_result, "name": name}
                call_id = call.get("id")
                if call_id:
                    tool_message["tool_call_id"] = call_id
                messages.append(tool_message)

        return ChatResult(
            content=messages[-1].get("content") or "(tool iteration budget exhausted)",
            tool_calls=[],
            raw_messages=messages,
            tool_iterations=iterations,
            used_fallback_parsing=used_fallback,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
