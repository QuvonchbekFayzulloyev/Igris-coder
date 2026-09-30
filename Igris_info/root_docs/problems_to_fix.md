# IGRIS — MUAMMOLAR VA TUZATISH REJASI (problems → fix)

> Har bir muammo uchun: **nima**, **nima sababdan** (ildiz sabab), **ta'siri**, **yechim**, **ustuvorlik**.
> Ustuvorlik: 🔴 Yuqori · 🟡 O'rtacha · ⚪ Past.
> Format: Word hujjat (IGRIS_FULL_AUDIT_V4.docx) bilan sinxron — "MUAMMOLAR VA TUZATISH REJASI" bo'limi.
> Oxirgi yangilanish: **2026-09-18** (S2 probe suitasi 4→21 task + run-oracle'lar + guard'lar, 32 yangi test)

---

## TEKSHIRUV NATIJASI (11-avgust 2026 audit)

> Har bir muammo kodda **amalda tekshirildi** va holati yangilandi:
> ✅ **Tuzatildi** (bu sessiyada kod o'zgartirildi) · ⚠️ **Tasdiqlandi** (kodda bor, hali tuzatilmagan) · ⬜ Topilmadi/tegishli emas

| ID | Holat | Qayerda tekshirildi / nima qilindi |
|----|-------|-----------------------------------|
| N1 | ✅ Tuzatildi | `memory_bridge.py` — `recall()` har yozuvni `check_security()` bilan tekshiradi, suspicious'ni bloklaydi; `remember()` shubhali kontentni yozmaydi |
| N2 | ✅ Tuzatildi | `memory_bridge.py` + yangi `safety.py` — RAG recall konteksti `has_suspicious()` bilan tozalanadi (injection qatorlar tashlanadi) |
| N3 | ✅ Tuzatildi | `tools/web_tools.py` (web_fetch) + `web-ai-bridge/server/src/safety.js` (browser_get_text, web_ai_get_conversation, ask_web_ai, web_ai_check_research) + `mcp_bridge.py` (BARCHA MCP chiqishi uchun defense-in-depth) |
| Dp2 | ✅ Tuzatildi | `desktop/components/TitleBar.tsx` — Electron API o'rniga Tauri v2 `getCurrentWindow()`; brend "IGRIS" |
| Dp3 | ✅ Tuzatildi | `src-tauri/tauri.conf.json` — `csp: null` o'rniga real CSP siyosati |
| Dp5 | ✅ Tuzatildi | `tools/shell_tools.py` — `run_command` uchun deny-pattern ro'yxati (rm -rf /, sudo, shutdown...) |
| Dp6 | ✅ Tuzatildi | `tools/workspace.py` — `_is_inside` endi `os.path.realpath` ishlatadi (symlink orqali chiqib ketish bloklanadi) |
| Dp4 | ⚠️ Qisman | `tools/python_tools.py` — xavfli tarmoq/protsess chaqiruvlari deny-list bilan bloklandi; to'liq sandbox (resource limits) hali yo'q |
| D1 | ✅ Tuzatildi | `input_validation.py` (yangi) + `server.py` — BARCHA `/api/` POST so'rovlariga umumiy validatsiya middleware: body hajm limiti (10MB → 413), string uzunlik/kontrol-belgilar/null-byte/kod-injection naqshlari (422), path maydonlarida traversal (`..`) va sxemali URL (`file://`) bloki, JSON depth (>32) va inf/nan rad etish. FAIL-SAFE: noma'lum holatlar (JSON emas body, GET, `/api` tashqari) o'zgarmagan o'tadi — regressiya yo'q; validatsiya hech qachon serverni qulatmaydi. Local app: `workspace` caller-tanlaydi (qat'iy root YO'Q) — endpoint'lar o'z `Workspace.resolve` realpath containment'ini saqlaydi (defense-in-depth). Qat'iy root rejimi `install_input_validation(app, workspace_root=...)` bilan mavjud. 32 doimiy test (`test_input_validation.py`): unit + middleware (413/422/pass-through) + real `server.app` smoke (middleware endpoint'ga tegmasdan rad etadi) |
| A3 | ✅ Tuzatildi | `probe_decisions.py` — bajarilgan run (ok/partial+fayl) endi outcome 0.0 olmaydi (sinovda 0.0→0.62); marker hit bonus sifatida |
| A1 | ⚠️ Tasdiqlandi | `executor.py` — `_verify_deliverable`/`_llm_verify_deliverable` mavjud (fayl mazmuni tekshiriladi), lekin per-domain oracle (pytest/DRC/SPICE) yo'q — uzoq muddatli |
| A2 | ✅ Tuzatildi | `igris_agent.py` — barcha hardcoded `confidence` (0.85/0.9/0.95/0.99) + `resolve()` deterministik yo'lidagi resolver heuristic'i SelfEvaluator (2.7) bilan kalibrlandi; `_self_eval_for(data)` + `_confidence_for(data)` — evaluate() BIR MARTA chaqiriladi, natija `data["self_eval"]`'ga keshga yoziladi va memory on_resolve + javob bir xil qiymatni ishlatadi (ikki marta hisoblash yo'q); failed/partial resolver bahosini saqlaydi (RAG ifloslanmaydi). VERIFIKATOR signali: `structure_check` (repaired/fail) `verified` parametri orqali SelfEvaluator'ga ulanadi (repaired −0.10, fail −0.25); logprob Ollama'da mavjud emas — OpenAI-mos endpoint uchun kelajakda rejada. `resolve()` natijasiga ham `self_eval` biriktiriladi (ok rezolyutsiyalar; LLM fallback + deterministik), confidence undan olinadi; `_calibrated_confidence()` o'chirildi (bitta `_self_eval_for` oqimi). chat() final yo'lida memory `output` endi `data["content"]` (=out_final, repair'dan keyin) — confidence signali bilan bir xil matn. RESOLVER_SCORE: deterministik OK rezolyutsiyada resolverning o'z bahosi (0.6*rule_score+0.4*coverage) engine signalini scaley qiladi (0.35*rs) — kuchsiz rule (0.5)→0.825, kuchli (1.0)→1.0, hammasi 1.0 bo'lib qolmaydi; qiymat `data["resolver_score"]` sifatida ham saqlanadi. LOGPROB signali: native `/api/chat` logprob QAYTARMAYDI (official docs tekshirildi) — OpenAI-mos `/v1/chat/completions` qo'llab-quvvatlaydi, shuning uchun ixtiyoriy ALOHIDA re-so'rov (`chat_logprobs`, temperature=0, logprobs:true → exp(mean(logprob)) o'rtacha token ehtimoli) SelfEvaluator'ga `avg_logprob` signali bo'lib ulanadi (0.15*(2p−1): 0.9→+0.12, 0.2→−0.09; None→neytral). Faqat LLM yo'llarida (llm/llm+tools/llm-fast) va faqat `--logprobs`/`IGRIS_LOGPROBS=1` yoqilganida (2x inference narxi — default O'CHIQ); asl messages `_llm_messages` orqali uzatiladi (chat/chat_stream turbo+tool+stream, resolve LLM fallback), `_self_eval_for` o'qiydi va olib tashlaydi (javob toza); kontekstsiz yalang'och fallback YO'Q. TURBO/OFFLINE AUDIT: chat() turbo (llm-fast) + chat_stream turbo yo'llari ham final yo'l bilan bir xil — repair `data["content"]`'ga yozilgach memory'ga saqlanadi (raw `out` emas), `_cacheable_out` guard qo'shildi ("I could not generate" RAG'ga tushmaydi); chat_stream turbo'dagi `engine` NameError latent bug tuzatildi (o'sha scope'da `engine` aniqlanmagan edi). offline yo'li — chat darajasida memory YOZILMAYDI (by design, guard), resolve() ichki deterministik yozuvi o'z-o'ziga mos. Yangi doimiy testlar: `test_turbo_consistency.py` (5 test — turbo memory output == confidence invariant + NameError + junk guard) + `test_intelligence.py` TestSelfEval'da chat final yo'li testi (repair'dan keyingi `data["content"]` memory'ga yoziladi — raw `out` emas; memory confidence == javobdagi self_eval confidence; verifier_repaired signali ishlaydi). CAG PUT/HIT AUDIT: `chat()`'da CAG put xom `out`ni emas, AYNAN `data["content"]` (repair'dan keyingi)ni keshlaydi (put repair'dan keyin ko'chirildi, guard `_cacheable_out(data["content"])`); CAG hit yo'li ham repair'dan o'tadi (eski/buzilgan yozuv canonical matn bo'ladi, memory output == content == confidence, `_cacheable_out` guard). chat_stream CAG hit + plain-stream put ham bir xil naqshga keltirildi (repair-before-write — chat() bilan bir xil kalitda bir xil qiymat, inter-path tafovut yopildi). Testlar: `test_rag_cag_mag_hooks.py` (+4: put/hit chat + stream). RESOLVER FLOOR: deterministic/healed'da `length_ok` ham resolver_score bilan scaley qilinadi (engine kabi) — kuchsiz rule (0.5) uchun 0.825 floor 0.75 ga tushdi (0.5+0.175+0.075); rs=None (llm/cag/weather/math) o'zgarmaydi (0.15), length_short to'liq jarima saqlanadi; doimiy test `test_intelligence.py` TestSelfEval'da (rs=0.5→0.75, rs=1.0→1.0, None→1.0, llm ta'sirlanmaydi) + `test_resolver_score_monotonic` (deterministic VA healed, rs ∈ [0,1] bo'ylab 11 nuqta non-decreasing — kuchsiz rule hech qachon kuchlidan yuqori ishonch bermaydi; analitik 0.5+0.5*rs: 0.0→0.5, 0.6→0.8, 1.0→1.0). Test infratuzilmasi: `_FakeLLM.extract_code` endi instance orqali chaqiradi (OllamaClient.extract_code(text) `text`ni `self` deb bog'lab TypeError berardi — resolve() LLM fallback repair testlarini bloklagan edi). RAG IFLOSLANISH HIMOYASI: resolve() LLM fallback'da repair qilib BO'LMAYDIGAN buzilgan chiqish (verified='fail') xotiraga YOZILMAYDI (guard `struct_check is None or ok is not False`) — aks holda keyingi recall buzilgan code'ni qaytaradi; javob baribir qaytadi (fail signali + past confidence), telemetry yoziladi; repaired holatda xotiraga AYNAN ta'mirlangan matn o'tadi (persisted == returned — chat_history.jsonl'ga server ham toza matn yozadi). Doimiy test: `test_resolve_llm_fallback_rag_not_polluted`. LOGPROB TESTI: `test_avg_logprob_signal` — 0.9→+0.12, 0.2→−0.09, 0.5/None→neytral (note qo'shilmaydi), clamp [0,1] (p=1.0→+0.15, p=0.0→−0.15, p=5.0==p=1.0), llm bazasida 1.0 cap holati, `avg_logprob=0.900` note formati. XAVFSIZLIK SWEEP: `test_confidence_bounds_across_input_matrix` — 10 engine × 4 status × 5 verified × 7 tool_set × 2 output × 12 periferik (33,600 kombinatsiya): confidence DOIM [0,1], exception tashlamaydi, uncertainty low/medium/high; bekor engine/status/verified qiymatlari xavfsiz; manfiy/kattalashgan resolver_score (−5→0.0, 5→1.0) va avg_logprob clamp qilinadi. STREAM TOOL YO'LI AUDITI: chat_stream tool yo'lida (engine='llm+tools'/'llm') repair endi data yig'ish paytida qilinadi (plain-stream/turbo kabi) — ilgari memory on_resolve XOM matnni + pre-repair confidence'ni yozar, `_done` esa keyin repair qilib confidence'ni qayta hisoblar edi (memory != done). Endi memory AYNAN `data["content"]` (repair'dan keyingi)ni oladi, verifier signali confidence'ga kirgan holda; `_done`'dagi eskirgan izoh yangilandi (`pop` endi faqat fail holati uchun xavfsizlik to'ri). Doimiy test: `test_stream_tool_memory_output_matches_self_eval_source` (repair'dan OLDIN yiqilardi — memory xom matn olardi). TRANSCRIPT OGOHLANTIRISHI: server.py ChatHistory.add_message endi ixtiyoriy `warning` maydonini ALOHIDA saqlaydi (xabar matni toza — suhbat davom ettirilganda LLM kontekstiga ogohlantirish qo'shilmaydi, frontend alohida bannerda ko'rsatadi); `_structure_fail_warning(data)` helper — faqat structure_check ok=False (repair qilib bo'lmagan) holatida ⚠️ matn qaytaradi (repaired/toza/rad etish/offline — bo'sh, chunki ular plain matn, structure_check olmaydi). /api/chat va /api/chat/stream done voqeasiga `warning` qo'shiladi (faqat non-empty — token/stage voqealari bo'sh kalit bilan ifloslanmaydi). Frontend: ChatMessage.warning + ChatMessage.tsx qizil banner + selectChat (qayta ochilgan suhbat) va handleSend done mapping'i; CLI (cli/components/ChatView.tsx) ham qizil banner ko'rsatadi (store orqali warning allaqachon keladi — web bilan bir xil handleSend/selectChat). Doimiy testlar: `test_chat_history.py` (+3: alohida saqlash + JSONL round-trip; helper fail/repaired/toza; `test_broken_output_round_trip_keeps_file_valid` — transcript'ga repair qilib bo'lmagan buzilgan output + xavfli belgilar (tirnoq/yangi qator/backslash/emoji) yozilsa ham har bir JSONL qatori valid, qayta yuklashda matn+warning aniq tiklanadi, 2nd Brain grafi faylni xatosiz o'qiydi). STREAM FAIL-GUARD: verified='fail' (repair qilib bo'lmaydigan) chiqish ENDI HAMMA LLM yo'llarida RAG'ga yozilmaydi — chat_stream turbo/plain-stream/tool + chat() final/turbo/CAG-hit + chat_stream CAG-hit (guard `struct_check is None or ok is not False`, `_cacheable_out` bilan birga); chat() final va stream plain CAG PUT ham buzilganni keshlashni to'xtatdi. weather/math/creative deterministik yo'llar ta'sirlanmaydi (structure_check tushunchasi yo'q). Javob baribir qaytadi (fail signali + past confidence bilan), faqat xotira tozalanadi. Doimiy testlar (6 ta): `test_stream_plain_fail_not_written_to_rag` + `test_stream_tool_fail_not_written_to_rag` + `test_chat_final_fail_not_written_to_rag` (test_intelligence.py), `test_chat_stream_turbo_fail_not_written_to_memory` (test_turbo_consistency.py — `_FakeIntel.verify_structure` qo'shildi, LogicLayer().check_structure delegatsiya), `test_cag_hit_fail_not_written_to_memory` + `test_cag_hit_stream_fail_not_written_to_memory` (test_rag_cag_mag_hooks.py) |
| Dp1 | ✅ Tuzatildi | `cli/components/Sidebar.tsx` + `StatusBar.tsx` + `App.tsx` — hardcoded qwen3:8b/"39%"/"12.4K" o'rniga real `agentInfo` (offline → "—") |
| D1 | ⚠️ Tasdiqlandi | `server.py` — Pydantic modellar tip tekshiradi; path canonicalize `Workspace.resolve`'da bor; middleware validatsiya yo'q |
| Dp7 | ⚠️ Tasdiqlandi | `mcp_servers/art_server.py` — qamrov cheklangan (12 PNG + 19 SVG); kengaytirish reja |
| Dp9 | ⚠️ Tasdiqlandi | `web/tauri.ts` — o'lik scaffolding; Rust memory in-memory (restart'da yo'qoladi) |
| S5 | 🟢 Asosiy qism tuzatildi | **igris_agent.py** 5641→4530 satr: `quick_paths.py` (math/weather), `web_strategy.py` (web darvoza/strategiya), `agent_stack_data.py` (statik stack jadvallari), `request_classifier.py` (klassifikatorlar + router + subject/stack aniqlash) modullarga ajratildi — IgrisAgent metodlari delegatsiya orqali, API o'zgarmagan; `igris_quick.py` toza fasad. **server.py** 3078→2273 satr (−805): `server_chat_history.py` (428, ChatHistory + progress buferi), `server_circuit.py` (116, CircuitBreaker), `server_health.py` (195, health metrikalari — DI bilan, uptime `dir()` bugi tuzatildi), `server_process.py` (292, restart/watchdog/ollama — `_server_start_command` endi doim SERVER.PY'ni qayta ochadi). Barcha endpoint'lar TestClient bilan real tekshirildi; testlar kontrakti (`from server import ChatHistory, _structure_fail_warning`) saqlangan. ~500 regressiya test ✅. Qolgan: store.ts (1320), index.js (1197) |

---

## Q1 — ANIQLIK (Accuracy)

| ID | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|--------|-------------|--------|--------|------------|
| A1 | LLM javobi **semantik tekshirilmaydi** — faqat struktura (JSON/kod qavslari) tekshiriladi | `_verify_and_repair` faqat format tekshiradi; ground-truth oracle yo'q | Hallucination, vazifaga nomos javoblar foydalanuvchiga yetib boradi | Per-domain verifikatorlar: kod→pytest+lint, PDF→text-extract+content-check, PCB→DRC, 3D→mesh-check; javob "oracle"ga solishtiriladi | 🔴 |
| A2 | `confidence` qiymatlari **qat'iy/sun'iy** (0.85, 0.9) — haqiqiy ishonchni o'lchamaydi | Confidence LLM logprob/prob yoki self-eval asosida emas, hardcode | Past-aniq javoblar "yuqori ishonch" bilan yorliqlanadi | Confidence = f(LLM logprob, self-eval, verifikator natijasi); past bo'lsa qayta so'rov/qayta yozish | ✅ TUZATILDI (V4) — 11 hardcoded qiymat `SelfEvaluator.evaluate()` bilan almashtirildi; `_self_eval_for(data)` BIR MARTA chaqiradi, `data["self_eval"]`'ga kesh; `resolve()` deterministik + LLM fallback yo'llari ham; signallar: engine/status/verified (structure_check)/resolver_score/avg_logprob; memory output == javob content == confidence manbai (barcha chat_stream/chat yo'llari) | 🟢 |
| A3 | Probe natijasi `outcome=0.0` (fix_code, status=partial) | Quality gate fayl **mavjudligini** tekshiradi, **bajarilishini** emas; agent faylni yozib qo'ydi-yu to'liq hal qilmadi | "Bajardim" degan javob aslida chala | ✅ QISMAN TUZATILDI — `probe_decisions.score_task()`: ok VA partial (fayl+natija bilan) run'lar outcome 0.0 olmaydi (0.8 koeff bilan kredit), marker hit bonus. Kod ishlaydimi (run) tekshiruvi + 4→20 task hali rejada | 🔴 |
| A4 | Web/fakt savollarida **manba tekshiruvi yo'q** — web content "ishonchli" deb qabul qilinadi | Web_strategy LLM tavsiyasi; natija manbaga qayta tekshirilmaydi | Eskirgan/noto'g'ri faktlar javob sifatida | RAG/web javobini manba bilan solishtirish; `web_fetch` natijasini 2 manbadan tasdiqlash | 🟡 |

---

## Q2 — TEZLIK (Speed)

| ID | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|--------|-------------|--------|--------|------------|
| T1 | RAG search har query'da **butun BM25 index skan qiladi**; yangi yozuv `bm25._built=False` → keyingi search rebuild O(N) | Incremental index yo'q; index diskda saqlanmaydi | Har savolda sekinlashish, katta xotira bilan kritik | SQLite/FTS5 (incremental, diskda); index-ni yozishda batchni yangilash; `SessionCache` ni barcha recall'larga qo'llash | 🔴 |
| T2 | `MemoryManager.__init__` **butun katalogni o'qiydi** (barcha .md/.json/.jsonl) — sessiya ochilishi sekin | Precompute/import cache yo'q; `load_documents` to'liq walk | Backend ishga tushishi / sessiya starti sekin | Cheklangan chuqurlik + mtime cache; faqat o'zgargan fayllarni indexlash | 🟡 |
| T3 | Vector retrieval **amalda ishlamaydi** (80MB model, lazy encode, bir martalik build) | Embedding qimmat; faqat search vaqtida encode; FAISS build bir martalik | Semantik qidiruv yo'q (faqat BM25), yoki juda sekin | Kichik hash-embedding (bricks 128-dim modeli kabi) yoki top-k uchun tanlab encode | 🟡 |
| T4 | Frontend **polling-ga tayangan**: task 4s, workspace 2s, brain version 4s + full 20s | SSE/push faqat `/api/chat/stream` da; qolgan ma'lumotlar polling | Real-vaqt emas, serverga ortiqcha yuk | Jonli ma'lumotlar uchun SSE/WebSocket; pollingni faqat fallback qilish | 🟡 |
| T5 | `creative_variants` 3 xil temperature → **3 marta LLM chaqiruv**, parallel emas, keshsiz | Multi-temperature dizayn; parallel/kesh yo'q | Kreativ so'rovlarda 3x sekinlashish | Parallel so'rov (asyncio), natijani CAG'ga kiritish | ⚪ |

---

## Q3 — NOISEGA ALDANMASLIK (Robustness / Prompt-injection)

| ID | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|--------|-------------|--------|--------|------------|
| N1 | `PoisoningProtection` **hech qaerga ulangan emas** — faqat klass sifatida mavjud, hech kim chaqirmaydi | MemoryBridge.on_resolve/recall'da `check_entry` chaqiruvi yo'q | Zaharlangan yozuvlar xotiraga erkin kiradi, RAG orqali javobga oqadi | ✅ TUZATILDI — `recall()` har yozuvni `check_security()` bilan tekshiradi, `remember()` shubhali kontentni bloklaydi | 🔴 |
| N2 | RAG konteksti (recall) **tozalanmasdan** system prompt'ga qo'shiladi | Sanitizatsiya qatlami yo'q | Web/chat manbaidan kelgan "system:" / "ignore previous" kabi injectionlar LLM'ga o'tishi mumkin | ✅ TUZATILDI — yangi `safety.py` + `memory_bridge.recall()`: injection naqshli yozuvlar kontekstga kirmaydi | 🔴 |
| N3 | `browser_get_text` natijasi **chiqish-tomon tekshiruvsiz** LLM'ga qaytariladi | Output-side guard yo'q (faqat kirishda harm-filter bor) | Web sahifadagi yashirin ko'rsatmalar agentni alday oladi | ✅ TUZATILDI (to'liq) — 3 qatlam: ① `web_fetch` → `safety.py`; ② `browser_get_text`/`web_ai_*` → yangi `web-ai-bridge/server/src/safety.js`; ③ `mcp_bridge.call_tool` → BARCHA MCP chiqishini tozalaydi (hech qanday tool unutilmaydi) | 🔴 |
| N4 | Retrieval **dublikat/karama-qarshi** yozuvlarni ajratmaydi (dedup faqat yozish vaqtida) | Contradiction detection (fact-memory) bor, lekin retrieval'da qo'llanilmaydi | Bir savolga 2 xil/qarama-qarshi javob | Retrieval'da `contradictions` flag'i bilan eng ishonchli yozuvni tanlash; dublikatni yig'ish | 🟡 |
| N5 | Probe/benchmark yozuvlari xotirada qoladi (grafda filtr bor, lekin saqlanadi) | Yozish vaqtida tozalash yo'q; `_is_junk_entry` faqat graf uchun | Xotira shovqin bilan to'ladi, RAG natijalarini ifloslantiradi | Yozishda "junk/task-run" yorlig'i qo'yish, recall filtrini kengaytirish | 🟡 |

---

## Q4 — DATA KONTROL (Data control)

| ID | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|--------|-------------|--------|--------|------------|
| D1 | API kirishlarida **chuqur validatsiya yo'q** — Pydantic model faqat tip tekshiradi (path/length/format yo'q) | Validation qatlami middleware emas; path canonicalize yo'q | `../` path, juda uzun input, noto'g'ri format xavfi | ✅ TUZATILDI (2026-09-13) — `input_validation.py` middleware barcha `/api/` POST'larda: body-hajm (413), string uzunlik/kontrol-belgilar/kod-injection (422), path traversal/sxema bloki, JSON depth + inf/nan. FAIL-SAFE pass-through (regressiya yo'q); qat'iy root rejimi ixtiyoriy. 32 test | 🟢 |
| D2 | JSONL **hech qachon kompaktlashmaydi** (update eski+nukvini yozadi; append-only) | Compaction yo'q; `cleanup_stale` faqat `/api/session/cleanup` yoki autodream pass5 — scheduler yo'q | Disk o'sishi, index sekinlashishi, eski yozuvlar chigalligi | JSONL compaction + size-cap scheduler; cleanup'ni muntazam (har kuni/soat) ishga tushirish | 🟡 |
| D3 | **Artifact provenance/version yo'q** — faylni kim/qachon o'zgartirgani aniqlanmaydi | Provenance model yo'q; checksum saqlanmaydi | Qaytarish (rollback) va audit qiyin | Artifact manifest: har fayl uchun {checksum, timestamp, agent, task_id}; workspace timeline | 🟡 |
| D4 | **Token/cost telemetry yo'q** — LLM sarfi hisoblanmaydi | Chaqiruv hisoblagichi yo'q | Byudjetni boshqarib bo'lmaydi; samarasiz chaqiruvlar aniqlanmaydi | Har LLM chaqiruvda token+cost hisoblagich; `/api/usage` endpoint + UI | 🟡 |
| D5 | Workspace fayllari uchun **rollback yo'q** (faqat memory snapshot bor) | Fayl versiyalash yo'q | Yomon o'zgarishni qaytarib bo'lmaydi | workspace_file history: har write'da oldingi nusxa + diff; "revert" amali | ⚪ |
| D6 | UI ma'lumotlar (graph pozitsiyalar, backend URL) **lokalstorage'da** — portativ emas, tozalash yo'q | Sync/export yo'q | Boshqa mashinaga ko'chirishda holat yo'qoladi | Settings'ga export/import; holatni backend config'ga birlashtirish | ⚪ |

---

## Q5 — SIFAT (Quality / standartlar)

| ID | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|--------|-------------|--------|--------|------------|
| S1 | Sifat eshigi **faqat bir nechta yo'lda** (executor task, drawing svg_validator) — chat javoblari va yangi domainlar uchun yo'q | ASSESSMENT_STANDARDS.md bor, lekin `standards` registry'ga barcha yo'llar ulanmagan | Past-sifat javoblar eshikdan o'tadi | `KnowledgeAssessor` ni chat/natija yo'liga ulash; per-domain standartlar registry | 🔴 |
| S2 | **Probe suitası 4 task** — qamrov past (kod, fayl, rasm, fix) | Suitani kengaytirish rejasi yo'q | Agent sifatining faqat tor qismi o'lchanadi | ✅ TUZATILDI (2026-09-18) — 4→21 task, 6 kategoriya (code/data/multi/web/draw/robustness): run-oracle'lar (yozilgan Python HAQIQATAN ishlab to'g'ri chiqat berishi tekshiriladi — A1 yo'nalishi), guard'lar (keep_files, must_not_create_file), os.walk fayl-skan (MCP/skill yozgan fayllar ham ko'rinadi), kategoriya agregati + `category:code` filtri; 32 doimiy test | 🟢 |
| S3 | Telemetry **signal/alert emas** — faqat UI'dagi sonlar | Alerting yo'q | Sifat pasayishi (confidence decline) avtomatik aniqlanmaydi | Telemetry threshold → `/api/system/services`'da "degraded" flag + log/email | 🟡 |
| S4 | UI **a11y tekshiruvi yo'q** (ARIA, keyboard, contrast) | Standart yo'q | Nogiron foydalanuvchilar uchun qiyin | Axe-core skanerini CI/qo'lda ishga tushirish; ARIA rollarini qo'shish | 🟡 |
| S5 | **God-file'lar** (igris_agent 5641, server 3078, store.ts 1320, index.js 1197 satr) | Refactor qadami yo'q, yagona faylda yig'ish odati | Maintainability, xato qilish ehtimoli, tekshirish qiyinligi | 🟢 ASOSIY QISM TUZATILDI (2026-09-14) — igris_agent → quick_paths + web_strategy + agent_stack_data + request_classifier; server.py → server_chat_history + server_circuit + server_health + server_process (delegatsiya/qayta eksport, API saqlangan; server endpoint'lari TestClient bilan tekshirildi). Qolgan: store.ts, index.js — har modul ≤ 500 satr maqsadi | 🟡 |

