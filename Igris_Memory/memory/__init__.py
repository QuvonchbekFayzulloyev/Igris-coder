"""
CODER AGENT MEMORY SYSTEM v2.1
================================

4-Pillar Architecture:
- L1 Runtime (18 types) — Session davomida, tez
- L2 Persistent (24 types) — Sessiyalararo, doimiy
- L3 Config (14 types) — Sozlamalar, static
- L4 Retrieval — Qidiruv, BM25 + Vector + RRF

Advanced Features:
- AutoDream: L1->L2 consolidation (5-pass)
- HookSystem: Trigger/action system
- TimeTravel: Snapshot/rollback
- PoisoningProtection: Security
- MultiAgentSync: Ko'p agent sync
- MemoryAPI: Agent-writable API

1.5B Optimizatsiya:
- Har bir entry ≤ 500 token
- summary field majburiy
- Flat structure (deep nesting yo'q)
- BM25 as primary (zero model overhead)
- LRU cache, max 50 entry
"""

from .runtime import RuntimeMemory
from .persistent import PersistentMemory
from .config import ConfigManager
from .retrieval import RetrievalPipeline
from .agent_api import MemoryAPI
from .autodream import AutoDream
from .hooks import HookSystem
from .sync import MultiAgentSync
from .time_travel import TimeTravel
from .poisoning import PoisoningProtection
from .schemas import L1_TYPES, L2_TYPES


class MemoryManager:
    """
    MemoryManager — Memory tizimining asosiy orchestratori.
    
    Barcha qatlamlarni (L1-L4) va ilg'or funksiyalarni boshqaradi.
    
    Usage:
        manager = MemoryManager()
        manager.start_session("my-session")
        
        # Agent writes
        manager.api.remember("JWT token handling", memory_type="knowledge")
        
        # Agent reads
        context = manager.api.context(task="Auth module refactor")
        
        # Session end
        manager.end_session(summary="Auth module refactored")
    """

    def __init__(self, base_dir: str = "memory"):
        """
        Initialize all memory components.
        
        Args:
            base_dir: Base directory for memory storage
        """
        self.base_dir = base_dir

        # L1: Runtime Memory
        self.runtime = RuntimeMemory(f"{base_dir}/runtime")

        # L2: Persistent Memory
        self.persistent = PersistentMemory(f"{base_dir}/persistent")

        # L3: Configuration
        self.config = ConfigManager(f"{base_dir}/config")

        # L4: Retrieval Pipeline
        self.retrieval = RetrievalPipeline()

        # Advanced Features
        self.api = MemoryAPI(self)
        self.autodream = AutoDream(self.runtime, self.persistent)
        self.hooks = HookSystem()
        self.sync = MultiAgentSync(f"{base_dir}/sync")
        self.time_travel = TimeTravel(f"{base_dir}/snapshots")
        self.poisoning = PoisoningProtection(f"{base_dir}/security")

        # Session state
        self._current_session_id: str = ""
        self._is_active: bool = False

        # Auto-load retrieval index
        self._load_retrieval_index()

    def _load_retrieval_index(self):
        """Load retrieval index from memory files."""
        try:
            self.retrieval.load_documents(self.base_dir)
        except Exception:
            pass  # Non-blocking

    # ============================================================
    # SESSION MANAGEMENT
    # ============================================================

    def start_session(self, session_id: str = "") -> dict:
        """
        Start a new memory session.
        
        Args:
            session_id: Optional session ID (auto-generated if empty)
        
        Returns:
            Session entry
        """
        import uuid
        if not session_id:
            session_id = f"ses-{uuid.uuid4().hex[:8]}"

        self._current_session_id = session_id
        self._is_active = True

        # Start runtime session
        session = self.runtime.start_session(session_id)

        # Trigger hooks
        self.hooks.trigger_session_start(session_id)

        # Create initial snapshot
        self.time_travel.auto_snapshot(self, trigger="session_start")

        return session

    def end_session(self, summary: str = "") -> dict:
        """
        End current session and run consolidation.
        
        Args:
            summary: Session summary
        
        Returns:
            Consolidation stats
        """
        if not self._is_active:
            return {"status": "no_active_session"}

        # End runtime session
        session = self.runtime.end_session(summary)

        # Trigger hooks
        self.hooks.trigger_session_end(self._current_session_id, summary)

        # Run AutoDream consolidation (L1 -> L2)
        consolidation_stats = self.autodream.consolidate()
        self.hooks.trigger_consolidation(consolidation_stats)

        # Create end-of-session snapshot
        self.time_travel.auto_snapshot(self, trigger="session_end")

        # Cleanup expired entries
        self.runtime.cleanup_expired()

        # Reset state
        self._is_active = False
        self._current_session_id = ""

        return {
            "session": session,
            "consolidation": consolidation_stats,
        }

    # ============================================================
    # QUICK ACCESS METHODS
    # ============================================================

    def remember(self, content: str, memory_type: str = "long-term", **kwargs) -> dict:
        """Quick memory write."""
        return self.api.remember(content, memory_type=memory_type, **kwargs)

    def recall(self, query: str, **kwargs) -> dict:
        """Quick memory read."""
        return self.api.recall(query, **kwargs)

    def search(self, query: str, **kwargs) -> dict:
        """Quick search."""
        return self.api.search(query, **kwargs)

    def context(self, task: str = "", **kwargs) -> dict:
        """Quick context assembly."""
        return self.api.context(task=task, **kwargs)

    def status(self) -> dict:
        """Get full system status."""
        base_status = self.api.status()
        base_status["session"] = {
            "id": self._current_session_id,
            "active": self._is_active,
        }
        base_status["advanced"] = {
            "autodream": self.autodream.get_stats(),
            "hooks": self.hooks.get_stats(),
            "time_travel": self.time_travel.get_stats(),
            "poisoning": self.poisoning.get_stats(),
            "sync": self.sync.get_stats(),
        }
        return base_status

    def snapshot(self, name: str = "manual", description: str = "") -> dict:
        """Create a manual snapshot."""
        memory_data = {}
        if self._is_active:
            for type_name in ["session", "active-context", "task-memory"]:
                entries = self.runtime.read(type_name, limit=5)
                if entries:
                    memory_data[type_name] = entries
        return self.time_travel.create_snapshot(name, memory_data, trigger="manual", description=description)

    def rollback(self, snapshot_id: str) -> dict:
        """Rollback to a snapshot."""
        return self.time_travel.rollback(snapshot_id)

    def check_security(self, entry: dict) -> dict:
        """Check entry for security issues."""
        return self.poisoning.check_entry(entry)

    def get_stats(self) -> dict:
        """Get comprehensive system statistics."""
        return {
            "runtime": self.runtime.get_stats(),
            "persistent": self.persistent.get_stats(),
            "retrieval": self.retrieval.get_stats(),
            "hooks": self.hooks.get_stats(),
            "time_travel": self.time_travel.get_stats(),
            "poisoning": self.poisoning.get_stats(),
            "sync": self.sync.get_stats(),
            "session": {
                "id": self._current_session_id,
                "active": self._is_active,
            },
        }


__all__ = [
    "MemoryManager",
    "RuntimeMemory",
    "PersistentMemory",
    "ConfigManager",
    "RetrievalPipeline",
    "MemoryAPI",
    "AutoDream",
    "HookSystem",
    "MultiAgentSync",
    "TimeTravel",
    "PoisoningProtection",
    "L1_TYPES",
    "L2_TYPES",
]
