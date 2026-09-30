# Protokol P06 — HOOKS VA VOQEALAR (Hooks & Events)

**Fayllar:** `Igris_brain/hooks.py`, `Igris_brain/watchdog.py`; ishlatuvchilar: `executor.py` (DEFAULT_BUS), `server.py`

---

## 1. Qisqacha mazmun

- **DEFAULT_BUS**: `on_plan`, `on_step_start`, `on_step_done`, `on_task_done` — executor hayotiy sikli voqealari
- `_default_hooks` ixtiyoriy (hooks bo'lmasa None — crash yo'q)
- **Watchdog** (16 funksiya, checklist.md'da to'liq): har 4s backend (8765) + Ollama (11434) sog'lig'ini tekshiradi; qulasa avtomatik qayta ishga tushiradi (~20-30s); rate-limit (10 daq/5), boot-grace 45s, marker handshake (UI restart'iga aralashmaydi), single-instance qulf, atomik holat fayli (`logs/watchdog.json`)
- LLM crashda avtomatik retry (cooldown bilan); memory snapshotlar avtomatik yaratiladi
- Hooks + progress_cb birgalikda jonli stage ko'rsatadi (UI pipeline: Plan→Read→Edit→Test→Review)

## 2. Bajarilgan holat

✅ **To'liq ishlayapti** — eng puxta o'rganilgan protokol (checklist.md: 8 kategoriya, jonli E2E test: 54.2s tiklanish o'lchangan). UI karta: Settings→Services'da "Degradations" kartasi faol (2026-09-12).

## 3. Takliflar

- ✅ **S3 QISM TUZATILDI (2026-09-12): Silent-degradation registry** (`degradation.py`) — komponent jim zaif rejimga o'tsa (MCP ulanmasa → no-tools, FTS5 import bo'lmasa → BM25, CAG/MAG → disabled), `mark()` bilan registryga yoziladi → `/api/system/services` javobida `degradations` + `degradations_active` ko'rinadi. Registry: thread-safe, dedup (component+fallback → count+1), atomik disk-fayl (`logs/degradations.json`), hech qachon exception tashlamaydi. Test: `test_degradation.py` 10/10 ✅
- ✅ **UI karta (2026-09-12)**: Settings→Services'da "Degradations (silent fallback)" kartasi — faol degradatsiyada qizil ramka + pulse + `active` badge, har yozuv: component → fallback → reason (×count), `↺ clear` tugmasi (`/api/system/degradations/clear`, `clearDegradations()` backend.ts'da). MCP kartasida ham `degraded` badge. `DegradationEntry` tipi backend.ts'da. TS typecheck ✅ (0 xato)
- 🟡 S3 davomi: confidence pasayishi auto-alert (registry faqat import/fallback xatolarini oladi)
- ⚪ Watchdog holati faqat Settings→Services'da — alohida dashboard sahifasi foydali bo'lardi
- ⚪ Hook voqealarini tarixda saqlash (replay/debug uchun)
