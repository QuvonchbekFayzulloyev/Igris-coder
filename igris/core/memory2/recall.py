"""
Auto-routing recall: searches session -> store -> knowledge in priority order.

Inspired by cognee's auto-routing (session first, then graph, then fallthrough).
Returns enriched context with source annotations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entries import MemoryEntry, MemoryPriority
from .session import SessionMemory
from .store import MemoryStore


@dataclass
class RecallResult:
    entries: list[MemoryEntry]
    source: str           # session | store | knowledge | hybrid
    query: str = ""
    total_found: int = 0
    took_ms: float = 0.0


class RecallEngine:
    def __init__(self, store: MemoryStore, session: SessionMemory):
        self._store = store
        self._session = session

    async def recall(
        self,
        query: str,
        session_id: str = "",
        top_k: int = 5,
        include_session: bool = True,
        include_store: bool = True,
    ) -> RecallResult:
        import time
        t0 = time.time()
        seen: set[str] = set()
        all_entries: list[MemoryEntry] = []

        # 1. Session memory (fastest, most recent)
        if include_session and session_id:
            for entry in self._session.recall(query, session_id=session_id, top_k=top_k):
                if entry.id not in seen:
                    seen.add(entry.id)
                    all_entries.append(entry)

        # 2. Permanent store (keyword search)
        if include_store:
            for score, entry in self._store.search(query, top_k=top_k):
                if entry.id not in seen:
                    seen.add(entry.id)
                    all_entries.append(entry)

        took = (time.time() - t0) * 1000
        source = "session" if all_entries and all(e.id in (self._session._sessions.get(session_id, {}) if session_id else {}) for e in all_entries) else "store"
        if include_session and include_store and all_entries:
            source = "hybrid"

        return RecallResult(
            entries=all_entries[:top_k],
            source=source,
            query=query,
            total_found=len(all_entries),
            took_ms=round(took, 1),
        )

    async def recall_decisions(self, question: str) -> MemoryEntry | None:
        return self._store.find_decision(question)

    def recent_decisions(self, limit: int = 10) -> list[MemoryEntry]:
        all_decisions = [e for e in self._store._entries.values() if e.type == "decision"]
        all_decisions.sort(key=lambda e: getattr(e, "last_accessed", 0), reverse=True)
        return all_decisions[:limit]


