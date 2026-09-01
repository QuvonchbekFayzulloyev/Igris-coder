# CODER AGENT MEMORY — QURILMA QO'LLANMASI

> **Asos:** `CODER_AGENT_MEMORY_FULL.md` — barcha tafsilotlar o'sha dokumentda
> **Target:** 1.5B gacha LLM
> **Stack:** Python 3.10+, FAISS, SQLite, JSON

---

## FOLDER STRUCTURE

```
memory/
+-- runtime/           # L1 — ishchi xotira (18 tur)
|   +-- 01-short-turn.jsonl
|   +-- 02-session.jsonl
|   +-- ... har bir L1 type uchun alohida fayl
+-- persistent/        # L2 — doimiy xotira (24 tur)
|   +-- 01-long-term.jsonl
|   +-- 02-experience.jsonl
|   +-- ... har bir L2 type uchun alohida fayl
+-- config/            # L3 — sozlamalar
|   +-- user.json
|   +-- agent.json
|   +-- mcp.json
|   +-- model.json
+-- retrieval/         # L4 — qidiruv tizimi
|   +-- index/         # FAISS/BM25 indekslari
|   +-- cache/         # Session cache (LRU)
+-- agent_api.py       # Agent-writable API
+-- autodream.py       # Background consolidation
+-- hooks.py           # Hook system
+-- sync.py            # Multi-agent sync
+-- time_travel.py     # Snapshot/rollback
```

---

## BUILD ORDER (4 Faza)

### FAZA 1: L1 Runtime (18 type)

**Maqsad:** Agent ishlayotganda kerak bo'ladigan barcha vaqtinchalik xotira turlarini yaratish.

**Bajarish:**
1. `memory/runtime/` papkasini yaratish
2. Har bir L1 type uchun JSON schema (CODER_AGENT_MEMORY_FULL.md §3.2 dan) bo'yicha `.jsonl` fayl yaratish:

| # | Type | Fayl | Chastota |
|----|------|------|----------|
| 01 | short-turn | `01-short-turn.jsonl` | har bir tur oxiri |
| 02 | session | `02-session.jsonl` | har bir step |
| 03 | active-context | `03-active-context.jsonl` | joriy task |
| 04 | working | `04-working.jsonl` | reasoning davomida |
| 05 | task | `05-task.jsonl` | task boshida |
| 06 | execution | `06-execution.jsonl` | har bir tool call |
| 07 | observation | `07-observation.jsonl` | natija kelganda |
| 08 | planning | `08-planning.jsonl` | rejalashtirishda |
| 09 | attention | `09-attention.jsonl` | agent tanlovida |
| 10 | scratchpad | `10-scratchpad.jsonl` | vaqtinchalik |
| 11 | temporary-knowledge | `11-temp-knowledge.jsonl` | session davomida |
| 12 | runtime-cache | `12-cache.jsonl` | TTL asosida |
| 13 | prompt-buffer | `13-prompt-buffer.jsonl` | prompt qurishda |
| 14 | decision-log | `14-decision-log.jsonl` | har bir qaror |
| 15 | reflection | `15-reflection.jsonl` | session oxiri |
| 16 | rollback-points | `16-rollback.jsonl` | checkpointda |
| 17 | streaming-buffer | `17-streaming.jsonl` | streaming vaqtida |
| 18 | context-compressor | `18-compressor.jsonl` | context limitda |

3. **Validation:** JSON schema'dagi barcha required fieldlar to'ldirilganligini tekshirish
4. **1.5B optimizatsiya:** Har bir entry 500 token dan oshmasligi, `summary` field'i majburiy

---

### FAZA 2: L2 Persistent (24 type)

**Maqsad:** Agent sessiyalararo eslab qolishi kerak bo'lgan barcha doimiy ma'lumotlarni saqlash.

