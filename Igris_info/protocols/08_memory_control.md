# Protokol P08 — XOTIRA BOSHQARUVI (Memory Control)

**Fayllar:** `Igris_brain/memory_bridge.py`, xotira modullari (Igris_Memory yonida); fayl tuzilishi: **P13_memory_fayllari** ga qarang

---

## 1. Qisqacha mazmun

Xotira qatlamlari: **L1 short-turn** (runtime) + **L2 persistent** (solution-memory) + **RAG recall** + CAG + MAG.

- Faqat sifatli javoblar xotiraga yoziladi (fail-guard: `verified='fail'` HECH QAYERGA yozilmaydi — 7 ta joyda guard)
- **Dedup**: bir xil content bir necha marta yozilmaydi (content-hash / summary+id)
- **Snapshot integrity**: `memory_state.json` == `metadata.json`
- **Cleanup**: eskirgan/bo'sh yozuvlarni tozalash (`/api/session/cleanup`, autodream pass5)
- Recall tozalash: `has_suspicious()` bilan injection naqshli yozuvlar kontekstga kirmaydi
- PoisoningProtection: `recall()` har yozuvni `check_security()` bilan tekshiradi

## 2. Bajarilgan holat

✅ **Ishlayapti** — N1/N2 tuzatishlari (11-avgust) + fail-guard (12-avgust, 20 doimiy test) faol. 2026-09-12: importlar sog'lom, `_cacheable_out` guard kengaytirildi.

## 3. Takliflar

- ✅ **T1 TUZATILDI (2026-09-12)**: RAG keyword index endi **SQLite/FTS5 incremental** (`Igris_Memory/memory/fts5_index.py`) — har `add_document`'da rebuild YO'Q, index diskda saqlanadi (`brain_data/fts_index.db`, restartda qayta qurilmaydi), dedup (content-hash), deferred commit (bulk-load tez), FTS5 yo'q bo'lsa avtomatik BM25 fallback. Search benchmark (3000 doc): FTS5 1.3ms vs BM25 4-9ms — **3-6x tezroq**. `HybridSearch` endi FTS5Index ishlatadi (interfeys drop-in). Test: `test_fts5_index.py` 12/12 ✅. **E2E tasdiqlandi**: haqiqiy MemoryBridge yo'lida FTS5 faol (import tuzatilgan — MemoryBridge faqat ildizni sys.path'ga qo'shardi, paket-ichki modul topilmasdi; endi `HybridSearch._make_keyword_index()` yo'lni o'zi tuzatadi); real recall 3.9–7.5ms (top_k=3)
- ✅ **T2 TUZATILDI (2026-09-13)**: `RetrievalPipeline.load_documents` endi **mtime-cache** bilan ishlaydi — fayl holati (mtime+size) `_file_state`'da saqlanadi; qayta chaqiruvda FAQAT o'zgargan/yangi fayllar o'qiladi va indekslanadi; o'zgargan faylning eski versiyasi yangi `remove_source` API bilan index'dan o'chiriladi (to'liq rebuild YO'Q); o'chirilgan fayllar ham index'dan tozalanadi. Yangi API: `BM25Index.remove_source`, `FTS5Index.remove_source` (incremental DELETE — Windows-path JSON-escape hisobga olindi), `VectorIndex.remove_source`, `HybridSearch.remove_source`; `force=True` — to'liq qayta o'qish. Test: `test_t2_mtime_cache.py` 10 test ✅ (o'zgarmagan fayl qayta o'qilmaydi, o'zgarish/o'chirilish to'g'ri aks etadi)
- 🟡 T3: Vector retrieval amalda ishlamaydi (80MB model, sekin) — kichik hash-embedding yoki tanlab encode
- 🟡 T3: Vector retrieval amalda ishlamaydi (80MB model, sekin) — kichik hash-embedding yoki tanlab encode
- 🟡 N4: retrieval'da dublikat/qarama-qarshi yozuvlar ajratilmaydi
- 🟡 D2: JSONL compaction scheduler yo'q — disk o'sadi
- ⚪ N5: probe/benchmark yozuvlari xotirada qoladi (recall filtrini kengaytirish)
