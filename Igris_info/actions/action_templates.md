# ISH SHABLONLARI (Action Templates)

Qanday vazifa → qaysi protokol ishlaydi → qanday tekshiriladi.

---

## 1. Suhbat savoli (chat-family)

```
So'rov: "qalaysan?", "Nima uchun osmon ko'k?" 
Yo'l:   chat_stream → turbo (oddiy) yoki real token stream
        → _verify_and_repair → CAG put → memory (faqat sifatli)
Protokol: P00 (P07, P08, P11 bilan)
Tekshiruv: test_turbo_consistency.py
```

## 2. Rasm chizish (creator-family)

```
So'rov: "olma chiz"
Yo'l:   _is_draw_request → req extract_fast (LLM'siz) → art MCP draw_*
        → svg_validator (style_comment: flat/realistic/cartoon)
        → fail-guard (buzilgan SVG xotiraga yo'q) → redraw_note
Protokol: P05 (+P00, P10)
Tekshiruv: test_svg_validator.py, test_chat_draw_e2e.py
```

## 3. Kod vazifasi (creator-family)

```
So'rov: "fayl yarat / dastur yoz / xato tuzat"
Yo'l:   executor: plan → act → observe → correct (max_iter=8)
        → quality gate (_verify_deliverable) → corrective pass
        → probe_decisions.score_task (outcome)
Protokol: P01 (+P02, P09)
Tekshiruv: test_executor.py, test_composition.py
```

## 4. Web so'rovi

```
So'rov: "saytni och / maqola top"
Yo'l:   _web_strategy → eng arzon vosita: web_fetch → ask_web_ai → browser
        → BUTTON_SAFETY_TIERS (3-daraja: tasdiq so'raladi)
        → BLOCKED/OBSTRUCTED alohida
Protokol: P04 (+P09, P03 output-guard)
Tekshiruv: test_web_strategy.py
```

## 5. Matematika / Ob-havo (tez yo'llar)

```
So'rov: "12*34+5", "Toshkentda havo"
Yo'l:   quick_math (safe_math) yoki quick_weather (Open-Meteo)
        → deterministik javob, LLM/brauzer KERAKSIZ
Protokol: P12 (+P11 LogicLayer)
Tekshiruv: test_intelligence.py::TestLogicQuickMath
```

## 6. Murakkab ko'p qadamli vazifa

```
So'rov: "butun ilova qur"
Yo'l:   TaskSupervisor: decomposition → DAG → node execution → summarise
        Composition: plan/read/edit/test/review (max_repair=3)
Protokol: P02 (+P01, P09)
Tekshiruv: test_task_supervisor.py, test_composition.py
```

## 7. Server/qulash holati

```
Alomat: backend javob bermaydi
Yo'l:   watchdog (4s poll) → 4 ketma-ket xato → taskkill + restart
        → ~20-30s da tiklanish → UI avtomatik qayta ulanadi
Protokol: P06
Tekshiruv: Igris_brain/logs/watchdog.json, checklist.md §7
```

## 8. Zararli/shubhali so'rov

```
So'rov: injection / zarar buyruq
Yo'l:   harm_filter.screen → rad etish + sabab → LLM'ga yo'q, xotiraga yo'q
        memory recall'da check_security har yozuvni tekshiradi
Protokol: P03 (+P08)
Tekshiruv: test_intelligence.py::TestHarmFilter
```
