# PHASE 3 — MEMORY & CONTEXT AUDIT REPORT
# IGRIS Architecture Audit Plan → Phase 3 natijalari

> Sana: 2026-09-16
> Qamrov: §5 Memory qatlamlari, §6 Context Management, §12 Goal Preservation
> Metod: memory_bridge.py (473), cag.py (118), mag.py (130), Igris_Memory/memory/ (runtime 307, persistent 353, retrieval 773, autodream 318, fts5, poisoning, time_travel), task_supervisor WorkingContext, igris_agent context yo'llari
> Holat: ✅ AUDIT YAKUNLANDI — reja checklistlari yangilandi

---

## §5. MEMORY QATLAMLARI

### 5.1 Mavjud qatlamlar xaritasi (kod asosida)

| Qatlam | Implementatsiya | Turlar | Baholash |
|---|---|---|---|
| **L1 Runtime** (working/task memory) | `runtime.py` — in-memory deque + JSONL append, TTL cleanup, per-type max_entries | 18 tur (short-turn, task-memory, decision-log, observation-memory, scratchpad...) | ✅ puxta; `short-turn` max 5 (1.5B optimizatsiya) |
| **L2 Persistent** (long-term) | `persistent.py` — JSONL + content-hash dedup + TTL archive (30k/90d) | 24 tur (solution-memory, experience, knowledge, workflow-memory...) | ✅ |
| **L1→L2 konsolidatsiya** | `autodream.py` — 5-pass (session summary, pattern, error, solution, archive) + `consolidate_from_runtime` type mapping | — | ✅ mavjud; trigger chastotasi tekshirilmagan |
| **L4 Retrieval** | `retrieval.py` — BM25 (primary) + FTS5 incremental (T1) + Vector FAISS (T3 ⚠️ ishlamaydi) + RRF hybrid + LRU session cache + query rewriter (rule-based) | — | ✅ deterministik scoring |
| **PoisoningProtection** | `poisoning.py` — score<50 safe; `recall`/`remember` ikkalasida ham (N1/N2) | — | ✅ ikki tomonlama himoya |
| **Time travel** | `time_travel.py` — snapshot navigatsiya | — | ✅ bonus |
| **CAG** (cache) | `cag.py` — LRU + TTL + sha256(system,prompt) kalit; faqat sifatli javoblar keshlanadi (_cacheable_out + fail-guard) | — | ✅ |
| **MAG** (assembly) | `mag.py` — L1+L2+RAG yig'ish, max_chars limit | — | ✅ |
| **Safety filterlar** | `safety.has_suspicious` + sanitize recall'da; yozishdan oldin blok | — | ✅ |

### 5.2 Audit topilmalari

**Kuchli tomonlar:**
- Qatlam arxitekturasi to'liq va hujjatlashtirilgan (18 L1 + 24 L2 turlar)
- Dedup: L2 content-hash + hybrid index
- TTL/cleanup: L1 expired cleanup + L2 stale archive/delete
- Recall xavfsizligi: har eslatma PoisoningProtection + has_suspicious (2 qatlam)
- FTS5 fallback: FTS5 yo'q bo'lsa BM25Index (crash yo'q)
- Latency tracking: recall_ms/remember_ms benchmark

**Zaif joylar:**

1. **Relevance scoring faqat BM25/leksik** — semantik (embedding) retrieval T3: `VectorIndex` mavjud lekin ishlamaydi (manifest'da qayd etilgan). O'zbekcha so'rovlar morfologiyasi BM25 tokenizatsiyasida zaif ( stemming yo'q)
2. **Conflict detection YO'Q** — ikki qarama-qarshi L2 yozuv (eskirgan + yangi solution) ikkalasi ham recall'ga tushishi mumkin; `confidence_score` maydoni schemas.py'da bor lekin recall ranking'ida ISHLATILMAYDI
3. **Task memory alohida layer emas executor'da** — L1'da `task-memory` turi bor, lekin executor run() davomida task state xotiraga yozilmaydi (faqat oxirida `_remember` → L2 solution-memory)
4. **Working memory (agent side) endi Phase 2 `AgentWorldState`da** — lekin u memory_bridge'ga ulanmagan (run tugagach yo'qoladi, faqat L2 solution-memory yoziladi)
5. **Eskirgan/conflicting memory filtri recall'da yo'q** — recall top_k natijalarini timestamp/confidence bo'yicha saralash yo'q (BM25 score tartibi faqat leksik moslik)
6. **Compaction (D2) yo'q** — L2 JSONL append-only; `cleanup_stale` bor lekin avtomatik scheduler yo'q (manifest todo bilan mos)

