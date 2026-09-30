# SELF-CHECK — Qanday tekshirish mumkin

User (inson) yoki AI coder o'zi tekshirishi uchun oddiy buyruqlar.

---

## 1. Backend jonlimi?

```bash
curl http://127.0.0.1:8765/api/status
# {"ok": true, ...} bo'lsa — jonli
```

## 2. Watchdog ishlayaptimi?

```bash
cat Igris_brain/logs/watchdog.json     # running, backend_up, ollama_up, restarts
tail -20 Igris_brain/logs/watchdog.log # qo'riqlash voqealari
```
UI: **Settings → Services → Watchdog (auto-restart)** kartasi.

## 3. Testlar o'tyaptimi?

```bash
cd Igris_brain
python -m pytest test_executor.py test_requirements.py test_svg_validator.py test_turbo_consistency.py test_composition.py -q
# 2026-09-12 holati: 58 passed
```

## 4. MCP serverlar ulanganmi?

```bash
curl http://127.0.0.1:8765/api/agent/mcp
curl http://127.0.0.1:8765/api/tools   # ro'yxatga olingan vositalar
```

## 5. Xotira yozilyaptimi?

```bash
tail -3 Igris_Memory/brain_data/runtime/01-short-turn.jsonl   # L1
tail -3 Igris_Memory/brain_data/persistent/07-solution.jsonl  # L2
# Sana/yozuv yangilanayotgani — fail-guard ishlayotganini ko'rsatadi
```

## 6. Junk xotiraga yozilmayaptimi (2026-09-12 tuzatishi)?

```bash
grep -c "could not" Igris_Memory/brain_data/persistent/07-solution.jsonl
# 0 bo'lishi kerak — junk fallback matnlari xotirada bo'lmasligi shart
```

## 7. Offline chat crash qilmayaptimi (2026-09-12 tuzatishi)?

```bash
cd Igris_brain
python -m pytest test_turbo_consistency.py::TestTurboMemoryConfidenceConsistency::test_chat_offline_no_chat_level_memory_write -q
# PASSED bo'lsa — `llm_failed` bugi tuzatilgan
```

## 8. LLM ishlayaptimi?

```bash
curl http://127.0.0.1:11434/api/tags   # Ollama modellari
# server log: Igris_brain/logs/server.log
```

## 9. Web bridge holati?

```bash
cd web-ai-bridge/server && node e2e-driver.mjs   # E2E smoki
```

## 10. Suhbat tarixi butunmi?

```bash
python -c "import json; [json.loads(l) for l in open('Igris_brain/chat_history.jsonl', encoding='utf-8')]; print('JSONL VALID')"
# Buzilgan qator yo'qligini tekshiradi (round-trip himoyasi)
```

## 11. API himoyasi ishlayaptimi? (D1, 2026-09-13)

```bash
python -m pytest Igris_brain/test_input_validation.py -q
# 32 test: katta body 413, zararli string/path 422, oddiy so'rov o'tadi
```

## 12. RAG tezmi? (T1+T2, 2026-09-12/13)

```bash
python -m pytest Igris_Memory/memory/test_fts5_index.py Igris_Memory/memory/test_t2_mtime_cache.py -q
# FTS5 index + mtime-cache: faqat o'zgargan fayllar qayta indekslanadi
```

## 13. Web javoblar manbaga tayanadimi? (A4, 2026-09-13)

```bash
python -m pytest Igris_brain/test_web_verify.py -q
# 21 test: grounded/ungrounded verdict + SelfEvaluator grounding signali
```

## 14. Agent yozgan kod ishlaydimi? (A1-2, 2026-09-13)

```bash
python -m pytest Igris_brain/test_deliverable_run.py Igris_brain/test_deliverable_syntax.py -q
# 24 test: runtime xatoli gate'dan o'tmaydi, import/deps neytral
```

---

*Agar biror tekshiruv olmayapsa — `state/health_matrix.md` dagi mos protokolga qarang va `todo_user/user_takliflari.md` ga muammolik qo'shing.*
