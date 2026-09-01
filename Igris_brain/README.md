# IGRIS CODER AGENT — Brain

Super-light **coder agent** (NOT an LLM training project). A hybrid engine:

1. **Deterministic**: `Brick + Knowledge + Resolver` — a single graph traversal
   turns natural language (uz/en) into code in **<10ms** with a transparent rule trace.
2. **Healing**: missing capability chains are reconstructed algebraically from
   the most similar available chains.
3. **Hybrid LLM**: when deterministic confidence is low, delegates to a local
   Ollama model (qwen3:8b) — the same runtime the GUI assumes.

> Corrected framing: the original plan (`Temp_EXAMPle_IGRIS_CODER_Plan.md`)
> was titled "Coder Agent LLM". This **is** a coder agent — the 400M-parameter
> transformer-training pipeline is out of scope. We build the agent brain.

## Structure

```
igris_brain/
├── core/
│   ├── brick_system.py          # Semantic primitives (words, functions, types)
│   └── knowledge_system.py      # Grammar & transformation rules
├── resolver/
│   └── constraint_resolver.py   # Graph traversal + healing engine
├── chains/
│   └── chain_system.py          # Modular chains + chain healer
├── llm/
│   └── ollama_client.py         # Hybrid LLM fallback (Ollama)
├── assessor/                    # Refactor Machine — meta-assessment layer
│   ├── standards.py             #   the STANDARD: scales, weights, thresholds
│   ├── assessor.py              #   4-dim scoring (situation/info/volume/semantics)
│   ├── classifier.py            #   brick vs experience vs derived
│   ├── linker.py                #   relationship graph linking
│   └── telemetry.py             #   continuous process analysis
├── refactor_machine.py          # Orchestrator: assess → classify → link → analyze
├── ASSESSMENT_STANDARDS.md      # Human-readable standard (uz/en)
├── igris_agent.py               # Main orchestrator
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

Endpoints: `/api/status`, `/api/llm/models`, `/api/resolve`, `/api/chat`,
`/api/memory/search`, `/api/memory/status`, `/api/session/start|end`.
The `Igris_Interface` web app talks to this bridge (see `web/backend.ts`);
when the bridge is offline the UI falls back to demo/mock mode.

## Benchmark harness

```bash
python benchmark.py                         # hybrid (LLM on)
python benchmark.py --no-llm                # deterministic only
python benchmark.py --out reports/bench.json
```

12 tasks (6 simple + 6 complex) measure quality (marker match) and speed
(duration, tokens/s). See `QUALITY_MAXIMIZATION_PLAN.md` for the latest
results and the improvement plan.

## Next steps

- Grow the brick bank to the ~4,000-node target (words, API surfaces, patterns).
- Optional: `sentence-transformers` + FAISS for semantic (vector) recall.
- Streaming chat (SSE) in the bridge + interface.
