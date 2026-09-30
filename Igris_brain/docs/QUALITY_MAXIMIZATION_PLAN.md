# IGRIS BRAIN — Sifatni Maksimallashtirish Rejasi
## (Quality Maximization Plan — benchmark natijalari asosida)

**Sana:** 2026-08-04
**Model:** qwen2.5-coder:7b (lokal, Ollama, RTX 5060)
**Asos:** `reports/benchmark_llm_v3.json` (12 task: 6 sodda + 6 murakkab)

---

## 1. Benchmark xulosasi

| Ko'rsatkich | Deterministik (no-llm) | Gibrid (LLM bilan) |
|---|---|---|
| Sodda tasklar pass | 83% | 83% |
| Murakkab tasklar pass | 0% | **100%** |
| Sodda tezlik | **3–27 ms** | 3–27 ms (deterministik yo'l) |
| Murakkab tezlik | 40–52 ms (noto'g'ri javob) | 3.1–4.9 s |
| Umumiy pass rate | 42% | **92% (11/12)** |

**Asosiy xulosa:** gibrid yondashuv ishlaydi — deterministik yadro sodda tasklarni
millisekundlarda, LLM murakkablarini bir necha soniyada hal qiladi. Murakkab
tasklarda 0% → 100% o'sish **min_confidence 0.5 → 0.7** ko'tarilishi hisobiga
erishildi (yarim-yaroqsiz brick kombinatsiyalari endi LLM'ga yo'naltiriladi).

---

## 2. Aniqlangan zaif tomonlar (benchmark asosida)

1. **Brick bank juda kichik** — atigi 18 brick. Rejada ~4000 node ko'zda tutilgan.
   `sum`, `max`, `min`, `intersection` qo'shildi, lekin `filter`, `map`, `regex`,
   fayl/HTTP operatsiyalari, pandas API'lari hali kam.
2. **LLM ishga tushirish kechikishi** — qwen2.5-coder:7b birinchi so'rovda
   ~3.5–4 s (model yuklanadi + kompozitsiya). KEEP_ALIVE sozlanganda takroriy
   so'rovlar tezroq.
3. **Sodda tasklarda bir "noto'g'ri negative"** — `s6` ("ro'yxatning o'rtachasini
   hisobla") LLM'ga o'tib, `sum(numbers)/len(numbers)` qaytardi — to'g'ri matematika,
   lekin `np.mean` markerini topmadi. Deterministik qoida qo'shilsa, bu 10 ms ga
   tushadi.
4. **RAG konteksti faqat LLM yo'lida** ishlatiladi — deterministik yo'lda xotira
   brick tanlashga yordam bermaydi (kelajakda: recall'dan olingan so'zlar bilan
   brick lookup kengaytiriladi).
5. **FAISS/vector qidiruv o'chirilgan** — `sentence-transformers` o'rnatilmagan,
   faqat BM25 ishlaydi. Bu "1.5B" rejimida ataylab qilingan (BM25 0 overhead),
   lekin semantik sinonimlar uchun vector qatlam foydali.

---

## 3. Harakat rejasi (ustuvorlik bo'yicha)

### 3.1 Bajarildi (ushbu sessiyada) ✅

| # | Harakat | Natija |
|---|---|---|
| 1 | **Igris_Memory bilan integratsiya** — `memory_bridge.py` (remember/recall/RAG, session, hooks, AutoDream) | RAG ishlaydi: resolve oldidan recall, keyin remember |
| 2 | **Agent'ga RAG** — LLM prompt'iga xotira konteksti qo'shildi | LLM endi xotiradagi bilimni ko'radi |
| 3 | **min_confidence 0.5 → 0.7** | Murakkab tasklar 0% → 100% |
| 4 | **Yangi brick/qoidalar** — `concept_max`, `concept_min`, `concept_intersection`, `sum_of_list`, `max_of_list`, `min_of_list` | s5 ("sum the list") deterministik: 1.0 |
| 5 | **O'zbekcha qo'shimcha shakllar** — `o'rtachasini`, `o'rtachani` (concept_mean) | s6 yaxshiroq yo'naltiriladi |
| 6 | **FastAPI bridge server** (`server.py`) — resolve/chat/status/memory endpointlari | Interfeys real backend'ga ulandi |
| 7 | **Web interfeys ulanishi** — `web/backend.ts` + store `handleSend` real chat, offline'da mock fallback, Settings'da backend URL | UI endi lokal LLM bilan suhbatlashadi |
| 8 | **Benchmark harness** (`benchmark.py`) — 12 task, sifat+tezlik o'lchovi, JSON hisobot | Takrorlanuvchan o'lchov tizimi |
| 9 | **Xotira yangi yozilganda darhol indekslanadi** (BM25 rebuild) | In-session RAG zudlik bilan ishlaydi |

### 3.2 Keyingi qadamlar (tavsiya etiladi) 🔜

| # | Harakat | Kutilgan effekt |
|---|---|---|
| 10 | Brick bankni kengaytirish: `filter`, `map`, `regex`, `read_file`, `http_get`, `pandas` API'lari (~100 brick) | Ko'proq sodda task deterministik (ms) |
| 11 | Ollama KEEP_ALIVE uzaytirish (5m → 30m) + `num_ctx` oshirish | Takroriy LLM so'rovlar 2-3x tez |
| 12 | `sentence-transformers` + FAISS o'rnatish (opsional) | Semantik sinonim qidiruv, RAG aniqligi |
| 13 | Deterministik yo'lda ham RAG: recall'dan olingan so'zlar bilan brick lookup | Ko'p tilli sinonimlar deterministik hal qilinadi |
| 14 | LLM javoblarini session cache (query → output) | Bir xil so'rovlar 0 ms |
| 15 | Streaming chat (SSE) interfeysga | Tokenlar kelishi bilan ko'rsatish |
| 16 | AutoDream konsolidatsiyasini session oxirida avtomatik | L1 → L2 o'tishi kuchayadi |

---

## 4. O'lchov metodikasi

Har bir o'zgarishdan keyin:
```bash
cd Igris_brain
python benchmark.py --no-llm --out reports/benchmark_no_llm.json
python benchmark.py --out reports/benchmark_llm.json
```
- **Sifat** = marker moslik ulushi (0..1) + pass_threshold
- **Tezlik** = duration_ms + tokens/sec
- **Gibrid foyda** = deterministik tezlik x ko'p sodda task + LLM sifat x murakkab task

Maqsad: **sodda ≥ 95% pass @ <50ms**, **murakkab ≥ 90% pass @ <4s** (7B lokal uchun).
