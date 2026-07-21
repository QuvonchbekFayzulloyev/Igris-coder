"""
igris.core.cia.lifecycle
--------------------------
Memory Lifecycle Manager — CIA Level 1-4.

Every memory entry has:
  - TTL: auto-archive after N days of no access
  - Access tracking: frequently used stays, rarely used goes
  - Priority: P0 never archived, P6 archived first
  - Status flow: ACTIVE → ARCHIVED → DELETED

Rules:
  P0: never archived, never deleted (current task)
  P1: archived after 90 days no access
  P2: archived after 60 days no access
  P3: archived after 30 days no access
  P4: archived after 14 days no access
  P5: archived after 7 days no access
  P6: archived after 3 days no access

  Archived entries deleted after 90 days (all priorities).
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import CIAStore, MemoryEntry, MemoryPriority, MemoryStatus

if TYPE_CHECKING:
    pass

TTL_ARCHIVE: dict[MemoryPriority, float] = {
    MemoryPriority.P0_CURRENT: 86400 * 365 * 10,  # never (10 years)
    MemoryPriority.P1_API: 86400 * 90,
    MemoryPriority.P2_ARCHITECTURE: 86400 * 60,
    MemoryPriority.P3_COMPONENT: 86400 * 30,
    MemoryPriority.P4_RESEARCH: 86400 * 14,
    MemoryPriority.P5_REFERENCE: 86400 * 7,
    MemoryPriority.P6_HISTORICAL: 86400 * 3,
}

ARCHIVE_DELETE_AFTER = 86400 * 90  # 90 days


class LifecycleManager:
    """Manages memory entry lifecycle: ACTIVE → ARCHIVED → DELETED."""

    def __init__(self, store: CIAStore):
        self.store = store

    def run_cycle(self) -> dict[str, int]:
        """Run one full lifecycle cycle. Returns counts of actions taken."""
        now = time.time()
        archived = 0
        deleted = 0
        touched = 0

        for entry in self.store._entries.values():
            priority_ttl = TTL_ARCHIVE.get(entry.priority, 86400 * 14)

            if entry.status == MemoryStatus.ACTIVE:
                if now - entry.last_accessed > priority_ttl and entry.access_count < 2:
                    entry.status = MemoryStatus.ARCHIVED
                    self.store._save_entry(entry)
                    archived += 1

            elif entry.status == MemoryStatus.ARCHIVED:
                if now - entry.last_accessed > ARCHIVE_DELETE_AFTER:
                    self.store.delete_entry(entry.id)
                    deleted += 1
                elif entry.access_count > 5:
                    entry.status = MemoryStatus.ACTIVE
                    self.store._save_entry(entry)
                    touched += 1

        return {"archived": archived, "deleted": deleted, "reactivated": touched}

    def touch(self, entry_id: str) -> None:
        """Record access to an entry, keeping it alive."""
        entry = self.store.get_entry(entry_id)
        if entry:
            entry.touch()
            if entry.status == MemoryStatus.ARCHIVED:
                entry.status = MemoryStatus.ACTIVE
            self.store._save_entry(entry)

    def should_load(self, entry: MemoryEntry) -> bool:
        """Check if an entry is worth loading based on recency."""
        if entry.status != MemoryStatus.ACTIVE:
            return False
        if entry.priority == MemoryPriority.P0_CURRENT:
            return True
        if entry.is_expired:
            return False
        return entry.access_score > 0.1

    def get_ttl_days(self, priority: MemoryPriority) -> int:
        return round(TTL_ARCHIVE.get(priority, 86400 * 14) / 86400)