---

## Soha (domain) kategoriyalari — bo'shliqlar

| Kategoriya | Holat | Asosiy bo'shliq / muammo | Yechim | Ustuvorlik |
|------------|-------|--------------------------|--------|------------|
| Code Intelligence | ✅ mavjud | God-file, probe outcome=0.0, per-domain gate yo'q | Modullashtirish + verifikatorlar | 🔴 |
| UI/UX Frontend | ✅ qisman | CLI stub, 3 ishlamaydigan tugma, a11y yo'q | CLI tugatish, tugmalarni ulash, a11y | 🔴 |
| Diagramma & Sxema | ❌ yo'q | Umumiy diagramma tool (Mermaid/Graphviz) yo'q | `diagram_server` MCP + render → SVG/PNG | 🟡 |
| Rasm (Image) | ⚠ qisman | Rastr tahrir, image→code, OCR/tahlil yo'q; svg_validator bor | PIL qatlami + image analysis | 🟡 |
| Video | ⚠ qisman | Faqat WebM build-record; storyboard/montaj/ffmpeg yo'q | ffmpeg pipeline + storyboard | 🟡 |
| Audio | ❌ yo'q | TTS/musiqa/transkripsiya umuman yo'q | `audio_server` (piper/whisper/ffmpeg) | 🟡 |
| 3D Model | ❌ yo'q | OpenSCAD/STL/render yo'q | `3d_server` (OpenSCAD) | 🔴 |
| Hardware 3D | ❌ yo'q | Slicer/G-code/preflight yo'q | slicer wrapper + preflight | 🔴 |
| Schematics & PCB | ❌ yo'q | KiCad/netlist/Gerber/DRC/SPICE yo'q | `eda_server` (KiCad Python) | 🔴 |
| Office hujjatlar | ❌ yo'q | DOCX/PPTX/XLSX/PDF generatsiya yo'q | `office_server` (python-docx/pptx/openpyxl/reportlab) | 🟡 |
| Audit & Review | ⚠ qisman | Faqat kod/telemetry; domain-eshiklar yo'q | Per-domain verifikatorlar | 🔴 |
| Detallashtirish | ⚠ qisman | Generic planner; domain-template yo'q | Per-domain spec→detail templatelar | 🟡 |
| MCP domain-serverlari | ⚠ qisman | art/ui_builder bor; 3d/eda/office/media/audio yo'q | Yangi MCP serverlar | 🔴 |
| Memory kengaytirish | ⚠ qisman | L2 24 tur bor; domain (3d/pcb/office/media) turlar yo'q | Domain-memory turlari + artifact registry | 🟡 |

