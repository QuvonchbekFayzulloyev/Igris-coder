# IGRIS ROADMAP v4 — HAQIQIY QOLDIQLARNI 100% GA YETKAZISH

**Sana:** 2026-09-18
**Asos:** v1 (§5–§20), v2 (C3), v3 (R3+R4) — kod tekshirildi, faqat haqiqiy qoldiqlar
**Maqsad:** Barcha qoldiqlarni yopish, 100% ga yetkazish
**Davomiylik:** 10 kun (2 hafta)

---

## HOZIRGI HOLAT (kod tekshirildi, 2026-09-18)

### Bajarilgan (v1 §5–§17 asosan tayyor)

| § | Bo'lim | Holat |
|---|--------|-------|
| §5 Memory | ✅ 3/3 | conflict detection, layer priority, relevance filter |
| §6 Context | ✅ 3/3 | context filter, cross-layer ranking, dedup |
| §7 Tool Protocol | ✅ 5/5 | output schema, precondition, error, verification, retry |
| §8 Pipeline | ⚠️ 3/4 | rollback yo'q |
| §9 Agentic Loop | ✅ 3/3 | UUID, reason, timeout |
| §10 Verification | ✅ 2/2 | expected mapping, comparison |
| §13 Communication | ⚠️ 4/7 | ResponseGenerator, voice policy yo'q |
| §14 LLM Output | ⚠️ 3/4 | alohida LLMOutput schema yo'q |
| §15 Runtime | ❌ 1/4 | queue, monitoring yo'q |
| §16 Observability | ✅ 6/6 | hammasi bor |
| §17 Deterministic | ⚠️ 2/3 | resource control yo'q |
| §18 Test Suite | ⚠️ qisman | v3 R3 bilan qamrab olingan, lekin §18 formatida emas |
| §19 Final Audit | ⚠️ qisman | phase6 audit bor, lekin §19 checklist formatida emas |
| §20 Diagnostics | ⚠️ qisman | asosiy diagnostika bor, to'liq emas |

### Qoldiqlar (faqat shular kerak)

| # | Nima | § | Muddat |
|---|------|---|--------|
| 1 | Rollback mechanism | §8 | 1 kun |
| 2 | ResponseGenerator moduli | §13 | 2 kun |
| 3 | Voice policy | §13 | 0.5 kun |
| 4 | LLMOutput schema (alohida) | §14 | 0.5 kun |
| 5 | Task queue (FIFO) | §15 | 1 kun |
| 6 | Priority queue | §15 | 0.5 kun |
| 7 | CPU/RAM monitoring | §15 | 1 kun |
| 8 | Resource control (CPU/RAM/disk) | §17 | 1 kun |
| 9 | §18 Test Suite — 17 senariy formatda | §18 | 1 kun |
| 10 | §19 Final Audit — 17 checklist formatda | §19 | 0.5 kun |
| 11 | §20 Diagnostics — 11 diagnostika formatda | §20 | 0.5 kun |
| 12 | v2 C3 Push kuzatish | v2 C3 | push vaqti |

---

## PHASE A: ROLLBACK + COMMUNICATION (3 kun)

### A1. §8 Rollback Mechanism (1 kun)

- [ ] `Igris_brain/executor.py` ga `rollback_step(step_id)` qo'shish:
  - `.igris_backups/` dan oldingi versiyani restore qilish
  - Fayl yaratilgan bo'lsa — o'chirish
  - Fayl o'zgartirilgan bo'lsa — eski versiyaga qaytarish
- [ ] Rollback log — `result["rollback_events"]`
- [ ] Test: rollback after failed step, backup restore

### A2. §13 ResponseGenerator Moduli (2 kun)

- [ ] `Igris_brain/response_generator.py` yaratish:
  - `generate_response(task, result, progress)` — verified results + progress + questions
  - `format_progress(step, total)` — `step N of M: {title}`
  - `format_completion(result, matrix)` — to'liq natija + requirement matrix
  - `format_failure(error, recovery)` — xato + qayta urinish
- [ ] IgrisAgent'ga ulash — `_ask_final_summary()` o'rniga
- [ ] Test: response generation, format accuracy

### A3. §13 Voice Policy (0.5 kun)

- [ ] `response_generator.py` ga `voice_mode` qo'shish:
  - voice=true bo'lsa — qisqa, ixcham javoblar (≤50 so'z)
  - voice=false bo'lsa — to'liq format
- [ ] Test: voice mode, length constraint

### A4. §14 LLMOutput Schema (0.5 kun)

- [ ] `Igris_brain/llm_output_schema.py` — `LLMOutput` dataclass:
  - `intent: Intent`
  - `decision: Decision`
  - `reasoning: str`
  - `confidence: float`
  - `action: Optional[Action]`
- [ ] `Decision` dan meros olmasdan, alohida schema
- [ ] Validation: parse → schema → tool-exists
- [ ] Test: schema validation, round-trip

**Test:** regressiya ~850+ test OK

---

## PHASE B: RUNTIME CONTROL (3 kun)

### B1. §15 Task Queue FIFO (1 kun)

- [ ] `Igris_brain/task_queue.py` yaratish:
  - `TaskQueue(max_concurrent=1)` — FIFO navbat
  - `submit(task)` → `queued` holat
  - `cancel(task_id)` — navbatdan o'chirish
  - `queue_info()` — navbat holati
