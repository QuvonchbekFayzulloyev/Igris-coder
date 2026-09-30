# IGRIS ROADMAP v2 — Polish, E2E & Vector Recall

**Sana:** 2026-09-17
**Oldingi reja:** `IGRIS_Architecture_Audit_Plan.md` — **22/22 bo'lim yopildi** (Phase 1–6, 2026-09-16/17)
**Asos:** Phase 3–6 auditlarida "past prioritet" sifatida qoldirilgan bo'shliqlar + yangi imkoniyatlar
**Davomiylik taxmini:** 2–3 hafta
**✅ YAKUNIY AUDIT:** `v2_final_audit.md` (2026-09-18) — Phase A+B+C 9/9 band ~752 test bilan rasman tasdiqlandi; psutil faollashtirildi; C3 push kuzatuvi foydalanuvchi amali

---

## ASOSIY TAMOYILLAR (v1'dan meros)

1. **Deterministic First** — hash-based embedding default, MiniLM faqat o'rnatilgan bo'lsa
2. **LLM = Decision Layer** — LLM faqat qaror/reja/xulosa; guard'lar kodda
3. **Goal Preservation** — goal pin + checkpoint restore saqlanadi
4. **Verification Required** — COMPLETE faqat VERIFIED bilan
5. **Observable Everything** — yangi qatlam = yangi telemetriya
6. **Fail Gracefully** — har xususiyat degrade yo'li bilan ishlaydi
7. **Backward Compatible** — mavjud 32 test fayl hech qachon buzilmaydi

---

## PHASE A: MEMORY UPGRADE (1 hafta) — ✅ TO'LIQ YAKUNLANDI 2026-09-17 (A1+A2+A3; test_vector_recall 19/19, test_uz_stemmer 19/19 CHECKS, test_phase_a2 9/9, to'liq regressiya OK)

**Phase A chiqishi (tasdiqlandi):** semantik recall offline kafolat bilan ishlaydi (hash embedding), L1>L2>vault ranking to'g'ri, conflict yozuvlar modelga [CONFLICT] belgisi bilan ko'rinadi, o'zbekcha morfologiya BM25/FTS5'da tutadi (kitoblarni↔kitob, o'qish↔oqish).

### A1. Vector recall — T3 yopish (§5) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] `VectorIndex`'ga **hash-based deterministic embedding** qo'shish (char 3-4-gram FNV-1a hash → 384-dim, pure-python cosine) — `sentence-transformers` o'rnatilmagan holatda ham ishlaydi ✅
- [x] MiniLM yo'li: `sentence-transformers` mavjud bo'lsa — haqiqiy embedding (lazy, optional); build() da avval MiniLM sinanadi, bo'lmasa hash ✅
- [x] `VectorIndex.build()` jim ishdan chiqishini tuzatish: `search()` endi hash rejimida JIM BO'SH QAYTARMAYDI (lazy build + noise floor 0.05) ✅
- [x] `HybridSearch.search(use_vector=True)` default holatda faol — RRF fusion ikkala manba bilan ✅ (test: semantik mos birinchi)
- [x] **Smoking test:** o'zbekcha parafraza ('pomidor o'stirish' → 'pomidor ekiladi' 0.29, unrelated 0.10) topildi ✅
- [x] Test: `Igris_Memory/test_vector_recall.py` — **19/19 PASS** (determinizm, dim, L2 norm, empty, parafraza>alohida, hash mode, lazy, remove_source, RRF, use_vector=False, stats embedding_mode) ✅
- [x] Regressiya: phase3_context 38/38, phase4 11/11, phase5 15/15, skills_mcp OK, BM25/FTS5/T2 OK ✅
- `get_stats()`: yangi `embedding_mode` maydoni ("minilm" | "hash" | "none") — observability