**Bajarish:**
1. `memory/persistent/` papkasini yaratish
2. Har bir L2 type uchun JSON schema (CODER_AGENT_MEMORY_FULL.md §4.2 dan) bo'yicha `.jsonl` fayl:

| # | Type | Fayl | Konsolidatsiya |
|----|------|------|---------------|
| 01 | long-term | `01-long-term.jsonl` | session oxiri |
| 02 | experience | `02-experience.jsonl` | har session |
| 03 | knowledge | `03-knowledge.jsonl` | yangi bilim |
| 04 | project | `04-project.jsonl` | project boshida |
| 05 | skill | `05-skill.jsonl` | pattern aniqlanganda |
| 06 | pattern | `06-pattern.jsonl` | takrorlanishda |
| 07 | solution | `07-solution.jsonl` | muammo yechilganda |
| 08 | research | `08-research.jsonl` | tadqiqotda |
| 09 | documentation | `09-docs.jsonl` | dokumentatsiyada |
| 10 | example | `10-example.jsonl` | namuna kerakda |
| 11 | error | `11-error.jsonl` | xatolikda |
| 12 | verification | `12-verify.jsonl` | test natijasi |
| 13 | workflow | `13-workflow.jsonl` | workflow yakunida |
| 14 | archive | `14-archive.jsonl` | eski ma'lumot |
| 15 | fact | `15-fact.jsonl` | fakt aniqlanganda |
| 16 | rule | `16-rule.jsonl` | qoida kerakda |
| 17 | code-map | `17-codemap.jsonl` | kod tahlilida |
| 18 | user-model | `18-usermodel.jsonl` | foydalanuvchi profili |
| 19 | test | `19-test.jsonl` | test yozishda |
| 20 | deployment | `20-deploy.jsonl` | deploy vaqtida |
| 21 | performance | `21-perf.jsonl` | monitoring |
| 22 | security | `22-security.jsonl` | xavfsizlik |
| 23 | dependency | `23-dep.jsonl` | dependency tree |
| 24 | integration | `24-integration.jsonl` | API integratsiya |

3. **Duplicate detection:** Har bir yangi entry `id` yoki `content` hash bo'yicha tekshirish
4. **Consolidation:** Session oxirida L1 → L2 merge (AutoDream §9.2)

---

### FAZA 3: L3 Config + L4 Retrieval

#### L3 Configuration (4 type)

`memory/config/` papkasida 4 ta fayl (CODER_AGENT_MEMORY_FULL.md §5.2):

| Fayl | Maqsad |
|------|--------|
| `user.json` | User profile, settings, limits |
| `agent.json` | Agent behavior, personality, tools |
| `mcp.json` | MCP server list, auth, rate limits |
| `model.json` | Model params, context window, cost |

#### L4 Retrieval Pipeline (CODER_AGENT_MEMORY_FULL.md §6.2)

```python
# 1. Vector index (FAISS)
retrieval/vector_index.py  — embedding + cosine similarity

# 2. Keyword index (BM25)
retrieval/keyword_index.py  — BM25/BM25F, exact match

# 3. Hybrid search (RRF fusion)
retrieval/hybrid_search.py  — BM25 + Vector + Graph + Meta (4-kanal)

# 4. Query rewriter
retrieval/query_rewriter.py  — rule-based, 1.5B uchun engil

# 5. Session cache (LRU)
retrieval/session_cache.py  — key-value, TTL, max 50 entry
```

**Ishga tushirish:**
```
# 1. FAISS indeks yaratish
python -c "from retrieval.vector_index import build_index; build_index()"

# 2. BM25 indeks yaratish
python -c "from retrieval.keyword_index import build_bm25; build_bm25()"

# 3. Test qidiruv
python -c "from retrieval.hybrid_search import search; print(search('query'))"
```

---

### FAZA 4: Advanced Features

CODER_AGENT_MEMORY_FULL.md §9 dagi 7 ta Python class ni implementatsiya qilish:

