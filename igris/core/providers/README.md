# igris/core/providers (backend.providers)

The LLM Gateway's actual provider implementations -- the only place in
igris that knows the wire format of a specific model API.

## Purpose

Give `core/gateway.py` something uniform to hand back regardless of
which backend is configured: every provider implements `async
chat(messages, tools)` and `async run_with_tools(system_prompt,
user_prompt, mcp_manager, max_iterations, on_tool_call)`, returning the
same `ChatResult` (content, tool_calls, prompt_tokens, completion_tokens,
used_fallback_parsing, tool_iterations) defined once in
`../llm_common.py`.

## Boundary

- **Does not** get imported directly by anything outside `gateway.py`.
  `RepromptLoop`, `server.py`, and `cli.py` only ever see the shared
  interface.
- **Does not** duplicate the JSON-text tool-call fallback parser --
  that's shared in `llm_common.py` and reused by every provider, since
  the failure mode (a model printing `{"name":...}` as plain content
  instead of using the real tool-calling field) isn't Ollama-specific.
- **A new provider belongs here as a new file**, not as branching logic
  inside an existing client -- see `change-type-discipline`: adding
  OpenRouter-but-different-pricing is a Create, not a Modify of
  `openrouter_provider.py`.

## Key files

| File | Role |
|---|---|
| `openai_compatible.py` | shared client for any server speaking the OpenAI `/chat/completions` protocol -- handles the `tool_call_id` echo-back OpenAI's protocol requires (Ollama doesn't need this) |
| `lmstudio_provider.py` | thin config wrapper around `openai_compatible.py` for LM Studio's local server |
| `openrouter_provider.py` | same, for OpenRouter's hosted API -- requires an API key, reads it from config or `OPENROUTER_API_KEY` |

`../ollama_client.py` (one level up, not in this folder) is the fourth
provider -- it predates this folder and speaks Ollama's own `/api/chat`
protocol rather than the OpenAI-compatible one, so it isn't a good fit
for `openai_compatible.py`'s shared client.

## Testing

`tests/test_providers.py` replays captured request/response shapes
against `httpx.MockTransport` -- including a regression test for the
`tool_call_id` echo-back, since that's the specific detail that's easy
to get right for a single-turn call and silently wrong for multi-turn
tool use. `tests/test_ollama_fallback.py` covers the same class of
regression for the Ollama client specifically (the `qwen2.5-coder`
JSON-as-text bug found via real usage).

## How this compares

Standardizing on the OpenAI `/chat/completions` shape as the "generic"
protocol (rather than inventing a project-specific one) is the same
choice most multi-provider tools make, since it's the de facto
lowest-common-denominator most local and hosted servers already speak.
