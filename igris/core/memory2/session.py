"""
Session memory: fast LRU cache with optional background sync to permanent store.

Inspired by cognee's session_manager (fast cache + graph sync) but
lightweight: LRU dict with max size, auto-syncs to MemoryStore on close/flush.

Pattern:
  1. remember("text", session_id="chat_1") -> writes to session cache
  2. recall("query", session_id="chat_1") -> searches session first, then store
  3. session ends -> sync to MemoryStore (or background every N writes)
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from .entries import QAEntry, TraceEntry, FeedbackEntry, make_id
from .store import MemoryStore


class SessionMemory:
    def __init__(self, store: MemoryStore, max_size: int = 200, auto_sync_every: int = 10):
        self._store = store
        self._max_size = max_size
        self._auto_sync_every = auto_sync_every
        self._sessions: dict[str, OrderedDict[str, Any]] = {}
        self._write_count: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def remember_qa(self, question: str, answer: str, context: str = "", session_id: str = "", tags: list[str] | None = None) -> str:
        entry = QAEntry(
            id=make_id("qa"),
            question=question,
            answer=answer,
            context=context,
            created_at=time.time(),
            last_accessed=time.time(),
            tags=tags or [],
        )
        self._put(session_id, entry)
        return entry.id

    def remember_trace(self, tool_name: str, status: str, params: dict | None = None, result: str = "", session_id: str = "") -> str:
        entry = TraceEntry(
            id=make_id("trc"),
            tool_name=tool_name,
            status=status,
            params=params or {},
            result=result,
            created_at=time.time(),
        )
        self._put(session_id, entry)
        return entry.id

    def remember_feedback(self, target_id: str, score: int, text: str = "", session_id: str = "") -> str:
        entry = FeedbackEntry(
            id=make_id("fb"),
            target_id=target_id,
            score=score,
            text=text,
            created_at=time.time(),
        )
        self._put(session_id, entry)
        return entry.id

    def remember_memo(self, topic: str, content: str, session_id: str = "", tags: list[str] | None = None) -> str:
        from .entries import MemoEntry
        entry = MemoEntry(
            id=make_id("mem"),
            topic=topic,
            content=content,
            created_at=time.time(),
            tags=tags or [],
        )
        self._put(session_id, entry)
        return entry.id

    # ------------------------------------------------------------------
    # Read (session-scoped)
    # ------------------------------------------------------------------

    def recall(self, query: str, session_id: str = "", top_k: int = 5) -> list[Any]:
        if session_id not in self._sessions:
            return []
        cache = self._sessions[session_id]
        scored: list[tuple[float, Any]] = []
        query_lower = query.lower()
        for eid, entry in cache.items():
            text = self._searchable(entry).lower()
            score = text.count(query_lower) * 1.0
            if hasattr(entry, "question") and query_lower in entry.question.lower():
                score += 3.0
            if hasattr(entry, "topic") and query_lower in entry.topic.lower():
                score += 3.0
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:top_k]]

    def recent(self, session_id: str = "", limit: int = 10) -> list[Any]:
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id].values())[-limit:]

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def flush(self, session_id: str) -> int:
        """Sync all entries for a session to permanent store. Returns count."""
        if session_id not in self._sessions:
            return 0
        cache = self._sessions.pop(session_id)
        self._write_count.pop(session_id, None)
        for entry in cache.values():
            self._store.put(entry)
        return len(cache)

    def close_session(self, session_id: str) -> int:
        """Alias for flush."""
        return self.flush(session_id)

    def active_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _put(self, session_id: str, entry: Any) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = OrderedDict()
        cache = self._sessions[session_id]
        cache[entry.id] = entry
        if len(cache) > self._max_size:
            cache.popitem(last=False)
        self._write_count[session_id] = self._write_count.get(session_id, 0) + 1
        if self._write_count[session_id] >= self._auto_sync_every:
            self._sync_batch(session_id)

    def _sync_batch(self, session_id: str) -> None:
        if session_id not in self._sessions:
            return
        for eid, entry in list(self._sessions[session_id].items()):
            self._store.put(entry)
        self._write_count[session_id] = 0

    def _searchable(self, entry: Any) -> str:
        return " ".join(str(getattr(entry, f, "")) for f in ("question", "answer", "topic", "content", "description", "tool_name", "text"))
