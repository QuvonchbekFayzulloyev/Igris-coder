# Igris Agentic Architecture: Pipeline → Loop → Agentic Work

Status: design spec, ready to scaffold.
Sources merged: (1) your own three-tier definitions, (2) the codebase-derived analysis of `igris_agent.py` / `PIPELINE_SPECS`, (3) your handwritten routing/requirement notes, (4) published agent-loop research (Anthropic, ReAct, Reflexion, harness-engineering literature).

---

## 0. Axioms (yours, unchanged)

These are the load-bearing definitions. Everything below is judged against them, not the other way around.

1. **Pipeline** — the set of actions needed to execute **one step**.
2. **Loop** — the set of pipelines needed to complete **one whole task**.
3. **Agentic Work** — the set of loops that activate to produce the result for **one user request**.

The three tiers nest: `Agentic Work → { Loop, Loop, ... } → { Pipeline, Pipeline, ... }`.

---

## 1. Research grounding

A few published control-flow shapes map cleanly onto this hierarchy, so the design below doesn't invent anything from scratch:

- **Anthropic's "Building Effective Agents"** distinguishes *workflows* (fixed code paths orchestrating LLM/tool calls) from *autonomous agents* (the model decides its own next step from environment feedback), and names five workflow shapes: prompt chaining, routing, parallelization, orchestrator-workers, and evaluator-optimizer. Their guidance is to start with the simplest workflow shape and only add autonomy where the task genuinely needs it.
- **ReAct** (Yao et al., 2022) — the canonical iterative loop: think → act → observe → think, repeating until the model emits a final answer. This is the shape underneath most "execution" iteration in coding agents.
- **Plan-and-Execute** — plan the full step sequence once, execute sequentially with a cheaper pass, and only re-plan on failure. Cheaper and more inspectable than ReAct, but less adaptive mid-task.
- **Reflexion / Self-Refine** (Shinn et al., 2023) — generate → self-critique → retry with the critique carried in context. Useful precisely when there's *no deterministic pass/fail signal* to check against (subjective/aesthetic output).
- **Build-verify loop / harness engineering** (recent coding-agent harness literature, e.g. the OpenDev terminal-agent paper) — plan → implement → verify against *executed evidence* (tests, compiler, schema, compliance check) → fix on failure, enforced as control flow rather than a prompt instruction. The same literature frames a coding agent as a **harness**: a central reasoning loop, surrounded by supporting subsystems (tool registry, context/memory, safety layer) that decide when the loop runs and what it's handed — which is a good structural analogue for your Agentic Work layer wrapping a Loop.

None of these are "the" answer — they're the small set of reusable loop *shapes* your `PIPELINE_SPECS` entries already, informally, pick from.

---

## 2. Where the prior analysis (the reverse-engineered doc) breaks its own rule

The earlier pass over `igris_agent.py` produced real, useful data — `PIPELINE_SPECS`, the SSE event names, the fact that it compiles — but then labeled six things as "loops": Clarification, Planning, Execution, Validation, Synthesis, Repair.

Check that against axiom 2: *a loop is the set of pipelines needed for one whole task.* Only **Execution** actually re-runs a pipeline stage repeatedly toward a task's completion. The rest fail the test:

- **Planning, Validation, Synthesis** each run once per task and hand off to the next stage — that's the definition of a **pipeline stage**, not a loop.
- **Clarification** doesn't execute any part of the task at all — it's a gate *before* a loop starts (or a pause *inside* one).
- **Repair** isn't a new loop type — it's the `review` stage being re-entered with a bound on attempts. It's an iteration *inside* the Execution loop, not a sibling of it.

Under your own definitions, the `PIPELINE_SPECS` table is *already* the loop registry — one loop per key (`chat`, `draw`, `ui_build`, `code`, `math`, `quick_math`, `weather`). That table doesn't need six more "loop" categories stacked on top; it needs each entry to declare **how it iterates**, which is the actual gap. Section 3.2 fixes that.

---

## 3. The three tiers, corrected

### 3.1 Pipeline (one step)

