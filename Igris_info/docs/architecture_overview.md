# IGRIS Brain — Architecture Overview (Yangilangan)

## System Structure

```
IGRIS_Coder/
├── Igris_brain/          # Asosiy AI tizimi
│   ├── agent/            # Agent logikasi
│   │   ├── igris_agent.py          # Asosiy agent (ReAct loop)
│   │   ├── response_generator.py   # Javob formatlash
│   │   ├── memory_bridge.py        # RAG/MAG xotira ko'prigi
│   │   ├── request_classifier.py   # So'rov tasniflash
│   │   └── quick_paths.py          # Tez yo'llar (math, todo, etc.)
│   ├── smart_build/      # Smart Build Engine v2
│   │   ├── __init__.py             # Package entry
│   │   ├── state.py                # State machine + BuildSession
│   │   ├── discovery.py            # Project aniqlash
│   │   ├── analyzer.py             # Requirement tahlili
│   │   ├── context.py              # Context engine
│   │   ├── context_intelligence.py # Retrieval → Filter → Rank → Compress
│   │   ├── planner.py              # Build plan generator
│   │   ├── deterministic_executor.py # LLMsiz execution
│   │   ├── error_parser.py         # Raw error → structured evidence
│   │   ├── verifier.py             # Reality verification
│   │   ├── vision_integration.py   # Vision + Smart Build bridge
│   │   ├── engine.py               # Smart Build Engine v1
│   │   ├── engine_v2.py            # Smart Build Engine v2
│   │   └── chat_stream.py          # Micro-actions → semantic actions
│   ├── vision/           # Custom Vision System
│   │   ├── contracts.py            # BBox, Scene, Target, etc.
│   │   ├── capture.py              # Screen capture
│   │   ├── preprocess.py           # Image preprocessing
│   │   ├── detector.py             # Object detection
│   │   ├── ocr.py                  # OCR backend
│   │   ├── spatial.py              # Spatial engine
│   │   ├── ui_analyzer.py          # UI analysis
│   │   ├── context.py              # Vision context builder
│   │   ├── action_bridge.py        # Vision → Action
│   │   ├── temporal.py             # Temporal vision
│   │   ├── verify.py               # Action verification
│   │   ├── memory.py               # Vision memory
│   │   ├── uncertainty.py          # Uncertainty detection
│   │   ├── backends.py             # Vision backends
│   │   ├── performance.py          # Performance tracking
│   │   └── perception.py           # Perception engine
│   ├── lsp/              # LSP Integration
│   │   ├── client.py               # LSP client
│   │   └── manager.py              # LSP manager
│   ├── llm/              # LLM Integration
│   │   ├── omniroute_client.py     # OmniRoute gateway
│   │   └── model_selector.py       # Task-based model selection
│   ├── planning/         # Rejalashtirish
│   │   ├── planner.py              # TaskPlanner
│   │   ├── requirement_matrix.py   # Talablar matritsasi
│   │   └── llm_output_schema.py    # LLMOutput validatsiya
│   ├── executor/         # Bajarish
│   │   ├── executor.py             # AgentExecutor (ReAct loop)
│   │   └── checkpoint_integrity.py # Checkpoint saqlash
│   ├── state/            # Holat boshqaruvi
│   │   ├── state_machine.py        # Formal tranzitsiya
│   │   ├── goal_model.py           # Goal → Objective → Task
│   │   ├── context_budget.py       # Token cheklov
│   │   └── world_state.py          # Dunyo holati + loop detection
│   ├── task/             # Task boshqaruvi
│   │   ├── task_queue.py           # FIFO navbat + priority
│   │   ├── task_supervisor.py      # Supervisor (sub-agent)
│   │   └── todo_manager.py         # Todo CRUD
│   ├── tools/            # Vositalar (28+)
│   │   ├── base.py                 # ToolError protocol
│   │   ├── registry.py             # ToolRegistry (typed tools)
│   │   ├── fs_tools.py             # File system tools
│   │   ├── extra_tools.py          # todowrite, question
│   │   ├── lsp_tools.py            # LSP tools (6 ta)
│   │   ├── python_tools.py         # python_exec, run_command
│   │   └── mcp_bridge.py           # MCP server integratsiya
│   ├── monitor/          # Monitoring
│   │   ├── resource_monitor.py     # CPU/RAM/disk
│   │   ├── degradation.py          # Degradation tracking
│   │   └── probe_decisions.py      # Decision tracing
│   ├── verification/     # Tekshirish
│   │   ├── verification_comparison.py  # Natija solishtirish
│   │   └── svg_validator.py        # SVG tekshirish
│   ├── server/           # API server
│   │   ├── server.py               # FastAPI (60+ endpoints)
│   │   ├── server_chat_history.py  # Chat tarixi
│   │   ├── server_circuit.py       # Circuit breaker
│   │   ├── server_health.py        # Health check
│   │   └── server_process.py       # Server boshqarish
│   ├── web/              # Web strategiya
│   │   ├── web_strategy.py         # Web qidirish + grounding
│   │   └── web_verify.py           # Web javob tekshirish
│   ├── core/             # Core tizimlar
│   │   ├── brick_system.py         # Brick knowledge base
│   │   ├── knowledge_system.py     # Knowledge bank
│   │   └── intelligence.py         # Intelligence core
│   ├── chains/           # Chain tizimi
│   │   └── chain_system.py         # Chain registry + healer
│   ├── resolver/         # Constraint resolver
│   │   └── constraint_resolver.py  # Rule-based resolution
│   ├── skills/           # Skills
│   │   ├── svg-artist/             # SVG chizish
│   │   └── self-correction/        # Xato tuzatish
│   └── tests/            # Testlar (1065+)
├── Igris_Interface/      # Frontend
│   └── web/
│       └── components/
│           ├── SmartBuildPanel.tsx  # Smart Build UI
│           ├── ChatStreamView.tsx   # Chat Stream UI
│           └── ...
└── Igris_Memory/         # Memory tizimi
```
│   ├── safety/           # Xavfsizlik
│   │   └── input_validation.py     # Input validatsiya
│   ├── brain_graph/      # Graaf vizualizatsiya
│   ├── skills/           # Skill management
│   ├── tests/            # Testlar (875+ test)
│   └── config/           # Konfiguratsiya
│
├── Igris_Memory/         # Xotira tizimi
│   ├── memory/
│   │   ├── retrieval.py            # RAG/FTS5 qidirish
│   │   ├── save.py                 # Xotiraga saqlash
│   │   └── workspace_memory.py     # Workspace xotirasi
│   └── Igris_Commander/            # Commander moduli
│
└── Igris_info/           # Ma'lumotlar
    ├── state/            # Tizim holati
    ├── plans/            # Rejalar (Roadmap v4)
    └── docs/             # Hujjatlar
