"""
File-based persistent store with in-memory keyword index.
Zero dependencies -- writes individual JSON files per entry.

Inspired by CIAStore (file-backed, priority, lifecycle) and
cognee's Postgres backend (typed entries, hybrid search).

Fast paths:
  - get_entry_by_id: O(1) dict lookup
  - keyword search: in-memory dict of term->set(ids), updated on write
  - priority+access sorted list: O(n) scan (n=total entries, typically <5000)
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from .entries import (
    MemoryEntry,
    MemoryPriority,
    _SERIALIZABLE_TYPES,
    deserialize,
    serialize,
)


class MemoryStore:
    def __init__(self, store_dir: str | Path):
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._decisions: dict[str, MemoryEntry] = {}
        self._index: dict[str, set[str]] = {}
        self._dirty = False
        self._load_all()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def put(self, entry: MemoryEntry) -> None:
        self._entries[entry.id] = entry
        self._index_entry(entry)
        self._save_one(entry)

    def delete(self, entry_id: str) -> None:
        entry = self._entries.pop(entry_id, None)
        if entry:
            self._unindex_entry(entry)
            p = self._path_for(entry_id)
            if p.exists():
                p.unlink()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, entry_id: str) -> MemoryEntry | None:
        entry = self._entries.get(entry_id)
        if entry:
            entry.touch()
            self._save_one(entry)
        return entry

    def find_decision(self, question: str) -> MemoryEntry | None:
        q = question.lower().strip().rstrip("?").strip()
        for e in self._entries.values():
            if e.type != "decision":
                continue
            eq = e.question.lower().strip().rstrip("?").strip()
            if q in eq or eq in q:
                e.touch()
                self._save_one(e)
                return e
        return None

    def list_by_priority(self, max_entries: int = 50) -> list[MemoryEntry]:
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: (e.priority.value if isinstance(e.priority, MemoryPriority) else 99, -(getattr(e, "access_count", 0))),
        )
        return sorted_entries[:max_entries]

    # ------------------------------------------------------------------
    # Keyword search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[tuple[float, MemoryEntry]]:
        terms = self._tokenize(query)
        if not terms:
            return []
        scores: list[tuple[float, str]] = []
        all_ids = set(self._entries.keys())
        for eid in all_ids:
            score = 0.0
            entry = self._entries[eid]
            text = self._searchable_text(entry)
            text_lower = text.lower()
            for term in terms:
                if term in text_lower:
                    score += 1.0
                    # bonus for title/name matches
                    if hasattr(entry, "question") and term in entry.question.lower():
                        score += 2.0
                    if hasattr(entry, "topic") and term in entry.topic.lower():
                        score += 2.0
                    if hasattr(entry, "name") and term in entry.name.lower():
                        score += 2.0
            # priority bonus: higher priority = higher score
            priority_val = entry.priority.value if isinstance(entry.priority, MemoryPriority) else 5
            score /= (priority_val + 1)
            if score > 0:
                scores.append((score, eid))
        scores.sort(key=lambda x: -x[0])
        return [(s, self._entries[eid]) for s, eid in scores[:top_k] if eid in self._entries]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        for e in self._entries.values():
            counts[e.type] = counts.get(e.type, 0) + 1
            pname = e.priority.name if isinstance(e.priority, MemoryPriority) else "UNKNOWN"
            priority_counts[pname] = priority_counts.get(pname, 0) + 1
        return {"total": len(self._entries), "by_type": counts, "by_priority": priority_counts}

    def count(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        for p in self._dir.glob("*.json"):
            try:
                data = json.loads(p.read_text("utf-8"))
                entry = deserialize(data)
                if entry:
                    self._entries[entry.id] = entry
                    self._index_entry(entry)
            except Exception:
                pass

    def _save_one(self, entry: MemoryEntry) -> None:
        data = serialize(entry)
        p = self._path_for(entry.id)
        p.write_text(json.dumps(data, ensure_ascii=False, default=str), "utf-8")

    def _path_for(self, entry_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", entry_id)
        return self._dir / f"{safe}.json"

    def _tokenize(self, text: str) -> list[str]:
        terms = re.findall(r"[a-z0-9_]{2,}", text.lower())
        return list(set(terms))

    def _searchable_text(self, entry: MemoryEntry) -> str:
        parts = [str(getattr(entry, f, "")) for f in ("question", "answer", "topic", "content", "description", "text", "name", "reasoning")]
        return " ".join(parts) + " " + " ".join(getattr(entry, "tags", []))

    def _index_entry(self, entry: MemoryEntry) -> None:
        text = self._searchable_text(entry)
        for term in self._tokenize(text):
            self._index.setdefault(term, set()).add(entry.id)

    def _unindex_entry(self, entry: MemoryEntry) -> None:
        text = self._searchable_text(entry)
        for term in self._tokenize(text):
            s = self._index.get(term)
            if s:
                s.discard(entry.id)
