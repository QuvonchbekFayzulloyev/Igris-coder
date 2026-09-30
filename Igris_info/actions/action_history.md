# QILINGAN ISHLAR TARIXI (Action History)

Har bir sessiyada Igris ustida nima qilingani — kronologik, kategoriya bo'yicha.

---

## Sessiya 2026-08-07 — Offline-himoya tizimi

**Kategoriya:** infratuzilma / ishonchlilik

- `watchdog.py` yaratildi (16 funksiya): backend + Ollama avtomatik restart
- `server.py`'ga fatal-handlers, launch-persist, watchdog-state integratsiyasi
- `run.bat` / `stop.bat` watchdog boshqaruvi; UI Settings'da Watchdog kartasi
- Jonli E2E test: backend o'ldirildi → 54.2s da to'liq tiklanish
- 6 ta xato topildi va tuzatildi (jonli test kodi review'dan kuchli ekanini ko'rsatdi)
- Natija: ✅ barcha testlar o'tdi — `checklist.md` da to'liq

## Sessiya 2026-08-11 — Xavfsizlik + sifat audit tuzatishlari

**Kategoriya:** xavfsizlik / sifat

| ID | Nima qilindi |
|---|---|
| N1 | PoisoningProtection `recall()`/`remember()`'ga ulandi |
| N2 | `safety.py` yaratildi; RAG recall konteksti tozalanadi |
| N3 | `web_fetch` chiqishi `safety.sanitize()` bilan tozalanadi |
| Dp1 | CLI AgentPanel + StatusBar real `agentInfo` ko'rsatadi (fake data yo'q) |
| Dp2 | TitleBar Tauri v2 API'ga o'tkazildi, brend IGRIS |
| Dp3 | Tauri CSP siyosati o'rnatildi (csp: null tugatildi) |
| Dp5 | `run_command` deny-pattern ro'yxati (rm -rf /, sudo...) |
| Dp6 | `Workspace` realpath asosida path tekshiruvi (symlink sandbox) |
| A3 | Probe outcome: bajarilgan run 0.0 olmaydi (0.0→0.62) |
| Dp4 | (qisman) `python_exec` xavfli chaqiruvlar deny-list |

## Sessiya 2026-08-12 — A2 kalibratsiya + RAG himoyasi (V4)

**Kategoriya:** aniqlik / xotira

- A2: confidence SelfEvaluator bilan kalibrlandi (11 hardcoded → `evaluate()`); `resolve()` deterministik yo'li ham
- `evaluate()` BIR MARTA — `_self_eval_for` kesh; memory output == javob content == confidence manbai (barcha yo'llar)
- Verifikator signali: `structure_check` (repaired −0.10, fail −0.25)
- `resolver_score` signali (0.35·rs) + `length_ok` scale; resolver floor 0.825→0.75
- `avg_logprob` signali (ixtiyoriy `--logprobs`/`IGRIS_LOGPROBS=1`)
- RAG fail-guard: `verified='fail'` HECH QAYERDA yozilmaydi (7 joyda guard)
- chat_stream tool yo'li repair-before-write (memory == done)
- Transcript `warning` maydoni — ⚠️ banner (web + CLI)
- +20 doimiy test (211 jami): turbo invariantlar, confidence sweep (33,600 kombinatsiya), round-trip

## Sessiya 2026-08-17 — 2nd Brain "qora oyna" tuzatishlari

**Kategoriya:** UI/UX

- K1: graf chiziqlari ko'rinmasligi (to'q kulrang qora fonda) — ranglar tuzatildi
- K2: `loading` bayrog'i qotib qolishi (StrictMode ikki chaqiruv) — tuzatildi
- K3: katta arxivda graf sekin — kesh qo'shildi
- K4: zustand aliasi butun app qora ekranga olib kelgan — vite config tuzatildi

## Sessiya 2026-09-12 — AUDIT + Igris_info tashkiloti + 3 jonli bug

**Kategoriya:** audit / hujjat / bug-fix

1. **Igris_info papkasi to'ldirildi**: 13 protokol hujjati, actions (shu fayl), state (3 hisobot), purposes, todo_user (3 kategoriya)
2. **Manifest nomuvofiqligi aniqlandi**: `web_strategy.py`, `memory_control.py`, `quick_math.py`, `quick_weather.py`, `intelligence/core.py`, `tools/registry.py` fayllari manifestda bor deb yozilgan edi — aslida yo'q (funksiyalar boshqa joyda yashaydi). Hujjatlar real joylashuv bilan tuzatildi.
3. **3 jonli bug topildi va tuzatildi** (`igris_agent.py`):
   - `llm_failed` UnboundLocalError — offline rejimda `chat()` HAR chaqiruvda crash qilardi
   - `_cacheable_out` junk-guard eskirgan — junk javoblar RAG/CAG'ga yozilardi
   - fallback matn kontrakti buzilgan + `extract_code` intent-sharti — fence qoldiqlari structure_check'ga xom kirardi
