# Layered Agentic Loop with Token Streaming

**Skill ID**: `layered-streaming`  
**Purpose**: Multi-layered agentic processing pipeline with real-time token streaming to chat. User prompts flow through purpose-driven layers (reprompt → planning → execution → validation → synthesis) while streaming intermediate results, tool calls, and final accumulation.

## Architecture

```
User Prompt
    │
    ▼
┌─────────────────────────────────────┐
│  RE-PROMPT ENGINE                   │
│  - Role: coder/artist/researcher    │
│  - Task: concrete action            │
│  - Purpose: end goal                │
│  - Complexity: simple/moderate/complex│
│  - Capabilities: [code, draw, web]  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  LAYER CONSTRUCTOR                  │
│  - Builds N layers (2-6)            │
│  - Each layer: role + tools + deps  │
│  - Dependencies between layers      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  LAYER EXECUTION LOOP               │
│  ┌───────────┐ ┌───────────┐       │
│  │ Layer 1   │→│ Layer 2   │→ ...  │
│  │ planning  │ │ execution │       │
│  └───────────┘ └───────────┘       │
│      │             │               │
│   streaming     streaming          │
│   (tokens)      (tokens)           │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  SYNTHESIS                          │
│  - Accumulate all layer results     │
│  - Stream final answer              │
│  - Present to user                  │
└─────────────────────────────────────┘
    │
    ▼
  Final Result (streamed)
```

## Clarification Flow (Pause/Resume)

The clarification layer uses a **thread-safe pause/resume mechanism** to wait for user input:

```
User sends: "rasm chiz menga"
    │
    ▼
┌─────────────────────────────────────┐
│  RE-PROMPT detects:                │
│  - clarification_needed: "What     │
│    subject should I draw?"         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  CLARIFICATION LAYER               │
│  1. yield clarify event → frontend │
│  2. Generator BLOCKS (Event.wait)  │
│  3. Frontend shows question to user│
│  4. User types answer              │
│  5. POST /api/chat/clarify         │
│  6. Answer queue → generator RESUMES│
│  7. Re-analyze with clarified msg  │
└─────────────────────────────────────┘
    │
    ▼
  Continue with layers...
```

**API Endpoints:**
- `POST /api/chat/clarify` — Submit clarification answer `{session_id, answer}`
- `GET /api/chat/clarify/status` — Check clarification status `{session_id}`

**SSE Events:**
- `clarify` — `{type: "clarify", question: "...", session_id: "..."}`
- `token` — `{type: "token", content: "User: <answer>", source: "user"}`

**Timeout:** Default 5 minutes. If no answer, the agent proceeds with the original request.

## Implementation Files

### `layered_agent.py` — Core Orchestrator

> **Holat (yangilangan):** LayeredAgent endi server chat oqimini boshqarmaydi —
> kanonik yo'l `IgrisAgent.chat_stream()` (review loop + resync bilan, §8.1).
> LayeredAgent compatibility API + clarification pause/resume infrastrukturasi
> sifatida saqlangan (testlari bilan: `tests/test_layered_agent.py`).

```python
from layered_agent import LayeredAgent, create_layered_agent

# Create from existing IgrisAgent
agent = IgrisAgent(...)
layered = create_layered_agent(agent)

# Run the layered loop
for event in layered.run_layered("React dashboard qurib ber"):
    # SSE events streamed to chat
    print(event)
```

**Key Classes:**
- `RepromptEngine` — Analyzes user prompt → role/task/purpose
- `LayerConstructor` — Builds execution layers from analysis
- `LayeredAgent` — Main orchestrator, runs layer-by-layer with streaming
- `ClarificationManager` — Pause/resume mechanism for user clarification (thread-safe)

### `layered_prompts.py` — Prompt Templates

Contains all prompt templates for:
- RE_PROMPT_SYSTEM — Role/task/purpose extraction
- LAYER_CONSTRUCTION_SYSTEM — Layer building
- LAYER_EXECUTION_PROMPTS — Per-layer instructions
- TOOL_STREAMING_PROMPTS — Tool-level streaming messages
- FINAL_SYNTHESIS_SYSTEM — Final answer formatting

## SSE Event Protocol

Each event is a JSON object with `type` field. Updated to match the agentic architecture specification (§3.2 + §5):

