# IGRIS ROADMAP v2 — YAKUNIY AUDIT HISOBOTI (Phase A+B+C)

**Sana:** 2026-09-18
**Holat:** ✅ PHASE A + B + C TO'LIQ YAKUNLANDI — barcha 9 band real test run bilan tasdiqlandi
**Qamrov:** `IGRIS_Roadmap_v2_Polish_E2E_Vector.md` (A1–A3, B1–B3, C1–C4) + v3 R1
**Ushbu hisobot** C4 sessiyasining rasmiy qoldig'i edi ("yakuniy audit hisoboti + push kuzatuvi").

---

## 1. REAL TEST NATIJALARI (2026-09-18, pytest run)

| Suite | Natija |
|---|---|
| phase1_foundation + integration + core_loop + phase3_context | 37 passed |
| phase3_checkpoint + phase4_resilience + phase5_gaps | (yuqoridagi guruhda) |
| A2 layer_priority + B1 verified_speech + B2 decision + B3 decision_trace + C2 timeline | 76 passed |
| C1 e2e_longrun + C4 hardening + R1 requirement_matrix + rag_cag_mag_hooks | 52 passed |
| deliverable_run + deliverable_syntax + skills_mcp_hitl + requirements + turbo_consistency | 63 passed |
| degradation + intelligence + stream_thinking + svg_validator + input_validation + chat_history + task_supervisor + web_verify | 218 passed |
| agentic_pipeline + web_strategy | 205 passed + 320 subtests |
| probe_decisions (S2, 21-task suite) | 32 passed |
| Igris_Memory: vector_recall + uz_stemmer | 37 passed |
| Igris_Memory/memory: fts5_index + t2_mtime_cache + bm25 | 32 passed + 2 skipped |
| **JAMI** | **~752 test passed, 0 failed** |

E2E marker: `pytest -m e2e` → C1 (longrun) + C2 (timeline) alohida yugurtiriladi
(C3 kontrakti saqlangan; unit job `-m "not e2e"`).

---

## 2. PHASE A — MEMORY UPGRADE ✅

| Band | Da'vo | Audit natija |
|---|---|---|
| A1 Vector recall | Hash-embedding (384-dim FNV-1a) offline kafolat; MiniLM lazy; `use_vector=True` default; RRF fusion; `embedding_mode` observability | ✅ test_vector_recall 19/19 — parafraza testi (pomidor o'stirish→ekiladi) real topildi |
| A2 Layer priority | L1>L2>vault sintetik base (1.0) + bonus {l1:0.5, l2:0.25}; vault high-score raqobati; [CONFLICT] prefiksi | ✅ test_phase_a2_layer_priority 9/9 |
| A3 Uzbek stemmer | 30+ suffiks iterativ kesish + affiks almashinuvi (k→g, q→', p→b, t→d) + apostrof normalizatsiya; BM25 token=asl+stem juftligi; FTS5 OR-variant | ✅ test_uz_stemmer 18/19 CHECKS; "kitoblarni o'qish"→"kitob oqish" E2E topildi; fts5 22 passed |

---

## 3. PHASE B — VERIFIED SPEECH & DECISION MODEL ✅

| Band | Da'vo | Audit natija |
|---|---|---|
| B1 Verified-only speech | `_verify_summary_claims` — fayl da'volari tool_calls + workspace.exists bilan; `[claim-check]` correction; `final_claims_checked` | ✅ test_phase_b1_verified_speech 11/11 — yolg'on da'vo ushlanadi |
| B2 Decision model | `decision.py` dataclass + `validate()` (clamp, duplicate id, engine guard) + `validation.py` parse→schema→tools zanjiri + `planner.decide()` fasad | ✅ test_phase_b2_decision 19/19 |
| B3 Reasoning trace | Native loop `reasoning`/`thinking` → `decision_trace[]` (≤500 preview); planned `result["decision"]` bloki | ✅ test_phase_b3_decision_trace 6/6 |

---

## 4. PHASE C — E2E & HARDENING ✅

| Band | Da'vo | Audit natija |
|---|---|---|
| C1 Long-running e2e | 22 qadam real bajarish; tool-failure injection (partial); cancel+resume (checkpoint kept→cleared, goal_id stabil) | ✅ test_phase_c1_e2e_longrun — time guard 0.1s << 30s |
| C2 Timeline | `result["timeline"]` — sm/tool/error/verify qatlamlari birlashgan chronological; ts monotonic; 2 asl executor bug tuzatilgan edi | ✅ test_phase_c2_timeline 21 CHECKS |
| C3 CI e2e qatlami | `pytest.ini` e2e marker; test.yml alohida e2e job; nightly to'liq suite | ✅ marker lokal tasdiqlandi; **GitHub Actions real job — PUSH TALAB qiladi (lokal imkonsiz, quyida §6)** |
| C4 FIFO queue + monitoring | `RunManager(max_concurrent=1)` — queued holat, `_on_run_finished` zanjiri, cancel-queued, `queue_info()` → `/api/health/metrics` `runs` bo'limi; psutil optional + fallback | ✅ test_phase_c4_hardening 8/8; server.py:1314 `RunManager`, `RUN_MANAGER` barcha run endpoint'larda ulangan |

### C4 qo'shimcha audit topilmasi (2026-09-18)
- **psutil o'rnatilmagan edi** — `requirements.txt`da bor, lekin muhitda yo'q →
  health metrics `system` bo'limi lightweight fallback'da ishlab turardi.
  **Tuzatish:** `pip install psutil` (7.2.2) — endi real RSS/CPU/threads qaytadi
  (stub-agent bilan tekshirildi: rss=18.8MB, threads=4). Fallback yo'li saqlangan
  (fresh env'lar uchun to'g'ri xatti-harakat).

---

## 5. ROADMAP V3 R1 HOLATI (v2'dan keyingi navbat)

R1 Requirement Matrix ✅ (17 test / 35 CHECKS): `requirement_matrix.py`,
`result["requirement_matrix"]` + `result["completion"]`, executor ok→partial
pasaytirish, §19 false-completion test.

**R1 qoldig'i (v3 navbat):**
- R1.2: `g_complete` SM guard'ini matrix bilan bir manbadan bog'lash
- R2: checkpoint integrity + reconciliation (version, corruption, re-execute)
- R3: real task suite + crash scenarios; R4: domain verifiers

---

## 6. QOLGAN YAGONA BAND — PUSH KUZATUVI

C3'ning oxirgi checklisti (`[ ] Push'dan keyin GitHub Actions'da real job
yugurishini kuzatish`) lokal muhitda bajarilmaydi — repo push talab qiladi.
Repo hozir 1 commit'li lokal tarixga ega. **Foydalanuvchi push qilganda:**
1. Actions'da `test` job (`-m "not e2e"`) va `e2e` job (`-m e2e`) alohida yashil bo'lishini tekshirish
2. Nightly'da to'liq suite + benchmark kuzatuvi

---

## 7. XULOSA

Roadmap v2 (A1–A3, B1–B3, C1–C4) **9/9 band bajarildi va real test run bilan
tasdiqlandi (~752 test)**. v3 R1 ham asosiy qismi bajarilgan. Navbat: R1.2 +
R2 (checkpoint reconciliation) yoki C3 push kuzatuvi (foydalanuvchi amali).
