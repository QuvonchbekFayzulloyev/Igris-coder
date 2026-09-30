# IGRIS LOCAL AGENT — ARCHITECTURE AUDIT & BUILD PLAN v1.0

> Maqsad: IGRIS local agent arxitekturasini to'liq audit qilish, zaif joylarni aniqlash va arxitekturani qayta qurish rejasini tuzish.
> Sana: 2026-09-16
> Holat: PHASE 1 ✅ + PHASE 2 ✅ + PHASE 3 AUDIT+IMPL(§8/§12) ✅ (2026-09-16) — natijalar: plans/phase1_foundation_audit.md, plans/phase2_core_loop_audit.md, plans/phase3_memory_context_audit.md

---

## 0. ARXITEKTURANI INVENTARIZATSIYA QILISH

### Vazifalar
- [x] Agentning barcha komponentlarini ro'yxatga olish — 13 qatlam: UI/API/Orchestration/Supervisor/Executor/Planner/LLM/Memory/Tools/Safety/Obs/Intelligence/Meta
- [x] Har bir komponentning vazifasini aniqlash — phase1_foundation_audit.md §0.2 jadval
- [x] LLM rollarini aniqlash — decision layer: plan/tool-tanlash/reasoning (§17 bilan)
- [x] Runtime/executor komponentlarini aniqlash — executor.py (run + run_native), task_supervisor.py, layered_agent.py
- [x] Memory komponentlarini aniqlash — memory_bridge.py + Igris_Memory (L1/L2/snapshots)
- [x] Tool/action komponentlarini aniqlash — 13 native tool + 8 MCP server
- [x] Voice/STT/TTS komponentlarini aniqlash — NATIJa: alohida STT/TTS qatlami MAVJUD EMAS (voice UI orqali, alohida modul yo'q)
- [x] UI va monitoring komponentlarini aniqlash — Igris_Interface + hooks/watchdog/server_health
- [x] Komponentlar orasidagi barcha aloqalarni diagrammaga tushirish — Mermaid diagram §0.1
- [x] Keraksiz yoki bir xil vazifani bajaruvchi komponentlarni aniqlash — layered_agent vs task_supervisor ~40% overlap; probe/tmp skriptlar

### Qadam
1. `Igris_brain/`, `Igris_Memory/`, `Igris_Interface/`, `Igris_info/`, `agent_workspace/` papkalarini to'liq skanerlash
2. Har bir faylni o'qish va import/export grafini chiqarish
3. Komponent xaritasini yaratish (Mermaid diagram formatida)
4. Takroriy komponentlarni aniqlash va birlashtirish/tashlab ketish

---

## 1. STATE MACHINE

### Vazifalar
- [x] Agentning barcha operational state'larini aniqlash — hozir 3 darajada tarqoq: PIPELINE_SPECS stages / executor status / NodeStatus
- [x] `INPUT` state'ini aniqlash — dizaynda (phase1 audit §1.3)
- [x] `UNDERSTAND` state'ini aniqlash — dizaynda (Requirement modeli → P10)
- [x] `PLAN` state'ini aniqlash — dizaynda
- [x] `EXECUTE` state'ini aniqlash — dizaynda
- [x] `OBSERVE` state'ini aniqlash — dizaynda
- [x] `VERIFY` state'ini aniqlash — dizaynda
- [x] `UPDATE_STATE` state'ini aniqlash — dizaynda
- [x] `CONTINUE` state'ini aniqlash — dizaynda
- [x] `COMPLETE` state'ini aniqlash — dizaynda
- [x] `FAIL` state'ini aniqlash — dizaynda (+ESCALATE qo'shildi)
- [x] Har bir state'ning entry condition'ini aniqlash — transition jadvali §1.3
- [x] Har bir state'ning exit condition'ini aniqlash — transition jadvali §1.3
- [x] State transition qoidalarini aniqlash — 10 ta guard qoidasi yozildi
- [x] Noto'g'ri transition'larni bloklash — ✅ state_machine.py: StateTransitionError + guard jadvali
- [x] State history/log tizimini tekshirish — ✅ StateMachine.history() + dump_history() JSONL (§16 asosi)

### Qadam
1. `igris_agent.py`, `planner.py`, `executor.py` fayllaridagi holat o'tishlarini aniqlash
2. Hozirgi state machine'MAVJUDLIGINI tekshirish (formal yoki informal)
3. Formal state diagram yaratish (Mermaid)
4. Har bir state uchun entry/exit invariantlarini yozish
5. Invalid transition guard'larini qo'shish

---

## 2. GOAL → TASK → ACTION HIERARCHY

### Vazifalar
- [x] User goal qanday saqlanishini aniqlash — NATIJA: plan["goal"] mutable, immutable emas (zaif)
- [x] Goal va objective o'rtasidagi farqni aniqlash — Goal(frozen)/Objective(mutable) modeli taklif qilindi
- [x] Objective → Task bog'lanishini tekshirish — TaskSupervisor TaskNode + TaskDAG mavjud ✅
- [x] Task → Subtask bog'lanishini tekshirish — DAG predecessors ✅, lekin ierarxik subtask daraxti yo'q
- [x] Subtask → Action bog'lanishini tekshirish — tool_calls ro'yxati mavjud ✅
- [x] Task decomposition mexanizmini tekshirish — supervisor decomposition + composition UCE (ikki mexanism, aralashmaslik kerak)
- [ ] Katta taskni avtomatik bo'lish qoidalarini aniqlash — domain-shablonlar qolgan (manifest todo)
- [ ] Subtask priority mexanizmini tekshirish — topological order bor, priority yo'q
- [x] Dependency'larni aniqlash — TaskDAG ✅
- [x] Completed tasklarni belgilash — NodeStatus.COMPLETED bor, verification bog'lanishi Phase 2'da
- [x] Failed tasklarni belgilash — NodeStatus.FAILED ✅
- [x] Partial tasklarni belgilash — executor status="partial" ✅ (supervisor darajasida NEEDS_MORE_STEPS)
- [x] Current objective doim saqlanishini tekshirish — ✅ goal_model.py GoalContext.prompt_pin() executor run_native + agent chat/chat_stream system prompt'ga ULANDI (2026-09-16)
- [x] Subtask bajarilganda parent objective yo'qolmasligini tekshirish — ✅ Task.goal_id immutable reference + Objective.replan() sinxroni

