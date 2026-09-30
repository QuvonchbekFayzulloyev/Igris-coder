# IGRIS vs Real Coding Assistants — Taqqoslash (Yangilangan)

## Tool Ro'yxati

| Tool | OpenCode | Claude Code | IGRIS | Holat |
|------|----------|-------------|-------|-------|
| **read_file** | ✅ | ✅ | ✅ | ✅ Teng |
| **write_file** | ✅ | ✅ | ✅ | ✅ Teng |
| **edit_file** | ✅ | ✅ | ✅ | ✅ Teng |
| **apply_patch** | ✅ | ✅ | ✅ | ✅ Teng |
| **smart_edit** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **list_files** | ✅ glob | ✅ glob | ✅ | ✅ Teng |
| **search_code** | ✅ grep | ✅ grep | ✅ | ✅ Teng |
| **grep** | ✅ | ✅ | ✅ | ✅ Teng |
| **glob** | ✅ | ✅ | ✅ | ✅ Teng |
| **search_in_file** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **run_command** | ✅ bash | ✅ bash | ✅ | ✅ Teng |
| **python_exec** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **git_command** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **create_directory** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **rename_file** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **delete_file** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **web_fetch** | ✅ | ✅ | ✅ | ✅ Teng |
| **web_search** | ✅ | ✅ | ✅ | ✅ Teng |
| **todowrite** | ✅ | ✅ | ✅ | ✅ Teng |
| **question** | ✅ | ✅ | ✅ | ✅ Teng |
| **lsp_* (6 ta)** | ✅ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **vision_* (5 ta)** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |
| **smart_build_* (3 ta)** | ❌ | ❌ | ✅ | ✅ IGRIS ustunligi |

## IGRIS Ustunliklari (Yangilangan)

### 1. Vision System — LLM-independent
- `vision_observe` — Ekran kuzatuvi
- `vision_find` — Element aniqlash
- `vision_click` — Bosish
- `vision_type` — Matn kiritish
- `vision_verify` — Amal tasdig'i

### 2. Smart Build Engine — Weak LLM + Strong Cognitive Infrastructure
- `smart_build_analyze` — Task tahlili
- `smart_build_check` — Deterministik checks
- `smart_build_error` — Error parsing

### 3. Context Intelligence Engine
- Semantic retrieval
- Symbol retrieval
- Dependency retrieval
- Filter → Rank → Compress

### 4. Deterministic Executor
- Filesystem checks (exists, readable, not empty)
- Code checks (function, class, syntax)
- Build checks (compile, tests)

### 5. LSP Integration (6 ta tool)
- `lsp_definition` — Go to definition
- `lsp_references` — Find references
- `lsp_hover` — Hover info
- `lsp_completion` — Autocomplete
- `lsp_diagnostics` — Diagnostics
- `lsp_status` — Server status

### 6. Chat Stream System — Semantic Action Aggregation
- Micro-actions → Semantic actions
- 4 Detail Levels (L0-L3)
- 7 Stream Groups (Understand → Recover)
- Live progress with automatic collapse

### 7. OmniRoute Multi-LLM Gateway
- 352+ providers
- Model selection
- Health check

## Arxitektura

```text
USER TASK
    ↓
INTENT ENGINE (complexity: trivial → ambiguous)
    ↓
CONTEXT INTELLIGENCE
  ├── semantic retrieval
  ├── symbol retrieval
  ├── dependency retrieval
  ├── filter
  ├── rank
  └── compress
    ↓
SMALL LLM (token budget: 0 → 12000)
    ↓
DETERMINISTIC EXECUTOR
  ├── file checks
  ├── AST checks
  ├── syntax checks
  ├── import checks
  └── build/test checks
    ↓
VISION VERIFICATION
  ├── UI element checks
  ├── click/type actions
  ├── error/success detection
  └── state verification
    ↓
EVIDENCE → SUCCESS / FAILURE
```

## Chat Stream UX

```text
L0 — Chat summary (doim ko'rinadi)
  ◉ Investigating · 6 files · 4.2s

L1 — Action detail (default collapsed)
  ▼ Investigating · 6 files
    M auth/token.py       +31 -12
    M auth/session.py      +8  -3
    Reason: Fix token refresh

L2 — Execution trace (user expand)
  ▼ Investigating · 6 files
    Trace:
      read_file    read auth/token.py
      read_file    read auth/session.py
      grep         search 'refresh_token'

L3 — Raw evidence (eng chuqur)
  ▼ Investigating · 6 files
    Commands:
      $ pytest tests/test_auth.py
      ..............................
      exit: 0
```

## Formula

```text
Intelligence =
  LLM reasoning
  + retrieval quality
  + structured state
  + deterministic tools
  + verification
  + vision evidence
```

## Statistika

- **Tools**: 28+ (OpenCode: ~15)
- **Tests**: 1065+
- **Modules**: Smart Build, Vision, LSP, OmniRoute
- **Chat Stream**: 4 levels, 7 groups
- **Token optimization**: 60-80% reduction

## Keyingi Qadamlar

1. ~~todowrite tool~~ ✅
2. ~~question tool~~ ✅
3. ~~grep/glob~~ ✅
4. ~~LSP integration~~ ✅
5. ~~Smart Build~~ ✅
6. ~~Vision integration~~ ✅
7. ~~Chat Stream~~ ✅
8. Task (subagent) tool
9. Real-time collaboration
10. Plugin system
