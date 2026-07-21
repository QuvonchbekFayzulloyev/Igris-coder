"""
igris.core.llm_common
-----------------------
Shared between every provider (Ollama, LM Studio, OpenRouter, ...):

- ChatResult: the uniform return shape every provider's chat()/
  run_with_tools() produces, so RepromptLoop never needs to know which
  provider it's talking to.
- _extract_fallback_tool_calls: recovers a tool call from models that
  print {"name":..., "arguments":...} as plain text instead of using the
  API's real tool_calls field (confirmed against qwen2.5-coder:7b on
  Ollama; the same failure mode shows up on some OpenAI-compatible local
  servers too, so it's shared rather than Ollama-specific).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _looks_like_call(obj: Any) -> bool:
    return isinstance(obj, dict) and "name" in obj and isinstance(obj.get("name"), str)


def _extract_fallback_tool_calls(content: str) -> list[dict] | None:
    """
    If `content` is (or contains, fenced) a JSON object/array shaped like
    {"name": ..., "arguments": {...}} -- or {"name":..., "parameters":{...}}
    -- treat it as the tool call(s) the model meant to make. Returns None
    if content doesn't parse as a recognizable tool call, in which case
    the caller should treat content as a normal final answer.
    """
    text = content.strip()
    if not text:
        return None

    fence_match = _FENCE_RE.search(text)
    candidate = fence_match.group(1).strip() if fence_match else text

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    objs = parsed if isinstance(parsed, list) else [parsed]
    if not objs or not all(_looks_like_call(o) for o in objs):
        return None

    calls = []
    for o in objs:
        calls.append({
            "function": {
                "name": o["name"],
                "arguments": o.get("arguments", o.get("parameters", {})),
            }
        })
    return calls


@dataclass
class ChatResult:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    raw_messages: list[dict] = field(default_factory=list)
    tool_iterations: int = 0
    used_fallback_parsing: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