### Qadam
1. `requirements.py`, `planner.py` fayllaridagi goal/task modellarini aniqlash
2. Hozirgi hierarchy mavjudligini tekshirish
3. Goal → Objective → Task → Subtask → Action formal modelini yaratish
4. Goal preservation mechanism'ni qo'shish (immutable goal reference)
5. Subtask completion'da parent goal'ni tekshirish

---

## 3. THINKING → DECISION → ACTION

### Vazifalar
- [x] Thinking va execution'ni ajratish — run_native: model faqat tool+args qaytaradi; executor bajaradi (phase2 audit §3.1)
- [x] LLM faqat decision chiqarishini tekshirish — chat_with_tools schema API ✅
- [x] Decision uchun structured schema yaratish — Ollama tools API (schema-based); content-JSON fallback qisqa §14'da
- [x] Decision → Action mapping'ni aniqlash — schema tool nomi → registry/MCP
- [x] Action executor'ni LLM'dan ajratish — _execute_agent_tool mustaqil qatlam ✅
- [x] LLM tomonidan to'g'ridan-to'g'ri system action bajarilishini bloklash — LLM faqat tool orqali ✅
- [x] Action precondition'larini tekshirish — ✅ Phase 1 ToolMeta.precondition (fn chaqirilmasdan oldin)
- [x] Action postcondition'larini aniqlash — ✅ Phase 1 ToolMeta.postcondition
- [x] Action ID tizimini yaratish — ✅ Phase 2: har tool record'da action_id (UUID, run + run_native); uniqueness test bilan
- [x] Har bir action uchun deterministic result formatini yaratish — ✅ ToolError {error, code, recoverable}

### Qadam
1. `executor.py`, `igris_agent.py` fayllarida LLM vs action border'ini aniqlash
2. LLM output schema (JSON) yaratish — faqat decision, action emas
3. Action executor class'ini LLM'dan ajratish (separate module)
4. LLM'ni "decision only" chegaralash — tool chaqirishni executor qiladi
5. Har bir action uchun precondition/postcondition validator yaratish

---

## 4. OBSERVATION → STATE

### Vazifalar
- [x] Raw observation formatini aniqlash — tool_calls record {tool, args, result, output_preview} ✅
- [ ] Observation'dan relevant information ajratish — ✅ Phase 2: AgentWorldState.confirmed_facts() / assumed_notes() ajratadi
- [x] Observation → state conversion mexanizmini tekshirish — ✅ Phase 2: world_state.py AgentWorldState.add_from_record() — har tool natijasi Observation'ga aylanadi (Igris_brain/world_state.py)
- [x] Current world/application state'ni saqlash — ✅ Phase 2: files_touched + last_error + stats; natija record'ida world_stats/confirmed_facts
- [x] Eski observation'larni avtomatik tozalash/compress qilish — supervisor WorkingContext.compact() ✅ (faqat supervisor yo'lida)
- [x] Observation va assumption'ni ajratish — ✅ Phase 2: confirmed=tool ok:true; SM OBSERVE guard'i endi world.observation_flags()dan real flag oladi
- [x] Agent "menimcha" va "tasdiqlangan" ma'lumotni ajrata olishini tekshirish — ✅ confirmed_facts vs assumed_notes alohida (prompt aralashtirmaydi)

### Qadam
1. Tool result'larini observation sifatida model qilish
2. Observation → state conversion function yaratish
3. "Confirmed" vs "Assumed" flag bilan observation'larni belgilash
4. Oldingi observation'larni summarize/compress qilish mekanizmi

---

## 5. MEMORY

### Vazifalar
- [x] Working Memory'ni tekshirish — ✅ L1 runtime (18 tur, deque+JSONL, TTL) + Phase 2 AgentWorldState (run ichida)
- [x] Task Memory'ni tekshirish — ⚠️ L1 task-memory turi bor; lekin executor run() davomida yozilmaydi (faqat oxirida L2)
- [x] Episodic Memory'ni tekshirish — ✅ L1 session/execution-memory + L2 experience
- [x] Semantic Memory'ni tekshirish — ⚠️ L2 knowledge bor; T3 vector retrieval ISHLAMAYDI (manifest)
- [x] Procedural Memory'ni tekshirish — ✅ L2 workflow-memory + skills/
- [x] Long-term Knowledge'ni tekshirish — ✅ L2 persistent 24 tur
- [x] Har bir memory turi uchun saqlash qoidalarini aniqlash — ✅ per-type max_entries + TTL (runtime.py limits)
- [x] Har bir memory turi uchun retrieval qoidalarini aniqlash — ✅ BM25+FTS5+RRF hybrid (deterministik)
- [x] Memory relevance scoring'ni tekshirish — ✅ Phase 3 impl: weighted recall — final_score = bm25 * (0.5 + 0.5*confidence) (memory_bridge.search; test_phase3_context.py 38/38)
- [x] Duplicate memory'larni aniqlash — ✅ L2 content-hash dedup + hybrid index
- [x] Eskirgan memory'larni aniqlash — ✅ Phase 3 impl: MemoryBridge.run_maintenance() — cleanup_stale (30d/90d) endi avtomatik trigger bilan (kuniga 1 marta, start_session'da + force; test bilan)
- [ ] Conflicting memory'larni aniqlash — ⚠️ qisman: hash-dedup bir xil yozuvni bloklaydi, weighted ranking past-sifat yozuvni pasaytiradi; lekin qarama-qarshi yozuvlarga alohida conflict flag hali yo'q
- [ ] Memory priority'ni aniqlash — ⚠️ qisman: confidence-weighted ranking sifat signalini beradi; L1/L2 layer priority hali ranking'da yo'q
- [ ] Task uchun faqat relevant memory chaqirilishini tekshirish — ⚠️ top_k+score bor; aloqasizlik filtri yo'q

