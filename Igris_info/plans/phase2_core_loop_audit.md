# PHASE 2 — CORE LOOP AUDIT REPORT
# IGRIS Architecture Audit Plan → Phase 2 natijalari

> Sana: 2026-09-16
> Qamrov: §3 Thinking→Decision→Action, §4 Observation→State, §8 Execution Pipeline, §9 Agentic Loop, §10 Verification
> Metod: manba kodi chuqur o'qish (executor.py 1794, igris_agent.py 4446, task_supervisor.py 1072) + Phase 1'da yaratilgan SM/goal_model bilan kesishuv
> Holat: ✅ AUDIT YAKUNLANDI — reja checklistlari yangilandi

---

## §3. THINKING → DECISION → ACTION

### 3.1 Mavjud holat

**Yaxshi yangilik: chegara allaqachon aniq ajratilgan.**

| Element | Joyi | Baholash |
|---|---|---|
| LLM faqat DECISION chiqaradi | `run_native()`: model `chat_with_tools` orqali faqat tool nomi + arguments qaytaradi | ✅ to'g'ri naqsh |
| Action executor LLM'dan ajratilgan | `_execute_agent_tool()` — LLM'dan mustaqil bajaruvchi qatlam | ✅ |
| LLM to'g'ridan-to'g'ri system action yo'q | LLM hech qachon `subprocess`/`os` chaqirmaydi — faqat tool orqali | ✅ |
| Decision → Action mapping | tool schema (Ollama tools API) orqali — xom matn emas | ✅ |
| Action ID | ❌ yo'q — `record = {step, tool, args, result}`; UUID/action_id yo'q | ⚠️ |
| Precondition/postcondition | ✅ Phase 1'da `ToolMeta` orqali qo'shildi (precheck fn CHAQIRILMASDAN oldin) | ✅ yangi |
| Deterministic result format | ✅ `{ok, error, code, recoverable}` (Phase 1 ToolError) | ✅ yangi |
| Correction loop | `_call_with_retry` → `_ask_fix` (LLM tuzatilgan JSON) — max `max_retries` | ✅ limit bor |
| **Hallucinated tool** | `registry.execute` → `Unknown tool` (code=1) + native yo'lda schema ro'yxatidan tashqari nom umuman kelmaydi | ✅ |
| `_replan` LLM chegarasi | max 2 re-plan — cheksiz loop yo'q | ✅ |

### 3.2 Zaif joylar (kamon)

1. **Action ID yo'q** — har bir tool chaqiruv record'ida `action_id` (UUID) bo'lishi kerak (§16 timeline uchun ham zarur)
2. **`_ask_tool_args` placeholder xavfi past lekin bor** — LLM args bermasa `{}` qaytadi, tool halol xato beradi (yaxshi), lekin offline yo'lda `_guess_path` hech narsa topmasa bo'sh
3. **Decision schema rasmiy emas** — Ollama tools API schema'siz modellar uchun `content-JSON fallback` bor; bu yo'lda JSON validatsiya qat'iy emas (§14 bilan bog'lanadi — Phase 5)

### 3.3 Qoida (tasdiqlandi)

```
LLM:   intent + tool tanlash + args + reasoning  (WHAT)
Executor: _execute_agent_tool → Tool.execute trubasi    (HOW)
       precheck (required+type+precondition) → fn → postcheck
       LLM output hech qachon to'g'ridan-to'g'ri bajarilmaydi
```

---

## §4. OBSERVATION → STATE

### 4.1 Mavjud holat

