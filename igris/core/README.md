# igris/core (backend.core)

The domain layer: the reprompt loop and everything it orchestrates. This
is the part of igris that would still make sense if you swapped the CLI
for a web API or the desktop app for something else entirely -- it knows
nothing about HTTP, WebSockets, or argument parsing.

## Purpose

Turns a raw user message into a verified response, without ever handing
the model the raw message alone. See the root README's "Why the
reprompt loop" section for the full pipeline diagram; this module is
where every stage of it actually lives.

## Boundary

- **Does not** talk to the network directly except through an injected
  LLM client (`gateway.py`'s `build_llm()` result) or `MCPManager` --
  nothing here opens its own `httpx` connection.
- **Does not** know about FastAPI, Tauri, or the CLI. `on_stage`
  callbacks let a caller observe progress without this module depending
  on *what* it's being observed by.
- **Does not** write ad hoc state. Durable state belongs either to
  `Memory` (short-term conversation/checkpoints), `KnowledgeStore`
  (embedded project rules), or `CoderMemoryStore` (source-backed reusable
  engineering artefacts).

## Key files

| File | Role |
|---|---|
| `reprompt_loop.py` | the pipeline itself: snapshot → intent → clarify/assume → complexity → loop template → skills → gather → spec → execute → self-review |
| `intent_resolver.py` | heuristic classifier + LLM escalation; the clarify vs. assume-and-proceed gate |
| `task_analyzer.py` | complexity tier (simple/medium/complex/multi_agent) |
| `loop_generator.py` | maps category + complexity to a stage template, or parallel subsystem branches |
| `execution_graph.py` | generic DAG executor -- runs multi_agent branches concurrently |
| `spec.py` | `TaskSpec` -- the actual "reprompt" handed to the model |
| `skill_loader.py` | parses `.igris/skills/*.md`, routes by keyword |
| `context_engine.py` | cheap snapshot + targeted MCP-backed gather (git status, file reads, knowledge base search) |
| `coder_memory.py` | durable artefact store: standard metadata, original payload files, deterministic indexes, and project collector |
| `mcp_manager.py` | spawns MCP servers over stdio, aggregates their tools |
| `gateway.py`, `llm_common.py` | provider selection and the shared `ChatResult`/fallback-parsing types |
| `cost.py` | honest token-cost estimation |
| `knowledge_base.py`, `knowledge_router.py`, `knowledge_seed.py` | the hierarchical project knowledge base |

## Testing

Every file here has a matching `tests/test_*.py` using `MockLLM` (never a
live model) -- `test_reprompt_loop.py`, `test_intent_resolver.py`,
`test_task_analyzer.py`, `test_loop_generator.py`,
`test_execution_graph.py`, `test_multi_agent_loop.py`,
`test_knowledge_base.py`, `test_knowledge_seed.py`. The one thing tested
against *real* infrastructure (spawned MCP subprocesses, not mocked) is
`context_engine.gather()`'s knowledge-base call, in
`test_knowledge_integration.py`.

## How this compares

The stage-by-stage explicit pipeline here (rather than a single big
system prompt asking the model to "think step by step") is closer to how
Aider's edit-format/repo-map machinery or a structured agent framework's
planning phase works than to a bare chat completion loop. The
distinguishing choice is where the reasoning happens: as much as
possible is decided by deterministic code (intent heuristics, complexity
scoring, stage templates) *before* the model is asked anything, so the
model's job is narrower and more checkable than "figure out the whole
task."