4. **Testlar**: 58 yadro test o'tdi (avval 2 failed); `test_intelligence.py` 41/41 (avval 6 failed)
5. **A1 1-qadam — Python sintaksis verifikatori** (executor quality gate): `_python_syntax_check()` ast.parse bilan 120+ belgili buzuk `.py` fayllar gate'dan o'tmaydigan bo'ldi + corrective pass ishga tushadi. Yangi test: `test_deliverable_syntax.py` (11 test). A1 to'liq oracle yo'lida birinchi deterministik qadam.
6. **T1 — RAG keyword index SQLite/FTS5 ga o'tkazildi** (`Igris_Memory/memory/fts5_index.py` yangi modul): incremental insert (har add'da O(N) rebuild YO'Q — eski BM25Index asosiy sekinlik sababi), diskda saqlanadi (`brain_data/fts_index.db` — restartda qayta qurilmaydi), content-hash dedup, deferred commit (200 hujjatda 1 fsync), FTS5 mavjud bo'lmasa avtomatik BM25Index fallback. `HybridSearch` drop-in ulandi (interfeys bir xil). Benchmark (3000 hujjat): search 1.3ms vs 4-9ms — **3-6x tezroq**; bulk-load barobar. Yangi test: `test_fts5_index.py` (12 test, persistence + fallback + dedup). Qo'shimcha: 2 ta eskirgan test hozirgi kontrakga moslashtirildi (CAG puts tartibi — req-kesh; junk fallback til-variantlari).
7. **T1 import-tuzatish (muhim!)**: E2E tekshiruvda aniqlandi — MemoryBridge faqat `Igris_Memory` ildizini `sys.path`ga qo'shadi, lekin `fts5_index` paket ichida (`memory/`) yashaydi → ishlab turgan serverda import jim XATO qilib, BM25 fallback'da qolardi (silent degradation). `HybridSearch._make_keyword_index()` endi: paket-ichki yo'lni `sys.path`ga qo'shadi + nisbiy import sinovi. Tasdiqlandi: haqiqiy MemoryBridge yo'lida `FTS5Index` faol (178 hujjat), recall 3.9–7.5ms (top_k=3, RAG qatlami bilan), regressiya 34/34 ✅
8. **S3 qism — Silent-degradation registry** (`degradation.py` yangi modul): T1 darsi umumlashtirildi — barcha `except Exception: fallback` nuqtalari endi jim qolmaydi. `mark(component, reason, fallback)` registry: dedup (component+fallback → count+1), atomik disk-fayl (`logs/degradations.json`, restart'da tarix saqlanadi), thread-safe, hech qachon exception tashlamaydi. Jihozlangan nuqtalar: MCP connect/config (`mcp.*`), FTS5→BM25 fallback (`memory.keyword-index`), MemoryBridge init (`memory.bridge`), agent `_cag`/`_mag` (`agent.*`). `/api/system/services` javobiga `degradations` (to'liq tarix) + `degradations_active` (so'nggi 10 daqiqa) + `mcp.degraded` flag qo'shildi. Yangi test: `test_degradation.py` 10/10 ✅ (MCP xato mark + FTS5 fallback mark simulyatsiyasi bilan). Regressiya 40/40 ✅
9. **S3 UI — Degradations kartasi** (Settings→Services): qizil ramka + pulse + `N active` badge (faol degradatsiya bo'lsa), yozuv ko'rinishi `component → fallback reason ×count` (top-5, qolgani hisoblangan), `↺ clear` tugmasi + yangi endpoint `/api/system/degradations/clear` + `clearDegradations()` (backend.ts). MCP kartasida `degraded` badge. `DegradationEntry` tipi qo'shildi. TS typecheck: 0 xato ✅; clear endpoint E2E ✅

## Sessiya 2026-09-13 — D1 + T2 + A4 (protokollar jonlantirildi)

**Kategoriya:** xavfsizlik / tezlik / aniqlik

| ID | Nima qilindi |
|---|---|
| D1 | **API kirish validatsiya middleware** (`input_validation.py` yangi + `server.py`): barcha `/api/` POST'larda body-hajm limiti (10MB→413), string uzunlik/kontrol-belgilar/null-byte/kod-injection naqshlari (422), path maydonlarida `..` traversal + `file://` sxema bloki, JSON depth >32 va inf/nan rad etish. FAIL-SAFE pass-through (GET/JSON-emas/parse-xato o'zgarmagan o'tadi — regressiya yo'q); validatsiya exception'i serverni qulatmaydi. Qat'iy root rejimi `install_input_validation(app, workspace_root=...)`. 32 doimiy test (`test_input_validation.py`) ✅ |
| T2 | **RAG mtime-cache** (`retrieval.py` `load_documents`): faqat o'zgargan fayllar qayta o'qiladi va indekslanadi (mtime+size); o'zgargan faylning eski versiyasi `remove_source` bilan o'chiriladi; o'chirilgan fayllar index'dan ham tozalanadi. Yangi API: `BM25Index.remove_source`, `FTS5Index.remove_source` (incremental DELETE — rebuild yo'q, Windows-path JSON-escape tuzatildi), `VectorIndex.remove_source`, `HybridSearch.remove_source`, `force=True` flag. 10 yangi test (`test_t2_mtime_cache.py`) — 22/22 (FTS5+BM25 bilan) ✅ |
| S5 | **Modullashtirish 1-qadam (2026-09-14)** — igris_agent 5641→4530 satr (−1111): ① `quick_paths.py` (math/weather tez yo'llar — P12), ② `web_strategy.py` (web darvoza/strategiya/tool leksikasi — P04), ③ `agent_stack_data.py` (STACK_PLANS/FRAMEWORK_STACK/ORM_STACK/LANG_STACK/DB_STACK/DB_DISPLAY_SUFFIX — faqat statik jadvallar), ④ `request_classifier.py` (pipeline detektorlari + ikki bosqichli router + subject/db/orm/stack aniqlash + clarify). IgrisAgent metodlari bir qatorli delegatsiya — klass API'si O'ZGARMAGAN (statik/classmethod dekoratorlar saqlangan); leksika/jadvallar klass-atribut sifatida qayta eksport (identik obyektlar, `is` bilan tekshirilgan). `igris_quick.py` buzuk shimdan toza fasadga (eski nomlar to'g'ri semantika bilan quick_paths'ga delegatsiya — avval math_prefix regex qaytarardi, needs_web doim False edi). O'lik kod tozalandi (ishlatilmagan import-bloklar, dublikat def'lar). Regressiya ~513 test ✅. Qolgan god-fayllar: server.py (3078), store.ts (1320), index.js (1197) |
| BUG | **KRITIK: supervisor cheksiz rekursiyasi (§9) — S5 auditida topildi** (`igris_agent.py`): `chat() → _run_supervisor → node → agent.chat() → _run_supervisor → ...` — ichki chat yana supervisor ochib CHEKSIZ ichma-ichma rekursiya (har daraja TaskSupervisor + DAG planner + checkpoint). Alomat: web/code so'rovlarida minutlab javobsizlik, stack to'lib qolish xavfi. Tuzatish: `_supervisor_active` re-entrancy guard — ichki chaqiruv None/bo'sh generator bilan o'tadi, node oddiy chat yo'lida bajaradi. Ta'sir: test_intelligence 228s→0.9s, rag_cag 98s→0.2s, turbo 39s→0.1s, stream_thinking 33s→0.1s; test_agentic_pipeline 166 test 280s+ timeout → 6.7s ✅ |
| BUG | **RequirementExtractor qotib qolgan LLM klienti** (`core/requirements.py` + `igris_agent.py`): ekstraktor `__init__`da klient nusxasini saqlardi — testlar/runtime `agent.llm` almashtirsa ekstraktor ko'rmasdi va real Ollama'ga tarmoq chaqiruvi qilardi. Tuzatish: `llm_provider` lazy-getter (`llm_available()` orqali — LLM yo'q/cooldown'da deterministik fallback, hujjatlashtirilgan shartnoma bo'yicha) |
| A4 | **Web javob manba tekshiruvi** (`web_verify.py` yangi): web tool natijalari (`web_fetch`, `browser_get_text`, `ask_web_ai`...) manba-indeksiga yig'iladi (`_chat_with_tools` capture, `mcp_call`/art serverlar KIRMAYDI — yolg'on "ungrounded" oldini olish), yakuniy javob deterministik grounding tekshiruviga o'tadi (token-bigram qamrov, fakt-fragment ajratish — raqamli gaplar to'liq, kod/URL o'tkaziladi, QO'SHIMCHA LLM CHAQIRUVI YO'Q). Natija: `grounded` (+0.10 ishonch) / `partial` (neytral) / `ungrounded` (−0.15) — `SelfEvaluator` yangi `grounding` parametri; `data["web_grounding"]` metrikaga yoziladi. Rasm javoblarida tekshiruv yo'q. Fail-safe: hech qachon chatni buzmaydi. 21 yangi test (`test_web_verify.py`) ✅ |
| P11 | SelfEvaluator + IntelligenceCore + orchestrator `grounding` parametri (backwards-compatible — None = signal yo'q) |
| A1-2 | **A1 2-qadam — run-verification** (`executor.py`): 120+ belgili `.py` fayl endi izolyatsiyada ishga tushirib ko'riladi — `NameError/TypeError/ZeroDivisionError...` kabi ishga tushmaslik xatolari quality gate'dan O'TMAYDI (repair pass ishga tushadi). Import/deps, deny-list, timeout — NEYTRAL (muhit bog'liq, rad etmaydi). Xavfsizlik: subprocess + `-I` izolyatsiya + 6s timeout + python_tools deny-listi. 13 yangi test (`test_deliverable_run.py`) ✅ |
| Testlar | Regressiya: chat_history 27, degradation/requirements/brain/svg_validator (59), input+web_verify (53), deliverable syntax+run (24), executor (7) ✅; turbo+rag_cag (29) ✅; intelligence fonda |

## Sessiya 2026-09-14 — S5 2-qadam: server.py modullashtirish

**Kategoriya:** refactoring / bugfix

| ID | Nima qilindi |
|---|---|
| S5 | **server.py 3078→2273 satr (−805)** — to'rt modulga ajratildi: `server_chat_history.py` (428: ChatHistory JSONL + CHAT_PROGRESS buferi + `_structure_fail_warning` — faqat stdlib), `server_circuit.py` (116: CircuitBreaker + `_CIRCUIT`), `server_health.py` (195: metrika ring-buffer + `collect_health_metrics` — DI orqali tashqi holat, import tsikli yo'q), `server_process.py` (292: restart/watchdog/ollama/port yordamchilari). server.py endi qayta eksport qatlamı (testlar kontrakti: `from server import ChatHistory, _structure_fail_warning` — `is` bilan tekshirildi) |
| BUG | **Health uptime doim ~0 edi** (`server.py`): `'_SERVER_START_TIME' in dir()` — funksiya ichida `dir()` faqat lokal nomlarni qaytaradi → doim False. Tuzatish: `collect_health_metrics(server_start_time=...)` DI parametri. TestClient: `/api/health/metrics` endi uptime > 0 |
| S5 | **Restart-ixlosi oldini olindi**: `_server_start_command` `os.path.abspath(__file__)` ishlatardi — server_process.py'ga ko'chsa restart noto'g'ri fayl ochardi. `configure(server_path=os.path.abspath(__file__))` main()'da — restart komandasi doim server.py'ni ko'rsatadi (parity test ✅) |
| S5 | `main()` global mutatsiyalari → `_proc.configure()`; endpoint read-saytlari late-binding (`_proc._RUN_PORT`) |
| Test | server regressiya: health/metrics/history + chat + system/services + circuit/reset endpoint'lari TestClient bilan real chaqirildi ✅; 25 test-fayl yashil (agentic_pipeline 166, web_strategy 39, task_supervisor 39, input_validation 32, chat_history 27...) |

