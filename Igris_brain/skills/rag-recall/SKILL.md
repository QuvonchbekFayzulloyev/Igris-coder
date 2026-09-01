---
name: rag-recall
description: >-
  Xotiradan (Igris_Memory — L1 runtime, L2 persistent, L4 retrieval) ma'lumot
  chaqirish metodikasi. Har qanday savol/taskga javob berishdan OLDIN
  xotiradan mos bilimni izlang: avvalgi yechimlar, faktlar, pattern'lar,
  qoidalar, xatolar. Bu RAG (Retrieval-Augmented Generation) — agent javobni
  faqat kontekstdan emas, to'plangan bilimdan quradi. Trigger: "avvalgisi qanday
  edi", "shu haqda nimadir bor edi", "xotiradan top", "recall", "eslab qol",
  yangi vazifa boshlanganda, kod yozishdan oldin, shunga o'xshash muammo
  avval hal qilingan bo'lishi mumkin bo'lgan hollarda. Igris'da bu
  MemoryBridge.recall / /api/memory/search orqali bajariladi.
---

# RAG Recall — xotiradan bilim chaqirish

## Nega kerak

Igris har bir yechimni, xatoni va faktni Igris_Memory'da saqlaydi (L1
runtime + L2 persistent + BM25/FAISS retrieval indeksi). Bu bilimdan
foydalanmaslik — har safar noldan boshlash, oldingi yechimlarni takror
qilish yoki xuddi shu xatoni qayta qilish demakdir. RAG-recall agentga
"to'plangan tajriba"dan javob qurish imkonini beradi.

## Tartib

1. **Qidirish (recall)** — javob berishdan / kod yozishdan / reja tuzishdan
   OLDIN xotiradan qidiring: `agent.memory.recall(query, top_k=3)` yoki
   HTTP `/api/memory/search {query, top_k}`.
   Query'ni task/savol so'zlari bilan tuzing (qisqa, aniq).
2. **Baholash** — qaytarilgan kontekst mosmi? (mavzu, til, maqsad).
   Mos bo'lsa — javobda foydalaning va manbani ayting
   (masalan `[l2:solution-memory]`).
3. **Boyitish** — recalled kontekstni LLM prompt'iga qo'shing
   (Igris buni avtomatik qiladi — `run_native` va `chat` system'ga
   "Relevant recalled knowledge" sifatida qo'shiladi).
4. **Yangi bilim yozish (remember)** — vazifa tugagach, yangi yechimni
   xotiraga yozing (`memory.remember` / `on_resolve`) — keyingi safar
   shu bilim ham recall bo'ladi.

## Qachon albatta recall qilish kerak

- Foydalanuvchi "avvalgisi", "shu haqida", "kecha", "o'sha yechim" deganida.
- Yangi task boshlanganda (har doim tekshirish arzon: BM25 <10ms).
- Bug tuzatishda: "bu xato avval ham uchragandir?"
- Xuddi shu loyihada boshqa joyda o'xshash kod borligi shubhali bo'lsa.

## Igris'da texnik qo'llanishi

```python
# kod darajasida (agent ichida)
ctx, hits = agent.memory.recall(task, top_k=3, max_chars=1200)
if hits:
    system += "\n\nRelevant recalled knowledge (use only if useful):\n" + ctx

# HTTP (frontend / tashqi chaqiruv)
# POST /api/memory/search {"query": "...", "top_k": 5}
```

## Anti-patterns

- Xotiradan qidirmasdan javob berish ("men bilmayman" deyish o'rniga).
- Recalled kontekstni ko'r-ko'rona nusxalash — baholashsiz ishlatish.
- Mos kelmagan xotirani majburlab qo'llash (rekall arzon, lekin noto'g'ri
  xotira javobni buzadi — shubhali bo'lsa e'tiborsiz qoldiring).
- Yangi bilimni xotiraga yozmaslik (RAG faqat yozilgan bilimdan foydalanadi).
