# igris (backend)

The Python backend: everything that makes igris an agent rather than a
thin wrapper around an LLM API. This package is the "backend" main
module in the project's layer classification (see the root
[README](../README.md) and `architecture-layer-classification`).

## Purpose

Owns the whole request lifecycle for a task: resolving what the user
actually wants, gathering the context needed to do it well, calling an
LLM with tools, and verifying the result -- before anything reaches a
human. Exposed three ways: the `igris` CLI (`cli.py`), a FastAPI+
WebSocket bridge for the desktop UI (`server.py`), and directly as a
library for anything else that wants to embed the same loop.

## Boundary

- **Does not** render any UI. `server.py` speaks JSON over HTTP/WebSocket
  and nothing else -- the desktop app (`desktop/`) is a separate process
  that happens to be the current consumer.
- **Does not** hardcode a single LLM provider. Every call to a model goes
  through `core/gateway.py`; nothing else in this package should import
  `OllamaClient` or `OpenAICompatibleClient` directly.
- **Does not** assume a specific project on disk implicitly -- every
  entry point resolves an explicit project root first (`workspace.py`),
  so the same code runs correctly regardless of which project or which
  directory it was launched from.

## Layout

| File | Sub-module | Role |
|---|---|---|
| `cli.py` | -- | `igris` command-line entry point |
| `server.py` | backend.server | FastAPI + WebSocket bridge for the desktop UI |
| `workspace.py` | -- | resolves which project a task runs against |
| `config.py` | -- | loads/persists `.igris/config.yaml` |
| `memory.py` | -- | session log + checkpoint store |
| `core/` | backend.core | the reprompt loop and everything it orchestrates -- see [core/README.md](core/README.md) |
| `core/providers/` | backend.providers | LLM Gateway provider implementations -- see [core/providers/README.md](core/providers/README.md) |
| `mcp_servers/` | backend.mcp_servers | the actual tools the agent can call -- see [mcp_servers/README.md](mcp_servers/README.md) |
| `skills/`, `templates/` | -- | default skill library and `.igris/` scaffold copied into new projects |

## Testing

`pytest tests/` from the repo root. Convention: async tests via
`asyncio.run()`, `tests/mock_llm.py` stands in for any provider (same
`chat()`/`run_with_tools()` interface every real provider implements),
and MCP-tool-behavior tests spawn the *real* MCP server subprocesses via
`MCPManager` rather than mocking the protocol -- this caught real bugs
(see `tests/test_knowledge_server.py`'s connection-failure regression)
that a mocked transport wouldn't have.

## How this compares

The closest like-for-like tools -- Aider, Claude Code, Cursor's agent
mode -- converge on the same three pieces this package has: a
provider-agnostic model gateway, a tool-calling loop, and some form of
project-level context injection (Aider's repo-map; Continue's
rules/`AGENTS.md` files; this project's TaskSpec + hierarchical
knowledge base). Where igris differs deliberately: the reprompt loop is
a separate, inspectable stage *before* the model call (see
`core/README.md`) rather than folded into the system prompt implicitly,
and confidence-gated clarification (ask vs. state-an-assumption-and-
proceed) is explicit rather than left to the model's own judgment.
