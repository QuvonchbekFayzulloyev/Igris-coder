# IGRIS CODER AGENT — Smart Planning & Execution: Gap Analysis va Qurilish Rejasi

**Sana:** 2026-08-04
**Holat:** tahlil boshlangan — reja v2.0 (smart planning & execution)

---

## 1. Maqsad

Coder agent haqiqiy ishlaydigan, kuchli va zamonaviy bo'lishi uchun:
- **Smart planning** — taskni tushunish, bosqichlarga bo'lish, reja tuzish
- **Execution** — fayllarni o'qish/yozish, kod yozish, buyruqlar bajarish, test ishga tushirish
- **Self-correction** — xatolarni ko'rib, o'zini tuzatish
- **Tool use** — LLM real vositalarni (fayl, terminal, python) chaqiradi

Bu hujjat: (1) nima bor / nima yo'q, (2) arxitektura, (3) qurilish bosqichlari.

---

## 2. Hozirgi holat (Gap Analysis) — NIMA BOR

### 2.1 Igris_brain (Python)

| Modul | Holat | Vazifasi |
|---|---|---|
| `core/brick_system.py` | ✅ ishlaydi | Semantik primitivlar (15 brick) |
| `core/knowledge_system.py` | ✅ ishlaydi | Grammatika + transformatsiya qoidalari (8 qoida) |
| `resolver/constraint_resolver.py` | ✅ ishlaydi | Grafik traversal + healing (<10ms) |
| `chains/chain_system.py` | ✅ ishlaydi | Modulli zanjirlar + healer |
| `llm/ollama_client.py` | ✅ ishlaydi | Ollama chat (qwen2.5-coder:7b) |
| `assessor/` + `refactor_machine.py` | ✅ ishlaydi | 4-o'lchovli baholash, telemetriya |
| `memory_bridge.py` | ✅ yangi | Igris_Memory RAG: recall/remember |
| `server.py` | ✅ yangi | FastAPI bridge (resolve/chat/memory) |
| `benchmark.py` | ✅ yangi | 12 task sifat+tezlik o'lchovi (**100% pass**) |
| `igris_agent.py` | ✅ | resolve() + chat() — LEKIN faqat javob beradi |

### 2.2 Igris_Memory (to'liq tayyor)

- L1 Runtime (18 tur), L2 Persistent (24 tur), L3 Config, L4 Retrieval (BM25+RRF)
- HookSystem, AutoDream, TimeTravel, PoisoningProtection, MultiAgentSync
- `MemoryAPI`: remember/recall/search/context

### 2.3 Igris_Interface (interfeys tayyor, lekin mock)

- Web (React), Desktop (Tauri), CLI (Ink)
- **ToolCallCard** — `read_file`, `apply_patch`, `run_command` ko'rsatishga tayyor (faqat mock)
- **PipelineStepper** — Plan → Read → Edit → Test → Review (faqat mock stage)
- **Terminal paneli** — mock buyruq chiqishlari

---

## 3. GAP ANALYSIS — NIMA YO'Q (muhim bo'shliqlar)

