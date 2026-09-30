# PHASE 4 — RESILIENCE AUDIT REPORT
# IGRIS Architecture Audit Plan → Phase 4 natijalari

> Sana: 2026-09-17
> Qamrov: §11 Failure & Recovery, §15 Runtime Control, §16 Observability / Debugging
> Metod: executor.py (retry/repair/loop-guard), tools/base.py (ToolError/ToolMeta), state_machine.py (guards/history), igris_agent.py (LLM circuit/backoff), server.py (RunManager/HITL/progress), Phase 2/3 artefaktlari (detect_loop/detect_stuck, checkpoint, VerificationLog, ContextBudget)
> Holat: ✅ AUDIT YAKUNLANDI — ko'p qismi Phase 1–3'da yopilgan; asosiy bo'shliq: cancellation endpoint, task queue, per-iteration deadline, alohida error/recovery log

---

## §11. FAILURE & RECOVERY

### 11.1 Mavjud mexanizmlar xaritasi (kod asosida)

| Mexanizm | Implementatsiya | Baholash |
|---|---|---|
| **Tool error formati** | `ToolError{error, code, recoverable}` (tools/base.py §7.3): 4=timeout, 5=internal; `to_tool_result()` barcha tool'larda | ✅ standart |
| **Retry + LLM correction** | `executor._call_with_retry` (max_retries): xato → `_ask_fix` (LLM'dan to'g'irlangan tool/args) → qayta; native rejada repair loop (max_repair=3) | ✅ |
| **Exponential backoff** | LLM darajasida: `_llm_failure_count` → cooldown `2^n` (cap 2^4), circuit state /api/status'da (state, failure_count, open_since) | ✅ LLM transport uchun |
| **Retry limitlari** | `max_retries` (tool), `max_repair=3` (DAG context), `max_iter=8` (loop), `max_layer_errors` (layered) | ✅ |
| **Takrorlashni bloklash** | Phase 2: `detect_loop` (A→B naqshi, window=6, threshold=2) + `detect_stuck` (6 iteratsiya 0 yozuv) → break + partial | ✅ deterministik |
| **Escalation (HITL)** | `request_human` tool → RunManager `awaiting_human` → frontend `POST /api/agent/respond`; SM holati: `ESCALATE` | ✅ yopiq zanjir |
| **Invalid state/action** | Phase 1: `StateTransitionError` (deterministik transitions), PLAN→EXECUTE guard tool nomlarini registry/MCP bilan tekshiradi | ✅ |
| **LLM invalid output** | `planner._extract_json` (direct/fenced/balanced fallback) + gap re-prompt + loop-guard; `llm+tools` ishonchsiz javob → repair | ✅ |
| **Partial success** | Phase 3 checkpoint: ok→cleared, partial→kept + `resume_from_checkpoint` step-skip | ✅ |
| **Recovery verification** | Phase 2 quality gate (requested vs written files) → SM COMPLETE faqat VERIFIED'da; VerificationLog evidence | ✅ |

### 11.2 Qolgan bo'shliqlar

1. **Yagona ErrorType enum yo'q** — ToolError code'lari bor, lekin executor darajasida TOOL_ERROR/TIMEOUT/INVALID_STATE/LLM_ERROR tipizatsiyasi yo'q; step_result faqat `status: "error"`. Reja qadami (1-2: error types enum + recovery strategy per type) deyarli tabiiy ravishda yopilgan — har xil xato uchun strategiya KODDA mavjud (retry/fix/backoff/resume/HITL), lekin rasmiy enum emas
2. **Same-error counter → escalate yo'q** — `detect_loop` action naqshini ushlaydi, lekin "bir xil error matni 3x → user'ga escalate" aniq hisoblagichi yo'q; hozir max_retries tugagach break+partial bo'ladi (escalate emas)
3. **Alternative action strategy qisman** — `_ask_fix` faqat xuddi shu ishni boshqa args bilan tuzatadi; "boshqa tool/orqa yo'l" taklif mexanizmi yo'q (native rejada LLM o'zi boshqa tool tanlaydi — implicit)
4. **Per-iteration timeout yo'q** — per-tool timeout'lar bor (ToolMeta + subprocess), lekin iteratsiya/task deadline yo'q (§9 checklistida ham qayd etilgan)

### 11.3 Xulosa
§11 amalda **yopiq**: retry/limits/loop-block/escalation/partial/verification barchasi kodda va testlarda (444+ test). Rasmiylashtirish qoladi: ErrorType enum + same-error→escalate counter (kichik, deterministik).

