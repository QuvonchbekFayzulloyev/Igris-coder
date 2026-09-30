# IGRIS — REALITY VERIFICATION ROADMAP (Roadmap v3)

**Sana:** 2026-09-17
**Manba:** Foydalanuvchi taqdim etgan "Real Task Execution & Reality Verification TODO" (29 bo'lim)
**Oldingi reja:** `IGRIS_Roadmap_v2_Polish_E2E_Vector.md` — 9/9 band bajarildi (A+B+C)
**Asosiy maqsad:** TODO'ning FINAL RULE'ini kod darajasida kafolatlash:
**VERIFIED SUCCESS = REALITY + REQUIREMENTS + EVIDENCE** (LLM "done" deyishi yetarli emas)

---

## HOZIRGI HOLAT XARITASI (audit, 2026-09-17)

TODO bo'limlarining mavjud implementatsiya bilan qoplanishi:

| TODO § | Mavjud kafolat | Qolgan bo'shliq |
|---|---|---|
| §0 Completion modeli | SM `g_complete` guard: faqat VERIFIED + steps=0 (state_machine.py) | Requirement darajasida matrix YO'Q (§17) |
| §1 Real test env | C1 e2e: temp workspace + before/after fayl hisobi | Snapshot diff moduli yo'q |
| §2 Requirement extraction | `core/requirements.py` (intent/constraints/deliverable) | Mandatory/optional ajratish YO'Q, immutable snapshot yo'q |
| §3 Goal pin | §12: goal_id STABIL resume, immutable Goal model | Restart'dan keyin tiklanish C1'da qamrovdigan |
| §4 Decomposition | Planner steps + dependencies (qisman) | Parent/child completion semantikasi yo'q |
| §5.1–5.3 Real tasks | C1/C2 e2e fayl yaratish; `_verify_deliverable` content/size | Modifikatsiya/org testlari yo'q |
| §6 Code execution | `_python_syntax_check` + `_python_run_check` (quality gate) | Exit code/stdout evidence yozuvi yo'q |
| §7 Multi-step | C1: 22 qadam + data processing | CSV→summary real task yo'q |
| §8 Brain kill | C1: cancel+resume (graceful) | SIGKILL simulation + state restore to'liq zanjir YO'Q |
| §9 Random interruption | — | Har SM fazada kill + resume testlari YO'Q |
| §10 Checkpoint integrity | Atomik write (os.replace), goal saqlanadi | **version/corruption-detection/requirements saqlash YO'Q** |
| §11 Duplicate protection | `_action_id()` har tool call'da | Resume'dan keyin already-completed detection YO'Q |
| §12 Reality vs result | B1 claim-check, VerificationLog | Intention≠action≠result ajratish hujjat/test darajasida |
| §13 File reality | `_verify_deliverable` (exists/size/content/encoding qisman) | Full manifest verify (extension/corruption/unexpected files) YO'Q |
| §14 Code reality | syntax + run | Expected output comparison YO'Q |
| §15 Research verify | — | Sources evidence YO'Q |
| §16 Document verify | — | — |
| §17 Requirement matrix | — | **YO'Q — R1'da quriladi** |
| §18 Independent verifier | Verifier quality gate executor'da (ajratilgan metod) | MUSTAQIL modul emas — R1'da ajratiladi |
| §19 False completion | `g_complete` guard + claim-check + deliverable gate | 11 senariy to'plami test sifatida YO'Q |
| §20 False failure | Retry/replan mavjud | Partial-progress status senariylari YO'Q |
| §21 Crash recovery | R2 checkpoint + R3 SIGKILL simulyatsiya ✅ (2026-09-18) | OOM/tool-crash simulation R4+ |
| §22 Resume correctness | R2 reconciliation + R3 duplicate kuzatuvi ✅ (2026-09-18) | — |
| §23 External reconciliation | R2 stale detection (ts vs mtime) ✅ (2026-09-18) | — |
| §24 Long-running | R3: 60 step + growth + SM forward-only ✅ (2026-09-18) | — |
| §25 Stress | R3: consecutive + slow-LLM + limit/resume ✅ (2026-09-18) | tool-failure stresi R4 |
| §26 E2E acceptance | R3 acceptance runner: 15/15 senariy ✅ (2026-09-18) | — |

**Eng katta bo'shliqlar (R1 fokus):** §17 matrix, §28 formal contract, §10 checkpoint
requirements, §19 false-completion to'plami, §22 reality reconciliation.
*(2026-09-18 yangilanish: §17/§28/§10/§19/§22 R1+R2 bilan yopildi; §21/§24/§25/§26 R3 bilan yopildi. Qoldi: §27 requirement-linked trace, §21 OOM simulyatsiyasi — R4.)*

---

## R1 — Requirement Matrix + Completion Contract (1-hafta)

Maqsad: §2 + §17 + §28 + §19'ni yopish — "COMPLETE" faqat evidence bilan.

- [x] **`requirement_matrix.py` modul**: `ReqItem {id, text, kind: mandatory|optional,
      check: file_exists|file_contains|file_absent|folder_exists|file_not_empty,
      target, status, evidence}` ✅ (regex/python_runs R4'da)
- [x] **Extraction**: task matndan DETERMINISTIK (LLM'siz ishlaydi) — fayl nomlari
      + fe'l konteksti (optional-hint faqat fayl nomidan OLDIN qidiriladi —
      oyna kesishuvi bug'i tuzatildi) ✅
- [x] **Immutable snapshot**: `RequirementSnapshot` — items tuple (o'zgarmas),
      `to_json/from_json` (checkpoint'ga saqlashga tayyor), run boshida quriladi ✅
- [x] **Matrix runner**: har ReqItem uchun deterministik fs check — PASS/FAIL/UNKNOWN
      + REAL evidence (exists/size/content_head/pattern_found) ✅
- [x] **Result contract**: `result["requirement_matrix"]` + `result["completion"]`
      — planned (`run()`) VA native (`run_native()`) loop'larda ✅
- [x] **Status enum**: `completion_status()` — all mandatory PASS → complete;
      FAIL aralash → partial; all FAIL → failed; UNKNOWN → blocked ✅
- [x] **Executor guard**: matrix FAILED/PARTIAL bo'lsa executor status="ok" →
      "partial" pasaytiriladi (COMPLETE faqat evidence bilan — §28) ✅
- [x] **False completion test (§19)**: tool chaqiruvisiz "bajarildi" xulosasi →
      completion=failed, status=partial, matrix FAIL evidence bilan ✅
- [x] **`g_complete` SM guard yangilash** (matrix bilan bir xil manba — R1.2)
      ✅ 2026-09-18: ctx `completion` maydoni — 'complete' bo'lmasa COMPLETE
      rad etiladi (hatto VERIFIED bo'lsa ham); planned + native ikkala loop'da
      executor `_build_requirement_matrix` natijasi guard ctx'ga uzatiladi
- [x] **Checkpoint'ga snapshot saqlash** (R2'da — §10 bilan birga) ✅ 2026-09-18
- [x] **Test `test_r1_requirement_matrix.py`**: 17 test / **35 CHECKS PASS**
      (extraction 5, snapshot 2, matrix 3, contract 6, executor 2 — regressiya:
      barcha 18 suite OK) ✅

## R2 — Checkpoint Integrity + Reconciliation (2-hafta) — ✅ TO'LIQ YAKUNLANDI 2026-09-18

Maqsad: §10 + §22 + §23 + §11.

- [x] Checkpoint **version** maydoni + schema evolution kafolati ✅ —
      `CHECKPOINT_VERSION = 2`; eski (v1, version yo'q) o'qiladi (backward
      compat), YANGIROQ rad etiladi (kelajakdagi format xavfsiz rad)
- [x] Checkpoint'ga **requirements snapshot + verification_log** qo'shish ✅ —
      `requirements` (to'liq snapshot JSON) + `verifications` (oxirgi 20) +
      `plan_steps` (reconciliation uchun) + `action_ids` (oxirgi 100)
- [x] **Corruption detection**: JSON parse xato → eski valid checkpoint fallback
      (`.bak` nusxa har atomik yozishda) ✅ — `_read_cp_json` parse xatoni
      ushlaydi; `.bak` ham buzuk → None (xavfsiz yangi run)
- [x] **Reconciliation**: resume'da fs bilan solishtirish —
      completed step'da yozilgan fayl HAZIR bo'lsa step skip (duplicate'siz);
      YO'QOLGAN bo'lsa step QAYTA bajariladi (re-plan signal) ✅ —
      yangi `checkpoint_integrity.py`: `reconcile_steps` (0-bayt fayl =
      yozilmagan; task-matn fayllari faqat step'ning o'z nomi topilmaganda),
      `merge_skip_with_reconciliation` (redo skip'dan chiqariladi);
      `resume_from_checkpoint` natijaga `reconciliation` hisoboti qo'shadi
- [x] **Stale checkpoint**: checkpoint ts vs fs mtime — tashqi o'zgarish aniqlanadi ✅ —
      `is_stale()` (grace 0.25s); stale bo'lsa natijada `checkpoint_stale: true`
- [x] **Duplicate protection**: `_action_id` registry — resume'da already-done
      action'lar qayta bajarilmaydi ✅ — checkpoint'da `action_ids` saqlanadi;
      step darajasida reconciliation skip/redo qarori
- [x] **Test `test_r2_checkpoint_recon.py`**: **15 test PASS** (versioning 2,
      corruption 2, R2 maydonlari 1, staleness 2, reconciliation 5, resume
      integratsiya 3) ✅
- [x] Regressiya: ~620 test yashil (phase1–5, C1–C4, R1, agentic_pipeline,
      intelligence, input_validation, chat_history, turbo, deliverable, skills,
      probe, degradation, web_strategy...) ✅

## R3 — Real Task Suite + Crash Scenarios (3-hafta) — ✅ 2026-09-18 YAKUNLANDI

Maqsad: §1 + §5 + §6 + §7 + §8 + §9 + §21 + §24–26 e2e qatlami.

- [x] **Test workspace harness**: initial/final snapshot + diff (files/mtime/hash)
      ✅ 2026-09-18: `workspace_harness.py` — `seed/snapshot/diff/read/exists`,
      `_cp/` checkpoint papkasi diff'dan avtomatik ignore qilinadi
- [x] **Real task tests**: file create/modify/organize, code-gen+run+exit-code,
      CSV→summary, multi-file ✅ 2026-09-18: `test_r3_real_tasks.py` — 8 test
      (scripted LLM + real executor + real fs; python_exec sandbox deny-list
      uchun runpy naqshi)
- [x] **Interruption matrix**: PLAN/EXECUTE/VERIFY fazalarida cancel/kill
      simulation + har safar resume → final verification (duplicate side-effect
      kuzatuvi bilan) ✅ 2026-09-18: `test_r3_interruption.py` — early/mid/late
      cancel@1/6/11 → har safar resume=ok, 12/12 fayl duplicate'siz;
      executor'ga TAQSIMLANGAN `cancel_event` uzatilishi (constructor)
      muhim pattern sifatida qayd etildi
- [x] **SIGTERM/SIGKILL simulation**: subprocess-based real kill test
      (checkpoint'ning diskda qolishi tasdiqlanadi) ✅ 2026-09-18: real
      `subprocess.Popen` + `proc.kill()` write#4'da → checkpoint kept (1) →
      yangi executor bilan cross-process resume → 12/12 fayl
- [x] **50+ step long-run** + memory/context growth assertion ✅ 2026-09-18:
      `test_r3_longrun.py` — 60 step (SM forward-only kuzatuvi bilan 60 execute
      event, growth: timeline writes >= 60 + verifications)
- [x] **Stress**: consecutive tasks + tool failures + slow-LLM (stub delays)
      ✅ 2026-09-18: 5×60-step ketma-ket izolyatsiyalangan run (checkpoint
      qoldiqsiz), slow-LLM (10ms avg) 2.0s'da yakun, max_tool_calls=10 limit →
      stopped cleanly → resume → 60/60
- [x] **E2E acceptance runner**: TODO §26'dagi 15 senariy ro'yxati — har biri
      matrix bilan yakunlanadi ✅ 2026-09-18: `test_r3_acceptance.py` —
      **15/15 senariy PASS** (jadval chiqishli, exit-code kontraktli;
      s01–s08 real tasklar, s09–s12 long-run/cancel/resume/crash,
      s13 tool-failure recovery, s14 requirement-failure detection,
      s15 false-completion prevention)
- [x] **Test fayllari**: `test_r3_real_tasks.py`, `test_r3_interruption.py`,
      `test_r3_longrun.py`, `test_r3_acceptance.py` (+ `workspace_harness.py`)
      — 19 R3 test + 15 senariy runner

**R3'da topilgan va tuzatilgan real bug:** `clear_checkpoint` `.bak` zaxira
nusxasini o'chirmasdan qoldirar edi (stress run izolyatsiyasini buzadi) —
endi checkpoint + `.bak` birga o'chiriladi (executor.py).

## R4 — Domain Verifiers (4-hafta) — ✅ 2026-09-18 YAKUNLANDI

- [x] **§14 code reality: expected output comparison** ✅ 2026-09-18:
      `verify_code_output(code, expected=, pattern=)` — izolyatsiyada run
      (`python -I`, 6s timeout, deny-list → NEYTRAL None), stdout expected
      yoki regex bilan solishtiriladi; executor integratsiyada buzuk skript
      status "ok"→"partial" pasayadi + VerificationLog'da FAILED evidence
- [x] **§15 research verify: source evidence** ✅ 2026-09-18:
      `verify_source_evidence(root, source, summary_path=)` — manba mavjud +
      bo'sh emas + **SHA-256 hash** evidence; summary manbaga HAVOLA qilishini
      va min_length'ni tekshiradi
- [x] **§16 document verify: section count/titles** ✅ 2026-09-18:
      `verify_document(root, path, min_sections=, required_sections=)` —
      .md (sarlavhalar), .csv (header+rows), .json (parse), .html (tegchalar),
      .docx (ZIP+document.xml); noma'lum format → None (neytral)
- [x] **§13 to'liq file manifest: extension/encoding/unexpected-files** ✅
      2026-09-18: `verify_file_manifest(root, expected, max_unexpected=)` —
      exists + size>0 + UTF-8 validatsiya (matn ext'lari) + unexpected
      leak hisoboti (`_cp/`/`.git` ignore, >= limit → FAIL)
- [x] **Test fayli**: `test_r4_domain_verifiers.py` — 30 test PASS
      (kod 7, manba 5, hujjat 7, manifest 5, routing 4, executor integratsiya 2)
- [x] **Executor integratsiya**: `run_domain_verifiers()` — yozilgan
      artefaktlar avtomatik routing (py→code, md/csv/json→document);
      VerificationLog'da `method="domain:code|document|research"` record'lar;
      ok=False → status pasayadi; fail-safe (verifier yiqilishi run'ni buzmaydi)

**R4 ta'siri (real catch):** R3 acceptance s08 soxta README (34 belgi,
tuzilishsiz) endi document verifier tomonidan USHLANDI — senariy real
tuzilishga tuzatildi. §13+§14+§15+§16 — YOPILDI. Roadmap v3 qoldiqlari:
§27 requirement-linked trace (keyingi), §21 OOM simulyatsiyasi (keyingi).

---

## QABUL MEZONLARI (har R phase oxirida)

1. Barcha yangi testlar PASS + eski 17 suite regressiyasi buzilmagan
2. `COMPLETE` statusi faqat evidence bilan mumkin (test bilan isbotlangan)
3. False-completion senariylari (§19) — har biri test sifatida qamrovdigan
4. `action_history.md` + roadmap checklist yangilangan

## XAVFLAR

- **R1 extraction aniqligi**: deterministik qism katta; LLM qismi optional —
  LLM'siz ham mandatory file req'lar ishlashi shart
- **R2 reconciliation xavfi**: fayl o'chirilganini aniqlovchi step re-execute
  — side-effect duplicate xavfi; action_id registry bilan kamaytiriladi
- **R3 real process kill** Windows'da SIGKILL farqi — subprocess + exit code
  bilan simulyatsiya qilinadi
