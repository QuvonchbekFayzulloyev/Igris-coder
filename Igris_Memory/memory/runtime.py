"""
CODER AGENT MEMORY — L1 Runtime (Ishchi Xotira)
18 tur, session davomida, tez ochiladi.

Storage: In-memory dict + JSONL file (append-only)
Cleanup: TTL based + max entries per type
1.5B: last 3 turns only for short-turn
"""

import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import L1_TYPES


class RuntimeMemory:
    """
    L1 Runtime Memory — session ichidagi vaqtinchalik xotira.
    
    18 ta memory type ni boshqaradi:
    - In-memory: tez o'qish/yozish (deque per type)
    - JSONL: diskga append-only saqlash
    - TTL: avto-tozalash
    """

    def __init__(self, runtime_dir: str = "memory/runtime"):
        self.runtime_dir = runtime_dir
        os.makedirs(runtime_dir, exist_ok=True)

        # In-memory stores (deque per type for bounded size)
        self._stores: dict[str, deque[dict]] = {}
        # Current session metadata
        self.session_id: str = ""
        self.session_start: Optional[str] = None
        self.turn_count: int = 0

        self._init_stores()

    def _init_stores(self):
        """Initialize in-memory deques for each L1 type."""
        for type_name, meta in L1_TYPES.items():
            max_entries = self._max_entries_for_type(type_name)
            self._stores[type_name] = deque(maxlen=max_entries)

    def _max_entries_for_type(self, type_name: str) -> int:
        """Max in-memory entries per type (1.5B optimization)."""
        limits = {
            "short-turn": 5,       # 1.5B: 3 turns only
            "session": 1,
            "active-context": 1,
            "working-memory": 3,
            "task-memory": 3,
            "execution-memory": 10,
            "observation-memory": 10,
            "planning-memory": 3,
            "attention-memory": 1,
            "scratchpad": 5,
            "temporary-knowledge": 20,
            "runtime-cache": 50,
            "prompt-buffer": 5,
            "decision-log": 15,
            "reflection-memory": 5,
            "rollback-points": 10,
            "streaming-buffer": 1,
            "context-compressor": 3,
        }
        return limits.get(type_name, 10)

    def _jsonl_path(self, type_name: str) -> str:
        """Get JSONL file path for a type."""
        meta = L1_TYPES.get(type_name)
        if not meta:
            raise ValueError(f"Unknown L1 type: {type_name}")
        return os.path.join(self.runtime_dir, meta["file"])

    def _append_jsonl(self, type_name: str, entry: dict):
        """Append entry to JSONL file (append-only)."""
        path = self._jsonl_path(type_name)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Non-blocking write

    def _read_jsonl(self, type_name: str, limit: int = 50) -> list[dict]:
        """Read last N entries from JSONL file."""
        path = self._jsonl_path(type_name)
        entries = []
        if not os.path.exists(path):
            return entries
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        except Exception:
            pass
        return entries

    # ============================================================
    # PUBLIC API
    # ============================================================

    def start_session(self, session_id: str) -> dict:
        """Start a new runtime session."""
        self.session_id = session_id
        self.session_start = datetime.now(timezone.utc).isoformat()
        self.turn_count = 0
        self._init_stores()  # Clear in-memory

        entry = {
            "id": f"session-{session_id}",
            "type": "session",
            "status": "active",
            "started_at": self.session_start,
            "updated_at": self.session_start,
            "total_turns": 0,
            "total_tool_calls": 0,
            "total_tokens_used": 0,
            "files_read": [],
            "files_modified": [],
            "errors_encountered": [],
            "summary": f"Session {session_id} started",
        }
        self.write("session", entry)
        return entry

    def end_session(self, summary: str = "") -> dict:
        """End current session and return session entry."""
        session_entries = self._read_jsonl("session", limit=1)
        if session_entries:
            entry = session_entries[-1]
            entry["status"] = "ended"
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            entry["total_turns"] = self.turn_count
            entry["summary"] = summary or entry.get("summary", "")
            self.write("session", entry)
            return entry
        return {}

    def write(self, type_name: str, entry: dict, ttl_seconds: int = 0) -> dict:
        """
        Write an entry to runtime memory.
        
        Args:
            type_name: One of the 18 L1 types
            entry: The memory entry dict
            optional ttl_seconds: Auto-expire after N seconds
        
        Returns:
            The written entry with id and timestamp
        """
        if type_name not in L1_TYPES:
            raise ValueError(f"Unknown L1 type: {type_name}. Valid: {list(L1_TYPES.keys())}")

        # Ensure required fields
        entry.setdefault("type", type_name)
        entry.setdefault("id", f"{type_name}-{self.turn_count}")
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry.setdefault("summary", "")
        if ttl_seconds > 0:
            entry["ttl_seconds"] = ttl_seconds
            entry["expires_at"] = time.time() + ttl_seconds

        # Write to in-memory deque
        store = self._stores.get(type_name)
        if store is not None:
            store.append(entry)

        # Write to JSONL
        self._append_jsonl(type_name, entry)

        return entry

    def read(self, type_name: str, limit: int = 5) -> list[dict]:
        """
        Read entries from runtime memory.
        
        Args:
            type_name: One of the 18 L1 types
            limit: Max entries to return (1.5B: use 3-5)
        
        Returns:
            List of matching entries, newest first
        """
        if type_name not in L1_TYPES:
            return []

        # Check in-memory first (faster)
        store = self._stores.get(type_name)
        if store and len(store) > 0:
            entries = list(store)
            # Filter expired
            now = time.time()
            entries = [
                e for e in entries
                if not e.get("expires_at") or e["expires_at"] > now
            ]
            return entries[-limit:]

        # Fall back to JSONL
        return self._read_jsonl(type_name, limit=limit)

    def read_latest(self, type_name: str) -> Optional[dict]:
        """Read the most recent entry of a type."""
        entries = self.read(type_name, limit=1)
        return entries[0] if entries else None

    def update(self, type_name: str, entry_id: str, updates: dict) -> Optional[dict]:
        """
        Update an existing entry by id.
        Only updates the latest matching entry.
        """
        if type_name not in L1_TYPES:
            return None

        store = self._stores.get(type_name)
        if store:
            for i in range(len(store) - 1, -1, -1):
                if store[i].get("id") == entry_id:
                    store[i].update(updates)
                    store[i]["updated_at"] = datetime.now(timezone.utc).isoformat()
                    return store[i]
        return None

    def increment_turn(self) -> int:
        """Increment turn counter and return current turn number."""
        self.turn_count += 1
        return self.turn_count

    def cleanup_expired(self) -> int:
        """Remove expired entries from all stores. Returns count removed."""
        now = time.time()
        removed = 0
        for type_name, store in self._stores.items():
            before = len(store)
            self._stores[type_name] = deque(
                (e for e in store if not e.get("expires_at") or e["expires_at"] > now),
                maxlen=store.maxlen,
            )
            removed += before - len(self._stores[type_name])
        return removed

    def get_stats(self) -> dict:
        """Get runtime memory statistics."""
        stats = {}
        for type_name, store in self._stores.items():
            stats[type_name] = {
                "in_memory": len(store),
                "max": store.maxlen,
            }
        stats["_meta"] = {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "total_in_memory": sum(len(s) for s in self._stores.values()),
        }
        return stats

    def get_context_summary(self, max_tokens: int = 2000) -> str:
        """
        Get a compact context summary for LLM prompt.
        1.5B optimization: only most relevant 5-10 entries.
        """
        sections = []

        # Active context (highest priority)
        active = self.read_latest("active-context")
        if active:
            sections.append(f"## Active Context\n{active.get('summary', '')[:300]}")

        # Last 3 short-turns (1.5B: 3 turns only)
        turns = self.read("short-turn", limit=3)
        if turns:
            turn_summaries = [t.get("summary", "")[:150] for t in turns]
            sections.append(f"## Recent Turns\n" + "\n".join(f"- {s}" for s in turn_summaries if s))

        # Planning status
        plan = self.read_latest("planning-memory")
        if plan:
            plan_data = plan.get("plan", {})
            sections.append(f"## Plan: {plan_data.get('goal', '')[:200]}")

        # Current task
        task = self.read_latest("task-memory")
        if task:
            sections.append(f"## Task: {task.get('title', '')[:200]}")

        # Decision log (last 3)
        decisions = self.read("decision-log", limit=1)
        if decisions:
            dec_list = decisions[0].get("decisions", [])[-3:]
            if dec_list:
                dec_summary = "; ".join(d.get("title", "")[:80] for d in dec_list)
                sections.append(f"## Recent Decisions: {dec_summary}")

        result = "\n\n".join(sections)
        return result[:max_tokens]

    def clear(self):
        """Clear all in-memory stores (keeps JSONL files)."""
        self._init_stores()
