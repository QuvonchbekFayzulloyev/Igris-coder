"""
CODER AGENT MEMORY — L2 Persistent (Doimiy Xotira)
24 tur, sessiyalararo, JSONL + Markdown format.

Storage: JSONL file (append-only) + duplicate detection
Consolidation: L1 -> L2 at session end
"""

import hashlib
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import L2_TYPES


class PersistentMemory:
    """
    L2 Persistent Memory — sessiyalararo doimiy xotira.
    
    24 ta memory type ni boshqaradi:
    - JSONL: structured storage
    - Duplicate detection: id yoki content hash bo'yicha
    - TTL: 30 kun ishlatilmagan -> archive, 90 kun -> deletion
    """

    def __init__(self, persistent_dir: str = "memory/persistent"):
        self.persistent_dir = persistent_dir
        os.makedirs(persistent_dir, exist_ok=True)

        # In-memory index for fast lookup
        self._index: dict[str, list[dict]] = defaultdict(list)
        # Content hash set for duplicate detection
        self._hashes: dict[str, set[str]] = defaultdict(set)

        self._init_dirs()

    def _init_dirs(self):
        """Create subdirectories for each L2 type."""
        for type_name, meta in L2_TYPES.items():
            type_dir = os.path.join(self.persistent_dir, type_name.replace("-memory", ""))
            os.makedirs(type_dir, exist_ok=True)

    def _jsonl_path(self, type_name: str) -> str:
        """Get JSONL file path for a type."""
        meta = L2_TYPES.get(type_name)
        if not meta:
            raise ValueError(f"Unknown L2 type: {type_name}")
        return os.path.join(self.persistent_dir, meta["file"])

    def _content_hash(self, entry: dict) -> str:
        """Generate a content hash for duplicate detection."""
        content = json.dumps(
            {k: v for k, v in entry.items() if k not in ("id", "timestamp", "updated_at")},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.md5(content.encode()).hexdigest()

    def _append_jsonl(self, type_name: str, entry: dict):
        """Append entry to JSONL file."""
        path = self._jsonl_path(type_name)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _read_jsonl(self, type_name: str, limit: int = 100) -> list[dict]:
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

    def _load_all_jsonl(self, type_name: str) -> list[dict]:
        """Load all entries from JSONL file."""
        return self._read_jsonl(type_name, limit=999999)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def write(
        self,
        type_name: str,
        entry: dict,
        check_duplicate: bool = True,
    ) -> dict:
        """
        Write an entry to persistent memory.
        
        Args:
            type_name: One of the 24 L2 types
            entry: The memory entry dict
            check_duplicate: Skip if duplicate content hash exists
        
        Returns:
            The written entry, or empty dict if duplicate skipped
        """
        if type_name not in L2_TYPES:
            raise ValueError(f"Unknown L2 type: {type_name}")

        # Ensure required fields
        entry.setdefault("type", type_name)
        entry.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        entry.setdefault("summary", "")

        # Duplicate detection
        if check_duplicate:
            content_hash = self._content_hash(entry)
            if content_hash in self._hashes[type_name]:
                return {}  # Skip duplicate
            self._hashes[type_name].add(content_hash)

        # Write to JSONL
        self._append_jsonl(type_name, entry)

        # Update in-memory index
        self._index[type_name].append(entry)

        return entry

    def read(
        self,
        type_name: str,
        limit: int = 10,
        query: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Read entries from persistent memory.
        
        Args:
            type_name: One of the 24 L2 types
            limit: Max entries to return
            query: Optional text filter (searches summary + content)
            tags: Optional tag filter
        
        Returns:
            List of matching entries, newest first
        """
        if type_name not in L2_TYPES:
            return []

        # Load from JSONL if index is empty
        if not self._index[type_name]:
            self._index[type_name] = self._load_all_jsonl(type_name)

        entries = self._index[type_name]

        # Apply filters
        if query:
            query_lower = query.lower()
            entries = [
                e for e in entries
                if query_lower in json.dumps(e, ensure_ascii=False).lower()
            ]

        if tags:
            entries = [
                e for e in entries
                if any(t in json.dumps(e, ensure_ascii=False).lower() for t in tags)
            ]

        return entries[-limit:]

    def search(self, query: str, types: Optional[list[str]] = None, limit: int = 10) -> list[dict]:
        """
        Search across multiple L2 types.
        
        Args:
            query: Search text
            types: Optional list of types to search (default: all)
            limit: Max results
        
        Returns:
            List of matching entries with type info
        """
        search_types = types or list(L2_TYPES.keys())
        results = []

        for type_name in search_types:
            if type_name not in L2_TYPES:
                continue
            entries = self.read(type_name, limit=5, query=query)
            for entry in entries:
                results.append({"type": type_name, "entry": entry})

        # Sort by relevance (entries with more matches first)
        results.sort(
            key=lambda r: json.dumps(r["entry"], ensure_ascii=False).lower().count(query.lower()),
            reverse=True,
        )
        return results[:limit]

    def read_latest(self, type_name: str) -> Optional[dict]:
        """Read the most recent entry of a type."""
        entries = self.read(type_name, limit=1)
        return entries[0] if entries else None

    def update(self, type_name: str, entry_id: str, updates: dict) -> Optional[dict]:
        """Update an existing entry by id."""
        if type_name not in L2_TYPES:
            return None

        entries = self.read(type_name, limit=999999)
        for entry in entries:
            if entry.get("id") == entry_id:
                entry.update(updates)
                entry["updated_at"] = datetime.now(timezone.utc).isoformat()
                # Rewrite JSONL (append updated version)
                self._append_jsonl(type_name, entry)
                return entry
        return None

    def delete(self, type_name: str, entry_id: str) -> bool:
        """Soft-delete an entry (mark as deleted)."""
        return self.update(type_name, entry_id, {"deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}) is not None

    def count(self, type_name: str) -> int:
        """Count entries of a type."""
        if type_name not in L2_TYPES:
            return 0
        if not self._index[type_name]:
            self._index[type_name] = self._load_all_jsonl(type_name)
        return len(self._index[type_name])

    def get_stats(self) -> dict:
        """Get persistent memory statistics."""
        stats = {}
        total = 0
        for type_name in L2_TYPES:
            c = self.count(type_name)
            stats[type_name] = {"count": c}
            total += c
        stats["_meta"] = {"total_entries": total, "total_types": len(L2_TYPES)}
        return stats

    def consolidate_from_runtime(self, runtime_entries: dict[str, list[dict]]) -> int:
        """
        Consolidate L1 runtime entries into L2 persistent.
        Called at session end (AutoDream).
        
        Args:
            runtime_entries: Dict of {type_name: [entries]} from L1
        
        Returns:
            Number of entries consolidated
        """
        consolidated = 0

        # Map L1 types to L2 types
        l1_to_l2_map = {
            "session": "experience",
            "task-memory": "solution-memory",
            "decision-log": "experience",
            "observation-memory": "knowledge",
            "planning-memory": "workflow-memory",
            "reflection-memory": "experience",
            "execution-memory": "experience",
            "short-turn": "experience",
        }

        for l1_type, entries in runtime_entries.items():
            l2_type = l1_to_l2_map.get(l1_type, "long-term")
            if l2_type not in L2_TYPES:
                continue

            for entry in entries:
                # Create L2 entry from L1 entry
                l2_entry = {
                    "id": f"from-{entry.get('id', 'unknown')}",
                    "type": l2_type,
                    "source": f"l1:{l1_type}",
                    "summary": entry.get("summary", "")[:500],
                    "data": entry,
                    "consolidated_at": datetime.now(timezone.utc).isoformat(),
                }
                if self.write(l2_type, l2_entry, check_duplicate=True):
                    consolidated += 1

        return consolidated

    def cleanup_stale(self, archive_days: int = 30, delete_days: int = 90) -> dict:
        """
        Move stale entries to archive, delete very old ones.
        
        Args:
            archive_days: Move to archive after N days without access
            delete_days: Delete after N days in archive
        
        Returns:
            Stats of cleanup operations
        """
        now = time.time()
        stats = {"archived": 0, "deleted": 0}

        for type_name in L2_TYPES:
            entries = self.read(type_name, limit=999999)
            for entry in entries:
                updated = entry.get("updated_at", "")
                if not updated:
                    continue

                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    age_days = (now - dt.timestamp()) / 86400
                except Exception:
                    continue

                if type_name == "archive" and age_days > delete_days:
                    # Delete very old archive entries
                    self.delete(type_name, entry.get("id", ""))
                    stats["deleted"] += 1
                elif type_name != "archive" and age_days > archive_days:
                    # Move to archive
                    archive_entry = {
                        "id": f"archived-{entry.get('id', 'unknown')}",
                        "type": "archive",
                        "source_type": type_name,
                        "original_id": entry.get("id"),
                        "summary": entry.get("summary", "")[:500],
                        "archived_at": datetime.now(timezone.utc).isoformat(),
                        "reason": f"Stale: {age_days:.0f} days old",
                    }
                    self.write("archive", archive_entry, check_duplicate=False)
                    self.delete(type_name, entry.get("id", ""))
                    stats["archived"] += 1

        return stats

    def clear_type(self, type_name: str):
        """Clear all entries of a specific type."""
        if type_name in L2_TYPES:
            self._index[type_name] = []
            self._hashes[type_name] = set()
            path = self._jsonl_path(type_name)
            if os.path.exists(path):
                os.remove(path)
