# Protokol P05 — SVG KAFOLATI (SVG Assurance)

**Fayllar:** `Igris_brain/svg_validator.py`, `Igris_brain/svg_quality_report.py`; MCP: `mcp_servers/art_server.py` (12 PNG + 19 SVG predmet), `art_svg.py`

---

## 1. Qisqacha mazmun

Chizma sifat tekshiruvi — gradient/soya/fon/markazlash/margin/chegara/ranglar/xilma-xillik/uslub/silliq chiziqlar.

- **style_comment bilan yondashuv**: `flat` — gradient/soya yo'q (to'g'ri), `realistic` — gradient+soya majburiy, `cartoon` — qalin kontur (stroke-width 4-6)
- **Fail-guard**: buzilgan SVG javoblari RAG'ga yo'l qo'ymaydi
- **redraw_note**: chizish so'rovlarida avvalgi xatolar takrorlanmaydi
- `_is_draw_request` + `_fake_draw_claim` — soxta "Chizdim" javoblari aniqlanadi (model rasmini chizmasdan "chizdim" deyishi bloklanadi)

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_svg_validator.py` 34 test (2026-09-12 da to'plamda bor), `test_chat_draw_e2e.py` E2E.

Manifestdagi "83%" bahosi eskirgan — so'nggi tuzatishlardan (fail-guard + fake-claim + style_comment) keyin funksionallik yuqori.

## 3. Takliflar

- 🔴 Dp7: predmetlar kutubxonasi tor (12 PNG + 19 SVG) — generativ yondashuv (PIL/rastr) kerak
- 🟡 Rastr tahrir, image→code, OCR/tahlil yo'q
- 🟡 Murakkab kompozitsiyalar (bir necha obyekt, fon sahnasi) validator'dan o'tmaydi
- ⚪ SVG animation (SMIL/CSS) tekshiruvi yo'q