| Event | Fields | Description |
|---|---|---|
| `layer_start` | `layer`: str | One **pipeline stage** begins (plan/read/edit/test/review) — not a loop boundary |
| `layer_done` | `layer`, `status`, `summary` | Pipeline stage completed |
| `loop_iteration` | `iteration`: int, `max_iter`: int, `shape`: str | One repetition of a ReAct/build-verify/reflexion loop cycle — frontend shows "attempt 2 of 8". `max_iter` = max(default, PIPELINE_SPECS `max_iter`) — halol budget (§8.1) |
| `done` | `content`, `review`?, `completion`, `structure_check`?, `self_eval` | Canonical chat_stream terminator. `review` = halol repair audit izi (quyida). `completion` transcript record (`completion.review`, `completion.supervisor` bilan) |
| `tool_start` | `tool`, `layer`, `description` | Tool execution began |
| `tool_done` | `tool`, `layer`, `result` | Tool completed |
| `mcp_start` | `mcp`, `layer`, `description` | MCP server call began |
| `mcp_done` | `mcp`, `layer`, `result` | MCP call completed |
| `skill_start` | `skill`, `layer`, `description` | Skill activated |
| `skill_done` | `skill`, `layer`, `result` | Skill output available |
| `token` | `content`, `source`: str | Streaming text chunk (source: llm/tool/skill/mcp) |
| `stage` | `stage`, `detail`, `layer` | Pipeline stage info |
| `clarify` | `question`: str, `missing_fields`: list | Human-in-the-loop gate (§3.3.c) — ask user for missing info once |
| `validation_error` | `issue`: str | Build-verify loop's review stage failing its deterministic check |
| `final_result` | `content`, `duration_ms`, `layers_executed` | Final accumulated answer |
| `end` | — | Stream terminator |

### loop_iteration event

The `loop_iteration` event is emitted once per repetition of an iterative loop shape. It replaces the previous pattern of inferring iteration count from repeated `stage` events.

```json
{"type": "loop_iteration", "iteration": 2, "max_iter": 8, "shape": "react_iterative"}
```

Supported shapes and their exit conditions:
- `straight_through` — no iteration (single pass)
- `react_iterative` — think → act → observe, repeat until final answer or `max_iter`
- `plan_then_execute` — plan once, execute stages sequentially
- `build_verify` — edit → review against deterministic check → repair, up to `max_repair`
- `reflexion_critique` — generate → self-critique → retry, up to `max_repair`

**Halol budget (§8.1):** `max_rounds = max(default_rounds, PIPELINE_SPECS max_iter)` —
spec kam budget bergan ham bajaruvchi loop'ni to'xtatmaydi, katta budget oshiriladi.
`_enforce_action_evidence` nudge retry ichidagi redraw ham xuddi shu
`max_rounds`/`loop_shape` ni oladi — evidence loop dekorativ emas.

## Review Loop Events (§8.1 halol kontrati)

Review repair loop'i ENDI HAQIQIY: content FAQAT mustaqil `review_fn` qayta
tekshiruvi tasdiqlasa almashtiriladi. Soxta "repaired" imkonsiz. Eventlar:

### `done.review` — halol repair audit izi

```json
{"type": "done",
 "content": "...final javob...",
 "review": {"ok": true, "repaired": true, "attempts": 2, "method": "build_verify"},
 "completion": {"review": {"ok": true, "repaired": true, "attempts": 2, "method": "build_verify"}}}
```

| Field | Ma'no |
|---|---|
| `ok` + `repaired` | review_fn tasdiqlagan haqiqiy yutuq — content ALMASHTIRILGAN |
| `ok: false`, `attempts > 0` | retry urinildi, tasdiqlanmadi — ORIGINAL content saqlangan |
| `note: "verifier unavailable"` | verifier yo'q — "repaired" e'lon qilinmagan |
| `attempts: 0`, maydon yo'q | retry UMUMAN boshlanmagan (max_repair=0, LLM yo'q, muammo yo'q) |

Frontend tavsiyasi: `review.repaired == true` → "tuzatish tasdiqlandi (N urinish)";
`attempts > 0 && !repaired` → "tuzatib bo'lmadi — original javob saqlandi" (ishonch
psti ko'rsatkichi `self_eval.confidence` bilan mos).

### `completion.supervisor` — DAG audit izi

```json
"completion": {"supervisor": {"status": "partial", "iterations_used": 5,
                              "nodes_count": 2, "failed_nodes": ["sub_0_code"]}}
```

chat_history.jsonl'ga yoziladi — keyingi audit uchun qaysi node yiqilgani yo'qolmaydi.

### Cache/RAG resync garant (ko'rinmas, lekin kafolatlangan)

Review content'ni almashtirsa `_review_resync` CAG/RAG yozuvini YANGI matn bilan
yangilaydi (`_finalize` va stream `_done()` ichida). Aks holda keyingi bir xil
so'rov CAG'dan eskirgan (tasdiqlanmagan) javobni qayta-qayta olardi. Frontend
buni ko'rmaydi — faqat natija: keshda HECH QACHON tasdiqlanmagan matn yashamaydi.

### `validation_error` — deterministik check rad etishi

`_domain_verify` soxta pozitivlardan himoyalangan (`x > 5`, `placeholder="Email"`,
JS/prose — LEGIT). `validation_error` ko'rinsa — bu HAQIQIY muammo (sintaksis
xatosi, markup balanssizligi, TODO placeholder) yoki uning LLM retry'ining
natijasi.

## Example SSE Stream

