"""
CODER AGENT MEMORY — Multi-Agent Sync
Ko'p agentlar o'rtasida xotira sinxronizatsiyasi.

Features:
- Memory sync between agents
- Conflict resolution
- Consistency checks
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional


class MultiAgentSync:
    """
    Multi-Agent Memory Sync tizimi.
    
    Ko'p agentlar bir xil memory ni ishlatganda:
    - Lock mechanism (yozish vaqtida)
    - Conflict resolution (bir xil entry ga turli yozuvlar)
    - Consistency check (data integrity)
    """

    def __init__(self, sync_dir: str = "memory/sync"):
        self.sync_dir = sync_dir
        os.makedirs(sync_dir, exist_ok=True)
        self._locks: dict[str, dict] = {}
        self._sync_log: list[dict] = []

    def acquire_lock(self, agent_id: str, resource: str, timeout: int = 30) -> bool:
        """
        Acquire a lock on a memory resource.
        
        Args:
            agent_id: Unique agent identifier
            resource: Resource to lock (e.g., "l2:experience")
            timeout: Lock timeout in seconds
        
        Returns:
            True if lock acquired
        """
        now = time.time()
        lock_key = f"{resource}"

        # Check existing lock
        if lock_key in self._locks:
            existing = self._locks[lock_key]
            if existing["agent_id"] != agent_id:
                # Check if lock expired
                if now - existing["acquired_at"] < existing["timeout"]:
                    return False  # Lock held by another agent
            # Same agent re-locking or expired - allow

        self._locks[lock_key] = {
            "agent_id": agent_id,
            "resource": resource,
            "acquired_at": now,
            "timeout": timeout,
        }

        self._log("lock_acquired", {"agent_id": agent_id, "resource": resource})
        return True

    def release_lock(self, agent_id: str, resource: str) -> bool:
        """Release a lock."""
        lock_key = f"{resource}"
        if lock_key in self._locks:
            if self._locks[lock_key]["agent_id"] == agent_id:
                del self._locks[lock_key]
                self._log("lock_released", {"agent_id": agent_id, "resource": resource})
                return True
        return False

    def sync_memories(
        self,
        source_agent: str,
        target_agents: list[str],
        entries: dict[str, list[dict]],
        conflict_strategy: str = "latest_wins",
    ) -> dict:
        """
        Sync memories between agents.
        
        Args:
            source_agent: Agent providing the memories
            target_agents: Agents to sync to
            entries: Dict of {type_name: [entries]}
            conflict_strategy: How to resolve conflicts (latest_wins, merge, source_wins)
        
        Returns:
            Sync result stats
        """
        result = {
            "source": source_agent,
            "targets": target_agents,
            "synced": 0,
            "conflicts": 0,
            "skipped": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for target in target_agents:
            sync_file = os.path.join(self.sync_dir, f"sync_{source_agent}_to_{target}.json")

            # Load existing sync data
            existing = {}
            if os.path.exists(sync_file):
                try:
                    with open(sync_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}

            # Merge entries
            for type_name, entry_list in entries.items():
                if type_name not in existing:
                    existing[type_name] = []

                existing_ids = {e.get("id") for e in existing[type_name]}

                for entry in entry_list:
                    entry_id = entry.get("id", "")
                    if entry_id in existing_ids:
                        result["conflicts"] += 1
                        if conflict_strategy == "latest_wins":
                            # Replace with newer entry
                            existing[type_name] = [
                                e for e in existing[type_name] if e.get("id") != entry_id
                            ]
                            existing[type_name].append(entry)
                        elif conflict_strategy == "merge":
                            # Merge fields
                            for e in existing[type_name]:
                                if e.get("id") == entry_id:
                                    e.update(entry)
                                    break
                    else:
                        existing[type_name].append(entry)
                        result["synced"] += 1

            # Save sync data
            try:
                with open(sync_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        self._log("sync_complete", result)
        return result

    def get_sync_state(self, agent_a: str, agent_b: str) -> dict:
        """Get sync state between two agents."""
        sync_file = os.path.join(self.sync_dir, f"sync_{agent_a}_to_{agent_b}.json")
        if os.path.exists(sync_file):
            try:
                with open(sync_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def check_consistency(self, memories: dict[str, list[dict]]) -> dict:
        """
        Check memory consistency.
        
        Args:
            memories: Dict of {type_name: [entries]}
        
        Returns:
            Consistency report
        """
        report = {
            "total_entries": 0,
            "duplicate_ids": [],
            "missing_summaries": [],
            "orphan_entries": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        all_ids = {}
        for type_name, entries in memories.items():
            for entry in entries:
                entry_id = entry.get("id", "")
                report["total_entries"] += 1

                # Check duplicate IDs
                if entry_id in all_ids:
                    report["duplicate_ids"].append({
                        "id": entry_id,
                        "type": type_name,
                        "first_seen": all_ids[entry_id],
                    })
                else:
                    all_ids[entry_id] = type_name

                # Check missing summary
                if not entry.get("summary"):
                    report["missing_summaries"].append({
                        "id": entry_id,
                        "type": type_name,
                    })

        return report

    def resolve_conflicts(
        self,
        entries_a: list[dict],
        entries_b: list[dict],
        strategy: str = "latest_wins",
    ) -> list[dict]:
        """
        Resolve conflicts between two sets of entries.
        
        Args:
            entries_a: First set of entries
            entries_b: Second set of entries
            strategy: Conflict resolution strategy
        
        Returns:
            Merged entries
        """
        merged = {}
        for entry in entries_a + entries_b:
            entry_id = entry.get("id", "")
            if not entry_id:
                continue

            if entry_id in merged:
                existing = merged[entry_id]
                if strategy == "latest_wins":
                    existing_time = existing.get("updated_at", existing.get("timestamp", ""))
                    new_time = entry.get("updated_at", entry.get("timestamp", ""))
                    if new_time > existing_time:
                        merged[entry_id] = entry
                elif strategy == "merge":
                    existing.update(entry)
            else:
                merged[entry_id] = entry

        return list(merged.values())

    def _log(self, event: str, details: dict):
        """Log sync events."""
        self._sync_log.append({
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        })
        if len(self._sync_log) > 500:
            self._sync_log = self._sync_log[-250:]

    def get_stats(self) -> dict:
        return {
            "active_locks": len(self._locks),
            "total_syncs": len([l for l in self._sync_log if l["event"] == "sync_complete"]),
            "log_size": len(self._sync_log),
        }
