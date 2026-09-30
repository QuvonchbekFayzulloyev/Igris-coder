# PHASE 5 AUDIT: Communication & Polish (§13, §14, §18)

**Sana:** 2026-09-17
**Metod:** statik kod audit + test coverage tahlili (Phase 3/4 audit uslubi)
**Fayllar:** `igris_agent.py`, `executor.py`, `planner.py`, `request_classifier.py`, `cag.py`, `state_machine.py`, `tools/__init__.py`, `server.py`, `Igris_brain/.github/workflows/*`

---

## §13. COMMUNICATION / SPEAKING

| # | Checklist | Holat | Dalil |
|---|-----------|-------|-------|
| 1 | Internal state va user response'ni ajratish | ✅ | natija dict'i ajratilgan: user-facing `final` matn ↔ ichki metadata (`completion`, `sm_history`, `world_stats`, `errors[]` alohida maydonlar); frontend `partial_rate`/status alohida ko'rsatadi |
| 2 | User-facing response generator'ni ajratish | ✅ | `executor._ask_final_summary()` — tool'lar bajarilgach ALOHIDA user-facing xulosa generatori (requirements'ga mos til/uzunlik: concise 1-2 / balanced 2-4 / detailed 5-8 gap); `IgrisAgent._finalize()` chat javobini yakunlaydi |
| 3 | Faqat verified information asosida gapirish | ⚠️ | SM darajasida kafolatlangan: COMPLETE faqat VERIFIED bilan (deterministik guard §17); LEKIN final xulosa matni verifications/confirmed_facts bilan programmatik SOLISHTIRILMAYDI — LLM xulosasiga ishoniladi |
| 4 | Action'dan oldin "bajarildi" demaslik | ✅ | native loop: final xulosa faqat tool'lar bajarilgach (`_ask_final_summary`); reja matni "reja" sifatida saqlanadi va bajarilishga undaladi (final emas); plan-gap reprompt |
| 5 | Failure'ni yashirmaslik | ✅ | `any_failure` → status `partial`, `failed_tools` hisobi; Phase 4: `errors[]` natijada; frontend partial_rate statistikasi |
| 6 | Current progress formati | ⚠️ | ✅ stage/detail format: RunManager `progress_cb(stage, detail)` + `stage_for_tool()` pipeline bosqichlari (UI PipelineStepper); ❌ "step N of M" aniq formati yo'q — planned loop `i/len(plan_steps)` biladi lekin progress detail'ga yozilmaydi |
| 7 | Final response formati | ✅ | `completion` record: {pipeline, label, stages, engine, tools, planned_tools, status, duration_ms, goal_id}; matn qismi requirements (Part L: language/verbosity/format) boshqaradi |
| 8 | Voice output qisqa policy | ❌/N-A | voice/TTS moduli YO'Q (lokal text UI) — hozircha N-A; `verbosity=concise` policy requirements orqali mavjud, voice qo'shilsa tayyor |
| 9 | Duplicate response'lar | ✅ | `CagCache` (LRU+TTL 1800s, max 256 — bir xil prompt'ga LLM chaqiruvi yo'q); native loop `seen_calls` duplicate tool-call bloki; `request_human` duplicate guard |

**Ball: 6/9 ✅, 2 ⚠️ (3, 6), 1 N-A (8)**

---

## §14. LLM OUTPUT CONTRACT

| # | Checklist | Holat | Dalil |
|---|-----------|-------|-------|
| 1 | LLM output schema | ✅ | tool-calling JSON schemas (`ollama_schemas()`); plan JSON (goal/steps/engine) prompt'da schema bilan; requirements modeli (Part L) |
| 2 | Free-form'ni kamaytirish | ✅ | qarorlar structured: plan JSON + tool_calls; free-form faqat final xulosa/reasoning maydonida |
| 3 | Intent schema | ✅ | `request_classifier.py`: `classify_family` → creator/chat, `classify_type` → weather/math/creative/structure/..., `classify_need` — deterministik (LLM'siz) router |
| 4 | Decision schema | ⚠️ | decision = plan JSON + requirements; plan'da alohida `intent/decision/reasoning/confidence` maydonlari YO'Q (plan `goal`+`steps`+`engine`); rasmiy Decision modeli yo'q |
| 5 | Action schema | ✅ | har Tool `schema()`/`ollama_schema()`; MCP tool_index schemas; `_normalize_native_args`/`_normalize_mcp_args` alias+path normalization |
| 6 | Reason/status separation | ⚠️ | status alohida ✅ (`ok/partial/cancelled/stopped`, `verify_status`, `refused`); reasoning esa final matn ICHIDA — alohida `reasoning` maydoni yo'q |
| 7 | Invalid JSON handling | ✅ | `planner._extract_json`: direct → fenced → balanced-block parse; plan invalid → rule-based `_fallback` (engine: fallback); `_ask_fix`/`_ask_tool_args` invalid → None → retry/fallback |
| 8 | Hallucinated tool detection | ✅ | `validate_plan_tools()` PLAN→EXECUTE guard: noma'lum tool → StateTransitionError (reja bajarilmaydi); `registry.execute`: `Unknown tool: {name}` → `{ok:false, code:1, recoverable}` |
| 9 | Unsupported action detection | ✅ | unknown skill/MCP xatolari (`unknown skill: X. Available: [...]`); capability-gap reprompt: model "qila olmayman" → skills/MCP ro'yxati eslatiladi |
| 10 | Validation layer | ✅ | qatlamli validatsiya mavjud: parse (_extract_json) → plan guard (validate_plan_tools) → execute guard (registry) → result shape ({ok, error, code, recoverable} §7); birlashgan modul emas, lekin qatlamlar to'liq |

**Ball: 7/10 ✅, 2 ⚠️ (4, 6), 1 qatlamli ✅ (10)**

---

## §18. TEST SUITE (17 senariy)

| # | Senariy | Holat | Qamrov |
|---|---------|-------|--------|
| 1 | Oddiy single-step task | ✅ | test_executor ("wrote file"), test_deliverable_run |
| 2 | Multi-step task | ✅ | test_executor (multi-step + limit), test_agentic_pipeline |
| 3 | Long-running task | ⚠️ | max_iter/max_tool_calls limit testlari bor; haqiqiy long-running e2e yo'q; CI'da benchmarks.yml + nightly.yml mavjud |
| 4 | Tool failure | ✅ | test_skills_mcp_hitl (failure→partial), test_phase2_core_loop |
| 5 | Timeout | ✅ | per-tool timeout testlari (test_phase1_foundation, test_phase4_resilience) |
| 6 | Wrong tool output | ✅ | empty-content senariylari (test_skills_mcp_hitl 18 test), deliverable verify |
| 7 | Wrong LLM decision | ✅ | wrong skill → repair (test_skills_mcp_hitl), `_ask_fix` path |
| 8 | Context overflow | ✅ | test_phase3_context 38/38 (fit_prompt, budget layers) |
| 9 | Memory conflict | ❌ | YO'Q — memory_bridge'da conflict detection ham yo'q (Phase 3 auditidan qolgan bo'shliq; §5 ga bog'liq) |
| 10 | Repeated failure | ✅ | test_phase4_resilience (same-error → escalation) |
| 11 | Infinite loop | ✅ | test_phase2_core_loop (detect_loop/detect_stuck), seen_calls duplicate blok |
| 12 | User interruption | ✅ | HITL awaiting_human (test_skills_mcp_hitl), cancel (test_phase4) |
| 13 | Task cancellation | ✅ | test_phase4_resilience — 4 cancel testi (planned/native/mid-step/endpoint) |
| 14 | Task resume | ✅ | test_phase3_checkpoint 16/16 (round-trip, step-skip, lifecycle) |
| 15 | Partial completion | ✅ | ko'p testlarda partial status (phase1_integration, phase2, executor...) |
| 16 | Final verification failure | ✅ | test_deliverable_run 13 (quality gate), test_deliverable_syntax |
| 17 | Full task success | ✅ | test_executor, test_deliverable_run e2e |

**Ball: 15/17 ✅, 1 ⚠️ (3), 1 ❌ (9)**

**CI/CD:** ✅ `Igris_brain/.github/workflows/test.yml` — push/PR, Python 3.10/3.11/3.12 matrix, pip cache, pytest; qo'shimcha: nightly.yml, benchmarks.yml, release.yml, dependencies.yml.

**Umumiy regressiya bazasi:** 30+ test fayl; oxirgi to'liq yugurish: phase1_foundation 48, phase1_integration 19, phase2_core_loop 27, phase3_context 38, phase3_checkpoint 16, phase4_resilience 11, skills_mcp_hitl 18, deliverable_run 13 — barchasi ✅.

---

## XULOSA — PHASE 5 HOLATI

### Kuchli tomonlar (plan kutganidan yuqori)
- **§13(2)**: user-facing generator nafaqat ajratilgan, balki requirements-aware (til/uzunlik)
- **§13(9)**: duplicate kamaytirish 3 qatlamda (CAG kesh, tool-call dedup, HITL dedup)
- **§14(3)**: intent router deterministik — LLM chaqiruvisiz
- **§14(7,8,9)**: invalid JSON, hallucinated tool, unsupported action — uchalasi ham guard qilingan
- **§18**: 15/17 senariy qamrab olingan + CI matrix (3 Python versiya) + nightly + benchmarks

### IMPLEMENTATSIYA (2026-09-17, audit o'sha kuni yakunlandi)

Qolgan 3 kichik bo'shliq yopildi (test_phase5_gaps 14/14 + 15/15 CHECKS, to'liq regression ✅):

| # | Bo'shliq | Yechim |
|---|---|---|
| 1 | §13(6) step N of M progress | ✅ `executor.run()`: har step boshlanishida `self._progress("execute", f"step {i}/{len(plan_steps)}: {title}")` |
| 2 | §14(4,6) decision/reasoning maydonlari | ✅ plan JSON'ga ixtiyoriy `reasoning` (max 500) + `confidence` (0..1 clamp); prompt schema yangilandi; fallback `confidence: 1.0` (determinizm signali); maydonsiz plan backward-compatible |
| 3 | §18(9) memory conflict | ✅ `MemoryBridge.detect_conflicts(query)` — deterministik: conflict-signali yozuvlar ("not/renamed/outdated/...") + normal yozuvlar score'lari yaqin bo'lsa (≤40% farq) CONFLICT flag; har yozuvda `conflicting` flag |

### Qolgan bo'shliqlar (tavsiya navbati bilan)
1. **§18(9) Memory conflict testi** — §5 conflict detection bilan bog'liq; Phase 3 auditida ham qolgan. Kichik: conflict flag + test (past xavf, lokal xotira).
2. **§13(6) step N of M progress** — planned loopda 1 qatorlik o'zgarish: `self._progress("execute", f"step {i}/{len(plan_steps)}: {title}")`.
3. **§14(4,6) Decision/reasoning maydonlari** — plan JSON'ga ixtiyoriy `reasoning`/`confidence` qo'shish (schema kengaytirish, breaking emas).
4. **§13(3) verified-only speech** — final xulosa bilan verifications solishtiruvi (murakkabroq, e2e dalil sifatida `completion` yetarli bo'lishi mumkin).
5. **§13(8) voice** — hozircha N-A; voice UI rejalansa `verbosity=concise` policy tayyor.

### Umumiy baholash
**Phase 5 asosiy talablari deyarli to'liq yopilgan** — kod arxitekturasi §13/§14 talablarini (structured output, validation qatlamlari, user-facing separation) allaqachon qanoatlantiradi; §18 test qamrovi 15/17. Qolgan 5 bo'shliqning 3 tasi kichik refaktor darajasida.