### 5.3 Tavsiyalar (ustuvorlik bilan)

1. **Confidence-weighted recall**: `schemas.confidence_score` maydonini retrieval natijasiga qo'shish — `final_score = bm25_score * (0.5 + 0.5*confidence)` (kichik o'zgarish, katta foyda)
2. **Recall'da eski/yangi conflict flag**: bir xil summary'li ikki yozuv topilsa — faqat eng yangisi olinadi
3. **T3 vector retrieval**: qisqa embedding (masalan hash-based yoki MiniLM optional) — manifest todo'da bor
4. **Compaction scheduler**: kunlik bir marta `cleanup_stale` + JSONL compact (D2)

---

## §6. CONTEXT MANAGEMENT

### 6.1 Mavjud holat

| Element | Joyi | Baholash |
|---|---|---|
| **Context budget** | ❌ rasmiy token hisob YO'Q; faqat `max_chars` limitlar (recall 1200–1600, MAG 2000, WorkingContext 12000) | ⚠️ belgi darajasida, token emas |
| Prompt tuzilishi | system (CHAT_TOOLS_SYSTEM + adapt + sana + skill + web rules + stack + memory_ctx + req + **goal_pin**) → history (12) → user | ✅ tartibli; qatlam tartibi deterministik |
| Irrelevant context chiqarish | ⚠️ recall top_k + score tartibi bor; lekin "bu taskga aloqasiz" filtri yo'q | ⚠️ |
| Duplicate context | ✅ MAG faqat recall bo'sh bo'lsa ishlaydi (takror yo'q); CAG dedup | ✅ |
| Context ranking | ⚠️ recall BM25 score tartibi; qatlam'lar orasida umumiy ranking yo'q | ⚠️ |
| **Long task history summarization** | ✅ supervisor WorkingContext._compact (3 yangi to'liq, eskilar summary) + Phase 2 AgentWorldState.compress_old | ✅ (2 joyda, turli darajada) |
| **Current objective doim contextda** | ✅ Phase 1: goal_pin system prompt'ga (chat/chat_stream/run_native); WorkingContext.set_goal (supervisor) | ✅ yopildi |
| Critical state yo'qotmaslik | ✅ goal_pin + WorkingContext current_goal/live_plan/dependencies to'liq saqlanadi | ✅ |
| **Context overflow test** | ❌ rasmiy overflow holati test qilinmagan (max_chars kesish bor, lekin token-limit model xatosi boshqarilmagan) | ❌ |

### 6.2 Asosiy topilma

**Token budget boshqaruvi yo'q** — belgi (char) kesish bor lekin:
- Model context oynasi (masalan 8k/32k) bilinmaydi; `config.py` `max_context_tokens: 4096` bor lekin HECH QAYERDA ishlatilmaydi
- Prompt qatlamlari (system ~2000-4000 char + history 12 ta + memory 2000) jamlanganda limit oshsa — LLM transport xatosi yoki jim kesish; graceful degradation yo'q

### 6.3 Tavsiyalar

1. **Context budget manager**: `ContextBudget(max_tokens)` — prompt qatlamlarini prioritet bilan joylash (goal_pin > system > req > memory > history); token estimatsiya: `len(text) // 3` (ko'rsatma sifatida, deterministik)
2. **History kesish prioritetli**: oxirgi N ta + birinchi user goal message doim saqlanadi (o'rtadagilar tashlanadi)
3. **Overflow graceful degradation**: budget oshsa — historyni qisqartirish → memory contextni qisqartirish → skill matnini qisqartirish (tartib bilan)

---

## §12. GOAL PRESERVATION (Phase 1/2'da katta qismi yopildi)

### 12.1 Mavjud holat — yopilganlar

| Talab | Holat |
|---|---|
| Original goal immutable reference | ✅ Phase 1: `Goal(frozen)` — `goal_model.py` |
| Current objective saqlash | ✅ Objective.current (mutable, goal_id majburiy) |
| Current subtask/action saqlash | ✅ Task/Action + tool_calls |
| Action o'zgarganda objective yo'qolmasligi | ✅ replan() goal_id sinxroni (test bilan) |
| Context compression'da goal saqlanishi | ✅ goal_pin har prompt'ga (chat/chat_stream/run_native) |
| Recovery'da original goal | ⚠️ re-plan goal_id saqlaydi; lekin FAIL→qayta urinishda goal avtomatik restore yo'q (SM FAIL terminalga yaqin) |
| **Resume'da original goal tiklanishi** | ⚠️ `save/load_goal_context` bor (goal_model.py) lekin executor run()ga ULANMAGAN; supervisor Checkpoint.goal matn saqlaydi (goal_id emas) |

### 12.2 Qolgan bo'shliqlar

1. **Executor checkpoint'ga GoalContext ulash** — §8 bilan bir xil item: `TaskCheckpoint` ga `goal_id` + goal text; resume'da `load_goal_context`
2. **FAIL recovery'da goal restore** — SM'da `FAIL → ESCALATE` bor; `FAIL → PENDING task reset` yo'li qo'shilsa, yangi run bir xil goal_id bilan boshlanishi mumkin
3. **Supervisor node'lar goal_id meros qilib olmaydi** — TaskSupervisor DAG node'lari `description` bilan ishlaydi; Phase 1 `Task.goal_id` modeli supervisor TaskNode'ga o'tkazilmagan

---

## XULOSA — PHASE 3 HOLATI

| Section | Asosiy topilma | Holat |
|---|---|---|
| §5 | Qatlam arxitekturasi ✅ to'liq (L1 18tur/L2 24tur/L4 hybrid/poisoning/CAG/MAG); zaif: semantic retrieval (T3), confidence-weighted recall yo'q, conflict detection yo'q, compaction scheduler yo'q | ✅/⚠️ |
| §6 | Goal pin ✅ (Phase 1), compact ✅ (2 joyda), dedup ✅; **token budget manager YO'Q** (config'dagi 4096 ishlatilmaydi), overflow graceful degradation yo'q | ⚠️ |
| §12 | Ko'p qismi Phase 1/2'da yopildi; qoldi: executor checkpoint goal ulash, FAIL recovery goal restore, supervisor node goal_id | ⚠️ |

**Phase 3 audit tugadi. Implementation hammasi bajarildi (2026-09-16/17):**
1. ✅ **ContextBudget** (§6) — context_budget.py fit_prompt() prioritet qatlamlar + overflow degradation; chat/chat_stream'ga ulandi
2. ✅ **Confidence-weighted recall** (§5) — final_score = bm25 * (0.5 + 0.5*confidence) (memory_bridge.search)
3. ✅ **Executor checkpoint + goal restore** (§8/§12) — executor checkpoint_dir + resume_from_checkpoint + goal continuity (test_phase3_checkpoint.py 16/16)
4. ✅ **Compaction scheduler** (§5 D2) — MemoryBridge.run_maintenance() kuniga 1 marta avtomatik cleanup_stale

Test: test_phase3_context.py 38/38 + test_phase3_checkpoint.py 16/16. Qolgan kichik: conflict flag, T3 vector, memory layer priority.