**Foyda (user ko'radi):**
- Monitoring dashboard endi REAL uptime ko'rsatadi (avval doim ~0)
- UI restart tugmasi ishonchli — backend xuddi shu server.py + flaglar bilan qayta ochiladi (modullashtirish restart'ni buzishi mumkin edi — oldindan yopildi)
- server.py endi 2273 satr — endpoint'lar va agent singleton; har bir yordamchi qatlam o'z modulida (testlash va o'zgartirish osonlashdi)

**Oldingi sessiya foydasi:**
- API endi katta/zararli so'rovlarni rad etadi (413/422) — server himoyalangan
- Chat tarixi katta bo'lsa ham server starti/recall tez (T2: o'zgarmagan fayllar qayta o'qilmaydi)
- Web'dan javob berayotganda manbaga tayanmagan faktlar past ishonch bilan belgilanadi — "Ishonch: past" ko'rsatiladi, hallucination aniqroq ko'rinadi
- Agent yozgan Python fayli ishga tushmasa (runtime xato) — "Bajardim" deb o'tib ketmaydi, gate uni rad etadi va tuzatish pass ishga tushadi (A1-2)

---

## Sessiya 2026-09-16 — Architecture Audit: Phase 1 Foundation

**Kategoriya:** audit / arxitektura

Reja: `Igris_info/plans/IGRIS_Architecture_Audit_Plan.md` (20 bo'lim, 6 faza). Hisobot: `Igris_info/plans/phase1_foundation_audit.md`

| Bo'lim | Nima qilindi |
|---|---|
| §0 | **To'liq komponent inventarizatsiyasi** — Igris_brain 32 672 satr skanerlandi; Mermaid komponent-graf (13 qatlam); takroriy komponentlar: layered_agent (1158) vs task_supervisor (1072) ~40% overlap, probe/tmp skriptlar rootda |
| §1 | **State machine audit** — formal SM YO'Q; holatlar 3 darajada tarqoq (PIPELINE_SPECS stages / executor status / NodeStatus); 10 ta transition guard qoidasi + formal dizayn (INPUT→UNDERSTAND→PLAN→EXECUTE→OBSERVE→VERIFY→UPDATE→CONTINUE/COMPLETE/FAIL/ESCALATE) yozildi |
| §2 | **Goal hierarchy audit** — `plan["goal"]` mutable (zaif); frozen Goal / Objective / Task modeli taklif qilindi; TaskNode+TaskDAG mavjudligi tasdiqlandi; goal pin + resume qoidalari yozildi |
| §7 | **Tool protokoli audit** — 13 native tool + 8 MCP server inventarizatsiyasi side-effect/timeout/guard bilan; **KRITIK topilma: `git_command` tool'da DENY-Pattern YO'Q** (push/reset --hard/rebase cheklanmagan); delete_file confirm'siz; ToolMeta + ToolError{error,code,recoverable} standart dizayni tayyor |
| §17 | **Deterministic/LLM chegarasi** — 11 funksiya baholandi; quick_paths/web_verify/verification/retry-limitlar ✅ deterministik; state transitions + task-completion hozircha LLM ta'sirida bo'lishi mumkin (Phase 2'da yopiladi); qoida: LLM=WHAT, executor=HOW |
| Hujjat | Reja checklistlari (§0/§1/§2/§7/§17) audit natijalari bilan yangilandi — 40+ item belgilandi |

**Natija:** Phase 1 audit 100% — 5 bo'limda asosiy topilmalar + barcha dizaynlar tayyor. Navbat: implementatsiya (state_machine.py, Goal modeli, ToolMeta, git_command deny-list) yoki Phase 2 audit.

### Phase 1 IMPLEMENTATSIYA (shu sessiyada davomi) — 2026-09-16

| ID | Nima qilindi |
|---|---|
| §1 | **`Igris_brain/state_machine.py` YANGI** — formal AgentState enum (INPUT→UNDERSTAND→PLAN→EXECUTE→OBSERVE→VERIFY→UPDATE_STATE→CONTINUE/COMPLETE/FAIL/ESCALATE), 10 ta deterministik guard (COMPLETE faqat VERIFIED bilan; repair VERIFY→EXECUTE retry limit bilan; iteration limit), StateTransitionError, history JSONL dump (§16 asosi), TaskStatus/VerificationStatus enum'lari, validate_plan_tools() |
| §2 | **`Igris_brain/goal_model.py` YANGI** — frozen Goal (immutable, dataclass frozen), Objective (mutable, goal_id majburiy saqlanadi), Task (parent/subtask daraxti, status transition guard'lari, priority, dependencies), Action, GoalContext.prompt_pin() (har LLM prompt'ga ORIGINAL GOAL pin), save/load_goal_context (resume) |
| §7 | **`tools/base.py` ToolMeta + ToolError** — side_effect (read_only/write/unsafe/destructive) 13 toolga default kategoriyalar; standart timeout'lar; permission=confirm delete_file uchun; precondition/postcondition validatorlar (fail-safe: validator yiqilsa rad); ToolError{error,code,recoverable} kodlar: 1=unknown 2=invalid_args 3=denied 4=timeout 5=internal; registry.execute standart formatga o'tdi |
| §7 FIX | **KRITIK: git_command deny-list BYPASS tuzatildi** — eski naqshlar `\bgit\s+push` ("git" prefiksini talab qilardi), holbuki tool'ga command "push origin main" ko'rinishida uzatiladi → push/reset --hard/branch -D/clean -f O'TIB KETARDI. Tuzatish: birinchi-token subcommand tahlili (`_git_denied`) + ikkinchi qatlam regex; push/rebase/revert/filter-branch doim blok; remote add/set-url, reflog delete, gc --prune qo'shildi |
| §7 FIX | **Tool schema: hamma parametr required edi** — `default` maydoni bor parametrlar (cwd, timeout, depth...) ham required deb e'lon qilingan; endi default-li parametrlar ixtiyoriy (Ollama schema'ga to'g'ri uzatiladi, precheck endi noto'g'ri rad etmaydi) |
| Test | `test_phase1_foundation.py` YANGI — 48 test: SM happy path/invalid transition/retry-iteration limitlar/history dump; goal frozen/replan-sinxron/pin/round-trip/resume; ToolMeta pre/postcheck/ToolError kodlari; git deny 15 bypass varianti; registry error formatlari |
| Regressiya | executor + phase1 + input_validation + web_verify + deliverable syntax/run + requirements (98) ✅; agentic_pipeline + task_supervisor + composition + web_strategy + rag_cag_mag + turbo (276 + 320 subtests) ✅ |

**Natija:** Phase 1 implementatsiya tugadi — formal state machine, goal preservation, tool kontrakti v2 kodda. Navbat: executor/agent'ga SM integratsiyasi (Phase 2 boshlanishi) yoki Phase 2 audit.

### Phase 1 INTEGRATSIYA: executor + igris_agent'ga SM/Goal ulash — 2026-09-16

| ID | Nima qilindi |
|---|---|
| §1/§2 | **executor.run()** — har run'da GoalContext (immutable Goal) yaratiladi yoki tashqaridan qabul qilinadi; StateMachine yuritiladi: INPUT→UNDERSTAND→PLAN→EXECUTE→(har step: EXECUTE→OBSERVE→VERIFY→UPDATE_STATE→CONTINUE→PLAN→EXECUTE)→COMPLETE/FAIL. PLAN→EXECUTE guard'i CRITICAL: reja tool nomlari registry+MCP bilan deterministik tekshiriladi — noma'lum tool bo'lsa StateTransitionError (noto'g'ri reja bajarilmaydi) |
| §1/§2 | **executor.run_native()** — SM + goal preservation native loop'da ham; GOAL PIN system prompt'ga qo'shiladi (context o'ssa ham goal yo'qolmaydi); yakuniy holat deterministik guard orqali (status ok→VERIFIED→COMPLETE; partial→UNKNOWN; stopped→FAIL) |
| §12 | **igris_agent.chat()/chat_stream()** — goal pin system prompt'ga (user maqsadi immutable Goal sifatida pin qilinadi); _work_completion'ga goal_id tracing (konversatsiya tarixida kuzatiladi) |
| §16 | Natija record'lariga tracing: goal_id, goal_text, sm_final_state, sm_history_len (executor run/run_native) |
| Test | **test_phase1_integration.py YANGI** — 19 test: run SM ketma-ketligi (INPUT→UNDERSTAND→PLAN→EXECUTE...VERIFY), goal tracing, tashqi GoalContext in'yeksiyasi, 2-run mustaqil goal'lar, invalid plan SM bloki, native goal pin promptda (MockLLM bilan) |
| Regressiya | 16 test-fayl: 434 passed + 320 subtests ✅ (executor, intelligence, stream, rag_cag, turbo, agentic_pipeline 166, task_supervisor, composition, web_strategy...) |

**Natija:** SM + goal preservation endi LIVE — executor va agent asosiy oqimlarida. Diqqat: executor offline run status'i (ok/partial) quality gate xatti-harakati o'zgarmagan (HEAD bilan bir xil); SM fail-safe — guard rad etishi faqat PLAN→EXECUTE'da critical, qolganida log+davom. Navbat: Phase 2 (§3/§4/§8/§9/§10) audit yoki chuqurroq SM integratsiya (supervisor darajasi).

### Phase 2 AUDIT: Core Loop (§3/§4/§8/§9/§10) — 2026-09-16

Hisobot: `Igris_info/plans/phase2_core_loop_audit.md`

| Bo'lim | Asosiy topilma |
|---|---|
| §3 | LLM/action chegara ✅ TO'G'RI (model faqat decision, executor bajaradi, correction loop limitli); kamon: Action ID yo'q |
| §4 | ❌ ENG KATTA BO'SHLIQ: Observation→State konversatsiyasi YO'Q — tool natijalari yig'iladi lekin confirmed/assumed flag'siz, world-state obyektiga aylanmaydi; supervisor compact() ✅ lekin executor yo'li compact'siz |
| §8 | Supervisor CheckpointManager ✅ puxta (2 fayl, budget tracking); ❌ executor darajasida interruption/resume yo'q — ikki daraja ulanmagan |
| §9 | Limitlar ✅ (max_iter, max_tool_calls, seen_calls exact dedup); ❌ aylanma (A→B→A→B) va stuck-state detection yo'q; per-iteration timeout yo'q |
| §10 | NAMUNALI: quality gate + AST sintaksis + run-verification + web grounding — deterministik; SM COMPLETE guard ✅; kamon: VerificationRecord evidence yo'q, expected formal emas |
| Hujjat | Reja checklistlari (§3/§4/§8/§9/§10) yangilandi — 30+ item audit natijasi bilan |

**Navbat (tavsiya tartib):** ① Action ID + VerificationRecord ② AgentWorldState (§4) ③ aylanma/stuck detection (§9) ④ executor checkpoint (§8)

### Phase 2 IMPLEMENTATSIYA (1-4 items) — 2026-09-16

| ID | Nima qilindi |
|---|---|
| §4 | **`Igris_brain/world_state.py` YANGI** — Observation (confirmed=tool ok:true / assumed), AgentWorldState (add_from_record, files_touched, last_error, confirmed_facts/assumed_notes ajratish, compress_old — eski observationlarni summary'ga siqish, MAX_OBSERVATIONS guard) |
| §10 | **VerificationRecord + VerificationLog** — yagona evidence {action_id, expected, actual, method, status, ts}; make() deterministik status (ok=True→VERIFIED, False→FAILED, None→UNKNOWN); executor quality gate natijasi endi logga yoziladi (deliverable: requested files vs written files) |
| §3 | **Action ID** — har tool record (run + run_native) endi action_id UUID bilan; uniqueness test bilan tasdiqlandi |
| §9 | **detect_loop + detect_stuck** — aylanma (A→B→A→B naqshi, window=6, repeat_threshold=2) va stuck (stall_limit=6 iteratsiyada 0 yozma ish) — deterministik, run_native'da break+partial |
| §1 | SM OBSERVE→VERIFY guard'i endi REAL world.observation_flags()dan flag oladi (oldin status taxminidan) |
| §16 | Natija record'lariga yangi tracing: world_stats, confirmed_facts, verifications (run + run_native) |
| Test | **test_phase2_core_loop.py YANGI** — 27 test: world state add/flags/compress, VerificationRecord 3 status + evidence maydonlari, A-B aylanma ushlash, stuck, executor action_id uniqueness, world tracking, native loop-guard |
| Regressiya | 17 test-fayl: 439 passed + 320 subtests ✅ |

**Natija:** §3/§4/§9/§10 asosiy bo'shliqlari yopildi (§8 executor checkpoint qoldi). SM endi real observation ma'lumoti bilan ishlaydi — confirmed facts bo'lmasa COMPLETE guard o'tmaydi.

### Phase 3 AUDIT: Memory & Context (§5/§6/§12) — 2026-09-16

Hisobot: `Igris_info/plans/phase3_memory_context_audit.md`

| Bo'lim | Asosiy topilma |
|---|---|
| §5 | Qatlam arxitektura ✅ TO'LIQ: L1 runtime (18 tur, deque+TTL), L2 persistent (24 tur, hash-dedup, 30d/90d archive), AutoDream 5-pass konsolidatsiya, L4 hybrid (BM25+FTS5+RRF), PoisoningProtection 2 tomonlama, CAG (LRU+TTL), MAG, time-travel. Zaif: T3 vector ishlamaydi, confidence_score ranking'da ishlatilmaydi, conflict detection YO'Q, compaction scheduler YO'Q |
| §6 | ❌ ENG KATTA BO'SHLIQ: token budget YO'Q — config.py max_context_tokens=4096 HECH QAYERDA ishlatilmaydi, faqat char kesish; overflow graceful degradation yo'q. Yaxshi: goal_pin ✅, compact 2 darajada ✅, MAG dedup ✅ |
| §12 | Ko'p qismi Phase 1/2'da yopilgan (frozen Goal, goal_pin, replan sinxron) ✅; qoldi: executor checkpoint'ga goal ulash + FAIL recovery goal restore + supervisor node goal_id |
| Hujjat | Reja checklistlari (§5/§6/§12) yangilandi |

**Navbat (tavsiya tartib):** ① ContextBudget (§6 — token budget prioritet qatlamlar bilan) ② confidence-weighted recall (§5 — bir qator formula) ③ executor checkpoint + goal restore (§8/§12) ④ compaction scheduler (§5 D2)

### Phase 3 IMPLEMENTATSIYA (①②④): Weighted recall + ContextBudget + maintenance — 2026-09-17

| ID | Nima qilindi |
|---|---|
| §5 | **Confidence-weighted recall** — `final_score = bm25 * (0.5 + 0.5*confidence)` (memory_bridge.search) — confidence_score endi ranking'da ishlatiladi |
| §5 D2 | **Compaction scheduler** — `MemoryBridge.run_maintenance()` — cleanup_stale (30d/90d) kuniga 1 marta avtomatik (start_session trigger + force), thread-safe lock |
| §6 | **ContextBudget** (`context_budget.py`) — max_tokens=config max_context_tokens=4096 endi ISHLATILADI; `fit_prompt()` prioritet qatlamlar: goal_pin/user > system/req > memory > history; token estimatsiya `len//3` deterministik |
| §6 | **Overflow graceful degradation** — budget oshsa: memory tashlanadi → eski history tashlanadi → goal_pin/user doim saqlanadi; chat() va chat_stream() ikkalasi ham fit_prompt orqali o'tadi (chat + chat_stream'da 2 chaqiruv nuqtasi) |
| Test | **test_phase3_context.py YANGI** — 38/38: weighted recall formula, maintenance interval/force/disabled, token estimatsiya, prioritet qatlamlar, overflow degradation |
| Regressiya | test_phase3_checkpoint.py 16/16 ✅ (③ bilan birga Phase 3 to'liq yopildi) |

**Natija:** Phase 3 (Memory & Context §5/§6/§12) to'liq yopildi — 4 tavsiyaning hammasi implementatsiya qilindi (①②③④). Qolgan kichik bo'shliqlar: conflict flag (§5), T3 vector retrieval, memory layer priority — Phase 4+ ga qoldirildi. Navbat: **Phase 4 Resilience** (§11 Failure & recovery, §15 Runtime control, §16 Observability).

### Phase 4 AUDIT: Resilience (§11/§15/§16) — 2026-09-17

Hisobot: `Igris_info/plans/phase4_resilience_audit.md`

| Bo'lim | Asosiy topilma |
|---|---|
| §11 | Asosiy mexanizmlar Phase 1–3'da YOPILGAN: ToolError{error,code,recoverable} + retry/LLM-fix, LLM circuit exponential backoff (2^n), max_retries/repair/iter limitlari, detect_loop/detect_stuck, request_human HITL, checkpoint partial/resume, quality gate. Qoladi: same-error→escalate counter, ErrorType enum rasmiylashtirish, alternative action |
| §15 | ✅ state (RunManager+SM), pause/resume (checkpoint), timeout (per-tool), resource limits (max_iter/token budget), health (/api/status circuit) | ⚠️ ASOSIY BO'SHLIQ: **cancellation endpoint yo'q** — run tashqaridan to'xtatilmaydi; task queue + CPU/RAM monitoring yo'q (solo lokal agent uchun past prioritet) |
| §16 | ✅ task/goal/action ID, SM transition log, tool_calls log (+duration_ms), VerificationLog, ContextBudget report, recall/remember latency, **live progress (RunManager progress_cb — plan'dan tashqari bonus)**. ❌ recovery log; ⚠️ structured error log, LLM decision log, timeline |
| Hujjat | Reja checklistlari (§11: 13/14, §15: 6/10, §16: 7/14) yangilandi |

**Navbat (tavsiya tartib):** ① Cancellation (§15 — POST /api/agent/run/{id}/cancel + executor threading.Event) ② Same-error→escalate (§11 — N x bir xil error → request_human) ③ Structured error/recovery log (§16 — errors[] natijada) ④ ErrorType enum (§11). Past prioritet: task queue, CPU monitoring, LLM decision log.

### Phase 3 IMPLEMENTATSIYA (③): Executor checkpoint/resume + goal restore (§8/§12) — 2026-09-16

| ID | Nima qilindi |
|---|---|
| §8 | **Executor checkpoint** — `_write_checkpoint()` har step'dan keyin atomik yozadi (.tmp→rename): goal (immutable Goal to'liq), sm_state, history, plan, completed_step_ids, world state summary; run() yakunida ok→checkpoint cleared, partial→kept (resume uchun) |
| §8 | **`resume_from_checkpoint(task)`** — checkpoint'dan qolgan qadamlarni davom ettiradi; bajarilgan step'lar `completed_step_ids` bo'yicha skip qilinadi |
| §12 | **Goal restore** — `_restore_checkpoint_for_task(task)`: yangi run bir xil task uchun checkpoint papkasida saqlangan goal'ni tiklaydi — **har xil executor bir xil goal_id** (goal continuity test bilan tasdiqlandi) |
| §1 | SM history checkpoint bilan saqlanadi — resume'da state machine konteksti to'liq tiklanadi |
| Test | **test_phase3_checkpoint.py YANGI** — 16 test: round-trip (goal restore), goal_id STABIL, step-skip (completed), checkpoint lifecycle (ok→cleared / partial→kept), SM history tiklanishi |
| Regressiya | 18 test-fayl: 444 passed + 320 subtests ✅ |

**Natija:** §8 executor darajasida interruption/resume va §12 FAIL recovery'da goal avtomatik restore yopildi. Supervisor CheckpointManager (pipeline daraja) endi executor darajasiga mos keladi.

---

### Phase 4 IMPLEMENTATSIYA (①–④): Cancellation + same-error escalation + structured logs + ErrorType — 2026-09-17

**Kategoriya:** Resilience / §11 Failure & recovery, §15 Runtime control, §16 Observability

| Komponent | Nima qilindi |
|---|---|
| ① Cancellation (§15) | `AgentExecutor.cancel_event: threading.Event` + `_check_cancelled()` — planned loop, mid-step, native loop va `_call_with_retry`'da tekshiriladi; status `cancelled`, SM → UNKNOWN (FAILED emas); `RunManager.cancel(id)` + `POST /api/agent/run/{id}/cancel` endpointi (circuit-breaker'aqlli 503) |
| ② Same-error → escalate (§11) | `_record_tool_error()` — oxirgi N=3 xato bir xil (tool+message) bo'lsa: (a) planned: step `request_human` bilan almashtiriladi, (b) native: modelga HITL escalation user-message yuboriladi |
| ③ Structured logs (§16) | `_error_log` (type/tool/message/time) + `_recovery_log` (replan/arg_fix/escalate_hitl/cancelled) — run() natijasida `errors[]` va `recovery_events[]` |
| ④ ErrorType enum (§11) | `tools/base.py`: `ErrorType(IntEnum)` — NETWORK/TIMEOUT/VALIDATION/PERMISSION/NOT_FOUND/RESOURCE/UNKNOWN + `tool_error_type(message)` pattern-klassifikatsiya; `tools/__init__` eksport qiladi |
| Test | **test_phase4_resilience.py YANGI** — 11 test: cancel (planned/native/mid-step/endpoint), same-error escalation, error/recovery loglar, ErrorType klassifikatsiya |
| Regressiya | test_skills_mcp_hitl 18/18, phase1_foundation 48, phase1_integration 19, phase2_core_loop 27, phase3_context 38/38, phase3_checkpoint 16, executor ✅, deliverable_run 13 ✅ |
| Bugfix | native loop'da `detect_stuck` hisobiga gap-reprompt iteratsiyalari kirmasligi tuzatildi (`iterations - gap_reprompted`) — bo'sh javob oqimi erta "partial"ga tushib qolmasligi uchun |

**Natija:** §11/§15/§16 audit tavsiyalari ①–④ amalga oshirildi; Phase 4 IMPLEMENTATSIYA yakunlandi. Qolgan past-prioritet: task queue, CPU monitoring, unified timeline.

---

### Phase 5 AUDIT: Communication & Polish (§13/§14/§18) — 2026-09-17

**Kategoriya:** Audit / plans/phase5_communication_audit.md

| Bo'lim | Natija |
|---|---|
| §13 Communication | 6/9 ✅ — user-facing generator (`_ask_final_summary`), failure-reporting, `completion` record, 3-qatlamli duplicate kamaytirish (CAG/seen_calls/HITL-dedup); ⚠️ verified-only speech, step N of M; voice N-A |
| §14 LLM Output Contract | 7/10 ✅ — deterministik intent router, tool schema'lar, `_extract_json` (3 daraja) + fallback planner, `validate_plan_tools` hallucination guard, capability-gap reprompt; ⚠️ alohida decision/reasoning maydonlari |
| §18 Test Suite | 15/17 ✅ — 17 senariydan 15 tasi qamrab olingan + CI (test.yml Py 3.10–3.12, nightly, benchmarks); ❌ memory conflict testi; ⚠️ long-running e2e |
| Regressiya bazasi | 30+ test fayl, oxirgi to'liq yugurish: 48+19+27+38+16+11+18+13 test ✅ |

**Natija:** Phase 5 asosiy talablari deyarli to'liq yopilgan; qolgan 5 bo'shliqdan 3 tasi kichik refaktor (step N of M progress — 1 qator; decision/reasoning maydonlari — ixtiyoriy schema kengaytirish; memory conflict testi). Phase 6 (Final Audit) ga tayyor.

---

### Phase 5 IMPLEMENTATSIYA (①–③): step N of M + plan decision maydonlari + memory conflict — 2026-09-17

**Kategoriya:** Communication & Polish / §13(6), §14(4,6), §18(9)

| # | Tuzatish | Fayl |
|---|---|---|
| ① | Planned loop'da har step boshlanishida `step {i}/{len(plan_steps)}: {title}` progress (UI real o'rinni ko'radi) | executor.py |
| ② | Plan JSON ixtiyoriy `reasoning` (≤500) + `confidence` (0..1) maydonlari; prompt schema yangilandi; fallback `confidence: 1.0`; maydonsiz plan backward-compatible | planner.py |
| ③ | `MemoryBridge.detect_conflicts(query)` — deterministik conflict deteksiya: signal-so'zlar ("not/renamed/outdated/obsolete/...") yozuvlar + normal yozuvlar score yaqinligi (≤40% farq) bo'lsa CONFLICT flag; `test_phase5_gaps.py` 14 test | memory_bridge.py |
| Test | **test_phase5_gaps.py YANGI** — 14 test: decision maydonlari (6), conflict (6), step progress (1), prompt schema (1); 15/15 CHECKS |
| Regressiya | foundation 48, integration 19, core_loop 27, context 38, checkpoint 16, resilience 11, skills_mcp 18, deliverable 13, executor ✅ |

**Natija:** Phase 5 checklistlari: §13 → 7/9, §14 → 8/10, §18 → 16/17. Faqat verified-only speech solishtiruvi, rasmiy Decision modeli va long-running e2e qoldi (hammasi past prioritet). **Phase 6: Final Audit ga tayyor.**

---

### Phase 6 FINAL AUDIT: Architecture + Diagnostics + Documentation (§19/§20) — 2026-09-17

**Kategoriya:** Final Audit / plans/phase6_final_audit.md

| Bo'lim | Natija |
|---|---|
| §19 Architecture | **17/17 ✅** — SM, goal hierarchy, planning/execution separation, world state, memory layers, context pipeline, tool contract, verification, recovery, loop control, loop-guard, cancellation, resume, goal preservation, communication, LLM boundary, critical paths (32/32 test fayl PASS) |
| §20 Diagnostics | **11/11 ✅** — 9 qatlam diagnostika vositalari tasdiqlandi; keraksiz qatlam topilmadi (import-graf: layered_agent/quick_paths/composition — hammasi ishlatiladi); **yakuniy mermaid diagramma + Architecture v1.0 spec (10 band)** hisobotda |
| Documentation | agentic_architecture.md ✅, plans/phase1–6 ✅, CI 6 workflow ✅; ⚠️ yagona qoldiq: README.md Structure bo'limi yangi core modullarni o'z ichiga olmaydi |
| To'liq test suite | 32/32 test fayl PASS (bu sessiyada hammasi yugurtirildi, CRLF-ga chidamli tekshiruv) |

**Natija:** IGRIS Architecture Audit Plan — 22/22 bo'lim yopildi, 6 fazalik yo'l xaritasi to'liq bajarildi. Keyingi tavsiyalar (yangi reja kerak): README modernizatsiya, verified-only speech solishtiruvi, rasmiy Decision modeli, long-running e2e.

---

### README.md modernizatsiya — 2026-09-17

**Kategoriya:** Documentation / Phase 6 qoldig'i

| Bo'lim | O'zgarish |
|---|---|
| Sarlavha | agentic core (v1.0) 4-band qo'shildi — SM/Goal/Executor/Verifier xulosa |
| Structure | Yangi core modullar: executor, state_machine, goal_model, planner, world_state, request_classifier, context_budget, memory_bridge, cag/mag/hooks, server.* modullari, tools/ paketi, skills/, benchmark, test_*.py (32 fayl), CI workflows |
| Endpoints | Eskirgan 7 ta endpoint ro'yxati → ~45 endpoint: chat/stream (SSE), agent/run+cancel, HITL respond, health/*, system/* |
| New section | "Agentic architecture (v1.0)" — harness kontseptsiyasi, core loop, resilience, observability xulosasi, phase1–6 havolalari |
| Next steps | Streaming (allaqachon bor) olib tashildi; o'rniga §5 T3 vector recall, verified-only speech, long-running e2e |

**Natija:** README.md real modul arxitekturasi bilan mos (160→223 qator). Phase 6'dagi yagona documentation qoldig'i yopildi.

---

### ROADMAP v2 tuzildi: Polish + E2E + Vector Recall — 2026-09-17

**Kategoriya:** Planning / plans/IGRIS_Roadmap_v2_Polish_E2E_Vector.md

| Phase | Mavzu | Asosiy item'lar |
|---|---|---|
| A (1 hafta) | Memory upgrade | **T3 vector recall** — hash-based deterministic embedding (offline kafolat) + MiniLM optional; layer priority; conflict belgisi recall'da; o'zbekcha stemmer |
| B (1 hafta) | Verified speech & Decision | final xulosa da'volari verifications bilan deterministik solishtiruv; `decision.py` rasmiy Decision modeli; native loop reasoning trace |
| C (1 hafta) | E2E & Hardening | 20+ qadamli long-running e2e (failure+cancel+resume injection); birlashgan `timeline[]`; CI e2e job; ixtiyoriy FIFO task queue + psutil |

**Tadqiqot asosi:** `VectorIndex` (Igris_Memory/memory/retrieval.py) FAISS+MiniLM bilan mavjud, lekin paket yo'q bo'lsa `search` bo'sh qaytaradi — hash-based fallback v2'ning 1-prioriteti.

**Natija:** v1 reja (22/22) yakunlangach keyingi bosqich rejalashtirildi; maqsad: §14 → 10/10, §18 → 17/17, T3 yopish.

---

### Roadmap v2 Phase A1: HASH-BASED VECTOR RECALL (T3 yopildi) — 2026-09-17

**Kategoriya:** Memory / §5 T3 — Igris_Memory/memory/retrieval.py

| Komponent | Nima qilindi |
|---|---|
| `_hash_embedding()` | char 3-4-gram FNV-1a hash sketch → 384-dim L2-norm vektor; deterministik, stdlib-faqat, model kerak emas |
| `_cosine()` | pure-python kosinus (numpy shart emas) |
| `VectorIndex.build()` | 3-rejimli: MiniLM (agar o'rnatilgan) → HASH fallback (endi JIM ishdan chiqmaydi); `_embedding_mode`="minilm"\|"hash" |
| `VectorIndex.search()` | hash rejimida lazy-build + noise floor 0.05; bo'sh index guard |
| `get_stats()` | yangi `embedding_mode` maydoni |
| Sifat | parafraza sim 0.64 vs alohida 0.10; 'pomidor o'stirish' → 'pomidor ekiladi' (0.29) topildi, unrelated (0.10) topilmadi |
| Test | **test_vector_recall.py YANGI (Igris_Memory) — 19/19 PASS** |
| Regressiya | phase3_context 38/38, phase4 11/11, phase5 15/15, skills_mcp OK, BM25/FTS5/T2 OK |

**Natija:** §5 T3 "vector retrieval ishlamaydi" muammosi yopildi — offline kafolatli semantic recall faol. Roadmap v2 navbati: A2 (layer priority).

---

### Roadmap v2 Phase A2: LAYER PRIORITY + CONFLICT BELGISI — 2026-09-17

**Kategoriya:** Memory / §5 — Igris_brain/memory_bridge.py

| Komponent | Nima qilindi |
|---|---|
| Asos tahlil | L1/L2 recall-format yozuvlarida `score` maydoni YO'Q ekan — weighted recall'da base=0 bo'lib har doim eng pastga tushardi (loyihada yashirin bug) |
| Layer priority | Sintetik base 1.0 (score'siz recall-formatga) + `LAYER_PRIORITY_BONUS` {l1: 0.5, l2: 0.25}; explicit score berilgan bo'lsa hurmat qilinadi; vault yuqori score bilan raqobatlashadi |
| Conflict belgisi | `_looks_conflicting()` mos yozuvlar recall kontekstda `[CONFLICT]` prefiksi bilan — model eski/qarama-qarshi ma'lumotni aniq ko'radi |
| Test | **test_phase_a2_layer_priority.py YANGI — 9/9 PASS** |
| Regressiya | foundation 48, integration 19, core_loop 27, phase3_context 38/38, checkpoint 16, phase4 11/11, phase5 15/15, skills_mcp 18, vector_recall 19/19 — HAMMASI OK |

**Natija:** §5 "memory layer priority" qoldig'i yopildi + yashirin ranking bugi tuzatildi. Roadmap v2 navbati: A3 (o'zbekcha stemmer).

---

### Roadmap v2 Phase A3: O'ZBEKCHA STEMMER — Phase A to'liq yakunlandi — 2026-09-17

**Kategoriya:** Memory / §5 — Igris_Memory/memory/retrieval.py + fts5_index.py

| Komponent | Nima qilindi |
|---|---|
| `uz_stem()` | Iterativ qo'shimcha kesish (max 3 bosqich, 30+ suffiks) + affiks almashinuvi (k→g, q→', p→b, t→d); min-3-belgi ildiz himoyasi |
| BM25 tokenize | Har token asl + stem juftligi (leksik saqlanadi, morfologik qo'shiladi) |
| Apostrof fix | ', ', ʻ, ʼ, ` o'chiriladi — 'o'qish'→'oqish' bir token (avval 'qish' bo'lib buzilardi) — BM25 + FTS5 |
| FTS5 query-side | `_query_tokens()` — MATCH'da stem variant OR bilan (index-side unicode61 o'zgarmas) |
| E2E dalil | "kitoblarni o'qish foydalimi" → 'kitob oqish' hujjati 1-o'rinda; inglizcha so'rovlar buzilmagan |
| Test | **test_uz_stemmer.py YANGI (Igris_Memory) — 18 test / 19 CHECKS PASS** |
| Regressiya | bm25/fts5/t2/vector_recall 19/19, phase3_context 38/38, phase4 11/11, phase5 15/15, A2 9/9, foundation 48 — OK |

**Natija:** **PHASE A TO'LIQ YAKUNLANDI** (A1 vector + A2 layer priority + A3 stemmer). Roadmap v2 navbati: Phase B1 (verified-only speech).

---

### Roadmap v2 Phase B1: VERIFIED-ONLY SPEECH — 2026-09-17

**Kategoriya:** Communication / §13 — Igris_brain/executor.py

| Komponent | Nima qilindi |
|---|---|
| `_verify_summary_claims()` | Final xulosadagi da'volar deterministik tekshiriladi: fayl da'volari (path regex) → tool_calls + workspace.exists; tool nomlari → bajarilganlar ro'yxati. LLM'siz |
| `_apply_claim_check()` | run() va run_native() yakunida chaqiriladi; result'ga `final_claims_checked` + `unverified_claims[]`; dalilsiz da'vo bo'lsa `[claim-check]` correction xulosaga qo'shiladi + recovery log |
| Fail-safe | claim-check istisnosi run'ni hech qachon buzmaydi (`final_claims_checked=False`) |
| E2E dalil | 'config.json yaratildi' (dalilsiz) → ushlandi + correction; 'hello.txt yaratildi' (write_file bor) → o'tdi |
| Test | **test_phase_b1_verified_speech.py YANGI — 10 test / 11 CHECKS PASS** |
| Regressiya | foundation 48, integration 19, core_loop 27, phase3 38/38, checkpoint 16, phase4 11/11, phase5 15/15, A2 9/9, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK |

**Natija:** §13 'Done claim only after verification' + 'failure yashirmaslik' to'liq kuchga kirdi — xulosa hallusinatsiyasi deterministik filtrlanadi. Roadmap v2 navbati: B2 (rasmiy Decision modeli).

---

### Roadmap v2 Phase B2: RASMIY DECISION MODELI + VALIDATION LAYER — 2026-09-17

**Kategoriya:** Output Contract / §14 — Igris_brain/decision.py + validation.py + planner.py

| Komponent | Nima qilindi |
|---|---|
| `decision.py` YANGI | `Decision` + `PlanStep` dataclass — §14 band 2/4/6: intent (KNOWN_INTENTS guard), reasoning, confidence (clamp 0..1), steps, engine, source; `from_plan()` exception-irmas kontrakt; `to_dict()` backward-compatible; `validate()` (duplicate id, llm/empty-steps, tool nom formati) |
| `validation.py` YANGI | §14 band 10 birlashgan layer: parse (`_extract_json`) → schema (`Decision.validate`) → tool-exists (`validate_plan_tools` — SM PLAN→EXECUTE guard'i bilan BIR XIL funksiya, double-source yo'q); `ValidationResult{ok, source, errors, decision}` |
| `planner.decide()` | Fasad: plan() → Decision → ixtiyoriy allowed_tools guard (rad etsa `source=tools_rejected`); fallback intent Requirement'dan |
| Test | **test_phase_b2_decision.py YANGI — 19 test / 19 CHECKS PASS** |
| Regressiya | foundation 48, integration 19, core_loop 27, phase3 38/38, checkpoint 16, phase4 11/11, phase5 15/15, A2 9/9, B1 11/11, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK |

**Natija:** §14 → 10/10 (rasmiy Decision modeli + birlashgan validation layer). Roadmap v2 navbati: B3 (native loop reasoning trace).

---

### Roadmap v2 Phase B3: LLM DECISION TRACE — Phase B to'liq yakunlandi — 2026-09-17

**Kategoriya:** Observability / §16 — Igris_brain/executor.py

| Komponent | Nima qilindi |
|---|---|
| Native decision_trace | Har iteratsiya: `{iteration, reasoning (≤500), tool_calls[], content_preview (≤200)}`; `reasoning` va `thinking` (qwen3) maydonlari ikkalasi olinadi; `result[decision_trace]` |
| Planned decision bloki | `result[decision]`: `{engine, reasoning, confidence, intent, plan_validated, steps_total}` — B2 Decision kontrakti bilan bir xil maydonlar |
| Test | **test_phase_b3_decision_trace.py YANGI — 5 test / 6 CHECKS PASS** |
| Regressiya | foundation 48, integration 19, core_loop 27, phase3 38/38, checkpoint 16, phase4 11/11, phase5 15/15, A2 9/9, B1 11/11, B2 19/19, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK |

**Natija:** **PHASE B TO'LIQ YAKUNLANDI** (B1 verified speech + B2 Decision model + B3 reasoning trace). §16 LLM decision log qoldig'i yopildi. Roadmap v2 navbati: Phase C1 (long-running e2e).

---

### Roadmap v2 Phase C1: LONG-RUNNING E2E — 2026-09-17

**Kategoriya:** Test Suite / §18 — Igris_brain/test_phase_c1_e2e_longrun.py

| Senariy | Natija |
|---|---|
| Full run | 22 qadamli reja → 22/22 done, 22 fayl, checkpoint cleared, 0.1s (time guard 30s) |
| Failure injection | 5-qadamda invalid path xatosi → run davom etdi: 21 done + 1 error step, errors[] to'ldi, status partial (crash yo'q) |
| Cancel injection | 3-write'dan keyin cancel_event.set() → status cancelled, checkpoint kept, 3 step progress saqlandi |
| Resume | resume_from_checkpoint(goal_id): qolgan 19 qadam bajarildi, 1-3 skip, goal_id STABIL (§12), yakuniy ok + checkpoint cleared, 22 fayl |
| Edge | checkpoint yo'q → None ✅ |
| Test | **test_phase_c1_e2e_longrun.py YANGI — 4 test / 14 CHECKS PASS** |
| Regressiya | barcha 13 suite OK (foundation 48, integration 19, core_loop 27, phase3 38, checkpoint 16, phase4 11, phase5 15, A2 9, B1 11, B2 19, B3 6, executor, deliverable 13, skills_mcp 18) |

**Natija:** §18 'long-running task', 'user interruption', 'task resume' senariylari endi REAL 20+ qadam e2e bilan qamrovi. Roadmap v2 navbati: C2 (birlashgan timeline).

---

### Roadmap v2 Phase C2: BIRLASHGAN TIMELINE — 2026-09-17

**Kategoriya:** Observability / §16 — Igris_brain/executor.py + test_phase_c2_timeline.py

| Komponent | Tafsilot |
|---|---|
| `_build_timeline()` | SM transitions + tool_calls + errors + recovery_events + verifications → birlashgan chronological `result["timeline"]`; har event `{ts, layer, kind, detail, ...}`; ts'siz eski rekordlar oxirga (crash yo'q) |
| Qamrov | Planned `run()` VA native `run_native()` loop'lari ikkalasida ham; tool record'larga `ts` qo'shildi (tartib aniqligi) |
| Frontend-ready | `GET /api/agent/run/{id}` orqali UI'da ko'rsatishga tayyor struktura |
| Bug fix 1 | `_execute_step`: `record` faqat `if corr:` shoxida yaratilgan edi → har tool call'da UnboundLocalError; endi har doim yaratiladi |
| Bug fix 2 | `_replan`: `int("s1")` ValueError — non-numeric step id position bilan almashtirildi |
| Test | **test_phase_c2_timeline.py YANGI — 3 test / 21 CHECKS PASS** (qatlam qamrovi, ts monotonic, maydonlar, error injection → error qatlami + errors[] mosligi, native + decision_trace) |
| Regressiya | barcha 16 suite OK (foundation 48, integration 19, core_loop 27, phase3 38, checkpoint 16, phase4 11, phase5 15, A2 9, B1 11, B2 19, B3 6, C1 14, executor, deliverable 13, skills_mcp 18) |

**Natija:** §16 "nima bo'ldi?" savoliga endi bitta strukturali javob bor — barcha qatlam voqealari bitta timeline'da. Roadmap v2 navbati: C3 (CI'da e2e qatlami).

---

### Roadmap v2 Phase C3: CI E2E QATLAMI — 2026-09-17

**Kategoriya:** CI / §18 — .github/workflows/test.yml + nightly.yml + pytest.ini

| O'zgarish | Tafsilot |
|---|---|
| `pytest.ini` | `e2e` marker ro'yxatdan o'tkazildi; konventsiya: unit = `-m "not e2e"`, e2e = `-m e2e` |
| Markerlar | C1 (test_phase_c1_e2e_longrun) + C2 (test_phase_c2_timeline) fayllariga `pytestmark = pytest.mark.e2e`; pytest yo'q bo'lsa fail-safe (plain runner ishlaydi) |
| `test.yml` | Yangi **`e2e` job** (`needs: test`): checkout → py3.12 → deps → `pytest -m e2e -v --tb=short`; unit job `-m "not e2e"` — e2e'dan toza |
| `nightly.yml` | To'liq suite (marker filtri yo'q — e2e bilan) + `python -m benchmarks.test_performance` qadam qo'shildi |
| Validatsiya | YAML parse OK (test.yml jobs: test+e2e); pytest: `-m e2e` 7 passed, `-m "not e2e"` 647 passed + 320 subtests; plain-runner 14/14 va 21/21 buzilmagan; benchmark runner lokal OK |
| Qoldiq | GitHub Actions'da real push kuzatuvi (lokal imkonsiz) |

**Natija:** §18 CI qamrovi to'liq — unit/CI tez qoladi, e2e scenario'lar alohida job'da, nightly'da to'liq suite + benchmark regressiya kuzatuvi. Roadmap v2 navbati: C4 (ixtiyoriy task queue + CPU/RAM monitoring) — Phase C'ning oxirgi bandi.

---

### Roadmap v2 Phase C4: HARDENING (FIFO QUEUE + MONITORING) — 2026-09-17

**Kategoriya:** Resilience / §15 — Igris_brain/server.py + server_health.py + test_phase_c4_hardening.py

| Komponent | Tafsilot |
|---|---|
| FIFO queue | `RunManager(max_concurrent=1)` — sig'im to'la bo'lsa run `queued` holatda navbatda; tugaganda `_on_run_finished` avtomatik keyingisini ishga tushiradi; launch xatosida error + zanjir davom etadi |
| Cancel-queued | Navbatdagi run cancel qilinsa navbatdan o'chiriladi, hech qachon ishga tushmaydi (`status: cancelled`) |
| Observability | `queue_info()` (`max_concurrent/active/queued/queued_ids`) → `/api/health/metrics` yangi `runs` bo'limi (`runs_total` bilan) |
| DI | `runner` parametri — real `_run()` o'rniga stub qo'yish mumkin (testlar) |
| psutil | `requirements.txt`ga qo'shildi (optional izoh bilan); bo'lmasa mavjud lightweight fallback ishlaydi — `/api/health/metrics` `system` bo'limi crash qilmaydi |
| Test | **test_phase_c4_hardening.py YANGI — 8 test / 25 CHECKS PASS** |
| Regressiya | barcha 17 suite OK — server testlari ham qamrovdiga (input_validation, skills_mcp_hitl, phase4, executor, deliverable) |

**Natija:** §15 right-sizing qoldiqlari yopildi — bir vaqtda 1 run (konfiguratsiya qilinadigan), qolganlari FIFO navbatda, monitoring `runs` bo'limida. **PHASE C TO'LIQ YAKUNLANDI → Roadmap v2 A+B+C hammasi bajarildi.** Qoldiq: yakuniy audit hisoboti + push qilib CI e2e job kuzatuvi.

---

### Roadmap v3 R1: REQUIREMENT MATRIX + COMPLETION CONTRACT — 2026-09-17

**Kategoriya:** Reality Verification / §2+§17+§28+§19 — requirement_matrix.py (YANGI) + executor.py

| Komponent | Tafsilot |
|---|---|
| `requirement_matrix.py` YANGI | ReqItem (mandatory/optional + check turlari), deterministik extraction (LLM'siz), immutable RequirementSnapshot (tuple + JSON roundtrip), matrix runner (fs evidence), `completion_status()` formal contract |
| Extraction | Fayl nomlari + fe'l konteksti; optional-hint faqat fayl nomidan oldin (oyna kesishuvi bug'i topildi-tuzatildi) |
| Executor integratsiya | Run boshida immutable snapshot; run oxirida matrix → `result["requirement_matrix"]` + `result["completion"]`; FAILED/PARTIAL → status "ok"→"partial" pasaytirish |
| False completion | §19 asosiy senariy bloklandi: fayl yo'q + "bajarildi" xulosa → completion=failed, status=partial (test bilan isbotlangan) |
| Test | **test_r1_requirement_matrix.py YANGI — 17 test / 35 CHECKS PASS** |
| Regressiya | barcha 18 suite OK (foundation 48 ... C4 25) |

**Natija:** TODO §0/§17/§28'ning asosiy kafolati kuchga kirdi — COMPLETE endi requirement matrix evidence'siz mumkin emas. Qoldiq: SM g_complete guard'ini matrix bilan bog'lash (R1.2), checkpoint'ga snapshot (R2).

---

### Roadmap v2 YAKUNIY AUDIT — C4 qoldig'i yopildi — 2026-09-18

**Kategoriya:** Audit / Roadmap v2 A+B+C rasmiy yopilishi — `Igris_info/plans/v2_final_audit.md` (YANGI)

| Qadam | Natija |
|---|---|
| To'liq regressiya | **~752 test passed, 0 failed** — 18+ suite real pytest run bilan (foundation→C4, A2/B1/B2/B3/C2, C1+C4+R1, deliverable/skills/requirements/turbo, degradation/intelligence/svg/input_validation/chat_history/task_supervisor/web_verify, agentic_pipeline 205+320 subtests, probe_decisions 32, Igris_Memory vector/stemmer/fts5/bm25/t2) |
| C3 qoldig'i | GitHub Actions real job kuzatuvi PUSH talab qiladi — lokal imkonsiz; hisobotda push'dan keyingi checklist qoldirildi |
| C4 audit topilmasi | **psutil muhitda o'rnatilmagan edi** (requirements.txt'da bor) — health `system` bo'limi fallback'da ishlab turardi. Tuzatish: `pip install psutil` (7.2.2) → real RSS/CPU/threads faol (stub-agent bilan tekshirildi). Fallback yo'li saqlandi |
| v3 holati | R1 asosiy qismi ✅ (17 test/35 CHECKS); qoldiq: R1.2 (g_complete↔matrix), R2 (checkpoint reconciliation), R3, R4 |

**Natija:** PHASE A+B+C (9/9 band) real test run bilan rasman tasdiqlandi. Roadmap v2 YAKUNLANDI. Navbat: R1.2+R2 yoki push kuzatuvi.

---

### Roadmap v3 R1.2 + R2: CHECKPOINT INTEGRITY + RECONCILIATION — 2026-09-18

**Kategoriya:** Reality Verification / §10+§22+§23+§11 — checkpoint_integrity.py (YANGI) + executor.py + state_machine.py

| Komponent | Tafsilot |
|---|---|
| R1.2 g_complete | SM guard endi ctx `completion` maydonini tekshiradi — matrix 'complete' bo'lmasa COMPLETE mumkin emas (hatto VERIFIED bo'lsa ham); executor planned + native loop'larda `_build_requirement_matrix` natijasini guard ctx'ga uzatadi (BIR MANBA) |
| Checkpoint v2 | `version: 2` + `plan_steps` + `requirements` snapshot + `verifications` (20) + `action_ids` (100); eski v1 o'qiladi, future-version rad |
| Corruption | Har atomik yozishda oldingi valid checkpoint `.bak`ga; parse xato → `.bak` fallback; ikkalasi buzuk → None |
| Staleness | `is_stale()` — workspace mtime > checkpoint ts + grace(0.25s) → `checkpoint_stale: true` |
| Reconciliation | yangi `checkpoint_integrity.py`: resume'da completed step fayllari fs bilan solishtiriladi — HAZIR → skip (duplicate'siz), YO'QOLGAN/0-bayt → REDO; `merge_skip_with_reconciliation` redo'ni skip'dan chiqaradi; hisobot `result["reconciliation"]` |
| Req restore | Checkpoint'dagi requirement snapshot resume'da TIKLANADI — bir xil requirement'lar bilan tekshiruv (immutable kafolat) |
| Test | **test_r2_checkpoint_recon.py YANGI — 15 test PASS** (versioning 2, corruption 2, maydonlar 1, staleness 2, reconciliation 5, resume 3) |
| Regressiya | ~620 test yashil — phase1-5, C1-C4, R1, agentic_pipeline (205+320 subtests), intelligence, input_validation, chat_history, turbo, deliverable, skills, probe, degradation, web_strategy |

**Natija:** §10 checkpoint integrity + §22 reality reconciliation + §23 external detection + §11 duplicate protection yopildi. COMPLETE endi SM guard DARAJASIDA ham matrix evidence talab qiladi (ikki qatlamli kafolat). Navbat: R3 (real task suite + crash scenarios) yoki R4 (domain verifiers).

---

### Roadmap v3 R3: REAL TASK SUITE + CRASH SCENARIOS — 2026-09-18

**Kategoriya:** Reality Verification / §1+§5+§6+§7+§8+§9+§21+§24–26 — workspace_harness.py (YANGI) + 4 test fayl (YANGI) + executor.py (1 bugfix)

| Komponent | Tafsilot |
|---|---|
| Harness | `workspace_harness.py`: tmp workspace + seed/snapshot/diff (files+mtime+sha256), `_cp/` checkpoint papkasi diff'dan ignore |
| Real tasks | `test_r3_real_tasks.py` (8 test): create/modify(hash)/organize(move)/code-gen+run(exit 0)/broken-script xato/CSV→total/multi-file/matrix-backed acceptance — scripted LLM + real executor + real fs, python_exec deny-list uchun runpy naqshi |
| Interruption | `test_r3_interruption.py` (4 test): cancel@1/6/11 (early/mid/late) → har safar resume=ok, 12/12 fayl duplicate'siz; R2 reconciliation hisoboti resume'da; ketma-ket cancel→resume→resume dublikatsiz. MUHIM PATTERN: cancel_event executor CONSTRUCTOR'iga uzatiladi (LLM va executor BIR event'ni bo'lishadi) |
| SIGKILL | Real `subprocess.Popen` + `proc.kill()` (write#4 marker'da) → checkpoint diskda QOLADI → yangi jarayonda cross-process resume → 12/12 fayl (§21) |
| Long-run | `test_r3_longrun.py` (6 test): 60 step (50+ talab), SM forward-only (60 execute event monoton), growth (timeline writes ≥ 60 + verifications), 5×60-step ketma-ket izolyatsiya (checkpoint qoldiqsiz), slow-LLM 10ms (2.0s), max_tool_calls=10 → stopped cleanly → resume → 60/60 |
| Acceptance | `test_r3_acceptance.py`: §26 15 senariy runner — **15/15 PASS** (jadval + exit-code kontrakt); har senariy requirement_matrix bilan yakunlanadi; s14 requirement-failure (FAIL aniqlanadi), s15 false-completion (tool'siz → stopped, 'ok' emas) |
| Bugfix | `clear_checkpoint` `.bak`'ni o'chirmasdan qoldirar edi (stress izolyatsiyasi buziladi) — endi checkpoint + `.bak` birga o'chiriladi |
| Regressiya | R3+R2+phase3/4: 50 PASS; phase1-2-3-5+C1+C2+C4+R1: 83 PASS; agentic_pipeline+intelligence+input_validation+chat_history+degradation+probe: 312 PASS + 320 subtests |

**Natija:** §24 long-run + §25 stress + §26 acceptance (15/15) + §21 SIGKILL + §9 interruption matrix yopildi. Roadmap v3'da qoldi: **R4** (domain verifiers: §14 expected-output, §15 source evidence, §16 document verify, §13 full manifest) + §27 requirement-linked trace.

---

### Roadmap v3 R4: DOMAIN VERIFIERS — 2026-09-18

**Kategoriya:** Reality Verification / §13+§14+§15+§16 — domain_verifiers.py (YANGI) + executor.py integratsiya + workspace_harness.py (bytes seed) + 1 test fayl (YANGI)

| Komponent | Tafsilot |
|---|---|
| §14 code | `verify_code_output(code, expected=, pattern=)` — izolyatsiyada run + stdout solishtirish; deny-list/timeout → NEYTRAL (None); crash → FAILED (oxirgi stderr qatori evidence) |
| §15 research | `verify_source_evidence()` — manba + SHA-256 hash; summary'da havola majburiy; missing/empty → FAILED |
| §16 document | `verify_document()` — .md bo'limlar (+required), .csv, .json, .html, .docx (ZIP konteyner); noma'lum ext → neytral |
| §13 manifest | `verify_file_manifest()` — exists/size>0/UTF-8 + unexpected leak (>=limit → FAIL; `_cp/`/`.git` ignore) |
| Routing | `run_domain_verifiers(root, task, written)` — yozilgan fayl ext bo'yicha verifier'ga; har natija VerificationLog'ga `method="domain:..."` bilan yoziladi |
| Status | ok=False → executor "ok"→"partial" (§29 golden rule); fail-safe: verifier xatosi run'ni buzmaydi |
| Test | **test_r4_domain_verifiers.py — 30 test PASS** (kod 7, manba 5, hujjat 7, manifest 5, routing 4, integratsiya 2) |
| Real catch | R3 acceptance s08 soxta README (34 belgi, tuzilishsiz) document verifier'da USHLANDI — senariy real 3-bo'limli hujjatga tuzatildi (verifier kuchsizlantirilmadi) |
| Regressiya | R1–R4+phase3/4: 97 PASS; phase1-2-3-5+C1+C2+C4+pipeline+intelligence+validation: 304 PASS + 320 subtests |

**Natija:** §13+§14+§15+§16 — A1 falsafasi executor darajasida yakunlandi: tool natijasiga emas, artefaktni O'ZINI tekshiruv 4 domaynda ishlaydi. Roadmap v3 qoldiqlari: §27 requirement-linked trace, §21 OOM simulyatsiyasi.

---

### Roadmap v4 PHASE A: MEMORY CONFLICT + CONTEXT FILTER + PIPELINE SAFETY — 2026-09-18

**Kategoriya:** Protocol 100 / v1 §5+§6+§8 qoldiqlari — memory_conflict.py (YANGI), context_filter.py (YANGI), pipeline_safety.py (YANGI) + 3 test fayl (YANGI)

| Komponent | Tafsilot |
|---|---|
| A1 §5 Memory | `memory_conflict.py`: contradiction detection (bor/yo'q, installed/not, true/false — nuqtali kalit regexi bilan, works/doesn't, passed/failed), `mark_conflicts` ([CONFLICT] maydonlari), `apply_layer_priority` (L1>L2>retrieval + tie-break), `filter_relevant` (min_score + overlap + keep) |
| A2 §6 Context | `context_filter.py`: relevance scoring (overlap + layer weight), `rank_context_layers` (cross-layer umumiy tartib), `dedup_layers` (fingerprint sha256, `dup_of`), `build_context` (pipeline + stats) |
| A3 §8 Pipeline | `pipeline_safety.py`: `StageInput/StageOutput` TypedDict; `InterruptiblePipeline` (har bosqichda cancel → atomik checkpoint kept → resume o'sha bosqichdan; stage xato → stopped; goal_id tekshiruvi); `WorkspaceBackup` (.igris_backups snapshot/restore — modified restored, extra deleted, deleted restored; prune) |
| Test | A1: 16, A2: 10, A3: 12 = **38 yangi test PASS**; regressiya R1-R4+phase1-4: 103 PASS |
| Real catch | Statement splitter `.` bo'yicha kesganda nuqtali kalit (cache.enabled) buzilardi — regex `\.\s+` (probelli nuqta) bilan tuzatildi |

**Natija:** v4 PHASE A (9/9 band) yakunlandi. v3 R3+R4 esa rejadagi F+G1 fazalaridan OLDIN allaqachon yopilgani hujjatga qayd etildi. Navbat: PHASE B (§7 tool protocol + §9 loop + §10 verification).

---

### Roadmap v4 PHASE B: TOOL PROTOCOL + AGENTIC LOOP + VERIFICATION — 2026-09-18

**Kategoriya:** Protocol 100 / v1 §7+§9+§10 qoldiqlari — tool_protocol.py (YANGI), verification_comparison.py (YANGI) + executor.py integratsiya + 1 test fayl (YANGI, 30 test)

| Komponent | Tafsilot |
|---|---|
| B1 §7 retry | `retry_policy()` — read:1, write:2, exec:2, web:1, destructive:0; `is_retryable()` faqat timeout/internal kodlari |
| B1 §7 schema | `output_schema_for()` 13 tool + `validate_output()` — ok=True'da on_ok maydonlar, ok=False'da error majburiy |
| B1 §7 verify | `verify_write_on_disk()` — write/patch/rename/mkdir'dan keyin disk mavjudlik+size+content-match (yolg'on tool ushlanadi) |
| B1 mavjud | precondition + ToolError Phase 1'da allaqachon bor edi — qayta yozilmadi (hujjatda belgilandi) |
| B2 §9 UUID | decision_trace har yozuvida `iteration_id` (iter-uuid12, unique test bilan) |
| B2 §9 reason | `action_reason` — har iteratsiya qaror sababi (reasoning/tool nomlari/content) |
| B2 §9 timeout | `per_iteration_timeout_s` (default 120s) — tool'siz sekin iteratsiya → stopped + recovery log; tool'li iteratsiya kesilmaydi; planned fallback bloklanadi (native status saqlanadi) |
| B3 §10 mapping | `map_expected_from_task()` — backtick fayllar, prints N, sum of A and B, containing 'X' — deterministik |
| B3 §10 compare | `VerificationComparison{match, score, diff, method}` + exact/semantic(SequenceMatcher)/numeric(float eps) + `compare_all()` |
| B3 integratsiya | planned + native loop'larda `result["expected_comparison"]`; stdout expected faqat python_exec bo'lsa (false-positive partial oldini olish); mismatch → status ok→partial |
| Test | B1: 13, B2: 4, B3: 13 = **30 yangi test PASS**; regressiya: 150 (A+B+R1-R4+phase1-4) + 268 + 320 subtests |
| Real catch | Boshlang'ich timeout implementatsiyasi tool bajarilgan iteratsiyani ham kesardi + planned fallback statusni yo'qotardi — ikkalasi tuzatildi (test bilan qamrovdigan) |

**Natija:** v4 PHASE B (14/14 band) yakunlandi. Navbat: PHASE C (§13 communication + §14 LLM output contract) yoki PHASE D (§15 runtime + §16 observability + §17 deterministic).

---

*Yangi sessiya qo'shishda: sana, kategoriya, ID/nom, nima qilindi, natija.*
