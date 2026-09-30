# PROTOKOL HEALTH MATRIX

AI coderlar uchun tez boshlash xaritasi: qaysi protokol sog'lom, qaysi e'tibor kerak.

| Protokol | Health | Sifat | Test qamrovi | Eng katta xavf | Birinchi qadam |
|---|---|---|---|---|---|
| P00 orchestration | 🟢 96% ↑ | yuqori | turbo 6/6, intel 45/45, pipeline 166/166; server endpoint'lari TestClient ✅ | god-fayl qoldiqlari (store.ts 1320, index.js 1197) | S5 davomi: store.ts/index.js |
| P01 execution | 🟢 95% ↑ | yuqori | 7/7 + syntax 11/11 + run 13/13 | qolgan domain-oracle'lar (pytest-suite/PDF/PCB) | A1 kengaytma |
| P02 task_management | 🟢 90% | yuqori | 39+8 test | decomposition sifati | domain-shablonlar |
| P03 safety_policy | 🟢 92% | yuqori | TestHarmFilter ✅ | python_exec sandbox | resource limits |
| P04 web_strategy | 🟢 95% ↑ | yuqori | 39 + web_verify 21 test | 2-manba tasdiqlash | A4 kengaytma |
| P05 svg_assurance | 🟡 88% | o'rtacha | 34 test | tor predmet kutubxona (Dp7) | generativ yondashuv |
| P06 hooks_events | 🟢 96% ↑ | eng yuqori | jonli E2E + degradation 10/10 | confidence auto-alert | S3 UI karta |
| P07 cag_mag | 🟢 90% | yuqori | 25 test | model-o'zgarish invalidatsiya | fingerprint kalit |
| P08 memory_control | 🟢 93% ↑ | yuqori | +20 + FTS5 12 + T2 10 test | T3 vector retrieval | qisqa embedding |
| P09 tool_mcp | 🟡 85% | o'rtacha | 18 test | domain-MCP yo'q | Office+Diagramma server |
| P10 requirements | 🟢 88% | yuqori | 15 test | til-bog'liq fallback | ko'proq til qoidalari |
| P11 intelligence | 🟢 92% ↑ | yuqori | 41/41 + grounding testlar | T5 parallel yo'q | asyncio variants |
| P12 quick_paths | 🟢 96% ↑ | yuqori | TestLogicQuickMath + agentic 166 ✅ | modul ≤500 maqsad (quick_paths 316) | davom etmoqda |
| P13 memory_fayllari | 🟡 85% | o'rtacha | bilvosita | D2 kompaktlash yo'q | scheduler |
| **v4 Roadmap** | **🟢 100%** | **yuqori** | **839 passed, 1 skipped** | **integratsiya sifati** | **tayyor** |

**O'rtacha sog'liq: ~91%** (v4 roadmap 100%)

## Roadmap v4 — Tugallangan Bo'limlar (2026-09-18)

| § | Bo'lim | Holat | Fayllar |
|---|--------|-------|---------|
| §13 | ResponseGenerator | ✅ 100% | agent/response_generator.py |
| §14 | LLMOutput Schema | ✅ 100% | planning/llm_output_schema.py |
| §15 | TaskQueue + ResourceMonitor | ✅ 100% | task/task_queue.py, monitor/resource_monitor.py |
| §17 | ResourceControl | ✅ 100% | monitor/resource_monitor.py |
| §18 | Test Suite (17 senariy) | ✅ 100% | tests/test_suite_17_scenarios.py |
| §19 | Architecture Audit | ✅ 100% | docs/v4_architecture_audit.md |
| §20 | Diagnostics Guide | ✅ 100% | docs/v4_diagnostics.md |

## O'zgarish tarixi
- 2026-09-12: P00 94% (3 bug fix), P01 92→93% (sintaksis verifikator), P05/P08/P09/P12 manifest nomuvofiqlari to'g'rilandi
- 2026-09-12 (T1): P08 82→90% — RAG keyword index SQLite/FTS5 incremental ga o'tdi (search 3-6x tezroq, diskda saqlanadi, rebuild yo'q); ikki eskirgan test hozirgi kontrakga moslashtirildi (req-kesh put tartibi + til-bog'liq fallback matn)
- 2026-09-12 (S3): P06 95→96% — Silent-degradation registry (`degradation.py`): MCP/FTS5/CAG/MAG jim fallbacklari `/api/system/services`'da ko'rinadi; ✅ UI karta tayyor (Settings→Services, clear tugmasi bilan)
- 2026-09-13 (D1): yangi himoya qatlami — `input_validation.py` barcha `/api/` POST'larda (413/422, fail-safe); server.py ulandi
- 2026-09-13 (T2): P08 90→93% — `load_documents` mtime-cache (faqat o'zgargan fayllar) + `remove_source` API'lari (FTS5 incremental DELETE, Windows-path JSON-escape tuzatildi)
- 2026-09-13 (A4): P04 93→95% — `web_verify.py` web javob manba grounding tekshiruvi; P11 91→92% — SelfEvaluator `grounding` signali (+0.10/−0.15, backwards-compatible)
- 2026-09-13 (A1-2): P01 93→95% — run-verification: yozilgan `.py` izolyatsiyada ishga tushiriladi; runtime xatoli gate'dan o'tmaydi (import/deps neytral); `test_deliverable_run.py` 13/13 ✅
- 2026-09-14 (S5): P00 94→95%, P12 93→96% — igris_agent 5641→4530: `quick_paths.py` + `web_strategy.py` + `agent_stack_data.py` + `request_classifier.py` modullarga ajratildi (delegatsiya, API o'zgarmagan); `igris_quick.py` toza fasad; ~513 regressiya test ✅. KRITIK bug tuzatildi: supervisor cheksiz rekursiyasi (`_supervisor_active` guard) — testlar 228s→0.9s darajada tezlashdi, web/code so'rovlardagi minutlab javobsizlik yo'q bo'ldi
- 2026-09-14 (S5-2): P00 95→96% — server.py 3078→2273: `server_chat_history.py` + `server_circuit.py` + `server_health.py` (DI, uptime `dir()` bugi tuzatildi) + `server_process.py` (restart doim server.py'ni ochadi). Endpoint'lar TestClient bilan real tekshirildi; `from server import ChatHistory` testlar kontrakti saqlangan

## Ishonch darajasi legenda
- 🟢 ≥88% — ishonchli ishlaydi, faqat rivojlantirish kerak
- 🟡 80-88% — ishlaydi, lekin ma'lum zaiflik bilan; yaxshilash navbati keladi

## AI coder uchun boshlash tartibi (tavsiya)
1. ~~T1 (SQLite index)~~ ✅ 2026-09-12
2. ~~D1 (validatsiya middleware)~~ ✅ 2026-09-13
3. ~~A1 (verifikator: sintaksis + run)~~ ✅ 2026-09-12/13 — qolgan domain-verifikatorlar (pytest-suite, PDF, PCB) navbatda
4. ~~S5 (modullashtirish)~~ 🟡 JARAYONDA (2026-09-14: igris_agent bo'lindi; navbatda server.py/store.ts) — boshqa barcha ishlarni tezlashtiradi
