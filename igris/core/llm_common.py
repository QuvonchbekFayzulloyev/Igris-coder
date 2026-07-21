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

_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def _looks_like_call(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return False
    args = obj.get("arguments") or obj.get("parameters")
    if not isinstance(args, dict):
        args = {}
    obj["arguments"] = args
    return True


def _extract_fallback_tool_calls(content: str) -> list[dict] | None:
    """
    If `content` is — or contains inside a ```json fence — a JSON
    object/array shaped like {"name": ..., "arguments": {...}} treat it as
    the tool call(s) the model meant to make. Returns None if content
    doesn't parse as a recognizable tool call, in which case the caller
    should treat content as a normal final answer.

    Strict: only ```json fences are matched (not ```python or bare fences).
    For unfenced content, the ENTIRE text must be valid tool-call JSON.
    """
    text = content.strip()
    if not text:
        return None

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
    else:
        candidate = text
        if not (candidate.startswith("{") or candidate.startswith("[")):
            return None

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