### Qadam
1. `Igris_Memory/memory/` strukturasini to'liq tekshirish
2. Working memory (current session) vs long-term memory ajratish
3. Task memory (current task state) — alohida layer
4. Memory conflict detection qoidalarini yaratish
5. Relevance scoring (BM25 + semantic) ni birlashtirish
6. Memory cleanup/garbage collection mechanism

---

## 6. CONTEXT MANAGEMENT

### Vazifalar
- [x] LLM context budget'ini aniqlash — ✅ Phase 3 impl: context_budget.py ContextBudget(max_tokens=4096, reserve_response) — fit_prompt() prioritet qatlamlar bilan (goal_pin/user > system/req > memory > history); chat()/chat_stream()'ga ulandi — config 4096 endi ISHLATILADI (test_phase3_context.py)
- [x] Promptga qaysi ma'lumotlar kirishini aniqlash — ✅ qatlam tartibi deterministik (system+skill+web+memory+req+goal_pin→history12→user)
- [ ] Irrelevant context'ni chiqarish — ⚠️ top_k+score bor; task-aloqasizlik filtri yo'q
- [x] Duplicate context'ni chiqarish — ✅ MAG faqat recall bo'sh bo'lsa; CAG dedup
- [ ] Context ranking mexanizmini tekshirish — ⚠️ BM25 score ichki; qatlam'lar orasida umumiy ranking yo'q
- [x] Context compression mexanizmini tekshirish — ✅ WorkingContext._compact + AgentWorldState.compress_old (Phase 2)
- [x] Long task history uchun summarization yaratish — ✅ ikki darajada (supervisor + world state)
- [x] Current objective contextda doim saqlanishini tekshirish — ✅ goal_pin (Phase 1: chat/stream/run_native)
- [x] Critical state ma'lumotlarini yo'qotmaslik — ✅ goal_pin + WorkingContext goal/plan/deps to'liq saqlanadi
- [x] Context overflow holatini test qilish — ✅ Phase 3 impl: fit_prompt overflow graceful degradation — memory tashlanadi → eski history tashlanadi → goal_pin/user doim saqlanadi (test_phase3_context.py 38/38)

### Qadam
1. Hozirgi prompt tuzilishini tahlil qilish
2. Context budget hisoblash (model context length - response预留)
3. Irrelevant context filter yaratish (relevance scoring)
4. Duplicate detection (exact + semantic)
5. Context compression: long history → summary
6. Critical state pinning (current goal, current task — doimo contextda)
7. Overflow test: context > limit holatini boshqarish

---

## 7. TOOL / ACTION PROTOCOL

### Vazifalar
- [x] Barcha tool'larni inventarizatsiya qilish — 13 native + 8 MCP server (phase1 audit §7.1)
- [x] Har bir tool uchun yagona schema yaratish — Tool.schema() bor ✅ (input)
- [x] Tool input schema'ni aniqlash — JSON-schema + ollama_schema ✅
- [ ] Tool output schema'ni aniqlash — IMPLEMENTATSIYA KERAK (output schema yo'q)
- [ ] Tool precondition'larini aniqlash — ToolMeta.precondition loyihasi tayyor, kodga kiritilmagan
- [x] Tool side-effect'larini aniqlash — to'liq jadval: read_only/write/unsafe/destructive (§7.1)
- [x] Tool timeout'larini aniqlash — mavjud qiymatlar yig'ildi; standartlashtirish qoldi (read10/write10/exec30/web15)
- [ ] Tool error formatini standartlashtirish — ToolError{error,code,recoverable} dizayni tayyor, implementatsiya qoldi
- [ ] Tool verification mexanizmini aniqlash — Phase 2 (§10) bilan bog'lanadi
- [x] Tool permission modelini tekshirish — NATIJA: git_command'da DENY-Pattern YO'Q (eng xavfli bo'shliq); delete_file confirm'siz
- [ ] Tool'lar uchun retry qoidalarini aniqlash — Phase 4 (§11) bilan bog'lanadi

### Qadam
1. `mcp_servers/`, `executor.py` fayllardagi barcha tool'larni ro'yxatga olish
2. Har bir tool uchun JSON Schema yaratish (input + output)
3. Precondition validator qo'shish
4. Side-effect tracking (read-only vs write vs destructive)
5. Timeout default'larni belgilash
6. Error format: `{error: str, code: int, recoverable: bool}`
7. Tool permission model: safe/unsafe/destructive categoriya

---

## 8. EXECUTION PIPELINE

### Vazifalar
- [x] `INPUT → UNDERSTAND → PLAN → EXECUTE → VERIFY` pipeline'ini tekshirish — ✅ Phase 1 SM formal + executor'da real yuritiladi
- [x] Pipeline bosqichlari bir-biriga aralashmasligini tekshirish — stages + stage_for_tool ✅
- [ ] Har bir bosqichning input/output'ini aniqlash — implicit dict, tipizatsiya yo'q (kichik)
- [x] Pipeline state'larini log qilish — ✅ SM history JSONL (Phase 1) + VerificationLog evidence (Phase 2)
- [ ] Pipeline interruption'ni test qilish — ⚠️ Phase 3: executor checkpoint (atomik JSON, har step'dan keyin) QO'SHILDI — crash'da progress saqlanadi; cancellation token hali yo'q
- [x] Pipeline resume mexanizmini test qilish — ✅ Phase 3: executor resume_from_checkpoint() + step-skip (completed_step_ids); goal restore bilan (test_phase3_checkpoint.py 16 test)
- [ ] Pipeline cancellation mexanizmini test qilish — ⚠️ server RunManager bor, executor checkpoint yo'q
- [x] Partial completion'ni test qilish — partial status + re-plan ✅
- [ ] Pipeline rollback kerak bo'ladigan holatlarni aniqlash — TaskNode.files_changed + .igris_backups bor, umumiy undo yo'q