- [ ] Server'ga ulash — `POST /api/agent/run` → queue'ga qo'shish
- [ ] Test: FIFO tartib, sig'im, cancel

### B2. §15 Priority Queue (0.5 kun)

- [ ] `TaskQueue` ga `priority: str` qo'shish (high/normal/low)
- [ ] High priority → oldinga surish
- [ ] Test: priority ordering

### B3. §15 CPU/RAM Monitoring (1 kun)

- [ ] `Igris_brain/resource_monitor.py` yaratish:
  - `get_resources()` — CPU%, RAM usage, disk I/O
  - psutil bilan (fallback: lightweight)
  - Har iteratsiyada log (qisman mavjud — psutil o'rnatilgan)
- [ ] `result["resource_usage"]` — run oxirida
- [ ] Test: resource collection, threshold alert

### B4. §17 Resource Control (1 kun)

- [ ] `executor.py` ga limitlar qo'shish:
  - `max_ram_mb: int = 512` — RAM cheklovi
  - `max_cpu_s: float = 30` — CPU vaqti
  - `max_disk_mb: int = 100` — disk yozuvi
- [ ] Limit o'tsa → abort + error
- [ ] Test: RAM limit, CPU limit, disk limit

**Test:** regressiya ~870+ test OK

---

## PHASE C: TEST SUITE + AUDIT + DIAGNOSTICS (2 kun)

### C1. §18 Test Suite — 17 Senariy Formatda (1 kun)

- [ ] Har bir senariy uchun alohida test:
  1. `test_suite_single_step.py` — oddiy task
  2. `test_suite_multi_step.py` — ko'p qadamli
  3. `test_suite_long_running.py` — uzoq ish
  4. `test_suite_tool_failure.py` — tool xatosi
  5. `test_suite_timeout.py` — vaqt tugashi
  6. `test_suite_wrong_output.py` — noto'g'ri natija
  7. `test_suite_wrong_decision.py` — noto'g'ri LLM qarori
  8. `test_suite_context_overflow.py` — context to'lib ketishi
  9. `test_suite_memory_conflict.py` — xotira ziddiyati
  10. `test_suite_repeated_failure.py` — takroriy xato
  11. `test_suite_infinite_loop.py` — cheksiz aylanma
  12. `test_suite_user_interruption.py` — foydalanuvchi to'xtatishi
  13. `test_suite_task_cancellation.py` — task bekor qilish
  14. `test_suite_task_resume.py` — qayta boshlash
  15. `test_suite_partial_completion.py` — qisman bajarilish
  16. `test_suite_verification_failure.py` — tekshiruvdan o'tmaslik
  17. `test_suite_full_success.py` — to'liq muvaffaqiyat
- [ ] Har biri独立 ishlaydi (pytest bilan)
- [ ] Test: 17/17 PASS

### C2. §19 Final Audit — 17 Checklist (0.5 kun)

- [ ] `v4_architecture_audit.md` yaratish:
  - 17/17 checklist — har biri [x] + dalil (file:line)
  - SM, goal hierarchy, planning/execution, observation/state, memory, context, tool contract, verification, recovery, loop, infinite loop, cancellation, resume, goal preservation, communication, LLM boundary, critical paths
- [ ] Har biri uchun kod tekshirish + test

### C3. §20 Diagnostics — 11 Diagnostika (0.5 kun)

- [ ] `v4_diagnostics.md` yaratish:
  - Agent qayerda tartibsiz → tekshirish usuli
  - Muammo LLM/ orchestration/memory/tool/verification/loop/communication qaysi qatlamda
  - Keraksiz layerlarni aniqlash
  - Minimal core architecture
  - Yakuniy architecture diagram
  - Architecture v1.0 spec

**Test:** 17 test suite + audit + diagnostics — barchasi PASS

---

## YAKUNIY HOLAT

| § | Boshlang'ich | v4 oxiri | O'zgarish |
|---|-------------|----------|-----------|
| §8 Pipeline | 3/4 | **4/4** | rollback qo'shildi |
| §13 Communication | 4/7 | **7/7** | ResponseGenerator + voice |
| §14 LLM Output | 3/4 | **4/4** | alohida schema |
| §15 Runtime | 1/4 | **4/4** | queue + priority + monitoring |
| §17 Deterministic | 2/3 | **3/3** | resource control |
| §18 Test Suite | qisman | **17/17** | formatda testlar |
| §19 Final Audit | qisman | **17/17** | formatda checklist |
| §20 Diagnostics | qisman | **11/11** | formatda diagnostika |
| v2 C3 | ❌ | **✅** | push kuzatish |

---

## XAVFLAR

1. **§15 Task queue** — server sync ishlaydi, queue async qilish kerak
2. **§13 ResponseGenerator** — mavjud inline kodni refactor qilish xavfi
3. **§18 Test Suite** — 17 alohida test fayli, har biri mock/stub talab qiladi
4. **Rollback** — .igris_backups mexanizmi mavjud, lekin to'liq ishlamasligi mumkin

## QABUL MEZONLARI

1. Barcha yangi testlar PASS + regressiya buzilmagan
2. §8/§13/§14/§15/§17/§18/§19/§20 — barchasi [x] bilan belgilangan
3. `health_matrix.md` yangilanishi — barcha protokol ≥98%
4. `v4_final_audit.md` — yakuniy audit hisoboti

---

*Bu reja faqat haqiqiy qoldiqlarga qaratilgan — kod tekshirildi, ortiqcha ish yo'q.*
