---
name: memory-engine
description: Use when remembering or recalling project knowledge, decisions, patterns, or session context via igris MemoryEngine. Use for remember/recall/forget/cognify/improve operations.
---

# Memory Engine (igris.core.memory2)

Unified memory system combining typed entries (QA/Trace/Feedback/Memo/Pattern/Decision), session cache with background sync, auto-routing recall (session → store), and progressive context loading with token budgets.

## API

```python
from igris.core.memory2 import MemoryEngine
me = MemoryEngine(project_root / ".igris" / "memory2")

# Store
me.remember("text fact", tags=["tag1", "tag2"])
me.remember("context", question="Q?", answer="A!", session_id="chat_1")

# Recall
r = await me.recall("query")     # returns RecallResult with entries + source
for entry in r.entries:
    print(entry.type, entry)

# Distill (add L1/L2/L3 levels)
me.cognify(entry_id)

# Decision cache (never re-think same question)
dec = me.get_or_decide("Which DB?", lambda: "SQLite", reasoning="zero config")
assert dec.answer == "SQLite"

# Context for LLM (token-budget aware)
ctx = me.build_context("current task", top_k=10)

# Session
me.close_session("chat_1")       # syncs to permanent store

# Stats
me.stats()  # {"total": N, "by_type": {...}, "by_priority": {...}}
```

## Entry types

| Type | Class | Use case |
|------|-------|----------|
| `qa` | QAEntry | Question + answer pairs |
| `trace` | TraceEntry | Tool call traces |
| `feedback` | FeedbackEntry | Quality scores on answers |
| `memo` | MemoEntry | General notes with L1/L2/L3 levels |
| `pattern` | PatternEntry | Reusable code patterns |
| `decision` | DecisionEntry | Architecture decisions (immutable once cached) |

## Configuration

Storage: `.igris/memory2/` directory (auto-created). JSON files, zero external dependencies.