```
data: {"type": "stage", "stage": "analyze", "detail": "Prompt tahlil qilinmoqda...", "layer": "meta"}

data: {"type": "layer_start", "layer": "planning"}

data: {"type": "stage", "stage": "plan", "detail": "Qatlamli reja tuzildi: 4 qatlam", "layer": "planning"}

data: {"type": "layer_done", "layer": "planning", "status": "complete", "plan": {"layers": ["planning", "execution", "validation", "synthesis"]}}

data: {"type": "layer_start", "layer": "execution"}

data: {"type": "tool_start", "tool": "write_file", "layer": "execution", "description": "Creating dashboard component..."}

data: {"type": "token", "content": "\n🔧 [execution] Creating dashboard component...", "source": "write_file"}

data: {"type": "token", "content": "  ✅ Created src/components/Dashboard.tsx", "source": "write_file"}

data: {"type": "tool_done", "tool": "write_file", "layer": "execution", "result": "Created src/components/Dashboard.tsx"}

data: {"type": "tool_start", "tool": "run_command", "layer": "execution", "description": "Running npm install..."}

data: {"type": "token", "content": "\n🔧 [execution] Running npm install...", "source": "run_command"}

data: {"type": "token", "content": "  ✅ Dependencies installed successfully", "source": "run_command"}

data: {"type": "tool_done", "tool": "run_command", "layer": "execution", "result": "Dependencies installed"}

data: {"type": "token", "content": "\n✅ [execution] Bajarildi — 2 amal", "source": "execution"}

data: {"type": "layer_done", "layer": "execution", "status": "complete", "summary": "Created dashboard component and installed dependencies"}

data: {"type": "layer_start", "layer": "synthesis"}

data: {"type": "token", "content": "✅ **Coder** — Deliver a working React dashboard application", "source": "synthesis"}

data: {"type": "token", "content": "\n**Execution layer:**", "source": "synthesis"}

data: {"type": "token", "content": "  Tools used: write_file, run_command", "source": "synthesis"}

data: {"type": "final_result", "content": "✅ Created React dashboard with Dashboard.tsx component and installed all dependencies.", "duration_ms": 12345.67, "layers_executed": ["planning", "execution", "synthesis"]}

data: {"type": "end"}
```

## Integration with server.py

**Holat (yangilangan):** `/api/chat/stream` endi KANONIK `IgrisAgent.chat_stream()`
oqimidan foydalanadi — u klassifikatsiya, xavfsizlik, verification, memory va
completion'ni o'z ichida oladi (review loop + resync shu yo'lda). LayeredAgent
faqat **compatibility API** sifatida qoldi: server undan faqat
`CLARIFICATION_MANAGER` (pause/resume gate) uchun foydalanadi.

```python
@app.post("/api/chat/stream")
def api_chat_stream(req: ChatRequest):
    from fastapi.responses import StreamingResponse
    agent = get_agent()
    sid = req.session_id or f"conv-{uuid.uuid4().hex[:12]}"

    def generate():
        CHAT_HISTORY.add_message(sid, "user", req.message)
        yield sse({"type": "meta", "session_id": sid})
        for ev in agent.chat_stream(
            req.message,
            history=req.history,
            use_memory=req.use_memory,
        ):
            yield sse(ev)  # stage/loop_iteration/tool_*/done — §8.1 kontrat bilan
        yield sse({"type": "end"})

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Terminatsiya kontrati:** oqim `done` event'siz tugasa — frontend uni xato
sifatida qabul qiladi ("stream finished without done"). Clarify holatida ham
terminal `done` yuboriladi (matn = savol).

## Key Design Decisions

1. **Reprompt Engine** — Every user prompt is re-analyzed to determine the optimal agent role, concrete task, and end purpose. This ensures the agent doesn't just "do something" but does the RIGHT thing.

2. **Tool Engineering** — Tools, MCP servers, and skills are used deliberately within layers. Each tool in a layer MUST serve that layer's purpose — no decorative tool calls.

3. **Streaming at Every Level** — Token streaming happens for:
   - Layer start/done events
   - Tool start/done events  
   - MCP start/done events
   - Skill start/done events
   - Intermediate tokens during tool execution
   - Final synthesis streaming

4. **Result Accumulation** — All layer results are collected and passed forward. The synthesis layer has access to everything that happened before it.

5. **Fallback** — If LLM is unavailable, the system falls back to deterministic layer construction based on regex analysis and predefined layer templates.

## Layer Types

| Layer | Purpose | Tools Used | Streaming |
|---|---|---|---|
| `clarification` | Ask missing info | — | Yes |
| `planning` | Build execution plan | read_file, list_files | Yes |
| `execution` | Do the actual work | write_file, run_command, draw, etc. | Yes |
| `validation` | Verify results | read_file, run_command | Yes |
| `synthesis` | Present final answer | LLM | Yes |

## Skills Integration

This skill is automatically loaded by `SkillManager`. It structures the entire agentic loop — individual task layers can still call `use_skill` for specialized sub-tasks (e.g., `svg-artist` for drawing, `plan-first-fix` for repair workflows).

The layered approach ensures that:
- **Skills are not decorative** — they're used when their specific capability is needed
- **MCP tools are purposeful** — called within the right layer context
- **Native tools serve the layer** — write_file in execution, read_file in validation, etc.