Contract for every stage, regardless of pipeline type: `shared task state in → one purposeful action (LLM call, tool call, or deterministic check) → shared task state out`. A stage should have one clear input/output, not a bag of side effects — same sharp-scoping standard you already apply elsewhere.

`PIPELINE_SPECS` stays as-is; it's grounded in real, compiling code:

| Pipeline type | Stages |
|---|---|
| `chat` | plan → review |
| `draw` | plan → edit → review |
| `ui_build` | plan → read → edit → test → review |
| `code` | plan → code → test → review |
| `reasoning` | plan → review |
| `math` | plan → review |
| `quick_math` | review |
| `weather` | review |

### 3.2 Loop (one whole task) — the missing piece: loop *shape*

A loop = a `PIPELINE_SPECS` entry **plus** an explicit iteration/exit rule. Five reusable shapes cover every entry in the table — pick one per pipeline type instead of leaving iteration implicit inside `chat_stream()`:

| Loop shape | Pattern | Exit condition | Fits |
|---|---|---|---|
| **Straight-through** | run the stage list once | stages complete | `quick_math`, `weather` (1 stage, no ambiguity) |
| **ReAct iterative** | think → act → observe, repeat | model emits final answer, or `max_iter` | `chat`, `reasoning` when a tool call is needed mid-conversation |
| **Plan-then-execute** | plan once → execute stages sequentially → re-plan only on failure | all stages pass, or re-plan budget exhausted | `ui_build` (5 stages — re-planning after every stage is wasted cost) |
| **Build-verify (evaluator-optimizer)** | edit → review against a *deterministic* check → repair → re-review | review passes, or `max_repair` | `draw`, `code` when compliance is checkable (colors, syntax, tests) |
| **Reflexion critique** | generate → self-critique (LLM judge, no ground truth) → retry with critique in context | critique signs off, or `max_repair` | the *subjective* half of `draw`/`code` reviews — e.g. "child style" has no deterministic check, so treat it as a critique loop, not a build-verify loop |

Note the last two rows: `draw` and `code` are not single-shape loops in practice. Split their `review` stage's failure handling by whether the failed criterion is checkable in code (color values, test pass/fail → build-verify) or judgment-only (style, tone → reflexion). Routing both through the same "review → repair" mechanism, as the current code does, is why a repair can pass compliance while still visibly not matching what was asked for.

### 3.3 Agentic Work (one user request)

Agentic Work is **not itself a loop** — axiom 3 says it's the layer that decides *which* loop(s) run and stitches the result together. Its parts are pipelines (single steps), not loops:

**a. Router pipeline (intent classification)** — this is where your handwritten "Chatting loop vs. Creator loop" note earns its place structurally, not just as a sketch. A single 8-way classifier over all of `PIPELINE_SPECS` is a real-time judgment call with 8 options — above the ≤5-option reliability ceiling for a small local model (`qwen2.5-coder`/`qwen3` on Ollama). Splitting it into two cheap stages fixes that:

  - *Stage 1 — family (n=2):* **chat-family** (`chat`, `reasoning`, `math`, `quick_math`, `weather` — the answer is the text itself) vs. **creator-family** (`draw`, `code`, `ui_build` — an artifact is produced and must pass a review stage).
  - *Stage 2 — type within family (n≤5):* only runs inside the family already selected, so it's never choosing among more than 5 things at once.

**b. Requirement-extraction pipeline** — this is your handwritten purpose/subject/object/detail note, and it's the same thing the prior analysis called "Part L." It runs once, produces a requirement block, and hands it to the loop's `plan` stage:

  - query purpose (*sorov maqsadi*)
  - query subject (*sorov subyekti*)
  - query object (*sorov obyekti*)
  - the object's core details/facts, and which of them the user already specified vs. left for the agent to fill in

**c. Human-in-the-loop gate** — not a loop, a pause/resume point. This is your "human in the loop — user's prompt gets fed back in at this node" note. If requirement-extraction is missing a required field, Agentic Work suspends, emits `clarify`, and — critically — **resumes the same loop** once the user answers, rather than starting a new independent request. Ask once; if the user's answer is still incomplete, proceed with a stated best-guess default rather than looping the question (matches the "idempotent" intent already in the prior draft).

