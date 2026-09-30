# Protokol P03 — XAVFSIZLIK VA SIYOSAT (Safety & Policy)

**Fayllar:** `Igris_brain/safety.py`, `Igris_brain/core/intelligence/harm_filter.py`, `Igris_brain/core/intelligence/user_model.py` (corrigibility)

---

## 1. Qisqacha mazmun

- **HarmFilter 2.10**: aniq zarar chegarasi (jismoniy/huquqiy/boshqa odamlarga qarshi) — buyruq rad etiladi, sabab tushuntiriladi, LLM'ga yo'l qo'yilmaydi, xotiraga yozilmaydi
- **safety.py** (`has_suspicious`): prompt-injection naqshlarini aniqlash ("ignore previous", "system:" kabi)
- **Corrigibility policy**: avtonomiya NOL — agent o'z system promptini / o'z maqsadini o'zgartirmaydi
- **Tool darajasida**: `shell_tools.py` DENY_PATTERNS (rm -rf /, sudo, shutdown...), `workspace.py` realpath sandbox, `python_tools.py` xavfli chaqiruvlar deny-list

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_intelligence.py::TestHarmFilter` 2026-09-12 da ✅.

Tarixiy tuzatishlar (11-avgust sessiyasi, `problems_to_fix.md`):
- N1: PoisoningProtection `recall()`/`remember()`'ga ulandi
- N2: RAG recall konteksti `has_suspicious()` bilan tozalanadi
- N3: 3 qatlam output-guard — `web_fetch` → `safety.py`; `browser_get_text`/`web_ai_*` → `web-ai-bridge/server/src/safety.js`; `mcp_bridge.call_tool` → barcha MCP chiqishi
- Dp5/Dp6: run_command deny-patterns + realpath sandbox

## 3. Takliflar

- 🟡 Dp4: `python_exec` to'liq sandbox (resource limits, network off) hali yo'q
- 🟡 Injection naqshlar ro'yxati statik — LLM-asosiy classifier qo'shish mumkin
- ⚪ Harm-filter qarorlari telemetry'da alohida ko'rinmaydi
- ⚪ Multilingual injection (o'zbekcha "avvalgi ko'rsatmalarni unut") naqshlari tekshirilishi kerak
