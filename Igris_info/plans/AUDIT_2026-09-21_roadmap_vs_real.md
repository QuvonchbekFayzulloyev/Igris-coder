# IGRIS — To'liq Audit Hisoboti (v4/v5 Roadmap vs Real Kod)

**Sana:** 2026-09-21
**Metod:** Har bir roadmap bandi real kodda (file:line) tekshirildi + testlar ishga tushirildi.

---

## 1. v4 "Protocol 100" Roadmap — real bajarilganmi? HA ✅

| # | Roadmap bandi | Real kod dalili | Holat |
|---|---------------|-----------------|-------|
| 1 | §8 Rollback | `executor/pipeline_safety.py` WorkspaceBackup (restore), `task/task_supervisor.py:1039 rollback()` + test `test_a3_pipeline_safety.py` | ✅ |
| 2 | §13 ResponseGenerator | `agent/response_generator.py:110` — `_finalize` ichida integratsiya (`igris_agent.py:3616`) | ✅ |
| 3 | §13 Voice policy | `response_generator.py` VoicePolicy (≤50 so'z) + test | ✅ |
| 4 | §14 LLMOutput schema | `planning/llm_output_schema.py` (Intent, validate, parse, tool-exists) | ✅ |
| 5 | §15 Task Queue FIFO | `task/task_queue.py:77` + `/api/queue/status` | ✅ (modul real) |
| 6 | §15 Priority queue | TaskPriority high/normal/low, `_sort_queue` | ✅ |
| 7 | §15 CPU/RAM monitoring | `monitor/resource_monitor.py` get_resources (psutil) | ✅ |
| 8 | §17 Resource control | ResourceControl (ram/cpu/disk limit) — `executor.run()` boshi va oxiri integratsiya (`executor.py:993,1399`) | ✅ |
| 9 | §18 17 senariy test suite | `tests/test_suite_17_scenarios.py` — **59/59 PASS** (test_new_modules_v4 bilan birga) | ✅ |
| 10 | §19 Final audit 17 checklist | `Igris_info/plans/v4_architecture_audit.md` — har bandda file:line dalil | ✅ |
| 11 | §20 Diagnostics 11 | `Igris_info/plans/v4_diagnostics.md` | ✅ |

**Xulosalar:** Bitta nozik farq — `/api/agent/run` hozir to'g'ridan-to'g'ri `executor.run()` ishlatadi;
`TaskQueue` modul va endpoint mavjud, lekin run yo'li navbat orqali o'tmaydi (kelajakda integratsiya nuqtasi).

## 2. v5 "Full Parity" Roadmap — qismen bajarilgan ⚠️

| Element | Holat | Dalil |
|---|---|---|
| Cloud LLM (OpenAI/Claude/Gemini) | ✅ | `llm/omniroute_client.py` (OpenAI-compatible gateway), `llm/model_selector.py` (task→model, cost estimate), `.env.example` OMNIROUTE_* |
| edit_file search&replace | ✅ | `tools/fs_tools.py` EDIT_FILE (registryda) |
| read_file offset/limit | ✅ | `tools/fs_tools.py` READ_FILE |
| Shell/package-manager | ⚠️ qismen | run_command bor; `install_dependencies` avtodeteksi yo'q |
| LSP integration | ✅ | `tools/lsp_tools.py` — definition/references/hover/completion/diagnostics/status |
| AST search | ❌ | kod yo'q |
| Structured git | ⚠️ | `extra_tools.GIT_COMMAND` umumiy; test_runner/import_graph/TransactionalEditor yo'q |
| Test runner tool | ❌ | kod yo'q |
| Smart context | ⚠️ analog | `state/context_budget.py` (token budget) mavjud |
| Multi-file atomic | ❌ | kod yo'q |
| Code review tool | ❌ | kod yo'q (lekin svg_validator mavjud) |
| Browser automation | ✅ | `web-ai-bridge/` real Chrome CDP MCP |

## 3. LLM cheklovlari — "The current model could not draw this accurately"

### Root cause (kodda topildi):
1. `_retry_generate()` (`igris_agent.py:1377`) — draw so'rovida `attempts = 0`:
   kuchsiz model bo'sh javob bersa agent UMUMAN qayta urinmasdan rad etardi.
2. `CANNED_SCENE_SUBJECTS` tor ro'yxat (17 obyekt) — "tuya", "samolyot" kabi
   so'rovlar deterministik yo'ldan chetlab, zaif LLM'ga tushardi.
3. Eski `_draw_unsupported_message()` — jadval ro'yxatdan tashqari subyektni
   darhol rad etardi.

### Qo'shilgan tuzatishlar (bu auditda):
| O'zgarish | Fayl | Nima beradi |
|---|---|---|
| 6 yangi subyekt: tuya/camel, it/dog/kuchuk, oqqush/mifqush/owl, o'rdak/duck, robot, samolyot/plane | `mcp_servers/art_svg.py` (SCENE_OBJECTS 33→50 ta kalit), `agent/request_classifier.py` (CANNED_SCENE_SUBJECTS), `mcp_servers/art_server.py` (DEFAULT_COLOR) | Ko'p so'rovlar endi LLM'siz, deterministik va aniq chiziladi |
| Last-chance draw retry | `agent/igris_agent.py` `_last_chance_draw()` + `_chat_with_tools()` oqimi | LLM bo'sh javob bersa — rad etishdan OLDIN 1 marta aniq "faqat SVG chiqar" buyrug'i bilan urinish; junk-guard (`<svg>` yo'q — voz kechish, soxta "chizdim" yo'q) |
| System prompt yangilandi | CHAT_TOOLS_SYSTEM + ART_TOOL_HINTS | Model yangi subyektlarni scene tool bilan chizishni biladi |
| MCP bridge cwd bug FIX | `tools/mcp_bridge.py:_connect` | Konfiguratsiyadagi nisbiy `cwd` endi konfig fayl joyiga nisbatan hal qilinadi — pytest/server qaysi papkadan ishga tushsa ham art_server topiladi (7 ta test xatosi ham shu sababdan edi) |

## 4. Test natijalari

```
tests/ (e2e brauzer testlaridan tashqari): 1075 passed, 320 subtests passed (~3 min)
Yangi: tests/test_draw_expansion.py — 9/9 PASS
```

## 5. Keyingi qadamlar (roadmapda qolganlar)

1. `/api/agent/run` ni TaskQueue orqali o'tkazish (§15 to'liq integratsiya)
2. v5: AST search, test_runner tool, multi-file transactional edit, code review tool
3. Deterministik kutubxonani yanada kengaytirish (baliq turlari, mashinalar, binolar...)
4. `install_dependencies` package-manager avtodeteksi