**d. Single-loop dispatch (default path)** — most requests: router picks one loop, it runs, synthesis formats the result. This is the common case and should stay the cheapest path.

**e. Orchestrator dispatch (multi-loop, exception path)** — only for requests that genuinely span more than one loop type (e.g. "build this UI *and* write its tests" = a `ui_build` loop plus a `code` loop). This is Anthropic's orchestrator-workers shape: a thin orchestrator pipeline decides which loops run and in what order; each loop runs as a self-contained worker; results merge at synthesis. Don't build this path speculatively — wire it only when a request actually needs two loop types, since forcing every request through an orchestrator adds latency and decision surface for no benefit on the common case.

**f. Synthesis pipeline** — accumulates whichever loop(s) ran, formats the final output, runs exactly once, and always terminates — even on partial failure (give the partial result rather than nothing).

```
User request
     │
     ▼
Router pipeline (family → type, ≤5 options per stage)
     │
     ▼
Requirement-extraction pipeline ── missing field? ──► Human-in-the-loop gate
     │                                                        │
     │ ◄──────────────────────────────────────────────────────┘  (resumes same loop)
     ▼
 one Loop runs                (default: single-loop dispatch)
   [ plan → ... → review ]     — iterating per its declared shape (3.2)
     │
     │   needs a second loop type?
     └──────────► Orchestrator pipeline ──► second Loop runs in sequence
     ▼
Synthesis pipeline
     │
     ▼
Final result → User
```

---

## 4. Reading the handwritten notes

For transparency, here's what was pulled from the two photographed pages, since parts of the handwriting were genuinely hard to read — flag anything below that's wrong and it's a quick fix:

- A routing idea: once the request's intent is fully formed, send it to one of two loop families — read as "Chatting loop" vs. "Creator loop." → formalized as the family-stage of the router in 3.3.a.
- A requirement checklist for the user's prompt: query purpose, query subject, query object, and the object's core details — which the user did or didn't already specify. → formalized as the requirement-extraction pipeline in 3.3.b.
- "Agent = automated use of LLM/SLM to do computer tasks; theory: an agent is itself made of loops; human-in-the-loop is a node where the user's own prompt gets fed back in." → the human-in-the-loop gate in 3.3.c, and the overall Agentic-Work-wraps-Loop framing in section 3.

---

## 5. Event protocol — corrected mapping

Keep the existing SSE event names (renaming them is churn for no behavior change); what changes is what they *mean* under this model:

| Event | Corrected meaning |
|---|---|
| `layer_start` / `layer_done` | boundary of one **pipeline stage** inside the active loop — not a "loop" boundary |
| `loop_iteration` *(new)* | one repetition of a ReAct/build-verify/reflexion loop's cycle — currently implicit, should be explicit so the frontend can show "attempt 2 of 8" instead of inferring it from repeated `stage` events |
| `clarify` | the human-in-the-loop gate firing (section 3.3.c) — not a loop type |
| `validation_error` | a build-verify loop's review stage failing its deterministic check |
| `token` (`source` field) | unchanged — still tags origin (`llm`, `tool_name`, `mcp__tool_name`, `skill_name`) |
| `final_result` | synthesis pipeline's output |

---

## 6. Numeric guardrails

| Guardrail | Value | Governs |
|---|---|---|
| `max_iter` | 8 (existing default) | ReAct-iterative and build-verify loops |
| `max_repair` | 3 | build-verify and reflexion-critique retries within one review stage |
| clarification rounds | 1 | human-in-the-loop gate — ask once, then proceed on best-guess default |
| router option-space | ≤2 (family stage), ≤5 (type-within-family stage) | intent classification reliability on small local models |

---

## 7. Worked example

**Request:** "Draw a red apple in child style with a stem."

