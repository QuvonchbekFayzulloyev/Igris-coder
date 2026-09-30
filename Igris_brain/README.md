# IGRIS CODER AGENT — Brain

Super-light **coder agent** (NOT an LLM training project). A hybrid engine with
an agentic harness on top:

1. **Deterministic**: `Brick + Knowledge + Resolver` — a single graph traversal
   turns natural language (uz/en) into code in **<10ms** with a transparent rule trace.
2. **Healing**: missing capability chains are reconstructed algebraically from
   the most similar available chains.
3. **Hybrid LLM**: when deterministic confidence is low, delegates to a local
   Ollama model (qwen3:8b) — the same runtime the GUI assumes.
4. **Agentic core** (v1.0): `StateMachine` + `GoalModel` + `AgentExecutor` +
   `Verifier` — planned/native tool loops, checkpoint/resume, cancellation,
   HITL escalation, ContextBudget and RAG memory (see
   [Agentic architecture](#agentic-architecture-v10)).

> Corrected framing: the original plan (`Temp_EXAMPle_IGRIS_CODER_Plan.md`)
> was titled "Coder Agent LLM". This **is** a coder agent — the 400M-parameter
> transformer-training pipeline is out of scope. We build the agent brain.

## Structure

```
igris_brain/
├── igris_agent.py               # Main orchestrator: chat/chat_stream, pipelines, goal pin
│
│   ── AGENTIC CORE (agentic_architecture.md) ──
├── executor.py                  # AgentExecutor: planned + native loops, checkpoint,
│                                #   cancel, same-error→HITL, errors[]/recovery_events[]
├── state_machine.py             # AgentState (10 states) + deterministic guards + history
├── goal_model.py                # frozen Goal + GoalContext pin (§12 goal preservation)
├── planner.py                   # TaskPlanner: LLM plan JSON + rule-based fallback
├── world_state.py               # AgentWorldState (confirmed/assumed), VerificationLog,
│                                #   detect_loop / detect_stuck
├── request_classifier.py        # Deterministic intent router (classify_need, LLM-free)
├── context_budget.py            # ContextBudget: token budget with priority layers
├── memory_bridge.py             # RAG recall / remember / conflicts / maintenance scheduler
├── cag.py, mag.py, hooks.py     # CAG cache, MAG, agent hook bus
├── input_validation.py, safety.py, degradation.py   # guards + telemetry
│
│   ── RUNTIME / SERVICES ──
├── server.py                    # FastAPI bridge: /api/chat, /api/status, /api/health/*,
│                                #   RunManager + POST /api/agent/run/{id}/cancel
├── server_health.py             # watchdog + health metrics
├── server_chat_history.py, server_circuit.py, server_process.py
├── mcp_bridge.py                # MCP tool bridge (sandbox path checks)
├── task_supervisor.py           # TaskSupervisor / CheckpointManager
├── tools/                       # ToolRegistry + §7 contract {ok, error, code, recoverable}
│   ├── base.py                  #   Tool/ToolMeta/ToolError + ErrorType enum
│   ├── fs_tools.py, shell_tools.py, python_tools.py, web_tools.py, extra_tools.py
│   └── workspace.py             #   workspace sandbox
├── skills/, mcp_servers/        # skill packs + MCP servers
│
│   ── DETERMINISTIC ENGINE (bricks → code, <10ms) ──
├── core/
│   ├── brick_system.py          # Semantic primitives (words, functions, types)
│   ├── knowledge_system.py      # Grammar & transformation rules
│   ├── requirements.py          # Requirement model (Part L)
│   └── intelligence/            # self_eval, orchestrator, creative/logic/…
├── resolver/
│   └── constraint_resolver.py   # Graph traversal + healing engine
├── chains/
│   └── chain_system.py          # Modular chains + chain healer
├── llm/
│   └── ollama_client.py         # Hybrid LLM fallback (Ollama)
├── quick_paths.py, igris_quick.py, layered_agent.py, layered_prompts.py, composition.py
├── assessor/                    # Refactor Machine — meta-assessment layer
│   ├── standards.py             #   the STANDARD: scales, weights, thresholds
│   ├── assessor.py              #   4-dim scoring (situation/info/volume/semantics)
│   ├── classifier.py            #   brick vs experience vs derived
│   ├── linker.py                #   relationship graph linking
│   └── telemetry.py             #   continuous process analysis
├── refactor_machine.py          # Orchestrator: assess → classify → link → analyze
├── benchmark.py                 # 12-task quality/speed harness
│
│   ── DOCS & OPS ──
├── agentic_architecture.md      # Pipeline → Loop → Agentic Work spec
├── ASSESSMENT_STANDARDS.md      # Human-readable standard (uz/en)
├── QUALITY_MAXIMIZATION_PLAN.md, CODER_AGENT_DEV_PLAN.md, RELEASE_CHECKLIST.md
├── test_*.py                    # 32 test files (unit + integration + e2e)
├── .github/workflows/           # CI: test (Py 3.10–3.12), nightly, benchmarks, release
├── config.yaml
└── requirements.txt
```

## Refactor Machine (brick vs experience)

Grounded in DIKW (Ackoff), Wang & Strong quality dimensions, and Tulving's
semantic/episodic memory split. It answers **"is this a brick or experience?"**
by scoring every item on 4 dimensions — **situation, information, volume,
query semantics** — then classifying, linking, and tracking the process stream.

```python
from refactor_machine import RefactorMachine
from igris_agent import IgrisAgent

agent = IgrisAgent(use_llm=False)
rm = RefactorMachine(agent)
rm.refactor_report()          # full assessment + suggestions
rm.evaluate_query("matritsani teskari top")  # query + telemetry
```

See `ASSESSMENT_STANDARDS.md` for the full standard.

## How it works

```
Input: "matritsani teskari top"
  ↓
Bricks: [matrix(accusative), inverse, find]
  ↓
Rule (Grammar): SOV → SVO = [find, inverse, matrix]
  ↓
Rule (Code): VERB+NOUN → function(argument) = np.linalg.inv(matrix)
  ↓
Output: np.linalg.inv(matrix)   (no monologue — just traversal)
```

Healing example:

```
If chain_math is missing:
  Available: chain_code (71% similar), chain_analysis (45% similar)
  Weights: [0.61, 0.39]
  Healed = 0.61 × chain_code + 0.39 × chain_analysis
```

## Run

```bash
cd Igris_brain
pip install -r requirements.txt
python igris_agent.py          # interactive CLI
python igris_agent.py --no-llm # deterministic only
```

Expected output:

```
Query: 'matritsani teskari top' [uz -> code]
Status: ✓
Confidence: 0.9xx
Engine: deterministic   Chains: ['chain_math']
Output:
np.linalg.inv(np.array)
```

## Commands in the CLI

- `status` — brick/knowledge/chain/LLM stats
- `heal chain_math` — show healing report for a missing chain
- `standards` — print the assessment standard
- `refactor` — full Refactor Machine report (inventory, links, telemetry)
- `telemetry` — continuous process-analysis stats
- `assess <query>` — query semantics + resolution + telemetry snapshot
- `exit` / `quit` — quit

## Memory / RAG integration (Igris_Memory)

The brain is wired to `Igris_Memory` via `memory_bridge.py`:

- **RAG recall** — before every resolution the agent recalls relevant memory and
  injects it into the LLM prompt (`resolve()` / `chat()`).
- **Auto-remember** — every resolution is persisted (L2 solution-memory + L1
  short-turn), duplicate-safe, and immediately re-indexed in BM25.
- **Hooks** — memory `HookSystem` fires `on_resolve` events; AutoDream
  consolidates L1 → L2 at session end.

```python
from igris_agent import IgrisAgent

a = IgrisAgent(memory_session="dev")
r = a.resolve("matritsani teskari top")   # recall before, remember after
```

## FastAPI bridge server (interface integration)

```bash
python server.py                     # http://127.0.0.1:8765
python server.py --model qwen3:8b --no-llm
```

Endpoints: `/api/chat`, `/api/chat/stream` (SSE), `/api/chat/history`,
`/api/agent/run` + `GET /api/agent/run/{id}` + `POST /api/agent/run/{id}/cancel`,
`/api/agent/respond` (HITL), `/api/status`, `/api/health/*`, `/api/llm/models`,
`/api/memory/search|status`, `/api/session/start|end`, `/api/system/*` —
~45 endpoints total. The `Igris_Interface` web app talks to this bridge
(see `web/backend.ts`); when the bridge is offline the UI falls back to
demo/mock mode.

## Benchmark harness

```bash
python benchmark.py                         # hybrid (LLM on)
python benchmark.py --no-llm                # deterministic only
python benchmark.py --out reports/bench.json
```

12 tasks (6 simple + 6 complex) measure quality (marker match) and speed
(duration, tokens/s). See `QUALITY_MAXIMIZATION_PLAN.md` for the latest
results and the improvement plan.

## Agentic architecture (v1.0)

The brain is a **harness**: a deterministic control core wrapped around an LLM.
LLM is only responsible for 3 things — plan drafting, tool-arg selection, and
the user-facing summary. Everything else (state machine guards, intent routing,
plan validation, JSON parsing, error classification, context budget) is
deterministic code.

- Core loop: `request_classifier` → `IgrisAgent.chat` → `AgentExecutor`
  (planned or native loop) → `StateMachine` guards → `VerificationLog` →
  COMPLETE only when VERIFIED.
- Resilience: per-tool timeouts, retry + LLM `_ask_fix`, same-error→HITL
  escalation (N=3), loop/stuck guards, cancellation endpoint, atomic
  checkpoints with resume, goal preservation.
- Observability: `/api/status`, `/api/health/*`, SM history (JSONL),
  `errors[]`/`recovery_events[]` per run, context budget report, latency.

Full spec: `agentic_architecture.md`; 6-phase audit history and the v1.0
diagram: `../Igris_info/plans/` (phase1–phase6 reports).

## Next steps

- Grow the brick bank to the ~4,000-node target (words, API surfaces, patterns).
- Optional: `sentence-transformers` + FAISS for semantic (vector) recall (§5 T3).
- Verified-only speech: cross-check final summaries against verification evidence.
- Long-running e2e test scenario (CI nightly).