---

## CHUQUR AUDIT QO'SHIMCHA TOPILMALARI (V3)

| ID | Modul | Muammo | Ildiz sabab | Ta'sir | Yechim | Ustuvorlik |
|----|-------|--------|-------------|-------|--------|------------|
| Dp1 | CLI | `AgentPanel` **hardcoded fake data** ko'rsatadi (qwen3:8b, "39%", "12.4K/32K tokens") — `agentInfo` emas | Status qismi agentga ulangani yo'q; ko'chirib yozilgan | Foydalanuvchini aldaydi — tizim holati yolg'on ko'rsatiladi | ✅ TUZATILDI — `AgentPanel`+`StatusBar` real `agentInfo` ko'rsatadi, offline → "—"; CLI App `loadAgentInfo()` chaqiradi | 🔴 |
| Dp2 | Desktop | `TitleBar.tsx` **`window.electronAPI` (Electron API)** ishlatadi — app TAURI, API mavjud emas → oyna tugmalari ishlamaydi; brend "Anchor" (IGRIS emas) | Electron'dan ko'chirilgan, Tauri API'ga o'tkazilmagan | Minimize/maximize/close tugmalari o'lik, noto'g'ri brend | ✅ TUZATILDI — `getCurrentWindow()` (Tauri v2) API'ga o'tkazildi + IGRIS brendi | 🔴 |
| Dp3 | Desktop | `tauri.conf.json` — **`csp: null`** (Content-Security-Policy o'chiq) | CSP sozlanmagan | XSS xavfi (agar kontent injekt qilinsa) | ✅ TUZATILDI — CSP siyosati o'rnatildi (self + ipc + localhost backend) | 🔴 |
| Dp4 | Tools | `python_exec` **"sandbox" deya atalgan, lekin haqiqiy sandbox emas** — to'liq OS/network/disk kirish (faqat timeout+cwd) | Cheklov faqat subprocess+cwd; resource/network cheklov yo'q | Agent kodi foydalanuvchi tizimida to'liq huquq bilan ishlaydi | ⚠️ QISMAN TUZATILDI — xavfli tarmoq/protsess/destruktiv chaqiruvlar deny-list bilan bloklandi; to'liq sandbox (resource limits, seyf) hali rejada | 🟡 |
| Dp5 | Tools | `run_command` da **deny-pattern tekshiruvi yo'q** (rm -rf / sudo kabi) | Igris_Memory config'ida deny bor, lekin tools qatlamida yo'q | Xavfli buyruqlar cheklanmagan | ✅ TUZATILDI — `DENY_PATTERNS` ro'yxati qo'shildi (rm -rf /, sudo, shutdown, format, disk yozish...) | 🟡 |
| Dp6 | Tools | `Workspace._is_inside` **symlink orqali chiqib ketishga qarshi emas** (`realpath` ishlatilmaydi) | `os.path.abspath` symlinkni yechmaydi | Workspace ichidagi symlink tashqariga ishora qilsa — sandbox buziladi | ✅ TUZATILDI — `os.path.realpath` asosida tekshiriladi | 🟡 |
| Dp7 | Image | `art_server` qamrovi **juda tor** — 12 PNG + 19 SVG oddiy predmet (olma, uy, mushuk...) | Qo'lda chizilgan predmetlar kutubxonasi; generatsiya emas | "Rasm chiz" so'rovida faqat ma'lum predmetlar ishlaydi | PIL/rastr qatlami + image→code + analiz | 🟡 |
| Dp8 | Tools | `apply_patch` simple-rejimda "+" qatorlarni **fayl oxiriga append** qiladi | Oddiy heuristic, pozitsiya aniq emas | Murakkab patch'da fayl noto'g'ri o'zgarishi mumkin | satr-pozitsiyali patch (unified diff) | ⚪ |
| Dp9 | Desktop | `web/tauri.ts` — **o'lik scaffolding** (komandalar hech kim chaqirmaydi); Rust memory in-memory (restart'da yo'qoladi) | Ishlatish rejasi yo'q | Keraksiz kod, chalg'ituvchi | Olib tashlash yoki FastAPI proxiga ulash | ⚪ |

---

## Konsolidatsiya (xulosa)

### ✅ 11-avgust sessiyasida tuzatilganlar

| ID | Nima qilindi |
|----|-------------|
| N1 | PoisoningProtection `recall()`/`remember()`'ga ulandi |
| N2 | `safety.py` yaratildi; RAG recall konteksti tozalanadi |
| N3 | `web_fetch` chiqishi `safety.sanitize()` bilan tozalanadi (to'liq — `browser_get_text` + barcha MCP) |
| Dp1 | CLI AgentPanel + StatusBar real `agentInfo` ko'rsatadi |
| Dp2 | TitleBar Tauri v2 API'ga o'tkazildi, brend IGRIS |
| Dp3 | Tauri CSP siyosati o'rnatildi |
| Dp5 | `run_command` deny-pattern ro'yxati |
| Dp6 | `Workspace` realpath asosida path tekshiruvi |
| A3 | Probe outcome: bajarilgan run 0.0 olmaydi (0.0→0.62) |
| Dp4 | (qisman) `python_exec` xavfli chaqiruv deny-list |

### ✅ 12-avgust sessiyasida tuzatilganlar (A2 to'liq + RAG himoyasi)

| ID | Nima qilindi |
|----|-------------|
| A2 | Confidence SelfEvaluator bilan kalibrlandi (11 hardcoded → `evaluate()`); `resolve()` deterministik yo'li ham; `self_eval` javobga biriktiriladi |
| A2 | `evaluate()` BIR MARTA — `_self_eval_for` kesh; memory == javob confidence (chat/chat_stream/resolve barcha yo'llar) |
| A2 | Verifikator signali: `structure_check` (repaired −0.10, fail −0.25) → `verified` parametri |
| A2 | `resolver_score` signali (0.35*rs) — deterministik OK hammasi 1.0 bo'lib qolmaydi; `length_ok` ham scaley (0.825→0.75 floor) |
| A2 | `avg_logprob` signali (0.15*(2p−1)) — ixtiyoriy `--logprobs`/`IGRIS_LOGPROBS=1` rejimi, OpenAI-mos endpoint uchun |
| RAG | `verified='fail'` chiqish HECH QAYERDA yozilmaydi — chat_stream turbo/plain/tool + chat() final/turbo/CAG-hit + CAG PUT (7 ta joy, `_cacheable_out` + struct_check guard) |
| RAG | chat_stream tool yo'li repair-before-write (memory output == done content == confidence manbai) |
| RAG | Transcript `warning` maydoni — structure_check fail holatida ⚠️ banner (web + CLI), xabar matni toza saqlanadi |
| RAG | ChatHistory JSONL buzilgan output bilan ham valid qoladi (round-trip test) |
| Test | **+20 doimiy test** (211 jami): turbo invariantlar, CAG put/hit, fail-guard (6), logprob, resolver monotonic, confidence sweep (33,600 kombinatsiya), warning, round-trip |

### ✅ 13-sentabr sessiyasida tuzatilganlar

| ID | Nima qilindi |
|----|-------------|
| D1 | `input_validation.py` — umumiy kirish validatsiya middleware (body-hajm 413, string/path/depth/number 422, fail-safe pass-through) + `server.py` ga ulandi; 32 doimiy test |
| T1 | `Igris_Memory/memory/fts5_index.py` — BM25 o'rniga SQLite FTS5 index (incremental, diskda); `retrieval.py` avtomatik fallback bilan uladi; 12 test |

### ✅ 18-sentabr sessiyasida tuzatilganlar (S2 — probe suitasi kengaytirish)

| ID | Nima qilindi |
|----|-------------|
| S2 | `probe_decisions.py` v2: 4→21 task, 6 kategoriya (code 6, data 3, multi 4, web 2, draw 2, robustness 4). Eski 4 id saqlangan (server/UI/eski hisobotlar mos) |
| A1 | **Run-oracle'lar**: code_fib, code_sort_fix, code_json_roundtrip, code_cli_argparse, data_filter_csv, data_multi_join, data_stats_json, rb_overspecified, multi_append_log, multi_nested_tree — yozilgan skript HAQIQATAN run qilinadi, stdout/fayl-mazmun kutilgan qiymat bilan solishtiriladi (oracle outcome'ning 60%'ini belgilaydi). Kanonik yechimlar oracle'dan o'tishi test bilan kafolatangan (data_multi_join'da kutilgan qiymat 29→27 deb TO'G'RILANDI — real hisob bilan) |
| S2 | **Guard'lar**: `keep_files` (mavjud fayl o'chirilmasligi KERAK — code_readonly_guard, multi_restructure, multi_append_log), `must_not_create_file` (javob faqat matnda — web_fetch_title). Buzilish → outcome 50% jarima |
| S2 | **files os.walk**: files_present/files_created — MCP/skill tomonidan yozilgan fayllar ham ko'rinadi (avval faqat write_file args'dan edi — draw tasklari noto'g'ri past baholanardi) |
| S2 | **Kategoriya agregati**: `report.categories[cat] = {n, outcome, reasoning}` — qaysi domenda agent kuchsiz, bir qarashda ko'rinadi; `--tasks category:code` filtri |
| S2 | `use_skill`/`request_human` signal'lari trace'ga yoziladi (qobiliyat-yetishmasligi va HITL o'lchanadi) |
| S2 | Executor konstruktisi ham crash-guard ichida (workspace/MCP xatosi butun probe'ni emas, faqat taskni "error" qiladi); max_iter 10→14 (murakkab tasklar uchun) |
| Test | `test_probe_decisions.py` — 32 doimiy test: task katalog, select_tasks (all/id/category/xato), oracle'lar (to'g'ri/yolg'on yechim ajratadi), scoring qoidalari (outcome kredit, oracle ustuvorligi, guard jarimalari), _scan_workspace, run_task fail-safety, UI kontrakt (backend.ts ProbeReport bilan mos) |
| Test | Regressiya ✅: agentic_pipeline (166+subtestlar), input_validation (32), chat_history (27), turbo+rag_cag+intelligence+requirements (89), degradation+web_strategy+skills_mcp_hitl+stream_thinking (77), task_supervisor+web_verify (60) |

| ID | Nima qilindi |
|----|-------------|
| S5 | `server.py` 3078→2273 satr (−805): to'rt modulga ajratildi — `server_chat_history.py` (428: ChatHistory JSONL do'kon + CHAT_PROGRESS buferi + `_structure_fail_warning`; FAQAT stdlib), `server_circuit.py` (116: CircuitBreaker + `_CIRCUIT` singleton; FAQAT stdlib), `server_health.py` (195: metrika ring-buffer + `collect_health_metrics` — tashqi holat DI orqali, import tsikli yo'q), `server_process.py` (292: restart/watchdog/ollama/port yordamchilari; FAQAT stdlib) |
| S5 | server.py qayta eksport kontrakti saqlanadi: `from server import ChatHistory, _structure_fail_warning` (testlar), `_install_fatal_handlers`/`_spawn_detached`/... (eski ichki nomlar) — hammasi `is` tekshiruvi bilan identik obyektlar |
| BUG | **Health uptime doim ~0 edi** (`server.py`): `'_SERVER_START_TIME' in dir()` funksiya ichida faqat LOKAL nomlarni qaytargani uchun doim False edi. Tuzatish: `collect_health_metrics(server_start_time=...)` DI parametri — `/api/health/metrics` endi real uptime qaytaradi (TestClient bilan tekshirildi: uptime > 0) |
| S5 | **Restart-ixlosi oldini olindi**: `_server_start_command` avval `os.path.abspath(__file__)` ishlatardi — server_process.py'ga ko'chsa restart NOTO'G'RI faylni ochardi. Endi `_SERVER_PATH` (configure() bilan o'rnatiladi) doim server.py'ni ko'rsatadi — parity test: restart komandasi `server.py`'ni o'z ichiga oladi, `server_process` emas |
| S5 | `main()` global mutatsiyalari → `_proc.configure(host, port, extra_args)`; endpoint read-saytlari late-binding (`_proc._RUN_PORT`) — restart paytida yangi qiymatlar to'g'ri ko'rinadi |
| Test | server.py regressiya ✅: barcha endpoint guruhlari (health/metrics/history, chat, system/services, circuit/reset) TestClient bilan real chaqirildi; 25 test-fayl (agentic_pipeline 166, web_strategy 39, task_supervisor 39, input_validation 32, chat_history 27...) yashil; "NO TESTS RAN" fayllar (test_chat_draw_e2e, test_executor, test_assessment, test_brain, test_composition) HEAD bilan bir xil script-rejim |
| S5 | `igris_agent.py` 5641→4530 satr (−1111): to'rt modulga ajratildi — `quick_paths.py` (math/weather tez yo'llar, 316), `web_strategy.py` (web darvoza/strategiya/tool leksikasi, 424), `agent_stack_data.py` (STACK_PLANS/FRAMEWORK_STACK/ORM_STACK/LANG_STACK/DB_STACK/DB_DISPLAY_SUFFIX — faqat statik data, 618), `request_classifier.py` (pipeline detektorlari + ikki bosqichli router + subject/db/orm/stack aniqlash + clarify, 899) |
| S5 | IgrisAgent metodlari bir qatorli delegatsiyaga o'tkazildi — klass API'si (nomlar, imzolar, statik/classmethod dekoratorlari) O'ZGARMAGAN; testlar mosligi uchun statik jadvallar va leksika klass-atribut sifatida qayta eksport qilinadi (identik obyektlar — `is` tekshiruvi bilan) |
| S5 | `igris_quick.py` buzuk yarim-tayyor shimdan toza FASADga aylantirildi (is_math_expr/weather_lookup/... eski nomlari quick_paths'ga to'g'ri delegatsiya qiladi — avval noto'g'ri semantika edi: math_prefix regex obyekt qaytarardi, needs_web doim False) |
| S5 | O'lik kod tozalandi: ishlatilmagan `from igris_web/igris_quick import ...` fallback bloklari (hech qachon ishga tushmagan), ikki marta aniqlangan `_detect_web_tech`/`_classify_need` dublikatlari |
| Test | Regressiya ~513 test ✅: agentic_pipeline 166, web_strategy 39, intelligence 45, chat_history 27, degradation 10, requirements 15, syntax 11, run 13, input_validation 32, web_verify 21, task_supervisor 39, skills_mcp_hitl 18, stream_thinking 10, svg_validator 34, turbo 6, rag_cag 23, adaptive 4, FTS5 12, T2 10 |
| BUG | **Supervisor cheksiz rekursiyasi tuzatildi** (audit paytida topilgan, §9): ichki chat yana supervisor ochib minutlab kutish/stack-portlash xavfi — `_supervisor_active` guard; testlar 228s→0.9s darajada tezlashdi |
| BUG | **RequirementExtractor qotib qolgan klient** tuzatildi: `llm_provider` lazy-getter — agent.llm almashtirilsa ergashadi; LLM yo'q bo'lsa deterministik fallback (real tarmoq chaqiruvi yo'q) |
| Audit | problems_to_fix.md'dagi barcha "tuzatildi" da'volari kodda qayta tekshirildi: T1 (FTS5 wired), T2 (mtime cache), A4 (grounding signal), A1-2 (run-verification), D1 (middleware), S3 (degradation registry), N3 (mcp_bridge sanitize), Dp5 (DENY_PATTERNS), Dp6 (realpath) — hammasi real va ishlaydi |

### Navbatdagi qadamlar

- **Eng tez natija (1-3 kun):** ~~D1~~ ✅, ~~T1~~ ✅, ~~S2 (probe 4→21 + oracle'lar)~~ ✅ — bajarildi. Navbatda: A4 (web manba tasdiqlash) va T2 (`load_documents` mtime cache) — barchasi mavjud modullarni **ulash**, yangi yozish emas. (N3 endi to'liq — `browser_get_text` va barcha MCP chiqishi tozalanadi.)
- **2026-09-14 sessiyasida tuzatilgan:**
  - **Q1 (Accuracy)** — `request_classifier.py` substring false positivlari tuzatildi: `is_draw_request`, `is_code_request`, `is_composition_request`, `is_creative_request` — barcha so'zlar `\bword\b` regex bilan tekshiriladi; Uzbek sufiklari (`kodini`, `faylni`) uchun `\bword\w*\b`
  - **Q1 (Accuracy)** — `igris_agent.py` `_fake_draw_claim` — `"drew"` → `\bdrew\b` (drawer false positive o'chirildi)
  - **Q1 (Accuracy)** — `_auto_select_model` — `agent._mark_llm_recovered()` qo'shildi (degradation recovery belgisi)
  - **Q2 (Speed)** — `web-ai-bridge/index.js` `MAX_TEXT_CHARS` 8000→20000 (xato javoblar kesilmaslik)
  - **Q5 (Quality)** — `store.ts` modullashtirilgan: helper funksiyalar (`time-helpers`, `brain-logs`, `drawing-helpers`, `tree-helpers`) ajratib chiqarildi (1292→1125 satr)
  - **Q1 (Accuracy)** — `igris_agent.py` `_domain_verify` method qo'shildi — kod uchun syntax tekshiruv (brackets balance, TODO/FIXME placeholderlari), draw uchun fake claim tekshiruvi
- **O'rta muddat (2-4 hafta):** Q1 verifikatorlar + probe suitasini 4→20 task kengaytirish; A2 confidence'ni `SelfEvaluator`'ga ulash; S5 davomi (store.ts 1125→≤500, index.js 1197→≤500); Office + Diagramma + Audio serverlar.
- **Uzoq muddat (1-2 oy):** Hardware (3D/PCB) serverlar; Video pipeline; to'liq a11y; CI+telemetry alerting; `python_exec` to'liq sandbox.
- **Umumiy balandlik:** mavjud "bor va ishlaydi" → "o'lchanadigan va kafolatlangan" darajaga ko'tarish.