| # | Yetishmayotgan qobiliyat | Nega muhim | Holat |
|---|---|---|---|
| G1 | **Tool registry** (read_file, write_file, apply_patch, run_command, python_exec) | Agent fayl tizimida ishlay olmaydi — faqat javob qaytaradi | ❌ yo'q |
| G2 | **Workspace abstraction** (xavfsiz fayl sandbox, real katalog) | Agent "ishtirokchi" emas, "suhbatdosh" bo'lib qolgan | ❌ yo'q |
| G3 | **Planner** (taskni bosqichlarga bo'lish, LLM yordamida) | "Smart planning" — reja tuzmasdan execution yo'q | ❌ yo'q |
| G4 | **Executor / Agent loop** (ReAct: plan→act→observe→correct) | Haqiqiy "executing" — iterativ bajarish sikli yo'q | ❌ yo'q |
| G5 | **Self-correction** (xato → qayta urinish, test natijalarini o'qish) | Kuchli agent xatolardan o'rganadi | ❌ yo'q |
| G6 | **LLM tool-calling** (Ollama tools API) | Model vositalarni o'zi tanlay olmaydi | ⚠️ qisman (client tools'ni yubormaydi) |
| G7 | **Code sandbox** (python subprocess xavfsiz bajarish) | Kodni bajarib, natijani qaytarish | ❌ yo'q |
| G8 | **Task state / context** (bosqichlar holati, reja kuzatuv) | Uzoq tasklarda agent adashadi | ⚠️ memory'da plan-turi bor, lekin agent ishlatmaydi |
| G9 | **Interfeys → real toolcall** | ToolCallCard/PipelineStepper mock — real server natijalarini ko'rsatishi kerak | ❌ |

### Xulosa (diagnostika)

Igris hozir **"qanday qilishni biladigan, lekin hech narsa qila olmaydigan"** agent.
U qoida asosida kod parchalari va LLM javoblarini qaytaradi, ammo:
- fayl ocholmaydi, yozolmaydi
- buyruq bajara olmaydi
- reja tuza olmaydi, bajarishni kuzata olmaydi
- xatolarni ko'rib o'zini tuza olmaydi

Interfeysdagi `ToolCallCard`, `PipelineStepper`, terminal panel — barchasi **mock**.
Memory'da planning/task/decision turlari bor, lekin agent ularni ishlatmaydi.

---

## 4. TARGET ARXITEKTURA (quriladigan tizim)

```
                  Igris_Interface (React/Tauri)
                           │  HTTP
                           ▼
                Igris_brain/server.py (FastAPI)
                           │
        ┌──────────────────┼───────────────────┐
        ▼                  ▼                   ▼
   /api/agent/plan   /api/agent/run      /api/resolve /api/chat
        │                  │
        ▼                  ▼
   ┌──────────┐      ┌──────────────┐
   │ Planner  │      │  Executor    │  (ReAct loop)
   │ (LLM)    │      │  plan → act  │
   └──────────┘      │  → observe   │
                     │  → correct   │
                     └──────┬───────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
      ┌──────────┐   ┌───────────┐   ┌──────────────┐
      │  Tools   │   │ Workspace │   │ MemoryBridge │
      │ read/wr  │   │ (sandbox) │   │ (RAG + state)│
      │ apply_pt │   │           │   └──────────────┘
      │ run_cmd  │   └───────────┘
      │ py_exec  │
      └──────────┘
```

### Yangi modullar (Igris_brain/)

```
tools/
  __init__.py          # ToolRegistry — barcha vositalar ro'yxati
  workspace.py         # Workspace: xavfsiz fayl sandbox (cwd cheklovi)
  fs_tools.py          # read_file, write_file, apply_patch, list_files
  shell_tools.py       # run_command (subprocess, timeout, sandbox)
  python_tools.py      # python_exec (izolyatsiya, timeout)
planner.py             # TaskPlanner: task → bosqichlar (LLM yoki qoidalar)
executor.py            # AgentExecutor: ReAct loop, self-correction
agent_loop.py          # (chiziqda integratsiya) server endpointlari uchun
```

---

## 5. QURILISH BOSQICHLARI (ustuvorlik bilan)

### Bosqich 1 — Asos (eng muhim) 🎯 HOZIR QURILADI
| # | Vazifa | Natija |
|---|---|---|
| 1.1 | `tools/workspace.py` | Xavfsiz fayl sandboxi (cwd, whitelist, path traversal himoyasi) |
| 1.2 | `tools/fs_tools.py` | `read_file`, `write_file`, `apply_patch`, `list_files` |
| 1.3 | `tools/shell_tools.py` | `run_command` (subprocess, timeout, output capture) |
| 1.4 | `tools/python_tools.py` | `python_exec` (kod bajarish, timeout, stdout capture) |
| 1.5 | `tools/__init__.py` | `ToolRegistry` — schema + execute birlashtiruvchi |
| 1.6 | `planner.py` | `TaskPlanner.plan(task) → [bosqichlar]` (LLM yordamida) |
| 1.7 | `executor.py` | `AgentExecutor.run(task)` — ReAct loop, max 8 iter, self-correct |

### Bosqich 2 — Integratsiya
| # | Vazifa | Natija |
|---|---|---|
| 2.1 | Server'ga endpointlar: `/api/agent/plan`, `/api/agent/run` | Interfeys real reja/execution olishi |
| 2.2 | Agent holatini memory'ga yozish (planning-memory, decision-log) | Task state kuzatiladi |
| 2.3 | Interfeys: ToolCallCard real natijalar, PipelineStepper real stage | Mock → real |

### Bosqich 3 — Kuchaytirish
| # | Vazifa | Natija |
|---|---|---|
| 3.1 | LLM tool-calling (Ollama tools API) | Model vositalarni o'zi tanlaydi | ✅ bajarildi |
| 3.2 | Self-correction loop testlari | Xatoni topib tuzatish |
| 3.3 | Benchmark: agent-task suite (fayl yaratish → test) | Sifat o'lchovi |

---

## 5.1 Bajarilgan holat (2026-08-04) ✅

| # | Vazifa | Holat | Tekshiruv natijasi |
|---|---|---|---|
| 1.1 | `tools/workspace.py` — xavfsiz fayl sandbox | ✅ | traversal bloklanadi (`../../etc/passwd` → ValueError) |
| 1.2 | `tools/fs_tools.py` — read/write/apply_patch/list | ✅ | write+read ishlaydi, registry orqali `{'ok': True}` |
| 1.3 | `tools/shell_tools.py` — run_command | ✅ | `python sum.py` bajarildi, stdout qaytdi |
| 1.4 | `tools/python_tools.py` — python_exec | ✅ | `print(2+3)` → `5` |
| 1.5 | `tools/__init__.py` — ToolRegistry | ✅ | 6 ta tool: read/write/apply_patch/list/run/python |
| 1.6 | `planner.py` — TaskPlanner | ✅ | LLM: 2 bosqichli reja, fallback: qoidalar |
| 1.7 | `executor.py` — AgentExecutor (ReAct) | ✅ | **End-to-end test:** `greet.py` yaratish + bajarish `status: ok` |
| 2.1 | Server: `/api/agent/plan`, `/api/agent/run`, `/api/agent/tools`, `/api/agent/workspace` | ✅ | Plan: `engine=llm` 2 bosqich; Run: `status=ok` 2 tool call |
| 2.3 | Interfeys: `⚡ task` → runAgent, real ToolCallCard | ✅ | store `runAgent` + AgentConsole `⚡` buyrug'i; tsc o'tdi |
| 3.2 | `test_executor.py` — 13 test | ✅ | traversal, patch (2 format), python_exec edge, tool limit — hammasi PASS |
| — | Review tuzatishlari | ✅ | L2 memory tipi `experience`; apply_patch CRLF; max_iter qo'llash; SOURCE collision |

### Bosqich 3.1 — Native LLM tool-calling (Ollama tools API) ✅

**Yangi:** `OllamaClient.chat_with_tools()` + `executor.run_native()` + `server /api/agent/toolrun`.

- `tools/base.py`: `schema()` flat qoldi, `ollama_schema()` qo'shildi (`{type:function, function:{...}}` Ollama formati)
- `tools/__init__.py`: `ollama_schemas()` — chat_with_tools uchun wrapper list
- `ollama_client.py`: `chat_with_tools()` — native `tool_calls` parse (function wrapper, string arguments), content-JSON fallback (qwen2.5-coder kabi modellar uchun), transport xatoda None
- `executor.py`: `run_native()` — model o'zi tool tanlaydi: loop → tool_calls bajariladi → natija tool-message qaytadi → final content. Takroriy chaqiruv bloki (`seen_calls`), bo'sh nom guard, `llm=None` guard, `python3→python` normalizatsiya (Windows), `any_failure` status logikasi, iteratsiya tugashida `stopped`
- Model tool chaqirmasa (qwen2.5-coder) → `run()` planned-execution fallback
- `run()` natijasiga `engine: "planned"` qo'shildi (interfeys uchun bir xillik)

**Native tool-calling demo natijasi (qwen3:latest):**
```
Task: "create calc.py that multiplies 6 by 7 and run it"
tool_calls: 2
  -> write_file {'path': 'calc.py', 'content': 'print(6 * 7)'} ok=True
  -> run_command {'command': 'python calc.py', 'cwd': '.'} ok=True
final: "I created a file named calc.py ... output the result of multiplying"
status: ok | engine: tool-calling | ~28s
```

### Smart execution demo natijasi

```
Task: "create greet.py that prints hello world and run it"
Plan (LLM): 1. Create the greet.py file  2. Run the greet.py script
step 1 done | write_file {'path': 'greet.py', 'content': "print('Hello World')"}
step 2 done | run_command {'command': 'python greet.py', ...}
status: ok | 2 tool_calls | 0 corrections | 13s
```

---

## 6. MEZONLAR (muvaffaqiyat ta'rifi)

1. ✅ `AgentExecutor.run("fayl yarat va ichiga hello yoz")` → real fayl yaratadi, `status: ok`
2. ✅ `AgentExecutor.run("greet.py yarat va bajar")` → skript yozdi, ishga tushirdi, stdout qaytdi
3. ⏳ Tool natijalari memory'ga saqlanadi (task-memory) — RAG recall testi keyingi bosqichda
4. ✅ Interfeysda `⚡ task` buyrug'i real toolcall ko'rsatadi
5. ✅ Self-correct: LLM tuzatish mexanizmi + retry bor; test_executor'da tool limit/safety tekshirildi
6. ✅ Native tool-calling: qwen3 model o'zi tool tanlaydi (write_file + run_command), `engine: tool-calling`; qwen2.5-coder → planned fallback

---

## 7. Qaydlar / Xavfsizlik

- **Sandbox**: barcha fayl operatsiyalari `workspace.root` ichida cheklanadi (path traversal bloklanadi)
- **run_command**: default `shell=False` emas — whitelist + timeout + max output
- **python_exec**: alohida subprocess, timeout, lekin DNS/network bloklanmagan (dev rejimi)
- Agent loop iteratsiyalari cheklangan (max 8), xatolarda orqaga qaytish
