---
name: mag-memory
description: >-
  MAG (Memory-Augmented Generation) — javobni faqat yangi kontekstdan emas,
  XOTIRA qatlamlaridan (L1 runtime + L2 persistent + session) to'plangan
  kontekst asosida qurish metodikasi. RAG — aniq qidiruv; MAG — agentning
  sessiya va uzoq muddatli xotirasini uzluksiz kontekstga aylantirish:
  avvalgi suhbatlar, qarorlar, task-tarixi va "joriy holat" yig'iladi va
  generatsiyaga uzatiladi. Trigger: davomiy suhbat, "shuni davom ettir",
  avvalgi qarorlarga tayanuvchi vazifalar, sessiya konteksti muhim bo'lgan
  har qanday ish. Igris'da MemoryBridge (L1 short-turn + L2 solution-memory)
  va session start/end shu ishni bajaradi.
---

# MAG Memory — xotira qatlamlaridan generatsiya

## Kontseptsiya

- **L1 (runtime)** — joriy sessiyaning qisqa muddatli xotirasi: short-turn,
  task-memory, decision-log, observation. "Hozirgi suhbatda nima bo'ldi".
- **L2 (persistent)** — uzoq muddatli xotira: solution-memory, facts,
  patterns. "Avval nimalar yechilgan, qanday qoidalar to'plangan".
- **MAG** — ikkalasini birlashtirib, LLM'ga boyitilgan kontekst beradi.

## Tartib

1. **Sessiyani oching** (agar yo'q bo'lsa) — `memory.start_session(id)`.
   Agent har bir vazifani sessiya ichida ishlaydi.
2. **Kontekstni yig'ing** — javob/ish boshlashdan oldin:
   - L1: `memory.recall(query)` → so'nggi tegishli yozuvlar
   - L2: `manager.api.remember(...)` natijalar / `manager.search(query)`
   - Session: `L1 - Session.md`, `L1 - Short Turn.md` holati
3. **Generatsiya** — yig'ilgan kontekstni system/prompt'ga qo'shing:
   `"Relevant recalled knowledge (use only if useful):\n" + ctx`.
4. **Yodlab qo'ying** — javobdan so'ng `memory.on_resolve(query, result)`:
   yechim L2 solution-memory'ga, qisqa qism L1 short-turn'ga yoziladi.
5. **Sessiyani yakunlang** — `memory.end_session(summary)` — konsolidatsiya
   (AutoDream) L1 → L2 o'tkazadi, eski short-turn arxivlanadi.

## MAG vs RAG

| | RAG | MAG |
|---|---|---|
| Manba | Qidiruv indeksi (BM25/FAISS) | L1+L2 xotira qatlamlari + sessiya |
| Maqsad | Aniq bilim topish | Uzluksiz kontekst qurish |
| Qachon | Yangi savolga bilim kerak | Davomiy ish, qarorlar zanjiri |

Ikkalasi birga ishlaydi: MAG kontekstni qurib beradi, RAG unga aniq
faktlarni topib beradi.

## Igris'da qo'llanishi

- `IgrisAgent.chat()` — har safar `memory.recall()` → system'ga kontekst →
  javob → `memory.on_resolve()` (avtomatik).
- `AgentExecutor.run_native()` — task uchun recall kontekst qo'shiladi,
  tugagach `_remember()` yozadi.
- Server: `/api/session/start`, `/api/session/end`, `/api/memory/status`.

## Anti-patterns

- Session'ni ochmasdan/yopmasdan ishlash — L1 yozuvlari yo'qoladi.
- Kontekstni yig'masdan javob berish (MAG'ni o'tkazib yuborish).
- Eski xotirani "hozirgi holat" deb qabul qilish — L1 har doim yangiroq.
- End_session'da summary bermaslik — konsolidatsiya sifatini pasaytiradi.