---

## §15. RUNTIME CONTROL

### 15.1 Mavjud holat

| Element | Implementatsiya | Baholash |
|---|---|---|
| Global task state | `RunManager` singleton (server) + `TaskSupervisor`/`WorkingContext` (agent) | ✅ |
| Current state manager | SM (executor run) + RunManager stage/stage_detail (jonli) | ✅ |
| Task queue / priority | — RunManager faqat aktiv run'lar dict; navbat/prioritet YO'Q | ❌ |
| Cancellation | ⚠️ live-build pause (frontend change-request) bor; **cancel endpoint/abort token yo'q** — run to'xtatib bo'lmaydi | ⚠️ |
| Pause/resume | Phase 3: executor checkpoint (atomik JSON) + `resume_from_checkpoint` (step-skip) | ✅ |
| Timeout control | per-tool ✅ (ToolMeta.timeout_s + subprocess timeout: run_command 30s, python 20s cap 60s); per-task/per-iteration ❌ | ⚠️ |
| Resource limits | max_iter=8, max_tool_calls, max_context_tokens=4096 (Phase 3 ContextBudget — ISHLATILADI), L1 memory max_entries, MAG max_chars | ✅ qisman |
| CPU/RAM/GPU monitoring | — hech qanday tizim resurs monitoringi yo'q | ❌ |
| Crash recovery | executor checkpoint + goal restore (Phase 3) — crash'dan keyin qayta run davom etadi; ⚠️ RunManager run holati faqat xotirada (restart'da yo'qoladi; chat tarixi disk'da saqlanadi) | ✅/⚠️ |
| Health checks | `/api/status`: model, llm_available, memory, intelligence, circuit{state, failure_count, open_since} | ✅ |

### 15.2 Asosiy topilmalar

1. **Cancellation endpoint yo'q** — uzoq run'ni tashqaridan to'xtatish imkoni yo'q (faqat jarayon o'zi tugatishi: max_iter/loop-guard). Reja §8'da ham "cancellation token hali yo'q" qayd etilgan. Yechim: RunManager'ga `POST /api/agent/run/{id}/cancel` + executor'ga `threading.Event` cancellation checkpoint'lari (har step boshida tekshirish)
2. **Task queue yo'q** — bir vaqtda bitta run semantikasi; parallel so'rovlar navbatsiz. Solo, lokal agent uchun past prioritet (right-sizing)
3. **CPU/RAM/GPU monitoring yo'q** — right-sizing bo'yicha past prioritet; resurs limitlari allaqachon daraja/daraja cheklovlari bilan almashtirilgan (max_iter, token budget, tool timeouts)

### 15.3 Xulosa
§15 **qisman yopiq**: state/checkpoint/crash-recovery/limits/health ✅; cancellation + queue ❌. Eng foydali qolgan item — **cancellation endpoint** (executor Event + RunManager cancel), chunki uzoq task'ni to'xtatish foydalanuvchi uchun real qiymat.

---

## §16. OBSERVABILITY / DEBUGGING

### 16.1 Mavjud loglar/tracing xaritasi

| Log | Joyi | Baholash |
|---|---|---|
| Task ID | `task_id` (supervisor), `goal_id` UUID (executor, immutable) | ✅ |
| Iteration ID | SM iteration counter; ❌ UUID yo'q (action_id tool darajasida bor) | ⚠️ |
| Action ID | UUID har tool record (Phase 2, uniqueness test) | ✅ |
| State transition log | SM `history()` + `dump_history()` (JSONL); `sm_final_state`, `sm_history_len` natijada | ✅ |
| LLM decision log | ⚠️ qisman: natijada tracing (gap_reprompted, engine, planned_tools); prompt+response+confidence alohida log YO'Q | ⚠️ |
| Tool call log | `tool_calls`: {tool, args, result, output_preview(300), action_id, duration_ms} | ✅ |
| Tool result log | result + ok status | ✅ |
| Verification log | VerificationLog (§10): {action_id, expected, actual, method, status, ts} → `result["verifications"]` | ✅ |
| Memory retrieval log | ⚠️ faqat latency: `recall_ms`/`remember_ms`; query+scores log yo'q | ⚠️ |
| Context composition log | Phase 3: `_last_budget_report` (fit_prompt: qaysi qatlamlar saqlandi/kesildi) | ✅ |
| Error log | ⚠️ step `status:"error"` natijada; type+stack+recovery alohida yo'q | ⚠️ |
| Recovery log | ❌ YO'Q (faqat checkpoint lifecycle: result["checkpoint"] cleared/kept) | ❌ |
| Final completion evidence | verifications + confirmed_facts + world_stats + deliverable check | ✅ |
| Task timeline | ⚠️ qisman: duration_ms + sm_history + tool_calls ketma-ket; birlashgan chronological timeline yo'q | ⚠️ |
| **Live progress (bonus)** | RunManager progress_cb: stage/stage_detail/last_tool/tool_count + `tool_calls_partial` (jonli, immutable swap) — frontend polling real vaqtda ko'radi | ✅ plan'dan tashqari |

### 16.2 Qolgan bo'shliqlar

1. **Recovery log yo'q** — checkpoint resume/circuit backoff/HITL javoblari alohida yozilmaydi (faqat natija record'da iz qoladi)
2. **Error log strukturasi yo'q** — reja qadami: {type, message, stack, recovery_action}; hozir error faqat step status'da
3. **LLM decision + memory retrieval loglar** — debug uchun foydali, lekin solo lokal agent uchun o'rtacha prioritet
4. **Timeline** — tool_calls + sm_history birlashtirilgan chronological event log (kichik refaktor)

