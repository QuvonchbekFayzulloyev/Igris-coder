# Hozirgi IGRIS HOLATI (2026-09-13)

> Ushbu hisobot **3 kategoriyaga** bo'lingan: (1) bajarilgan ishlar, (2) bajarilishi kerak bo'lgan user takliflari, (3) hozirgi tizim holati.

---

## 1-KATEGORIYA: BAJARILGAN ISHLAR

| Sana | Nima bajarildi | Batafsil |
|---|---|---|
| 2026-08-07 | Offline-himoya (watchdog) — backend/Ollama avtomatik tiklanish ~20-30s | `actions/action_history.md` §1 |
| 2026-08-11 | Xavfsizlik: N1/N2/N3 injection himoyasi, Dp1/Dp2/Dp3/Dp5/Dp6 desktop+tools | `actions/action_history.md` §2 |
| 2026-08-12 | A2 confidence kalibratsiya + RAG fail-guard (7 joy) + 20 doimiy test | `actions/action_history.md` §3 |
| 2026-08-17 | 2nd Brain qora oyna/loading qotish/graf sekinlik tuzatishlari | `actions/action_history.md` §4 |
| 2026-09-12 | **3 jonli bug tuzatildi** + Igris_info to'liq tashkil etildi | `actions/action_history.md` §5 |
| 2026-09-13 | **D1 + T2 + A4 + A1-2** — API validatsiya, mtime-cache, web grounding, run-verification | `actions/action_history.md` §6 |

**2026-09-13 sessiyasi tafsiloti (eng so'nggi):**
1. **D1 bajarildi**: `input_validation.py` — barcha `/api/` POST so'rovlarida chuqur validatsiya (hajm 413, string/path/depth/number 422), fail-safe pass-through; 32 test ✅
2. **T2 bajarildi**: `load_documents` mtime-cache — faqat o'zgargan fayllar qayta indekslanadi; `remove_source` API'lari (FTS5 incremental DELETE); 22 test ✅
3. **A4 bajarildi**: `web_verify.py` — web javoblar manbaga grounding tekshiruvidan o'tadi (deterministik, LLM yo'q); SelfEvaluator `grounding` signali (grounded +0.10 / ungrounded −0.15); 21 test ✅
4. **A1 2-qadam bajarildi**: run-verification — agent yozgan `.py` izolyatsiyada ishga tushirib ko'riladi; runtime xatoli (NameError/TypeError...) gate'dan o'tmaydi (import/deps neytral); 13 test ✅
5. Regressiya: 160+ test o'tdi (chat_history, degradation, requirements, brain, svg_validator, input_validation, web_verify, deliverable syntax+run, executor, turbo, rag_cag, intelligence)

## 2-KATEGORIYA: BAJARILISHI KERAK — USER TAKLIFLARI

To'liq ro'yxat `todo_user/user_takliflari.md` da. Eng muhimlar:

| Ustuvorlik | Taklif | Sabab |
|---|---|---|
| 🔴 | A1 qolgan verifikatorlar (pytest-suite, PDF→extract, PCB→DRC) | "Bajardim" aytmaydigan bo'lishi uchun |
| 🟡 | S5: God-file'lar modullashtirish — igris_agent ✅ (5641→4530, 2026-09-14); server.py/store.ts navbatda | Maintainability |
| 🔴 | Domain-MCP serverlar: Office, Diagramma, Audio, 3D, EDA | Soha bo'shliqlari |
| 🟡 | 2-manba tasdiqlash (A4 kengaytmasi) | Eskirgan/noto'g'ri faktlar |
| 🟡 | T4: polling → SSE/WebSocket | Real-vaqt |
| 🟡 | D4: token/cost telemetry | Byudjet nazorati |
| 🟡 | S2: probe suitasi 4→20 task | Sifat o'lchanadi |
| 🟡 | S4: a11y (axe-core, ARIA) | Foydalanuvchi qamrovi |

## 3-KATEGORIYA: HOZIRGI TIZIM HOLATI

**Umumiy baho: TIZIM JONLI VA ISHLAYDI** — barcha 13 protokolning asosiy oqimlari faol.

| Qatlam | Holat | Izoh |
|---|---|---|
| Backend (FastAPI :8765) | ✅ ishlayapti | Importlar toza, 58 yadro test ✅ |
| LLM (Ollama qwen3:8b) | ✅ sozlangan | turbo/thinking/logprobs (ixtiyoriy) |
| Watchdog | ✅ faol | `logs/watchdog.json` |
| Xotira (L1/L2/RAG) | ✅ faol | JSONL fayllar jonli yozilyapti |
| CAG/MAG | ✅ faol | put/hit/fail-guard testlari ✅ |
| Tools/MCP | ✅ faol | art/ui_builder/skills/... 8 MCP server |
| Web-ai-bridge | ✅ sozlangan | CDP + real Chrome (mr.wtin) |
| Interface (web/desktop) | ✅ faol | Vite + Tauri; `AgentConsole.tsx`, `RightSidebar.tsx` so'nggi o'zgarishlar |
| 2nd Brain | ✅ faol | Graf + katalog + kesh |

**Qolgan zaif joylar** (tizim o'lik emas, lekin cheklov): A1 qolgan verifikatorlar (pytest-suite, PDF, PCB), S5 qolgan god-fayllar (server.py 3078, store.ts 1320 — igris_agent 2026-09-14 da 4 modulga bo'lindi), Dp4 python_exec to'liq sandbox emas, Dp7 tor predmet kutubxonasi.

**So'nggi sessiyada yo'qotilgan zaifliklar:** ~~D1 API validatsiya~~ ✅, ~~T1 FTS5~~ ✅, ~~T2 mtime-cache~~ ✅, ~~A4 web manba tekshiruvi~~ ✅, ~~A1 sintaksis+run verifikator~~ ✅ (qolgan domain-verifikatorlar navbatda)

---

*Yangilash qoidasi: har asosiy o'zgarishdan keyin shu fayl + `health_matrix.md` yangilanadi.*