| Element | Joyi | Baholash |
|---|---|---|
| Raw observation | tool natijalari `tool_calls` ro'yxatida (record: tool, args, result, output_preview) | ✅ yig'iladi |
| Observation → state conversion | ❌ TO'LIQ YO'Q — natijalar faqat YIG'ILADI, umumiy "state" obyektiga aylantirilmaydi | ❌ asosiy bo'shliq |
| Confirmed vs Assumed | ❌ kodda flag YO'Q (Phase 1 SM'da `observation_flags` konseptsiyasi bor, lekin tool natijalari hali belgilanmaydi) | ❌ |
| Eski observation tozalash | ✅ supervisor `WorkingContext.compact()` — eski observationlar summarize qilinadi | ✅ (faqat supervisor yo'lida) |
| Observation/assumption ajratish | ❌ yo'q | ❌ |
| Executor yo'lida context rot | ⚠️ `run_native` da messages o'sib boradi; compact YO'Q (faqat `seen_calls` dedup) — uzoq run'da context o'sadi | ⚠️ |

### 4.2 Taklif (Phase 2 implementation uchun tayyor dizayn)

```python
@dataclass
class Observation:
    id: str                     # UUID
    source: str                 # tool nomi
    content: str
    confirmed: bool             # True=tool tasdiqladi, False=assumed
    timestamp: float
    action_id: str              # §3 Action ID bilan bog'lanadi

class AgentWorldState:
    """Tool natijalaridan yig'ilgan joriy holat — faqat CONFIRMED fact'lar."""
    observations: list[Observation]
    files_created: dict[str, str]   # path -> sha/size
    last_error: str | None
    def add(self, obs: Observation) -> None: ...
    def confirmed_facts(self) -> list[str]: ...
    def compress_old(self, keep_last_n: int) -> str: ...  # summary qaytaradi
```

**Bog'lanish:** Phase 1'dagi SM `OBSERVE → VERIFY` guard'i (`observation_flags`) aynan shu model bilan to'ldiriladi.

---

## §8. EXECUTION PIPELINE

### 8.1 Mavjud holat

| Element | Baholash |
|---|---|
| `INPUT → UNDERSTAND → PLAN → EXECUTE → VERIFY` | ✅ Phase 1 SM'da formal; executor'da endi real yuritiladi |
| Bosqichlar aralashmasligi | ✅ stages (plan/read/edit/test/review) nominal + `stage_for_tool()` progress'da |
| Har bosqich input/output | ⚠️ implicit — `step_result` dict, tipizatsiya yo'q |
| Pipeline state log | ✅ Phase 1: SM history JSONL (`dump_history`) |
| **Interruption** | ❌ cancellation token YO'Q — `run()` ni o'rtada to'xtatish vositasi yo'q (faqat `max_tool_calls` limit) |
| **Resume** | ✅ supervisor yo'lida: `CheckpointManager` 2 fayl (task_*.json + exec_*.json) — goal, DAG, active node/stage saqlanadi. **Executor yo'lida resume YO'Q** |
| **Cancellation** | ⚠️ server darajasida RunManager bekor qilishi mumkin (window), lekin executor ichida checkpoint yo'q |
| Partial completion | ✅ `partial` status + re-plan |
| Rollback | ⚠️ TaskNode `files_changed` + `.igris_backups` bor (delete_file backup), lekin umumiy undo mexanizmi yo'q |

### 8.2 Asosiy topilma

**Executor darajasida interruption/resume yo'q** — supervisor darajasida checkpoint tizimi allaqachon puxta (`CheckpointManager` + `TaskCheckpoint` + budget tracking). Bu ikki daraja bir-biriga ulanmagan: executor `run()` supervisor checkpoint'idan bilmaydi.

**Tuzatish yo'li:** `AgentExecutor.run()` ga ixtiyoriy `checkpoint_cb` parametri — har step oxirida `TaskCheckpoint` yozish (goal_id + step id + tool_calls soni). Resume: `run(task, resume_from=checkpoint)`.

---

## §9. AGENTIC LOOP

### 9.1 Mavjud holat

| Element | Baholash |
|---|---|
| Main loop aniqlangan | ✅ `run()` (plan-step loop) + `run_native()` (ReAct tool loop) |
| OBSERVE→DECIDE→ACT→VERIFY→UPDATE | ✅ Phase 1 SM bilan formal — har step'da yuritiladi |
| Iteration ID | ⚠️ SM `iteration` hisoblagichi bor; lekin har iteration UUID'siz |
| Current objective saqlanadi | ✅ yangi: goal pin promptda (§12) |
| Selected action saqlanadi | ✅ `tool_calls` + `steps` |
| Action result saqlanadi | ✅ record.result |
| Verification result saqlanadi | ✅ status/quality_note + SM history |
| Next action sababi | ⚠️ native yo'lda model reasoning message'lar ichida — alohida log Yo'Q |
| Iteration limit | ✅ `max_iter` (config: 8) + SM `max_iter` (50 default) |
| Timeout per iteration | ❌ YO'Q — iteration darajasida vaqt nazorati yo'q (faqat per-tool timeout'lar) |
| **Infinite loop detection** | ⚠️ `seen_calls` dedup (ayniy bir xil tool+args blok) ✅ — lekin AYLANMA (A→B→A→B) aniqlanmaydi |
| Repeated action detection | ✅ qisman (exact dedup) |
| Stuck-state detection | ❌ YO'Q — N iteratsiya davomida holat o'zgarmasa break yo'q |

### 9.2 Tuzatish dizayni (kichik, deterministik)

```python
# run_native loop ichiga (SM bilan):
if sm.iteration >= 6 and not any_new_write:
    status = "stuck"           # yangi status qiymati
    break
# aylanma aniqlash: oxirgi 4 chaqiruv pattern'i takrorlansin:
if tool_signature in last_4_window and window_count >= 2: -> break
```

---

## §10. VERIFICATION

### 10.1 Mavjud holat — eng kuchli tomonlardan

| Element | Baholash |
|---|---|
| Critical action verification | ✅ quality gate (`_verify_deliverable`): fayl yo'q/bo'sh/shablon → repair pass |
| Tool success vs real-world success | ✅ AJRATILGAN: `out.get("ok")` tool darajasi; quality gate deliverable darajasi |
| Expected result | ⚠️ implicit (requested files + LLM verdict) — formal expected schema yo'q |
| Actual result | ✅ workspace o'qib tekshiriladi (haqiqiy fayl mazmuni) |
| Expected vs Actual comparison | ⚠️ qisman — requested_files matching + LLM verify (qisqa fayllarda) |
| Verification status | ✅ Phase 1 SM: VERIFIED/FAILED/UNKNOWN/SKIPPED |
| `VERIFIED` holat | ✅ SM COMPLETE guard'i faqat VERIFIED bilan o'tadi (Phase 1) |
| Verification evidence | ⚠️ quality_note + A1 sintaksis/run natijalari bor; lekin yagona evidence record (expected/actual/method/timestamp) YO'Q |
| Task completion faqat verification'dan keyin | ✅ SM guard majburlaydi |
| Deterministik verifikatorlar | ✅ `_python_syntax_check` (AST) + `_python_run_check` (izolyatsiyada ishga tushirish, 6s) + web_verify grounding — namunali |

### 10.2 Zaif joylar

1. **Verification evidence record yo'q** — `{action_id, expected, actual, method, status, ts}` shaklida yozilishi kerak (§16 bilan bog'lanadi)
2. **Expected result formal emas** — Requirement modelidan (P10) `deliverable` expected'iga mapping qilinmagan
3. **LLM verdict qisqa fayllarda ishonchsiz** — 120 belgidan qisqa fayl LLM'ga beriladi; deterministik qoidalar (masalan bo'sh funksiya skeleti) kengaytirilishi mumkin (A1 qolgan domain-oracle'lar bilan bir qatorda)
4. **Supervisor node COMPLETED belgilash LLM verdict'iga tayanadi** — supervisor yo'lida SM guard hali ulanmagan (Phase 1 integratsiya executor'ni qamrab oldi, supervisor node status transitionlarini TaskStatus.set_status guard'i kutmoqda)

### 10.3 Taklif: VerificationRecord

```python
@dataclass
class VerificationRecord:
    action_id: str
    expected: dict          # {files: [...], min_len, syntax_ok, runs}
    actual: dict            # {files_written, content_len, syntax, run_result}
    method: str             # syntax | run | llm | grounding | requested_files
    status: str             # VERIFIED | FAILED | UNKNOWN | SKIPPED
    note: str
    timestamp: float
```

---

## XULOSA — PHASE 2 HOLATI

| Section | Asosiy topilma | Holat |
|---|---|---|
| §3 | LLM/action chegara ✅ to'g'ri; Action ID yo'q; correction loop limitlangan | ✅/⚠️ |
| §4 | **Observation→State konversatsiya YO'Q** — confirmed/assumed flag yo'q; executor context compact yo'q | ❌ asosiy bo'shliq |
| §8 | Supervisor checkpoint ✅ puxta; **executor darajasida interruption/resume yo'q** — darajalar ulanmagan | ⚠️ |
| §9 | Limitlar ✅; exact dedup ✅; **aylanma/stuck detection yo'q**, per-iteration timeout yo'q | ⚠️ |
| §10 | Quality gate + A1 verifikatorlar namunali; SM COMPLETE guard ✅; **evidence record + formal expected yo'q** | ✅/⚠️ |

**Phase 2 audit tugadi. Implementation navbati (tavsiya etilgan tartib):**
1. `Action ID` + `VerificationRecord` (kichik, ko'p foyda — §3/§10/§16 birga)
2. `AgentWorldState` (Observation→State, §4) — SM OBSERVE guard'ini real ma'lumot bilan to'ldirish
3. Aylanma/stuck detection (§9) — run_native loop'ga
4. Executor checkpoint (§8) — supervisor CheckpointManager'ni qayta ishlatish