### 16.3 Xulosa
§16 **asosiy qismi yopiq** (Phase 1–3 tracing qatlamlari). Qolganlar — "structured error/recovery log" + timeline birlashtirish. Live observability (RunManager progress) plan kutganidan kuchliroq.

---

## IMPLEMENTATSIYA holati (2026-09-17)

Audit tavsiyalari ①–④ amalga oshirildi (test_phase4_resilience 11/11 PASS, to'liq regression ✅):

| # | Tavsiya | Holat |
|---|---|---|
| ① | Cancellation: `POST /api/agent/run/{id}/cancel` + executor `threading.Event` | ✅ `RunManager.cancel()` → `_check_cancelled()` planned/mid-step/native/retry'da; status `cancelled`, SM → UNKNOWN |
| ② | Same-error → escalate (`request_human`) | ✅ `_record_tool_error()` — N=3 bir xil xato bo'lsa planned'da step HITL'ga almashadi, native'da modelga escalation buyrug'i yuboriladi |
| ③ | Structured error/recovery log (`errors[]` natijada) | ✅ `_error_log` + `_recovery_log` — run natijasida `errors[]` va `recovery_events[]` |
| ④ | ErrorType enum | ✅ `tools/base.py`: `ErrorType(IntEnum)` + `tool_error_type()` klassifikatsiya |

Past prioritet (o'zgarmadi): task queue/priority, CPU-RAM monitoring, unified timeline view.

## XULOSA — PHASE 4 HOLATI

| Section | Asosiy topilma | Holat |
|---|---|---|
| §11 | Retry+LLM fix, exponential backoff (LLM circuit), retry/repair limitlari, detect_loop/stuck, HITL escalation, partial+resume, verification gate — HAMMASI KODDA VA TESTDA. Qoladi: ErrorType enum rasmiylashtirish, same-error→escalate counter | ✅/⚠️ |
| §15 | State/checkpoint/crash-recovery/limits/health ✅; **cancellation endpoint YO'Q** (asosiy bo'shliq), task queue/priority yo'q (past prioritet), CPU/RAM monitoring yo'q (past prioritet) | ⚠️ |
| §16 | action_id/goal_id/SM history/tool_calls/verifications/budget-report/latency/live-progress ✅; recovery log + structured error log + timeline ❌/⚠️ | ✅/⚠️ |

**Implementation navbati (tavsiya):**
1. **Cancellation** (§15) — `POST /api/agent/run/{id}/cancel` + executor `threading.Event` (har step checkpoint'ida tekshiriladi) — foydalanuvchiga real qiymat, kichik o'zgarish
2. **Same-error → escalate** (§11) — bir xil error matni N marta → request_human (deterministik counter, HITL allaqachon bor)
3. **Structured error/recovery log** (§16) — errors list natijada: {type, message, recovery_action, ts}; RecoveryEvent qo'shish
4. **ErrorType enum** (§11) — ToolError code'lari asosida executor darajasida rasmiylashtirish (tasniflash uchun)
5. Task queue / CPU monitoring / LLM decision log — past prioritet (right-sizing: solo lokal agent)
