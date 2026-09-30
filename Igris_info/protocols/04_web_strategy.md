# Protokol P04 — VEB STRATEGIYA (Web Strategy)

**Fayllar:** ✅ S5 (2026-09-14) — `Igris_brain/web_strategy.py` (yagona manba: `needs_web`, `web_strategy`, `detect_web_tech`, `WEB_TOOLS_GUIDE`, `WEB_TOOL_HINTS`, qaror qoidalari); `igris_agent.py` delegatsiya + `_log_web_strategy()`, `web_strategy_report.py`; MCP: `web-ai-bridge/`

---

## 1. Qisqacha mazmun

Veb ehtiyojini aniqlash va eng arzon vosita chizig'ini tanlash:

1. To'g'ridan-to'g'ri javob (web kerak emas)
2. `web_fetch` (statik sahifa)
3. Web AI subagent (`ask_web_ai`)
4. Real brauzer (`web_ai_bridge__browser_*` — CDP orqali haqiqiy Chrome, mr.wtin profili)

Qo'shimcha:
- **BUTTON_SAFETY_TIERS**: 1 avtomatik (routine/reversible), 2 avtomatik oltin (cookie bannerlar), 3 so'rov bilan tasdiqlash (Buy Now / Place Order / Delete Account...)
- Login kerak bo'lsa → `ask_web_ai`
- Deep research polling: `web_ai_start_research` + `web_ai_check_research`
- Download tekshiruvi: `browser_list_downloads`
- BLOCKED (CAPTCHA) / OBSTRUCTED (cookie banner) alohida holatlar
- Natija tahlili: HTTP status + Content-Type
- HOTFIX: so'rovda sayt/URL/brauzer ehtiyoji bo'lsa — chatda ham avtomatik browser tool'lari ochiladi

## 2. Bajarilgan holat

✅ **Ishlayapti** — `test_web_strategy.py` 39 test mavjud; importlar sog'lom (2026-09-12).

✅ **A4 BAJARILDI (2026-09-13)** — web javob manba tekshiruvi:
- `web_verify.py` (yangi modul): web tool natijalari (`web_fetch`, `browser_get_text`, `ask_web_ai`, `web_ai_*`) manba-indeksiga yig'iladi (`_chat_with_tools` capture; art/MCP rasm serverlari KIRMAYDI)
- Yakuniy javob deterministik grounding tekshiruviga o'tadi: fakt-fragment ajratish (raqamli gaplar to'liq, kod/URL o'tkaziladi) + token-bigram qamrov — QO'SHIMCHA LLM CHAQIRUVI YO'Q
- Verdict: `grounded` (+0.10 ishonch) / `partial` (neytral) / `ungrounded` (−0.15) — `SelfEvaluator.grounding` parametri orqali
- `data["web_grounding"]` metrikaga yoziladi (coverage, verdict, eng zaif fragmentlar); rasm javoblarida tekshiruv yo'q
- Test: `test_web_verify.py` 21/21 ✅

## 3. Takliflar

- ✅ ~~A4: manba tekshiruvi~~ BAJARILDI (2026-09-13). Kengaytma: **2-manba tasdiqlash** — bir manbadagi fakt ikkinchi mustaqil manbada ham bo'lsa `grounded+` (yuqori ishonch)
- 🟡 CAPTCHA'da user'ga aniq ko'rsatma + qo'lda davom ettirish oqimi yo'q
- ⚪ `web_strategy_report.py` hisobotlari UI'da ko'rsatilmaydi
- ⚪ Sahifa o'zgarishlarini kuzatish (watch/diff) — kelajakdagi imkoniyat