1. **Router** — family stage: creator-family (n=2 decision). Type stage: `draw` (n=3 decision, within creator-family only).
2. **Requirement-extraction** — purpose: produce an image; subject: apple; object details: color=red, style=child, has-stem=true. Nothing missing → human-in-the-loop gate doesn't fire.
3. **Loop dispatched:** `draw`, shape = build-verify for the checkable parts (color, stem present) + reflexion-critique for the judgment part (does it read as "child style").
   - `plan` stage (pipeline): turn the requirement block into an SVG generation brief.
   - `edit` stage (pipeline): `svg-artist` skill produces the SVG.
   - `review` stage (pipeline): deterministic check on color/stem (build-verify) and a critique pass on style (reflexion). If either fails, bounded repair (`max_repair`=3) re-enters `edit`.
4. **Synthesis** — one loop ran, no orchestrator needed; format the final message and emit `final_result`.

Total: 1 router pipeline + 1 requirement-extraction pipeline + 1 loop (draw, 3 stages, possibly repeating `edit → review` up to 3 times) + 1 synthesis pipeline. No "6 loops" — one loop, several pipelines, some of them repeating.

---

## 8. Build order

1. ✅ Keep `PIPELINE_SPECS` as the loop registry — it's already correct and compiling.
2. ✅ Add a `loop_shape` field to each `PIPELINE_SPECS` entry (values: `straight_through`, `react_iterative`, `plan_then_execute`, `build_verify`, `reflexion_critique`) so iteration logic stops being implicit inside `chat_stream()`.
3. ✅ Split the current intent classifier into the two-stage router (family, then type) described in 3.3.a.
4. ✅ Separate `max_iter` (loop-shape iteration cap) from `max_repair` (single-stage retry cap) as two distinct, independently tunable numbers — right now "repair" reads as folded into `review`'s side effects.
5. ✅ Move clarification out of the pipeline-stage list entirely; implement it as a pre-loop gate function that can suspend and resume, per 3.3.c.
6. ✅ For `draw`/`code`, split the `review` stage's failure handling by checkable-vs-judgment criteria (build-verify vs. reflexion-critique), instead of one undifferentiated repair path.
7. ✅ Extend the `layered-streaming` skill doc with the `loop_shape` per pipeline type and the new `loop_iteration` event, rather than replacing it — most of its event protocol is still correct.

**All 7 build-order steps completed.** Code changes:
- `PIPELINE_SPECS`: `loop_shape`, `max_iter`, `max_repair` fields added
- `_classify_family()` + `_classify_type()` — two-stage router (§3.3.a)
- `_build_pipeline()` returns `loop_shape`, `max_iter`, `max_repair`
- `_clarification_gate()` — pre-loop gate (§3.3.c)
- `_review_dispatch()` + `_build_verify_repair()` + `_reflexion_repair()` — split review (§3.2)
- `layered-streaming/SKILL.md` — `loop_iteration` event, corrected event meanings
- All tests passing, `py_compile` clean.

---

## 9. Scaling to complex tasks

Sections 1–8 cover a **single Loop**, plus a fixed **two-loop orchestrator** for the rare case of two loop types (3.3.e). That's enough for most requests. Genuinely complex, multi-part, open-ended tasks need four more capabilities — all of them live inside the **Agentic Work** tier; none of them change the Pipeline or Loop definitions in sections 3.1/3.2.

### 9.1 Recursive task decomposition (generalizes the fixed orchestrator)

The fixed two-loop orchestrator doesn't scale past a known, hardcoded pair of loop types. What complex tasks need instead, grounded in current long-horizon-agent research (Task-Decoupled Planning / TDP, ROMA, Plan-and-Act): a **Supervisor** that recursively decides, for any request, whether it's atomic or not.

- **Atomic** → dispatch straight to one Loop (3.2), exactly as today.
- **Non-atomic** → a **Planner** breaks it into a dependency graph (DAG) of sub-tasks, not a flat list — some sub-tasks can run independently, others must wait on a predecessor ("write the tests" depends on "scaffold the module").
- The Supervisor runs **topological scheduling**: at any moment, only dispatch the sub-task nodes whose predecessors are already `completed`.
- Each dispatched node gets its own **node-scoped context** — only its own spec plus whatever its predecessors produced, not the entire task's history. This is what keeps a 10-subtask complex task from having subtask #8 reasoning get diluted by irrelevant detail from subtask #2.
- Each node carries an explicit status: `pending → running → needs_more_steps | completed | failed`.
- On `failed` or an unexpected result, the Supervisor triggers **Self-Revision**: the Planner edits the dependency graph (add a fix-up node, re-route around the failure) instead of the whole task aborting.
- An **Aggregator** merges completed node outputs bottom-up once the graph is fully resolved, then hands off to the existing synthesis pipeline (3.3.f) unchanged.