```

## Data Flow

```
User Input → Request Classifier → Clarification Gate → TaskPlanner
    ↓
Goal Model (Goal → Objective → Task)
    ↓
Executor (ReAct Loop):
  1. PLAN    → TaskPlanner breaks into steps
  2. ACT     → ToolRegistry executes tools
  3. OBSERVE → Collect results
  4. CORRECT → Self-correction (max 2 retries)
    ↓
Verification → Comparison Engine → Requirement Matrix
    ↓
ResponseGenerator → Voice Policy → User Output
```

## Key Components

### 1. State Machine (`state/state_machine.py`)
- 10 states: INPUT, UNDERSTAND, PLAN, EXECUTE, OBSERVE, VERIFY, UPDATE_STATE, CONTINUE, COMPLETE, FAIL, ESCALATE
- Guard functions for transitions
- Loop detection (stuck, infinite)

### 2. Goal Model (`state/goal_model.py`)
- Immutable goals (never change during execution)
- Goal → Objective → Task → Action hierarchy
- Goal preservation tracing

### 3. Task Queue (`task/task_queue.py`)
- FIFO + Priority (high > normal > low)
- Thread-safe
- Max concurrent control

### 4. Resource Control (`monitor/resource_monitor.py`)
- RAM, CPU time, Disk write limits
- Real-time monitoring
- Violation tracking + abort

### 5. Response Generator (`agent/response_generator.py`)
- Voice-aware formatting (short for voice, detailed for text)
- Progress, completion, failure formats
- History tracking

### 6. LLM Output Schema (`planning/llm_output_schema.py`)
- Intent classification (EXECUTE, CHAT, CLARIFY, UNKNOWN)
- Structured output validation
- Fallback defaults

## API Endpoints (56+)

| Category | Endpoints |
|----------|-----------|
| Chat | `/api/chat`, `/api/chat/stream`, `/api/chat/clarify` |
| Agent | `/api/agent/run`, `/api/agent/plan`, `/api/agent/task` |
| Memory | `/api/memory/search`, `/api/memory/status` |
| System | `/api/health`, `/api/system/services`, `/api/system/restart` |
| Tools | `/api/agent/tools`, `/api/agent/mcp` |
| Queue | `/api/queue/status` |
| Settings | `/api/settings/speed`, `/api/llm/models` |

## Test Coverage

- **875 tests** passing
- **17 scenario** test suite
- **36 new module** tests
- Coverage areas:
  - Orchestration (P00): 96%
  - Execution (P01): 95%
  - Task Management (P02): 90%
  - Safety (P03): 92%
  - Memory (P08): 93%
  - Intelligence (P11): 92%

## Roadmap v4 Status: 100% Complete

| § | Module | Status |
|---|--------|--------|
| §13 | ResponseGenerator | ✅ |
| §14 | LLMOutput Schema | ✅ |
| §15 | TaskQueue + ResourceMonitor | ✅ |
| §17 | ResourceControl | ✅ |
| §18 | Test Suite (17 scenarios) | ✅ |
| §19 | Architecture Audit | ✅ |
| §20 | Diagnostics Guide | ✅ |
