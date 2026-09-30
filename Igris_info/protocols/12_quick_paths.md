# Protokol P12 — TEZ YO'LLAR (Quick Paths: math + weather)

**Joylashuv:** ✅ S5 (2026-09-14) — `Igris_brain/quick_paths.py` (yagona manba: `is_math_request`, `format_math_result`, `quick_weather` — wttr.in+Open-Meteo); `core/intelligence/logic.py` (`safe_math`); `igris_agent.py` metodlari delegatsiya qiladi; `igris_quick.py` — eski nomlar uchun compat fasad.

⚠️ Manifestdagi `quick_math.py` / `quick_weather.py` fayllari MAVJUD EMAS — funksionallik endi `quick_paths.py` modulida (god-file'dan ajratildi, S5 1-qadam).

---

## 1. Qisqacha mazmun

**Math tez yo'l**:
- `safe_math(expr)` — xavfsiz arifmetika (eval emas, AST-asosida)
- `MATH_EXPR_RE` — matematik ifodani matndan topadi
- LLM/brauzer KERAKSIZ — tez + aniq + bepul

**Weather tez yo'l**:
- Open-Meteo (geocoding + forecast) — kalit talab qilmaydi, 2-4 soniya
- Turli joylashuv ifodalariga moslashadi
- " Manba: Open-Meteo (jonli)" — manba ko'rsatiladi

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_intelligence.py::TestLogicQuickMath` ✅ (2026-09-12), `test_agentic_pipeline.py` va `test_real_tasks.py`'da quick_math mock testlari ham bor.

## 3. Takliflar

- ✅ ~~Funksiyalarni alohida `quick_paths.py` moduliga ajratish~~ BAJARILDI (2026-09-14, S5): math+weather moduli 316 satr; agent delegatsiya orqali; ~428 regressiya test ✅
- 🟡 Birlik konvertatsiyalari (℃/℉, km/mil) va qo'shimcha birlik hisoblari quick_math'ga
- ⚪ Valyuta konvertatsiyasi (API kerak) — quick path'ga qo'shish mumkin
- ⚪ Weather'da bir necha kun prognozi formatini user tanlashi