| # | Class | Fayl | § |
|---|-------|------|---|
| 1 | `MemoryAPI` | `agent_api.py` | §9.1 |
| 2 | `AutoDream` | `autodream.py` | §9.2 |
| 3 | `AdvancedHybridSearch` | — | §9.3 |
| 4 | `PoisoningProtection` | — | §9.4 |
| 5 | `HookSystem` | `hooks.py` | §9.6 |
| 6 | `MultiAgentSync` | `sync.py` | §9.7 |
| 7 | `TimeTravel` | `time_travel.py` | §9.8 |

**Implementatsiya tartibi:**
1. `MemoryAPI` — avval buni, chunki agent tizim bilan shu orqali gaplashadi
2. `HookSystem` — keyin, monitoring va triggerlar uchun
3. `AutoDream` — L1→L2 konsolidatsiya
4. `PoisoningProtection` — xavfsizlik
5. `AdvancedHybridSearch` — RRF fusion
6. `MultiAgentSync` — multi-agent
7. `TimeTravel` — snapshot/rollback

---

## TEZKOR ISHGA TUSHIRISH (5 daqiqa)

```bash
# 1. Loyihani yaratish
mkdir -p memory/{runtime,persistent,config,retrieval/{index,cache}}

# 2. L1 fayllarni yaratish (18 ta .jsonl)
for i in $(seq -w 1 18); do touch "memory/runtime/$i-type.jsonl"; done

# 3. L2 fayllarni yaratish (24 ta .jsonl)
for i in $(seq -w 1 24); do touch "memory/persistent/$i-type.jsonl"; done

# 4. Config fayllar
touch memory/config/{user,agent,mcp,model}.json

# 5. Python virtual env
python -m venv .venv
source .venv/bin/activate  # yoki .venv\Scripts\activate (Windows)

# 6. Install dependencies
pip install faiss-cpu numpy scikit-learn

# 7. Agent API handler yozish
cp agent_api.py memory/agent_api.py

# 8. Test
python -c "from memory.agent_api import MemoryAPI; api = MemoryAPI(); print('OK')"
```

---

## 1.5B MODEL UCHUN 10 QOIDA

CODER_AGENT_MEMORY_FULL.md §8.3 dan:

1. **Filter** — contextga faqat eng muhim 3-5 entry
2. **JSON format** — minimal field, `summary` mandatory
3. **Qisqa context** — har bir entry ≤ 50 token
4. **File-based** — DB emas, JSON fayl (zero overhead)
5. **Retrieval** — faqat BM25 (FAISS juda og'ir)
6. **Consolidation** — L1→L2 AutoDream 5-pass
7. **Cache** — LRU, max 50 entry, TTL = 30 min
8. **Logging** — faqat error/warning, debug emas
9. **Test** — har bir memory type alohida test
10. **Update** — append-only, never rewrite

---

## TEKSHIRISH LISTI

| Step | Nima tekshiriladi | Status |
|------|-------------------|--------|
| 1 | L1: 18 ta .jsonl fayl bor | ☐ |
| 2 | L2: 24 ta .jsonl fayl bor | ☐ |
| 3 | L3: 4 ta config fayl bor | ☐ |
| 4 | FAISS indeks ishlayapti | ☐ |
| 5 | BM25 indeks ishlayapti | ☐ |
| 6 | Hybrid search natija qaytaradi | ☐ |
| 7 | MemoryAPI.Read ishlayapti | ☐ |
| 8 | MemoryAPI.Write ishlayapti | ☐ |
| 9 | AutoDream merge qiladi | ☐ |
| 10 | Poisoning detection ishlayapti | ☐ |
| 11 | Hook system trigger qiladi | ☐ |
| 12 | Time-travel snapshot oladi | ☐ |
| 13 | 1.5B optimizatsiya yoqilgan | ☐ |

---

## MANBA

Barcha JSON schema, kod misollari va batafsil tushuntirishlar:
→ `CODER_AGENT_MEMORY_FULL.md`
