"""
igris.core.memory2
-------------------
Unified memory/knowledge engine combining:
  - cognee's typed entries (QA/Trace/Feedback) + remember/recall/forget API
  - CIA's distillation (L1/L2/L3 levels), priority lifecycle, decision cache
  - New: session memory, auto-routing recall, progressive context builder

Zero external dependencies: file-based JSON storage with in-memory keyword index.
Optional: SQLite upgrade for larger datasets (add later).

Usage:
    from igris.core.memory2 import MemoryEngine

    me = MemoryEngine(project_root="/path")
    me.remember("User prefers dark mode", session_id="chat_1")
    r = await me.recall("dark mode preferences")
    me.forget(r.entries[0].id)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .context import ContextBuilder
from .entries import (
    DecisionEntry,
    FeedbackEntry,
    KnowledgeLevel,
    MemoEntry,
    MemoryEntry,
    MemoryPriority,
    PatternEntry,
    QAEntry,
    TraceEntry,
    make_id,
)
from .recall import RecallEngine, RecallResult
from .session import SessionMemory
from .store import MemoryStore


class MemoryEngine:
    def __init__(self, store_dir: str | Path, model_size: str = "7b"):
        self._store = MemoryStore(store_dir)
        self._session = SessionMemory(self._store)
        self._recall = RecallEngine(self._store, self._session)
        self._context = ContextBuilder(self._store, model_size)

    # ------------------------------------------------------------------
    # Public API: remember / recall / forget / cognify / improve
    # ------------------------------------------------------------------

    def remember(
        self,
        text_or_entry: str | MemoryEntry,
        session_id: str = "",
        tags: list[str] | None = None,
        question: str = "",
        answer: str = "",
    ) -> str:
        if isinstance(text_or_entry, str):
            if question and answer:
                entry = QAEntry(
                    id=make_id("qa"),
                    question=question,
                    answer=answer,
                    context=text_or_entry,
                    created_at=time.time(),
                    tags=tags or [],
                )
            else:
                entry = MemoEntry(
                    id=make_id("mem"),
                    topic=text_or_entry[:80],
                    content=text_or_entry,
                    created_at=time.time(),
                    tags=tags or [],
                )
            if session_id:
                self._session._put(session_id, entry)
            else:
                self._store.put(entry)
            return entry.id
        eid = text_or_entry.id or make_id(text_or_entry.type)
        text_or_entry.id = eid
        if session_id:
            self._session._put(session_id, text_or_entry)
        else:
            self._store.put(text_or_entry)
        return eid

    async def recall(
        self,
        query: str,
        session_id: str = "",
        top_k: int = 5,
    ) -> RecallResult:
        return await self._recall.recall(query, session_id=session_id, top_k=top_k)

    def forget(self, entry_id: str) -> None:
        self._store.delete(entry_id)

    def cognify(self, entry_id: str) -> str | None:
        """Add L1/L2 distilled levels to a memo entry."""
        entry = self._store.get(entry_id)
        if entry is None or entry.type != "memo":
            return None
        text = entry.content
        lines = text.strip().split("\n")
        entry.level1 = lines[0][:80] if lines else text[:80]
        entry.level2 = "\n".join(lines[:5])[:300] if len(lines) > 1 else text[:300]
        entry.level3 = text[:5000]
        self._store.put(entry)
        return entry.level1

    def improve(self, target_id: str, score: int, text: str = "", session_id: str = "") -> str:
        return self._session.remember_feedback(target_id, score, text, session_id=session_id)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def close_session(self, session_id: str) -> int:
        return self._session.close_session(session_id)

    def flush_session(self, session_id: str) -> int:
        return self._session.flush(session_id)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def get_or_decide(self, question: str, compute_fn, reasoning: str = "") -> DecisionEntry:
        existing = self._store.find_decision(question)
        if existing:
            return existing
        answer = compute_fn() if callable(compute_fn) else compute_fn
        entry = DecisionEntry(
            id=make_id("dec"),
            question=question,
            answer=str(answer),
            reasoning=reasoning or "",
        )
        self._store.put(entry)
        return entry

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def build_context(self, task: str, top_k: int = 10) -> str:
        return self._context.build(task, top_k=top_k)

    def context_summary(self) -> str:
        return self._context.summary()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return self._store.stats()
