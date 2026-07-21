"""
A stand-in for OllamaClient used in tests so the reprompt loop's control
flow (clarify gate, spec synthesis, bounded self-review retries, token
aggregation) can be verified without a live Ollama server. Implements the
same two methods RepromptLoop actually calls: chat() and run_with_tools().
"""
from __future__ import annotations

from igris.core.ollama_client import ChatResult


class MockLLM:
    def __init__(
        self,
        chat_responses: list[str] | None = None,
        run_responses: list[str] | None = None,
        chat_tokens: list[tuple[int, int]] | None = None,
        run_tokens: list[tuple[int, int]] | None = None,
    ):
        # queues popped in order; last value repeats once exhausted
        self._chat_queue = list(chat_responses or ["PASS\nlooks good"])
        self._run_queue = list(run_responses or ["mock response"])
        # (prompt_tokens, completion_tokens) per call; defaults to 0,0 if
        # not given -- most tests don't care about token accounting.
        self._chat_tokens_queue = list(chat_tokens or [(0, 0)])
        self._run_tokens_queue = list(run_tokens or [(0, 0)])
        self.chat_calls: list[list[dict]] = []
        self.run_calls: list[tuple[str, str]] = []

    def _pop(self, queue: list):
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]

    async def chat(self, messages, tools=None) -> ChatResult:
        self.chat_calls.append(messages)
        content = self._pop(self._chat_queue)
        pt, ct = self._pop(self._chat_tokens_queue)
        return ChatResult(content=content, tool_calls=[], raw_messages=messages, prompt_tokens=pt, completion_tokens=ct)

    async def run_with_tools(self, system_prompt, user_prompt, mcp_manager, max_iterations=12, on_tool_call=None) -> ChatResult:
        self.run_calls.append((system_prompt, user_prompt))
        content = self._pop(self._run_queue)
        pt, ct = self._pop(self._run_tokens_queue)
        return ChatResult(content=content, tool_calls=[], raw_messages=[], tool_iterations=1, prompt_tokens=pt, completion_tokens=ct)