This subsumes 3.3.e — a two-node DAG *is* the fixed orchestrator case, so you're not maintaining two separate mechanisms.

### 9.2 Working-context management inside long loops

Long-running loops (many `react_iterative` or `build_verify` cycles) accumulate tool observations until the context degrades ("context rot" in the recent long-horizon-agent literature — measurable performance loss as accumulated context grows, independent of whether it still fits the window). The fix isn't truncation, it's a **stack-style working set**: keep the current sub-goal and its live plan in full detail, and progressively compact older tool observations into short summaries once they're no longer load-bearing for the next decision — while explicitly preserving open dependency state ("node B is still blocked on node A") through the compaction, since that's exactly the kind of detail default summarizers drop.

This is the in-flight, per-loop half of context management. The persistent, cross-session half is already scoped in [[coder-agent-memory-system]] — reuse that rather than building a second memory system here.

### 9.3 Checkpointing (survive interruption, not just in-loop retry)

`max_repair` (section 6) already handles a stage failing and retrying *in memory*. Complex tasks also need to survive the process itself stopping — a crash, a closed terminal, a long pause — which an in-memory retry can't do. Two small files per active task, written after **every completed pipeline stage** (not just at the end):

- **Task-continuity file** — the goal, the dependency graph, and each node's status.
- **Execution-continuity file** — which loop is active, which stage, the last completed step.

Resuming reads both and picks up exactly where it left off. Pair this with an **operation log** (which files changed, per step) so a failed node can be rolled back cleanly. For a solo local tool, git-commit-at-checkpoint is enough for this — no bespoke time-travel/versioning subsystem needed (same right-sizing call as the memory-system work).

### 9.4 Budget awareness across the whole task

`max_iter` and `max_repair` already bound one Loop (section 6). A complex task with a five-node DAG needs one more number: a **total iteration/time budget owned by the Supervisor** and shared across every node, so five sub-tasks each independently spending their full `max_iter` can't silently multiply cost/latency by five. When the shared budget runs low, degrade to partial synthesis (report what's done, what's blocked) rather than continuing to spend silently or failing with nothing to show.

### What not to add

Matching the right-sizing standard used throughout this doc: a solo, local, Windows-native tool doesn't need multi-process agent-sync, a distributed task queue, or per-user isolation — those solve problems Igris doesn't have. Recursive decomposition + node-scoped context + two checkpoint files + git-commit rollback covers "murakkab task" completely without importing enterprise scope creep.

### Updated top-level flow

```
User request
     │
     ▼
Router + Requirement-extraction        (unchanged — 3.3.a / 3.3.b)
     │
     ▼
Supervisor: atomic?
     │
     ├── yes ──► dispatch directly to one Loop (3.2) ──────────────┐
     │                                                              │
     └── no ───► Planner builds a dependency graph (DAG)            │
                       │                                            │
                 topological scheduler:                             │
                 run all "ready" nodes (predecessors completed)     │
                       │                                            │
                 each ready node = 1 Loop, own node-scoped context  │
                       │                                            │
                 node status: pending/running/needs_more_steps/     │
                               completed/failed                     │
                       │                                            │
                 failed or unexpected? → Self-Revision:             │
                       Planner edits the graph, keeps going          │
                       │                                            │
                 (checkpoint both files after every completed node) │
                       │                                            │
                 Aggregator merges completed node outputs            │
                       │                                            │
                       ▼                                            │
                 Synthesis pipeline (unchanged — 3.3.f) ◄───────────┘
                       │
                       ▼
                 Final result → User
```

---

## 0. Files Created / Modified

