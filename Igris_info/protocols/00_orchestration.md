# Protokol P00 — BOSHQARUV (Orchestration) — IgrisAgent

**Fayl:** `Igris_brain/igris_agent.py` (~6000 satr)
**Sinf:** `IgrisAgent`

---

## 1. Qisqacha mazmun

Har bir foydalanuvchi so'rovini boshqaradi:

- `resolve()` — deterministik brick → healing → LLM fallback (RAG recall bilan)
- `chat()` — to'liq yo'l: turbo → llm+tools → offline/degraded graceful degradation
- `chat_stream()` — jonli oqim: turbo buffered → real token stream → tool stream
- Pipeline (PIPELINE_SPECS), RAG, compliance, retry, CAG/MAG integratsiyasi

## 2. Bajarilgan holat (2026-09-12 audit)

✅ **Ishlayapti** — 3 ta jonli bug bu sessiyada tuzatildi:

| Bug | Belgisi | Tuzatish |
|---|---|---|
| `llm_failed` UnboundLocalError (qator ~2000) | Offline rejimda (LLM yo'q) `chat()` HAR chaqiruvda crash | `llm_failed = False` endi `llm_available()` blokidan OLDIN ishga tushiriladi |
| Junk guard eskirgan | `_retry_generate` "I could not produce an answer" deydi, `_cacheable_out` faqat "could not generate"ni bilardi → junk RAG/CAG'ga yozilardi | Guard ro'yxati kengaytirildi (5 marker) |
| Fallback matn kontrakti buzilgan | `test_chat_stream_turbo_junk_not_written_to_memory` olmayapti edi | Fallback matn kanonik "I could not generate a response..." ga qaytarildi |
| `extract_code` shartli chaqiruv | `resolve()` fallback'da fence qoldiqlari structure_check'ga xom kirardi | Endi HAR DOIM chaqiriladi (oddiy matn uchun zararsiz passthrough) |

Test natijasi: `test_turbo_consistency` 6/6 ✅, `test_intelligence` 41/41 ✅ (avval 6 failed).

## 3. Takliflar (qolgan zaifliklar)

- 🔴 God-file: 6000 satr — modullarga ajratish (web_strategy, quick_paths alohida fayl bo'lishi mumkin edi, lekin hozir hammasi bitta faylda)
- 🟡 `chat_stream` tool yo'lidagi repair-before-write naqshini barcha yo'llarga bir xil helper orqali qilish (4 joyda takrorlangan)
- 🟡 Graceful degradation cooldown (60s..600s) qiymatlarini config'ga chiqarish
- ⚪ `resolve()` deterministik yo'lida ham `structure_check` sinovi (hozir faqat LLM yo'lda)
