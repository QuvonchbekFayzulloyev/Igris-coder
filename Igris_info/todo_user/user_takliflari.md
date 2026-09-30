# USER TAKLIFLARI — bajarilishi kerak bo'lgan ishlar

> Manbalar: user so'rovlari, `problems_to_fix.md`, audit V3/V4, `TempTskilBuildForIgris.md`.
> Har bir taklif: nima, nega (foydalanuvchi foydasi), qayer, qiyinlik.

---

## 1-KATEGORIYA: Bajarilgan (tarixda user so'rab bergan va bajarilgan)

| Taklif | Qachon bajarildi | Natija |
|---|---|---|
| "Offline bo'lib qolishni to'xtat" (watchdog) | 2026-08-07 | ✅ ~20-30s avtomatik tiklanish |
| "Agent soxta status ko'rsatyapti" (fake data) | 2026-08-11 | ✅ Dp1 real agentInfo |
| "Desktop tugmalari ishlamayapti" | 2026-08-11 | ✅ Dp2 Tauri v2 |
| "Chizish so'rovlarida soxta 'chizdim'" | 2026-08-12 (V4 davri) | ✅ `_fake_draw_claim` guard |
| "Confidence har doim 0.9 ko'rsatyapti" | 2026-08-12 | ✅ A2 SelfEvaluator kalibratsiya |
| "Igris qilishi kerak ishlarni sifatli bajara olmayapti — o'lik protokollar" | 2026-09-12 | ✅ 3 jonli bug tuzatildi + 13 protokol auditi + Igris_info tashkil etildi |
| (navbatdagi "o'lik" protokollar: tezlik/xavfsizlik/aniqlik) | 2026-09-13 | ✅ D1 API validatsiya (32 test) + T2 mtime-cache (22 test) + A4 web manba grounding (21 test) + A1-2 run-verification (13 test) |

## 2-KATEGORIYA: Bajarilishi uchun user takliflari (navbat kutmoqda)

### 2.1 Aniqlik va sifat
- 🔴 **A1 per-domain verifikatorlar** — kod→pytest+lint, PDF→text-extract, PCB→DRC, 3D→mesh-check. *Nega:* "Bajardim" degan javob haqiqatan bajarilganini isbotlashi kerak. *Qayer:* `executor.py` `_verify_deliverable`. *Qiyinlik:* o'rtacha. *Holat:* 1-qadam (sintaksis `ast.parse`) 2026-09-12; 2-qadam (run-verification — fayl ishga tushadimi) 2026-09-13 ✅; qoldi: pytest-suite, PDF, PCB, 3D.
- ✅ **A4 manba tekshiruvi** — BAJARILDI (2026-09-13): `web_verify.py` — web javoblar manbaga grounding tekshiruvidan o'tadi (deterministik), SelfEvaluator `grounding` signali. Kengaytma navbatda: 2-manba tasdiqlash.
- 🟡 **S2 probe suitasi 4→20 task** — web, office, long-context, HITL, injection hujumlari. *Qayer:* `probe_decisions.py`.

### 2.2 Tezlik
- ✅ **T1 SQLite/FTS5 RAG index** — ✅ BAJARILDI (2026-09-12): `Igris_Memory/memory/fts5_index.py` — incremental, diskda, search 3-6x tezroq; `HybridSearch` ulandi.
- ✅ **T2 mtime-cache** — BAJARILDI (2026-09-13): `retrieval.py` `load_documents` faqat o'zgargan fayllarni qayta indekslaydi (mtime+size); `remove_source` API'lari barcha index'larda (FTS5 incremental DELETE).
- 🟡 **T4 polling→SSE** (task 4s, workspace 2s polling). *Qayer:* `server.py`, `Igris_Interface/shared/store.ts`.
- ⚪ **T5 creative_variants parallel** (asyncio). *Qayer:* `creative.py`.

### 2.3 Yangi imkoniyatlar (soha bo'shliqlari)
- 🟡 **Office server** (docx/pptx/xlsx/pdf) — MCP. *Foyda:* hujjat generatsiya.
- 🟡 **Diagramma server** (Mermaid/Graphviz→SVG/PNG). *Foyda:* sxema chizish.
- 🔴 **3D + EDA serverlar** (OpenSCAD, KiCad). *Foyda:* muhandislik domeni.
- ⚪ **Audio server** (piper TTS, whisper STT). *Foyda:* ovozli interfeys.
- 📌 **S1 skill qo'shish** — `progressive-visual-construction` (haqiqiy bosqichma-bosqich vizual qurish, 5 bosqichli rekursiv naqsh). *Manba:* `TempTskilBuildForIgris.md` — tayyor matn, skill'ga aylantirish kerak.

### 2.4 Tizim salomatligi
- ✅ **D1 kirish validatsiya middleware** — BAJARILDI (2026-09-13): `input_validation.py` — body-hajm (413), string/path/depth/number (422), fail-safe pass-through; `server.py`ga ulandi.
- 🟡 **S5 modullashtirish** — 1-2 QADAM BAJARILDI (2026-09-14): ① igris_agent 5641→4530 satr — `quick_paths.py` (math/weather), `web_strategy.py` (web strategiya), `agent_stack_data.py` (stack jadvallari), `request_classifier.py` (klassifikator+router); ② server.py 3078→2273 satr — `server_chat_history.py` (ChatHistory+progress), `server_circuit.py` (CircuitBreaker), `server_health.py` (metrikalar, uptime bugi tuzatildi), `server_process.py` (restart/watchdog). Delegatsiya/qayta eksport orqali API saqlandi, server endpoint'lari TestClient bilan real tekshirildi. *Qolgan: store.ts (1320), index.js (1197).*
- 🟡 **Dp4 python_exec to'liq sandbox** — resource limits, network off.
- 🟡 **D2 JSONL compaction** — size-cap scheduler (har kuni).
- 🟡 **D4 token/cost telemetry** — `/api/usage` + UI.

## 3-KATEGORIYA: Hozirgi holat (takliflar kontekstida)

- Tizim **jonli va ishlaydi** (batafsil: `state/current_state_report.md` §3)
- O'rtacha protokol sog'lig'i **~90%** (`state/health_matrix.md`)
- Eng katta hissiy shikoyat — "o'lik protokollar" — ildizida 2 narsa bor edi: (1) yashirin crash buglari (3 ta topildi-tuzatildi), (2) hujjatsizlik — kim nima qilishini bilmasdi. Endi ikkalasi ham hal qilingan; qolgan "o'liklik" — yo'q bo'lgan domain-imkoniyatlar (2.3) — bu yangi qurilish, tuzatish emas.
- **Boshlash tartibi** (AI coder uchun): ~~T1~~ ✅ → ~~D1~~ ✅ → **A1(kod verifikatori: pytest run)** → S5 → Office+Diagramma serverlar.

---

*Yangi taklif qo'shishda: kategoriya, ustuvorlik (🔴🟡⚪), nima, nega, qayer, qiyinlik.*
