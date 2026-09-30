# Igris_info/ — Protokollar, Holat, Hisobotlar, Takliflar

Bu papka **Igris tizimining barcha boshqaruv protokollarini**, ularning **hozirgi holatini**, **qilingan/qilinadigan ishlarni**, **protokollar maqsadlarini** va **user/AI coder takliflarini** ochiq formatda (markdown + JSON) saqlaydi.

Ushbu papka AI coderlar ham tushunib foydalanishi, user ham o'zi tekshirib borishi mumkin bo'lgan holda shakllantirilgan.

> **So'nggi yangilanish: 2026-09-13** — D1 (API validatsiya), T2 (mtime-cache), A4 (web grounding), A1-2 (run-verification) bajarildi; hujjatlar sinxronlandi.

---

## 📁 Papka tuzilishi (real, mavjud fayllar)

```
Igris_info/
├── README.md                          # 🌐 umumiy: nima, qanday ishlatish
├── protocol_manifest.json             # 📋 protokollar manifesti (holat, muammolar, reja) — koddan tekshirilgan
├── protocols/                         # 📁 har bir protokol — ochiq markdown (13 ta)
│   ├── 00_orchestration.md            # IgrisAgent (resolve/chat/stream, pipeline, graceful degradation) + 3 bug tuzatish tarixi
│   ├── 01_execution.md                # AgentExecutor (plan→act→observe→correct + quality gate)
│   ├── 02_task_management.md          # task_supervisor + composition + todo_integration
│   ├── 03_safety_and_policy.md        # harm_filter + safety + corrigibility + tool deny-lists
│   ├── 04_web_strategy.md             # _web_strategy + BUTTON_SAFETY_TIERS + BLOCKED/OBSTRUCTED
│   ├── 05_svg_assurance.md            # svg_validator + svg_quality_report + art MCP
│   ├── 06_hooks_and_events.md         # hooks + DEFAULT_BUS + watchdog (eng puxta)
│   ├── 07_cag_and_mag.md              # cag.py + mag.py (kesh + sessiya konteksti)
│   ├── 08_memory_control.md           # memory_bridge + L1/L2/RAG + fail-guard
│   ├── 09_tool_and_mcp.md             # tools/ + registry + mcp_bridge (8 MCP server)
│   ├── 10_requirements.md             # RequirementExtractor (til/format/intent)
│   ├── 11_intelligence.md             # IntelligenceCore + SelfEvaluator signallari
│   ├── 12_quick_paths.md              # math/weather tez yo'llar (igris_agent ICHIDA — alohida fayl emas!)
│   └── 13_memory_fayllari.md          # Igris_Memory/ fayllari (L1/L2/snapshots)
├── actions/                           # 📁 igris ustida qilingan/qilinadigan ishlar
│   ├── action_history.md              # 5 sessiya tarixi (08-07 → 09-12), nima qilingani
│   ├── action_templates.md            # 8 vazifa shabloni: so'rov → protokol → test
│   └── audit_extracts.md              # audit V3/V4 + problems + temp fayllar ekstraktlari
├── state/                             # 📁 hozirgi holat hisobotlari
│   ├── current_state_report.md        # ⭐ 3 kategoriya: bajarilgan / user takliflari / hozirgi holat
│   ├── health_matrix.md               # 13 protokol health + AI coder boshlash tartibi
│   └── self_check.md                  # 10 tekshiruv buyrug'i (user o'zi ko'rishi uchun)
├── purposes/
│   └── protocol_purposes.md           # qaysi vazifa → qaysi protokol; protokol "o'lsa" nima buziladi
└── todo_user/
    └── user_takliflari.md             # ⭐ 3 kategoriya: bajarilgan / bajarilishi kerak / hozirgi holat
```

---

## 🔍 Qanday ishlatish kerak

### AI coderlar uchun

1. `protocol_manifest.json` — har protokolning qisqacha ma'lumoti, **real fayl joylashuvi**, holati, reja
2. `protocols/*.md` — mazmun + bajarilgan holat + takliflar
3. `state/health_matrix.md` — qayerdan boshlash (T1 ✅ → D1 ✅ → A1 ✅ → S5)
4. `actions/action_templates.md` — vazifa turi → qaysi protokol → qaysi test
5. `todo_user/user_takliflari.md` — navbatdagi ishlar ro'yxati

### User (inson) uchun

1. `state/current_state_report.md` — **hozirgi holat** 3 kategoriyada
2. `state/self_check.md` — **o'zi tekshirish** uchun 10 buyruq
3. `todo_user/user_takliflari.md` — nima bajarildi, nima navbatda
4. `purposes/protocol_purposes.md` — har protokol nimaga kerak ("o'lsa nima buziladi")

---

## 📋 Protsess

1. **Yaratish**: yangi protokol/action → mos papkada `.md`, so'ng `protocol_manifest.json` yangilash
2. **Tekshirish**: user yoki AI coder `state/self_check.md` orqali
3. **Takliflar**: yangi taklif `todo_user/user_takliflari.md` ga (kategoriya + ustuvorlik bilan)
4. **Holat**: har asosiy o'zgarishdan keyin `state/current_state_report.md` + `health_matrix.md` + `actions/action_history.md` yangilanadi

## 📝 Format

Har bir `protocols/*.md` 3 qismdan iborat:

1. **Qisqacha mazmun** — nima qiladi, qaysi fayl(lar)da (REAL joylashuv — manifest yolg'on yo'l yozmagan holatda)
2. **Bajarilgan holat** — qaysi testlar o'tadi, so'nggi tekshiruv sanasi
3. **Takliflar** — muammolar, yaxshilash yo'nalishlari, ustuvorlik

---

## 🧩 Boshqa ma'lumotlar

- **Protokollar**: 13 ta (P00_orchestration → P13_memory_fayllari)
- **O'rtacha sog'liq**: ~92% (2026-09-13 holati) — barcha asosiy oqimlar jonli
- **Manba auditi**: `Igris_brain` importlari + 160+ regressiya test (2026-09-13: D1 32, T2 10, A4 21, A1-2 13 yangi testlar shu jumladan)

*Ushbu papka orqali AI coderlar va user Igris tizimining barcha protokollarini, holatini, hisobotlarini va takliflarini o'rganishi va tekshirishi mumkin.*
