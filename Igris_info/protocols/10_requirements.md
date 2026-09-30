# Protokol P10 — TALAB AJRATISH (Requirements)

**Fayl:** `Igris_brain/core/requirements.py` — `Requirement`, `RequirementExtractor`

---

## 1. Qisqacha mazmun

So'rovdan talab modelini ajratadi (JSON): **til / format / chuqurlik / cheklovlar / intent**.

- **Intent turlari**: math, weather, draw, web, summarize, code, file, compose_ui
- **CAG kesh**: `req:<message>` kalit bilan keshlangan semantik ekstraksiya
- **LLM path**: `EXTRACT_SYSTEM` prompt bilan; parse: json.loads → `extract_balanced_json` fallback
- **Deterministik fallback**: LLM yo'q/offline/xatolikda kalit-so'z qoidalari (`_MATH_RE`, `_DRAW_WORDS`, `_WEB_WORDS`, `_CODE_WORDS`...) — "hech qachon exception bermaydi"
- `extract_fast()`: chizish/tezkor yo'llar uchun LLM'siz (kechikish yo'q)
- `_is_draw_request` / `_is_date_question` bilan keraksiz chaqiruvlar oldini olinadi
- `req.to_block()` — talab bloki javob promptiga qo'shiladi; `_retry_generate` req-aware

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_requirements.py` 15 test (2026-09-12 da to'plamda, passed).

⚠️ Muhim eslatma (bu sessiyada o'rnatildi): `Requirement.intent` LLM fallback'da `extract_code` chaqiruvini boshqargan edi — bu shart olib tashlandi (P00 ga qarang). Intent endi faqat prompt yo'naltirishda ishlatiladi.

## 3. Takliflar

- 🟡 Deterministik fallback intent'ni so'rov tiliga juda bog'liq (o'zbek/ingliz) — boshqa tillarda zaif
- 🟡 `compose_ui` intent kalitlari ("uy", "ilova", "app") juda umumiy — noto'g'ri mos kelishi mumkin
- ⚪ Req natijasi UI'da ko'rsatilmaydi (user agent nima tushungandek ko'ra olmaydi)
- ⚪ Ko'p qadamli so'rovlar (bir necha obyekt/vazifa bitta message) to'liq ajratilmaydi
