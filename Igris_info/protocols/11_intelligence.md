# Protokol P11 — INTELLEKT (IntelligenceCore + 12 modul)

**Fayllar:** `Igris_brain/core/intelligence/` — `orchestrator.py` (IntelligenceCore), `logic.py`, `self_eval.py`, `user_model.py`, `tone_detect.py`, `language.py`, `spatial.py`, `creative.py`, `naturalist.py`, `music.py`, `harm_filter.py`; `core/knowledge_system.py`, `core/brick_system.py`

---

## 1. Qisqacha mazmun

**IntelligenceCore** barcha modullarni birlashtiradi:

| Modul | Vazifa |
|---|---|
| `adapt_system` | til/ohang/domain/CoT bo'yicha system prompt moslash |
| `reasoning_suffix` | CoT yo'naltirish |
| `observe` | foydalanuvchi profil (user_model) |
| `screen` | harm-filter 2.10 — zararli so'rovni aniqlash |
| `self_eval` | **SelfEvaluator (2.7)** — har javobga ishonch kalibratsiyasi: engine/status/verified/resolver_score/avg_logprob/grounding signallari |
| `creative` | multi-temperature variantlar + eng yaxshisini tanlash |
| `quick_math` | safe_math deterministik (LogicLayer) |
| weather | quick_weather deterministik yo'l |
| `spatial` / `naturalist` | loyiha strukturasi + muhit taqsimoti |
| `music` | musiqa so'rovini aniqlash + yo'naltirish |
| fail-guard | bo'sh/xato javoblar xotiraga yo'q |

**SelfEvaluator signallari** (A2 tuzatishi):
- engine/status bazasi, `verified` (repaired −0.10, fail −0.25), `resolver_score` (0.35·rs scale), `avg_logprob` (0.15·(2p−1), ixtiyoriy `--logprobs` rejim)
- **`grounding` (A4, 2026-09-13)**: web manba tekshiruvi signali — `grounded` +0.10, `ungrounded` −0.15, `partial` neytral, `None` (web yo'q) = signal yo'q. `web_verify.verify_answer` deterministik hisoblaydi (LLM yo'q); agent `_with_self_eval` ichida chaqiriladi, natija `data["web_grounding"]` metrikasida ham ko'rinadi
- `evaluate()` javobda BIR MARTA chaqiriladi (`_self_eval_for` kesh) — memory == javob confidence

## 2. Bajarilgan holat

✅ **Ishlayapti** — 2026-09-12: `test_intelligence.py` 41/41 ✅ (TestSelfEval 17, boshqa sinflar 19, sweep 33,600 kombinatsiya bounds testi shu jumladan). Bu sessiyada 4 ta TestSelfEval failure tuzatildi (P00 dagi extract_code tuzatishi orqali).

✅ **grounding signali qo'shildi (2026-09-13)**: `SelfEvaluator.evaluate(grounding=...)` + `IntelligenceCore.evaluate` passthrough (backwards-compatible — eski chaqiruvlar None bilan ishlaydi). Test: `test_web_verify.py::TestSelfEvaluatorGrounding` ✅

## 3. Takliflar

- 🟡 T5: `creative_variants` 3 temperature → parallel emas (3x sekin); asyncio + CAG kerak
- 🟡 `avg_logprob` faqat OpenAI-mos endpoint'da — Ollama native /api/chat qaytarmaydi (hujjatlashtirilgan)
- ⚪ Self-eval kalibratsiyasi statik og'irliklar — real natijalar bo'yicha auto-tune kelajakda
- ⚪ user_model (observe) profili UI'da ko'rsatilmaydi