### A2. Memory layer priority (§5 qoldiq) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] `recall()` kontekst yig'ishda L1 (session) > L2 (persistent) > vault tartibini score'ga integratsiya qilish ✅ — asos sabab: L1/L2 recall-format yozuvlarida score MAYDONI YO'Q edi (weighted recall'da base=0 → eng pastga tushardi); yechim: sintetik base 1.0 + `LAYER_PRIORITY_BONUS` {l1: 0.5, l2: 0.25}; vault o'z BM25/RRF score'i bilan raqobatlashadi (yuqori score > 1.5 bo'lsa L2'ni ortlab ketadi) ✅
- [x] Konfliktli yozuvlar: recall kontekstida `[CONFLICT]` prefiksi bilan modelga ko'rsatiladi ✅ — `_looks_conflicting()` (Phase 5) dan qayta foydalanildi; `detect_conflicts` + recall flag bir xil patternlar
- [x] Test: `test_phase_a2_layer_priority.py` — **9/9 PASS** (L2>vault, L1>L2, vault high-score competitive, explicit score hurmat, [CONFLICT] prefix, normal yo'q, confidence regression) ✅
- [x] Regressiya: foundation 48, integration 19, core_loop 27, phase3_context 38/38, checkpoint 16, phase4 11/11, phase5 15/15, skills_mcp 18 OK, vector_recall 19/19 ✅

### A3. Uzbek morphology yordamchisi (BM25 zaifligi) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] Oddiy stemmer: `uz_stem()` — iterativ qo'shimcha kesish (max 3 bosqich, 30+ suffiks: -lar/-ning/-dagi/-imiz/...), affiks almashinuvi (k→g, q→', p→b, t→d) — `Igris_Memory/memory/retrieval.py` ✅
- [x] BM25 `tokenize`: har token asl + stem juftligi sifatida (leksik moslik saqlanadi, morfologik QO'SHILADI) ✅
- [x] **Apostrof normalizatsiya**: ', ', ʻ, ʼ, ` o'chiriladi — 'o'qish'→'oqish' bir token (avval: 'qish' — so'z buzilardi) — BM25 + FTS5 tokenizelarida ✅
- [x] FTS5 query-side: `_query_tokens()` — MATCH so'rovida stem variant OR bilan (index-side unicode61 o'zgarmas, DB mosligi saqlanadi) ✅
- [x] Test: "kitoblarni o'qish" → 'kitob oqish' hujjati topildi (E2E); inglizcha/tech so'rovlar buzilmagan ✅
- [x] Test: `Igris_Memory/test_uz_stemmer.py` — **18 test / 19 CHECKS PASS**; regressiya: bm25/fts5/t2/vector_recall/phase3/4/5/A2 hammasi OK ✅

**Phase A chiqishi:** semantik recall ishlaydi (offline kafolat bilan), test_phase3_context 38/38 saqlanadi

---

## PHASE B: VERIFIED SPEECH & DECISION MODEL (1 hafta) — ✅ TO'LIQ YAKUNLANDI 2026-09-17 (B1 11/11 + B2 19/19 + B3 6/6; to'liq regressiya OK)

**Phase B chiqishi (tasdiqlandi):** xulosa hallusinatsiyasi deterministik ushlanadi ([claim-check]), LLM qarori rasmiy Decision modelida tipga ega, to'liq validation layer (parse→schema→tools) SM guard bilan bir manbadan, har iteratsiya reasoning trace'da — §13 → 8/9, §14 → 10/10, §16 decision log qoldig'i yopildi.

### B1. Verified-only speech (§13 qoldiq) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] **deterministik solishtiruv**: `_verify_summary_claims()` — xulosadagi fayl da'volari (path regex) tool_calls + workspace.exists bilan; tool da'volari bajarilganlar ro'yxati bilan solishtiriladi (LLM'siz) ✅
- [x] Dalilsiz da'vo topilsa — xulosaga `[claim-check]` correction qo'shiladi + `_log_recovery("claim_check")` ✅
- [x] Natijada `final_claims_checked: true` + `unverified_claims[]` maydonlari (run() va run_native() ikkalasida) ✅
- [x] Test: yolg'on da'vo (config.json yaratilmagan) → ushlanadi + tuzatiladi ✅
- [x] Fail-safe: claim-check xatosi hech qachon run'ni buzmaydi (`final_claims_checked=False`) ✅
- [x] Test: `test_phase_b1_verified_speech.py` — **10 test / 11 CHECKS PASS**; regressiya: foundation 48, integration 19, core_loop 27, phase3 38, checkpoint 16, phase4 11, phase5 15, A2 9, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK ✅

### B2. Rasmiy Decision model (§14 qoldiq) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] `decision.py`: `@dataclass Decision {decision, goal, intent, reasoning, confidence, steps[], engine, source}` + `PlanStep` (§14 band 2, 4, 6) ✅
- [x] `Decision.from_plan()` — HECH QACHON exception irmaydi (invalid maydonlar defaultga); `to_dict()` plan dict shaklini TO'LIQ saqlaydi (backward-compatible) ✅
- [x] `Decision.validate()` — §14 band 10: maydonlar + confidence clamp + engine/intent guard + duplicate step.id + llm/empty-steps kontrakt ✅
- [x] `validation.py`: parse (`_extract_json`) → schema (`Decision.validate`) → tool-exists (`validate_plan_tools` — SM guard bilan BIR XIL funksiya) zanjiri, `ValidationResult{ok, source, errors, decision}` ✅
- [x] `planner.decide()` fasad: plan + Decision + ixtiyoriy allowed_tools guard (rad etsa `source=tools_rejected`); fallback intent'ni Requirement'dan oladi ✅
- [x] Test: `test_phase_b2_decision.py` — **19 test / 19 CHECKS PASS** (round-trip, invalid, clamp, duplicate id, chain bosqichlari, decide fasad, backward-compat) ✅
- [x] Regressiya: foundation 48, integration 19, core_loop 27, phase3 38/38, checkpoint 16, phase4 11/11, phase5 15/15, A2 9/9, B1 11/11, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK ✅

### B3. Native loop'da reasoning saqlash — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] Native tool-call javoblaridagi `reasoning`/`thinking` maydoni **decision_trace**'ga yoziladi — har iteratsiya: `{iteration, reasoning (≤500), tool_calls[], content_preview (≤200)}`; ikkala maydon nomi qo'llab-quvvatlanadi (qwen3 "thinking" ham) ✅
- [x] Planned loop: `result["decision"]` bloki — `{engine, reasoning, confidence, intent, plan_validated, steps_total}` (B2 Decision maydonlari bilan bir xil kontrakt) ✅
- [x] Test: `test_phase_b3_decision_trace.py` — **5 test / 6 CHECKS PASS** (reasoning olinadi, thinking alternativi, tartib, content_preview, planned blok, fallback conf=1.0) ✅
- [x] Regressiya: foundation 48, integration 19, core_loop 27, phase3 38/38, checkpoint 16, phase4 11/11, phase5 15/15, A2 9/9, B1 11/11, B2 19/19, executor ✅, deliverable 13, skills_mcp 18 — HAMMASI OK ✅

**Phase B chiqishi:** §13 → 8/9, §14 → 10/10; xulosa hallusinatsiyasi deterministik filtrlanadi

---

## PHASE C: E2E & HARDENING (1 hafta)

### C1. Long-running e2e (§18 qoldiq) — ✅ IMPLEMENTATSIYA 2026-09-17
- [x] `test_phase_c1_e2e_longrun.py`: **22 qadamli reja** (planner.max_steps kengaytirilgan holda), max_iter=66 ✅
- [x] To'liq bajarish: 22/22 step done, 22 fayl diskda, checkpoint cleared, **time guard 0.1s << 30s** ✅
- [x] O'rtada **tool failure injection** (5-qadamda invalid path) — run davom etdi: 21 done + 1 error step, `errors[]` to'ldi, status partial ✅
- [x] O'rtada **cancel injection** (3-write'dan keyin `cancel_event.set()`) — `cancelled` status + `checkpoint: kept` + 3 step progress ✅
- [x] **Resume**: `resume_from_checkpoint(goal_id)` — yangi executor nusxada qolgan 19 qadam bajarildi, 1-3 skip, goal_id STABIL (§12), yakuniy `ok` + `checkpoint: cleared`, 22 fayl ✅
- [x] Regressiya: barcha 13 suite OK (foundation 48 ... skills_mcp 18) ✅

### C2. Timeline view (§16 qoldiq) ✅
- [x] `result["timeline"]`: SM transitions + tool_calls + errors + recovery_events + verifications **birlashgan chronological** ro'yxat — har eventda `{ts, layer, kind, detail, ...qatlam-maydonlari}`; ts YO'Q eski rekordlar oxiriga qo'yiladi (yiqilmaydi); planned (`run()`) va native (`run_native()`) loop'lar ikkalasida ham ✅
- [x] Tool record'larga `ts` qo'shildi (planned + native) — timeline tartibi aniqligi ✅
- [x] Frontend AgentConsole'da (keyinroq) yoki `GET /api/agent/run/{id}` orqali ko'rsatish uchun tayyor ✅
- [x] Test: `test_phase_c2_timeline.py` — 3 test / **21 CHECKS PASS** (qatlam qamrovi sm/tool/error/verify, ts monotonic, maydonlar kontrakti, error injection → error qatlami + errors[] mosligi, native + decision_trace) ✅
- [x] Bonus: 2 ta asl executor bug topildi va tuzatildi — `_execute_step`da `record` faqat `corr` shoxida yaratilgan edi (UnboundLocalError) va `_replan`da `int("s1")` qulashi (non-numeric step id); regressiya: barcha 16 suite OK ✅

### C3. CI'da e2e qatlami ✅
- [x] `pytest.ini`'ga `e2e` marker ro'yxatdan o'tkazildi — C1 (longrun) va C2 (timeline) test fayllariga `pytestmark = pytest.mark.e2e` belgilandi (ImportError'da fail-safe — pytest bo'lmasa oddiy runner ishlaydi) ✅
- [x] `test.yml`'ga alohida **`e2e` job** qo'shildi (`needs: test`): `pytest -m e2e -v --tb=short`; unit job esa `-m "not e2e"` bilan toza bo'ldi ✅
- [x] Nightly'da **to'liq suite** (e2e bilan) + `python -m benchmarks.test_performance` qo'shildi ✅
- [x] Lokal validatsiya: YAML parse OK (jobs: test, e2e); `pytest -m e2e` → 7 passed; `pytest -m "not e2e"` → 647 passed + 320 subtests; plain-runner'lar (14/14, 21/21) buzilmagan ✅
- [ ] Push'dan keyin GitHub Actions'da real job yugurishini kuzatish (repo push talab qiladi — lokal imkonsiz)

### C4. Right-sizing qoldiqlari (agar kerak bo'lsa) ✅
- [x] Task queue: `RunManager`'ga FIFO navbat — `max_concurrent` (default 1), ortiqchasi `queued` holatda, tugaganda avtomatik keyingisi ishga tushadi; `queue_info()` + `/api/health/metrics` `runs` bo'limi; navbatdagi run'ni cancel — navbatdan o'chiriladi; `runner` DI nuqtasi (test/stublar); eski xatti-harakat backward-compatible ✅
- [x] CPU/RAM monitoring: psutil endi `requirements.txt`da (optional izoh bilan) — mavjud lightweight fallback o'zgartirilmadi, test bilan qamrovdiga ✅
- [x] Test: `test_phase_c4_hardening.py` — 8 test / **25 CHECKS PASS** (FIFO tartib, sig'im 2, cancel-queued, queue_info, runs bo'limi, system fallback) ✅
- [x] Regressiya: barcha 17 suite OK — server testlari (input_validation, skills_mcp_hitl, phase4) ham qamrovdiga ✅

**Phase C chiqishi:** §18 → 17/17; e2e scenario'lari CI'da; timeline observability to'liq

---

## YAKUNIY HOLAT (maqsad)

| Bo'lim | Hozir | v2 maqsad |
|--------|-------|-----------|
| §5 Memory | weighted recall, conflicts | + vector (T3), layer priority, uz stemming |
| §13 Communication | 7/9 | 8/9 (voice N-A qoladi) |
| §14 Output Contract | 8/10 | 10/10 (Decision model + validation module) |
| §16 Observability | asosiy to'liq | + unified timeline, decision trace |
| §18 Test Suite | 16/17 | 17/17 (+ long-running e2e) |

## BAJARILISH TARTIBI

```
A1 (vector T3)  →  A2 (priority)  →  A3 (stemmer)     # 1-hafta
B1 (verified speech) → B2 (Decision) → B3 (trace)     # 2-hafta
C1 (e2e longrun) → C2 (timeline) → C3 (CI) → C4      # 3-hafta
```

Har phase tugaganda: audit hisoboti (`plans/v2_phase{A,B,C}_*.md`) + action_history yozuvi + to'liq regressiya (32 fayl).

## XAVFLAR VA CHEKLOVLAR

1. **Hash embedding sifati** — MiniLM'dan past; lekin deterministik, tez (~ms) va offline. Ikkala yo'l qo'shniqda: hash default, MiniLM detected → upgrade.
2. **sentence-transformers modeli ~90MB** — faqat foydalanuvchi o'rnatgan bo'lsa yuklanadi (lazy, import guarded).
3. **E2E testlar LLM'siz** — FakeLLM stublar bilan; haqiqiy Ollama e2e faqat nightly'da (mashinada model borligi noma'lum).
4. **Backward compatibility** — plan dict shakli, endpoint schema'lari o'zgarmaydi; faqat yangi maydonlar qo'shiladi.

---

*Bu roadmap v1 audit rejasining davomi — IGRIS agentni production-grade holatga olib boradigan polish bosqichi.*