| File | Action |
|---|---|
| `agentic_architecture.md` | **Created** — full design spec |
| `skills/layered-streaming/SKILL.md` | **Updated** — `loop_iteration` event, corrected event meanings |
| `igris_agent.py` | **Modified** — §8 build-order + §9 supervisor integration |
| `task_supervisor.py` | **Created** — §9 Supervisor + Planner + DAG + checkpointing |
| `test_agentic_pipeline.py` | **Updated** — 30 new tests |
| `test_task_supervisor.py` | **Created** — 39 tests |
| `test_real_tasks.py` | **Created** — 21 real task tests (PPTX, Game, Combined) |

### igris_agent.py changes:

**Build order 1–7:**
1. `PIPELINE_SPECS` — `loop_shape`, `max_iter`, `max_repair` fields
2. `_classify_family()` — two-stage router bosqich 1 (n=2)
3. `_classify_type()` — two-stage router bosqich 2 (n≤5)
4. `_clarification_gate()` — pre-loop gate (§3.3.c)
5. `_review_dispatch()` — build-verify vs reflexion-critique dispatcher
6. `_build_verify_repair()` / `_reflexion_repair()` — split repair
7. `chat()` + `chat_stream()` — clarification gate + `loop_iteration` event
8. `_chat_with_tools()` / `_chat_with_redraw()` — `on_loop_iteration` callback

**§9 Supervisor integration:**
9. `_run_supervisor()` — sync supervisor (chat())
10. `_run_supervisor_stream()` — streaming supervisor (chat_stream())
11. SSE events: `supervisor_start`, `node_start`, `node_done`, `supervisor_done`
12. Classifier: `powerpoint`, `pptx`, `game`, `o'yin` kabi so'zlar qo'shildi

### task_supervisor.py (§9):

| Komponent | Vazifa |
|-----------|--------|
| `TaskNode` | Sub-vazifa (pending/running/completed/failed) |
| `TaskDAG` | Bog'liqlik grafigi (topological order) |
| `TaskSupervisor` | Scheduler — ready nodlarni dispatch |
| `LLMDAGPlanner` | LLM orqali DAG planning |
| `WorkingContext` | Context rot prevention (compact) |
| `CheckpointManager` | Crash recovery (2 ta JSON fayl) |
| `GitCheckpointManager` | Git commit at checkpoint + rollback |

---

## Verification

- `python -m py_compile igris_agent.py` → **OK**
- `python -m py_compile task_supervisor.py` → **OK**
- `pytest` → **103 passed** (43 + 39 + 21)
- Frontend `tsc --noEmit` → OK (no frontend changes)
- Workspace image counts: **0** in both `Igris_brain\agent_workspace` and root `agent_workspace`
- Backend restarted and responding

---

## Summary: Why Redirection, Not Generic Work

**Key Insight**: IGRIS redirects requests before real work because:

1. **Intent must be classified** (chat vs creator) — different tools, different outputs, different compliance checks
2. **Requirements must be extracted** (Part L) — ensures complete before any work starts
3. **Generic work doesn't exist effectively** — the two families have fundamentally different expectations, tools, and success criteria

### The Two Families

| Family | Output | Compliance | Example |
|--------|--------|------------|--------|
| **chat-family** | Text answer | Logic/math correctness | "What's the weather?" |
| **creator-family** | SVG/UI/Code artifact | Visual/style compliance | "Draw an apple" |

### Why This Design Works

- **Reliability**: 2-stage classification keeps each stage ≤5 options (within small model capability)
- **Cost efficiency**: No wasted LLM calls or tool executions
- **User expectations**: Matches "tell me" vs "make me" intent
- **Error prevention**: Catches missing info early via clarification loop

### The Flow

```
User Request
    ↓
Router: Family? (chat vs creator, ≤2)
    ↓
Router: Type? (≤5 options)
    ↓
Requirement extraction: Missing fields?
    ↓
[If yes → Clarification gate → Ask user → Resume]
[If no → Loop dispatch → Run pipeline → Synthesis → Result]
```

**Bottom line**: Redirection ensures IGRIS does the *right* work the *first time*, not generic work that might do *some* work but not *the right work* for what you actually need.