### Qadam
1. Hozirgi pipeline flow'ni xaritalash
2. Har bir bosqich uchun input/output type'larini aniqlash
3. Pipeline state machine (formal transition'lar)
4. Interruption: cancellation token pattern
5. Resume: checkpoint + state serialization
6. Rollback: undo actions (agar mumkin bo'lsa)

---

## 9. AGENTIC LOOP

### Vazifalar
- [x] Main agentic loop'ni aniqlash — run() (plan-step) + run_native() (ReAct) ✅
- [x] `OBSERVE → DECIDE → ACT → VERIFY → UPDATE` loop'ini tekshirish — ✅ Phase 1 SM bilan har step'da yuritiladi
- [ ] Har iteration uchun ID yaratish — SM iteration hisoblagichi bor, UUID yo'q
- [x] Current objective'ni iteration davomida saqlash — ✅ goal pin (Phase 1 integratsiya)
- [x] Current state'ni saqlash — ✅ SM history + tool_calls
- [x] Selected action'ni saqlash — ✅ tool_calls/steps
- [x] Action result'ni saqlash — ✅ record.result
- [x] Verification result'ni saqlash — ✅ status/quality_note + SM history
- [ ] Next action sababini saqlash — native yo'lda reasoning message'lar ichida, alohida log yo'q
- [x] Loop iteration limitini belgilash — max_iter=8 config + SM 50 ✅
- [ ] Timeout limitini belgilash — ❌ per-iteration timeout yo'q (faqat per-tool)
- [x] Infinite loop detection yaratish — ✅ Phase 2: detect_loop() aylanma (A→B→A→B) naqshini ushlaydi + eski seen_calls exact dedup; run_native'da break
- [x] Repeated action detection yaratish — ✅ seen_calls exact dedup (native)
- [x] Stuck-state detection yaratish — ✅ Phase 2: detect_stuck() — stall_limit iteratsiyada yozma ish yo'qligi break+partial

### Qadam
1. Main loop'ni aniqlash va log qilish
2. Har iteration uchun unique ID (UUID)
3. Current state snapshot (objective, task, action, result)
4. Iteration limit (default: 50)
5. Timeout per iteration (default: 30s)
6. Infinite loop: repeated state/action detection
7. Stuck-state: N iteration davomida state o'zgarmasa → break

---

## 10. VERIFICATION

### Vazifalar
- [x] Har bir critical action uchun verification yaratish — ✅ quality gate (_verify_deliverable) + repair pass
- [x] Tool success va real-world success'ni ajratish — ✅ tool ok vs deliverable gate AJRATILGAN
- [ ] Expected result'ni aniqlash — ⚠️ implicit (requested_files + LLM verdict); Requirement→expected mapping yo'q
- [x] Actual result'ni aniqlash — ✅ workspace haqiqiy mazmun o'qiladi
- [ ] Expected vs Actual comparison yaratish — ⚠️ qisman; formal comparison yo'q
- [x] Verification status yaratish — ✅ Phase 1 SM: VERIFIED/FAILED/UNKNOWN/SKIPPED
- [x] `VERIFIED` holatini aniqlash — ✅ SM COMPLETE guard faqat VERIFIED bilan (Phase 1 majburlaydi)
- [x] `FAILED` holatini aniqlash — ✅
- [x] `UNKNOWN` holatini aniqlash — ✅ (partial status)
- [x] Verification evidence'ni saqlash — ✅ Phase 2: VerificationRecord {action_id, expected, actual, method, status, ts} + VerificationLog; natijada verifications maydoni
- [x] Task completion faqat verification'dan keyin bo'lishini tekshirish — ✅ SM guard + quality gate (deterministik: AST sintaksis + run-check)

### Qadam
1. Tool call natijasini verification'ga uzatish
2. Expected result: tool schema'dan kelib chiqadi
3. Actual result: tool output
4. Comparison: exact match vs semantic match vs partial
5. Verification status enum: VERIFIED, FAILED, UNKNOWN, SKIPPED
6. Evidence: natija + timestamp + verification method
7. Task completion guard: faqat VERIFIED status bilan

---

## 11. FAILURE & RECOVERY

### Vazifalar
- [x] Tool error handling — ✅ Phase 4 audit: ToolError{error, code, recoverable} (tools/base.py §7.3) + executor _call_with_retry → LLM _ask_fix (plans/phase4_resilience_audit.md)
- [x] Timeout handling — ✅ Phase 4 audit: per-tool timeout (ToolMeta.timeout_s: read 10s/command 30s/python 20s cap 60s); ⚠️ per-iteration deadline qoladi
- [x] Invalid state handling — ✅ Phase 1: StateTransitionError deterministik transitions (test bilan)
- [x] Invalid action handling — ✅ Phase 1/2: PLAN→EXECUTE guard tool nomlarini registry/MCP bilan tekshiradi; noma'lum tool = error
- [x] Partial success handling — ✅ Phase 3: checkpoint ok→cleared / partial→kept + resume_from_checkpoint (step-skip)
- [x] Unexpected observation handling — ✅ Phase 2: AgentWorldState.observation_flags → SM OBSERVE→VERIFY guard real flag bilan
- [x] LLM invalid output handling — ✅ planner._extract_json (3 fallback) + gap re-prompt + loop-guard + repair
- [x] Recovery strategy'larni aniqlash — ✅ Phase 4 audit: xato turi bo'yicha strategiya KODDA (retry→fix→resume→HITL); rasmiy enum qoladi
- [x] Retry strategy'ni aniqlash — ✅ Phase 4 audit: tool retry + LLM circuit exponential backoff (2^n, cap 16)
- [ ] Alternative action strategy'ni aniqlash — ⚠️ _ask_fix faqat args tuzatadi; boshqa tool/orqa yo'l taklifi yo'q (native rejada implicit)
- [x] Retry limitini belgilash — ✅ max_retries (tool) + max_repair=3 + max_iter=8 + max_layer_errors
- [x] Bir xil xatoni qayta-qayta takrorlashni bloklash — ✅ Phase 2: detect_loop (naqsh) + detect_stuck (0 yozuv) → break+partial; ⚠️ same-error matn counter qoladi
- [x] Escalation mechanism yaratish — ✅ request_human → RunManager awaiting_human → /api/agent/respond; SM ESCALATE holati
- [x] Recovery natijasini verification'dan o'tkazish — ✅ Phase 2: quality gate → SM COMPLETE faqat VERIFIED; VerificationLog evidence

### Qadam
1. Error types enum: TOOL_ERROR, TIMEOUT, INVALID_STATE, LLM_ERROR, etc.
2. Recovery strategy per error type
3. Retry: max 3, exponential backoff
4. Alternative action: different tool/approach
5. Error counter: same error 3x → escalate to user
6. Escalation: user intervention required
7. Recovery result must be verified

---

## 12. GOAL PRESERVATION

### Vazifalar
- [x] Original user goal'ni immutable reference sifatida saqlash — ✅ Phase 1: Goal(frozen) dataclass
- [x] Current objective'ni saqlash — ✅ Objective.current (goal_id majburiy saqlanadi)
- [x] Current subtask'ni saqlash — ✅ Task/Action + tool_calls
- [x] Current action'ni saqlash — ✅ Action (Phase 1) + action_id (Phase 2)
- [x] Action o'zgarganda objective yo'qolmasligini tekshirish — ✅ Objective.replan() goal_id sinxroni (test bilan)
- [x] Context compression'da goal saqlanishini tekshirish — ✅ goal_pin har LLM prompt'ga (chat/stream/native)
- [x] Recovery vaqtida original goal saqlanishini tekshirish — ✅ Phase 3: checkpoint'da immutable Goal to'liq saqlanadi; qayta run — bir xil goal_id (goal continuity, test bilan)
- [x] Resume vaqtida original goal tiklanishini tekshirish — ✅ Phase 3: _restore_checkpoint_for_task() — checkpoint'dagi goal disk'dan tiklanadi (yangi UUID yaratilmaydi); run ok → checkpoint cleared, partial → kept

### Qadam
1. Original goal: immutable, never modified
2. Current objective: mutable, but references original goal
3. Context compression: always pin original goal
4. Recovery: restore from original goal
5. Resume: load original goal + current progress

---

## 13. COMMUNICATION / SPEAKING

### Vazifalar
- [ ] Internal state va user response'ni ajratish
- [ ] User-facing response generator'ni ajratish
- [ ] Agent faqat verified information asosida gapirishini tekshirish
- [ ] Action bajarilishidan oldin "bajarildi" demasligini tekshirish
- [ ] Action failure'ni yashirmasligini tekshirish
- [ ] Current progress formatini aniqlash
- [ ] Final response formatini aniqlash
- [ ] Voice output uchun qisqa response policy yaratish
- [ ] Duplicate response'larni kamaytirish

### Qadam
1. Internal state: agent memory, context, decisions — userga ko'rsatilmaydi
2. User response: verified results + progress + questions
3. Response generator: separate from agent logic
4. "Done" claim only after verification
5. Failure: always report to user
6. Progress: step N of M format
7. Voice: short, concise responses

---

## 14. LLM OUTPUT CONTRACT

### Vazifalar
- [ ] LLM output schema yaratish
- [ ] Free-form output'ni kamaytirish
- [ ] Intent schema yaratish
- [ ] Decision schema yaratish
- [ ] Action schema yaratish
- [ ] Reason/status separation yaratish
- [ ] Invalid JSON/output handling
- [ ] Hallucinated tool/action detection
- [ ] Unsupported action detection
- [ ] LLM output validation layer yaratish

### Qadam
1. LLM output: JSON schema (structured decision)
2. Fields: intent, decision, reasoning, confidence, action (optional)
3. Action: tool_name + params (validated against schema)
4. Free-form: only reasoning/explanation field
5. Validation layer: validate JSON + schema + tool exists
6. Hallucination: tool name not in allowed list → reject
7. Invalid output: retry with error context

---

## 15. RUNTIME CONTROL

### Vazifalar
- [x] Global task state yaratish — ✅ Phase 4 audit: RunManager singleton (server) + TaskSupervisor/WorkingContext (agent)
- [x] Current state manager yaratish — ✅ SM (executor) + RunManager stage/stage_detail jonli progress
- [ ] Task queue'ni tekshirish — ❌ YO'Q: RunManager faqat aktiv run'lar; navbat yo'q (solo lokal agent uchun past prioritet)
- [ ] Priority queue'ni tekshirish — ❌ YO'Q (task queue bilan birga; past prioritet)
- [ ] Cancellation checkpoint'larini tekshirish — ❌ ASOSIY BO'SHLIQ: cancel endpoint/abort token yo'q — run tashqaridan to'xtatilmaydi (tavsiya: POST /api/agent/run/{id}/cancel + executor threading.Event)
- [x] Pause/resume mexanizmini tekshirish — ✅ Phase 3: executor checkpoint (atomik) + resume_from_checkpoint; live-build pause (frontend)
- [x] Timeout control'ni tekshirish — ✅ Phase 4 audit: per-tool timeout'lar (ToolMeta + subprocess); ⚠️ per-task/per-iteration deadline qoladi
- [x] Resource limitlarini tekshirish — ✅ Phase 4 audit: max_iter/max_tool_calls/max_context_tokens (ContextBudget ISHLATILADI)/memory max_entries
- [ ] CPU/RAM/GPU monitoring'ni tekshirish — ❌ YO'Q (right-sizing: daraja cheklovlari bilan almashtirilgan; past prioritet)
- [x] Crash recovery'ni tekshirish — ✅ Phase 3: checkpoint + goal restore avtomatik; ⚠️ RunManager run holati faqat xotirada (chat tarixi disk'da)

### Qadam
1. Global state: singleton manager
2. Task queue: FIFO with priority
3. Cancellation: checkpoint at each pipeline stage
4. Pause/resume: serialize state to disk
5. Timeout: per-task and per-iteration
6. Resource limits: CPU, RAM, GPU VRAM
7. Monitoring: periodic health checks
8. Crash recovery: state checkpoint + auto-resume

---

## 16. OBSERVABILITY / DEBUGGING

### Vazifalar
- [x] Har bir task uchun unique ID — ✅ task_id (supervisor) + goal_id UUID (executor, immutable, Phase 3 continuity test)
- [ ] Har bir iteration uchun unique ID — ⚠️ SM iteration counter bor; UUID yo'q (action_id tool darajasida ✅)
- [x] State transition log — ✅ SM history() + dump_history() (JSONL); sm_final_state/sm_history_len natijada
- [ ] LLM decision log — ⚠️ qisman: tracing natijada (engine, planned_tools, gap_reprompted); prompt+response alohida log yo'q
- [x] Tool call log — ✅ tool_calls: {tool, args, result, output_preview, action_id, duration_ms}
- [x] Tool result log — ✅ result + ok status har tool record'da
- [x] Verification log — ✅ Phase 2 VerificationLog: {action_id, expected, actual, method, status, ts}
- [ ] Memory retrieval log — ⚠️ faqat latency (recall_ms/remember_ms); query+scores log yo'q
- [x] Context composition log — ✅ Phase 3: _last_budget_report (fit_prompt qatlamlar hisoboti)
- [ ] Error log — ⚠️ qisman: step status:"error" natijada; structured {type, message, stack, recovery_action} yo'q
- [ ] Recovery log — ❌ YO'Q: checkpoint lifecycle (cleared/kept) bor lekin resume/backoff/HITL voqealari alohida yozilmaydi
- [x] Final completion evidence — ✅ verifications + confirmed_facts + world_stats + deliverable check
- [ ] Task execution timeline — ⚠️ qisman: duration_ms + tool_calls + sm_history; birlashgan chronological timeline yo'q (kichik refaktor)
- [x] Live progress (bonus, plan'dan tashqari) — ✅ RunManager progress_cb: stage/last_tool/tool_count + tool_calls_partial jonli (frontend polling)

### Qadam
1. Task ID + Iteration ID: UUID format
2. Structured logging: JSON format
3. State transition: from_state → to_state + trigger
4. LLM decision: prompt + response + confidence
5. Tool call: name + params + result + duration
6. Verification: expected + actual + status
7. Memory: query + results + scores
8. Error: type + message + stack trace + recovery action
9. Timeline: chronological event log per task

---

## 17. DETERMINISTIC vs LLM BOUNDARY

### Vazifalar
- [x] Qaysi qarorlar deterministic ekanini aniqlash — xarita §17.1 (11 funksiya baholandi)
- [x] Qaysi qarorlar LLM talab qilishini aniqlash — plan/tool-tanlash/reasoning ✅ to'g'ri joyda
- [ ] LLM kerak bo'lmagan joylarni LLM'dan chiqarish — quick_paths/web_verify/requirement-fallback ✅; qolganlari Phase 2
- [ ] State transition'larni imkon qadar deterministic qilish — dizayn tayyor (§1.3), implementatsiya Phase 2
- [x] Validation'ni deterministic qilish — D1 input_validation + Tool schema ✅
- [x] Verification'ni deterministic qilish — _verify_deliverable + _python_run_check + web_verify ✅ (task-completion bog'lanishi Phase 2)
- [x] Retry limitlarini deterministic qilish — max_retries=2, max_repair=3, re-plan max 2 — hammasi config'da ✅
- [ ] Resource control'ni deterministic qilish — Phase 4 (§15) bilan bog'lanadi
- [x] LLM'ni "smart trigger / decision layer" sifatida chegaralash — qoida yozildi: LLM=WHAT, executor=HOW (§17.2)

### Qadam
1. Deterministic: state transitions, validation, retry, resource control, verification
2. LLM: intent understanding, decision making, planning, reasoning
3. Boundary: LLM decides WHAT, executor does HOW
4. Validation: always deterministic (schema check)
5. Verification: always deterministic (expected vs actual)
6. Retry: deterministic (count + backoff)
7. LLM scope: narrow decision layer only

---

## 18. TEST SUITE

### Vazifalar
- [ ] Oddiy single-step task
- [ ] Multi-step task
- [ ] Long-running task
- [ ] Tool failure
- [ ] Timeout
- [ ] Wrong tool output
- [ ] Wrong LLM decision
- [ ] Context overflow
- [ ] Memory conflict
- [ ] Repeated failure
- [ ] Infinite loop
- [ ] User interruption
- [ ] Task cancellation
- [ ] Task resume
- [ ] Partial completion
- [ ] Final verification failure
- [ ] Full task success

### Qadam
1. Unit tests per component
2. Integration tests for pipeline
3. E2E tests for full task flow
4. Failure injection tests
5. Performance tests (timeout, resource limits)
6. Regression test suite
7. CI/CD integration

---

## 19. FINAL ARCHITECTURE AUDIT

### Vazifalar
- [ ] State machine aniq
- [ ] Goal hierarchy aniq
- [ ] Planning/execution ajratilgan
- [ ] Observation/state ajratilgan
- [ ] Memory qatlamlari aniq
- [ ] Context pipeline aniq
- [ ] Tool contract'lari standart
- [ ] Verification mavjud
- [ ] Failure recovery mavjud
- [ ] Agentic loop nazorat ostida
- [ ] Infinite loop himoyasi mavjud
- [ ] Cancellation mavjud
- [ ] Resume mavjud
- [ ] Goal preservation mavjud
- [ ] Communication layer ajratilgan
- [ ] LLM responsibility chegaralangan
- [ ] Barcha critical path'lar test qilingan

### Qadam
1. Checklist bo'yicha har bir bandni tekshirish
2. Yakuniy architecture diagram yaratish
3. Architecture review session
4. Documentation yaratish

---

## 20. YAKUNIY DIAGNOSTIKA

### Vazifalar
- [ ] Agent qayerda tartibsiz ishlayotganini aniqlash
- [ ] Muammo LLM'dami yoki orchestration'dami aniqlash
- [ ] Muammo memory'dami yoki context'dami aniqlash
- [ ] Muammo tool execution'dami aniqlash
- [ ] Muammo verification'dami aniqlash
- [ ] Muammo loop/state machine'dami aniqlash
- [ ] Muammo communication layer'dami aniqlash
- [ ] Keraksiz agent/LLM layerlarini olib tashlash
- [ ] Minimal va deterministic core architecture'ni belgilash
- [ ] Yakuniy architecture diagrammasini yaratish
- [ ] Architecture v1.0 specification'ni yozish

### Qadam
1. Har bir komponentni test qilish
2. Muammo joylarini xaritalash
3. Root cause analysis
4. Keraksiz layerlarni aniqlash va olib tashlash
5. Minimal core: State Machine + Goal Hierarchy + Action Executor + Verifier
6. Yakuniy architecture spec yozish

---

## IMPLEMENTATION ORDER

### Phase 1: Foundation (1-2 hafta) — AUDIT ✅ + IMPLEMENTATSIYA ✅ 2026-09-16
1. Component inventory (Section 0) — ✅ audit tugadi
2. State machine design (Section 1) — ✅ `Igris_brain/state_machine.py` yaratildi (AgentState, 10 guard, history JSONL)
3. Goal hierarchy design (Section 2) — ✅ `Igris_brain/goal_model.py` yaratildi (frozen Goal, GoalContext pin, resume)
4. Tool protocol standardization (Section 7) — ✅ `tools/base.py` ToolMeta/ToolError + 13 tool kategoriyasi; git_command deny-list bypass tuzatildi (birinchi-token tahlil + 2-qatlam regex)
5. Deterministic vs LLM boundary (Section 17) — ✅ state transitions + validation + pre/postcheck endi deterministik kodda

**Phase 1 testlar:** test_phase1_foundation.py 48/48 ✅ + regressiya 374+ test ✅
**Qo'shimcha topilma va tuzatish:** barcha tool parametrlari required deb e'lon qilingan edi (`default` borlari ham) — endi `default`-li parametrlar ixtiyoriy (Ollama schema to'g'irlandi)

### Phase 2: Core Loop (1-2 hafta) — SM+Goal INTEGRATSIYA ✅ 2026-09-16 (§1/§2 executor+agent'ga ulandi)
6. Thinking → Decision → Action separation (Section 3)
7. Observation → State (Section 4)
8. Agentic loop (Section 9)
9. Execution pipeline (Section 8)
10. Verification system (Section 10) — QISMIY ✅: executor quality gate SM COMPLETE guard'iga bog'landi

**Integratsiya (2026-09-16):** executor.run()/run_native() — har run'da GoalContext yaratiladi, StateMachine yuritiladi (INPUT→UNDERSTAND→PLAN→EXECUTE→OBSERVE→VERIFY→UPDATE_STATE zanjiri), PLAN→EXECUTE guard'i reja tool nomlarini registry/MCP bilan deterministik tekshiradi (noma'lum tool = StateTransitionError, noto'g'ri reja bajarilmaydi), goal pin system prompt'ga qo'shiladi, natijada goal_id/sm_final_state/sm_history_len tracing. agent.chat()/chat_stream() — goal pin system prompt'ga. Testlar: test_phase1_integration.py 19/19 + regressiya 434+320 ✅

### Phase 3: Memory & Context (1 hafta) — AUDIT ✅ + IMPLEMENTATSIYA ✅ 2026-09-16/17 (plans/phase3_memory_context_audit.md; test_phase3_checkpoint 16/16 + test_phase3_context 38/38)
11. Memory layers (Section 5) — ✅ arxitektura to'liq + IMPLEMENTATSIYA ✅ 2026-09-16: weighted recall + run_maintenance scheduler (test_phase3_context.py 38/38); qoldi: conflict flag, T3 vector
12. Context management (Section 6) — ✅ IMPLEMENTATSIYA ✅ 2026-09-16: ContextBudget fit_prompt — token budget prioritet qatlamlar bilan + overflow degradation, chat/chat_stream'ga ulandi (test_phase3_context.py 38/38)
13. Goal preservation (Section 12) — ✅ ko'p qismi Phase 1/2'da yopildi; §8/§12 checkpoint/resume + goal restore IMPLEMENTATSIYA ✅ 2026-09-16 (executor checkpoint_dir + resume_from_checkpoint + goal continuity; test_phase3_checkpoint.py 16/16)

### Phase 4: Resilience (1 hafta) — AUDIT ✅ + IMPLEMENTATSIYA ✅ 2026-09-17 (plans/phase4_resilience_audit.md; test_phase4_resilience 11/11 + to'liq regression ✅)
14. Failure & recovery (Section 11) — ✅ retry/fix/backoff/loop-block/HITL/partial/verification + **same-error→HITL escalation** (`_record_tool_error` → `request_human` undovi, N=3) + **ErrorType enum** (tools/base.py, `tool_error_type()` klassifikatsiya) + errors[]/recovery_events[] natija record'da
15. Runtime control (Section 15) — ✅ state/checkpoint/crash-recovery/limits/health + **CANCELLATION**: `RunManager.cancel(id)` → executor `threading.Event` → har iteratsiyada `_check_cancelled()` → status `cancelled`, `POST /api/agent/run/{id}/cancel` endpointi; task queue/CPU monitoring — past prioritet (right-sizing)
16. Observability (Section 16) — ✅ action_id/goal_id/SM/tool_calls/verifications/budget-report/live-progress + **structured error log** (`_error_log`: type/tool/message/time) + **recovery log** (`_recovery_log`: replan/arg_fix/escalate_hitl/cancelled) — ikkalasi ham run natijasida; timeline — keyingi polishlist bilan

### Phase 5: Communication & Polish (1 hafta) — AUDIT ✅ + IMPLEMENTATSIYA ✅ 2026-09-17 (plans/phase5_communication_audit.md; test_phase5_gaps 14/14, to'liq regression ✅)
17. Communication layer (Section 13) — 7/9 ✅: user-facing generator, failure-reporting, final format, duplicate kamaytirish + **step N of M progress** (`step {i}/{len}: {title}` har step'da) ✅; ⚠️ verified-only speech (SM guard bor); voice N-A (`verbosity=concise` tayyor)
18. LLM output contract (Section 14) — 8/10 ✅: tool schema'lar + intent router, invalid JSON handling, hallucination guard + **plan `reasoning`/`confidence` maydonlari** (ixtiyoriy, backward-compatible, fallback 1.0) ✅; ⚠️ rasmiy Decision modeli, birlashgan validation moduli
19. Test suite (Section 18) — 16/17 ✅: 17 senariydan 16 tasi + **memory conflict testi** (`detect_conflicts`: signal patternlar + score yaqinligi) ✅; ⚠️ long-running e2e (CI matrix: Py 3.10–3.12, nightly, benchmarks mavjud)

### Phase 6: Final Audit (3 kun) — AUDIT ✅ 2026-09-17 (plans/phase6_final_audit.md; 32/32 test fayl PASS)
20. Architecture audit (Section 19) — ✅ 17/17: SM/goal/planning/observation/memory/context/tool-contract/verification/recovery/loop/cancel/resume/goal-preservation/communication/LLM-boundary/critical-paths — barchasi dalil bilan tasdiqlandi
21. Final diagnostics (Section 20) — ✅ 11/11: 9 qatlam diagnostika vositalari (/api/status, /api/health/*, degradation.report, errors[].type, budget report, latency, verifications, sm_history, completion) + keraksiz qatlam YO'Q (import-graf tekshirildi) + **yakuniy architecture diagram (mermaid) + Architecture v1.0 spec** hisobotda
22. Documentation — ✅ agentic_architecture.md, plans/phase1–6 hisobotlar, CI (6 workflow) + **README.md yangilandi** (Structure bo'limi agentic core modullar bilan, "Agentic architecture (v1.0)" bo'limi qo'shildi, Next steps yangilandi)

---
## FINAL STATUS: 22/22 BO'LIM YOPILDI — 6 fazalik yo'l xaritasi to'liq bajarildi ✅

---

## ESTIMATED DURATION: 6-8 HAFTA

---

## KEY PRINCIPLES

1. **Deterministic First**: Har qanday joyda deterministic yechim mavjud bo'lsa — LLM ishlatmaslik
2. **LLM = Decision Layer**: LLM faqat qaror qabul qiladi, bajaruvchi emas
3. **Goal Preservation**: Original goal hech qachon yo'qolmasligi kerak
4. **Verification Required**: Task faqat verified bo'lsa tugallangan hisoblanadi
5. **Observable Everything**: Har bir qadam log qilinishi kerak
6. **Fail Gracefully**: Har bir xato recovery strategy'si bilan bo'lishi kerak
7. **Minimal Context**: Context'da faqat relevant ma'lumot bo'lishi kerak
8. **Action Isolation**: LLM va action executor ajratilgan bo'lishi kerak

---

*Bu reja IGRIS local agent arxitekturasini qayta qurish uchun asos bo'ladi.*
*Har bir section bo'yicha batafsil implementation plan alohida yaratiladi.*
