"""
CODER AGENT MEMORY — Time Travel
Snapshot va rollback imkoniyatlari.

Features:
- State snapshots (checkpoint)
- Rollback to previous state
- History browsing
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Optional


class TimeTravel:
    """
    TimeTravel — Memory snapshot/rollback tizimi.
    
    Muhim actionlardan oldin snapshot olish,
    kerak bo'lganda oldingi holatga qaytish.
    """

    def __init__(self, snapshots_dir: str = "memory/snapshots"):
        self.snapshots_dir = snapshots_dir
        os.makedirs(snapshots_dir, exist_ok=True)
        self._snapshots: list[dict] = []

    def create_snapshot(
        self,
        name: str,
        memory_data: dict,
        trigger: str = "manual",
        description: str = "",
    ) -> dict:
        """
        Create a memory snapshot.
        
        Args:
            name: Snapshot name
            memory_data: Current memory state to save
            trigger: What triggered the snapshot
            description: Optional description
        
        Returns:
            Snapshot metadata
        """
        snapshot_id = f"snap-{int(time.time() * 1000)}"
        snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
        os.makedirs(snapshot_dir, exist_ok=True)

        # Save memory data
        snapshot_file = os.path.join(snapshot_dir, "memory_state.json")
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # Save metadata
        metadata = {
            "id": snapshot_id,
            "name": name,
            "trigger": trigger,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": os.path.getsize(snapshot_file),
            "layers": list(memory_data.keys()),
        }

        meta_file = os.path.join(snapshot_dir, "metadata.json")
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        self._snapshots.append(metadata)
        return {"status": "ok", "snapshot": metadata}

    def rollback(self, snapshot_id: str, memory_manager=None) -> dict:
        """
        Rollback to a previous snapshot.
        
        Args:
            snapshot_id: ID of the snapshot to restore
            memory_manager: Optional MemoryManager to restore state into
        
        Returns:
            Restored memory data
        """
        snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
        snapshot_file = os.path.join(snapshot_dir, "memory_state.json")

        if not os.path.exists(snapshot_file):
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}

        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
            
            # If memory_manager provided, restore state into it
            restored_count = 0
            if memory_manager:
                if "runtime" in memory_data and hasattr(memory_manager, "runtime"):
                    for type_name, entries in memory_data["runtime"].items():
                        for entry in entries:
                            memory_manager.runtime.write(type_name, entry)
                            restored_count += 1
                if "persistent" in memory_data and hasattr(memory_manager, "persistent"):
                    for type_name, entries in memory_data["persistent"].items():
                        for entry in entries:
                            memory_manager.persistent.write(type_name, entry, check_duplicate=False)
                            restored_count += 1
            
            return {"status": "ok", "data": memory_data, "snapshot_id": snapshot_id, "restored_entries": restored_count}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_snapshots(self, limit: int = 20) -> list[dict]:
        """
        List available snapshots.
        
        Args:
            limit: Max snapshots to return
        
        Returns:
            List of snapshot metadata
        """
        snapshots = []

        if not os.path.exists(self.snapshots_dir):
            return snapshots

        for entry in os.listdir(self.snapshots_dir):
            meta_file = os.path.join(self.snapshots_dir, entry, "metadata.json")
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    snapshots.append(metadata)
                except Exception:
                    pass

        # Sort by created_at descending
        snapshots.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return snapshots[:limit]

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        """Get metadata for a specific snapshot."""
        meta_file = os.path.join(self.snapshots_dir, snapshot_id, "metadata.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
        if os.path.exists(snapshot_dir):
            try:
                shutil.rmtree(snapshot_dir)
                return True
            except Exception:
                pass
        return False

    def auto_snapshot(
        self,
        memory_manager,
        trigger: str = "auto",
        max_snapshots: int = 10,
    ) -> Optional[dict]:
        """
        Automatically create a snapshot of current memory state.
        
        Args:
            memory_manager: MemoryManager instance
            trigger: What triggered the auto-snapshot
            max_snapshots: Max snapshots to keep
        
        Returns:
            Snapshot metadata or None
        """
        # Collect current state
        memory_data = {}

        if hasattr(memory_manager, "runtime"):
            # Get key runtime entries
            memory_data["runtime"] = {}
            for type_name in ["session", "active-context", "task-memory", "decision-log"]:
                entries = memory_manager.runtime.read(type_name, limit=5)
                if entries:
                    memory_data["runtime"][type_name] = entries

        if hasattr(memory_manager, "persistent"):
            # Get key persistent entries
            memory_data["persistent"] = {}
            for type_name in ["long-term", "experience", "error-memory", "solution-memory"]:
                entries = memory_manager.persistent.read(type_name, limit=3)
                if entries:
                    memory_data["persistent"][type_name] = entries

        if not memory_data:
            return None

        # Create snapshot
        result = self.create_snapshot(
            name=f"auto-{trigger}",
            memory_data=memory_data,
            trigger=trigger,
            description=f"Auto snapshot on {trigger}",
        )

        # Cleanup old snapshots
        snapshots = self.list_snapshots(limit=100)
        if len(snapshots) > max_snapshots:
            for old_snapshot in snapshots[max_snapshots:]:
                self.delete_snapshot(old_snapshot["id"])

        return result.get("snapshot")

    def compare_snapshots(self, snap_id_a: str, snap_id_b: str) -> dict:
        """
        Compare two snapshots and show differences.
        
        Args:
            snap_id_a: First snapshot ID
            snap_id_b: Second snapshot ID
        
        Returns:
            Comparison results
        """
        data_a = self.rollback(snap_id_a)
        data_b = self.rollback(snap_id_b)

        if data_a.get("status") != "ok" or data_b.get("status") != "ok":
            return {"status": "error", "message": "Could not load one or both snapshots"}

        state_a = data_a.get("data", {})
        state_b = data_b.get("data", {})

        comparison = {
            "snapshot_a": snap_id_a,
            "snapshot_b": snap_id_b,
            "layers_changed": [],
            "details": {},
        }

        all_layers = set(list(state_a.keys()) + list(state_b.keys()))
        for layer in all_layers:
            a_count = sum(len(v) for v in state_a.get(layer, {}).values()) if isinstance(state_a.get(layer), dict) else 0
            b_count = sum(len(v) for v in state_b.get(layer, {}).values()) if isinstance(state_b.get(layer), dict) else 0

            if a_count != b_count:
                comparison["layers_changed"].append(layer)
                comparison["details"][layer] = {
                    "a_count": a_count,
                    "b_count": b_count,
                    "diff": b_count - a_count,
                }

        return comparison

    def get_stats(self) -> dict:
        """Get time travel statistics."""
        snapshots = self.list_snapshots(limit=1000)
        total_size = sum(s.get("size_bytes", 0) for s in snapshots)
        return {
            "total_snapshots": len(snapshots),
            "total_size_bytes": total_size,
            "oldest_snapshot": snapshots[-1]["created_at"] if snapshots else None,
            "newest_snapshot": snapshots[0]["created_at"] if snapshots else None,
        }
