# Protokol P07 — CAG & MAG (Cache-Augmented / Memory-Augmented Generation)

**Fayllar:** `Igris_brain/cag.py`, `Igris_brain/mag.py`

---

## 1. Qisqacha mazmun

**CAG** (javob keshi):
- O'zgarmas kalit (CHAT_TOOLS_SYSTEM + message) — prompt o'zgarsa kesh buzilmaydi
- Faqat sifatli javoblar keshlanadi (`_cacheable_out` guard + fail-guard)
- Keshlangan javob HAM repair'dan o'tadi (eski/buzilgan yozuv canonical matnga aylanadi)
- CAG hit'da memory yozuvi repair'dan OLDIN qilinadi; memory AYNAN `data["content"]`ni oladi
- TURBO/MAG/lag'ga keshlanmaydi (tool_calls bo'lsa, draw/date savol bo'lsa, offline/xato javob bo'lsa)

**MAG** (sessiya konteksti): L1 + L2 + RAG kontekstini yig'ish.

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_rag_cag_mag_hooks.py` 25 test (put/hit chat+stream, fail-guard CAG-hit variantlari bilan) — 2026-09-12 da importlar va to'plam tasdiqlandi.

Bu sessiyada `_cacheable_out` guard kengaytirildi (5 marker) — junk endi CAG'ga ham, RAG'ga ham yozilmaydi.

## 3. Takliflar

- 🟡 Kesh invalidatsiyasi faqat kalit asosida — model o'zgarganda kesh to'liq tozalanmaydi (model-fingerprint kalitga qo'shilsa yaxshi)
- 🟡 Kesh statistikasi (hit-rate) UI'da ko'rinmaydi
- ⚪ Semantik kesh (o'xshash savolga keshdan javob) — riskli, ehtiyotkorlik bilan
- ⚪ Kesh TTL/sig'im limiti konfiguratsiyasi yo'q
