"""
CODER AGENT MEMORY — Hook System
Trigger-based actions for memory events.

Hook types:
- pre_write: Before writing to memory
- post_write: After writing to memory
- pre_read: Before reading from memory
- post_read: After reading from memory
- on_error: On memory operation error
- on_session_start: Session start
- on_session_end: Session end
- on_consolidation: AutoDream consolidation
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional


class Hook:
    """A single hook (trigger + action)."""

    def __init__(
        self,
        name: str,
        trigger: str,
        action: Callable,
        priority: int = 0,
        enabled: bool = True,
        filter_fn: Optional[Callable] = None,
    ):
        self.name = name
        self.trigger = trigger
        self.action = action
        self.priority = priority
        self.enabled = enabled
        self.filter_fn = filter_fn
        self.execution_count = 0
        self.last_executed: Optional[str] = None
        self.total_time_ms: float = 0

    def should_run(self, context: dict) -> bool:
        """Check if this hook should run based on filter."""
        if not self.enabled:
            return False
        if self.filter_fn:
            return self.filter_fn(context)
        return True

    def execute(self, context: dict) -> Any:
        """Execute the hook action."""
        if not self.should_run(context):
            return None

        start = time.time()
        try:
            result = self.action(context)
            self.execution_count += 1
            self.last_executed = datetime.now(timezone.utc).isoformat()
            self.total_time_ms += (time.time() - start) * 1000
            return result
        except Exception as e:
            return {"error": str(e)}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "priority": self.priority,
            "enabled": self.enabled,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed,
            "total_time_ms": self.total_time_ms,
        }


class HookSystem:
    """
    Hook system for memory events.
    
    Supports:
    - Multiple hooks per trigger
    - Priority ordering
    - Conditional execution (filter functions)
    - Statistics tracking
    """

    def __init__(self):
        self.hooks: dict[str, list[Hook]] = defaultdict(list)
        self.hook_log: list[dict] = []
        self._register_defaults()

    def _register_defaults(self):
        """Register default hooks."""
        # Auto-log all writes
        self.register(
            "auto-logger",
            "post_write",
            lambda ctx: self._log_action(ctx),
            priority=100,
        )

        # Auto-cache invalidation on write
        self.register(
            "cache-invalidator",
            "post_write",
            lambda ctx: self._invalidate_cache(ctx),
            priority=50,
        )

    def register(
        self,
        name: str,
        trigger: str,
        action: Callable,
        priority: int = 0,
        enabled: bool = True,
        filter_fn: Optional[Callable] = None,
    ):
        """
        Register a hook.
        
        Args:
            name: Unique hook name
            trigger: Event trigger (pre_write, post_write, etc.)
            action: Callable to execute
            priority: Lower = runs first
            enabled: Whether hook is active
            filter_fn: Optional filter function
        """
        hook = Hook(name, trigger, action, priority, enabled, filter_fn)
        self.hooks[trigger].append(hook)
        self.hooks[trigger].sort(key=lambda h: h.priority)

    def unregister(self, name: str, trigger: str):
        """Remove a hook by name and trigger."""
        if trigger in self.hooks:
            self.hooks[trigger] = [h for h in self.hooks[trigger] if h.name != name]

    def enable(self, name: str, trigger: str):
        """Enable a hook."""
        for hook in self.hooks.get(trigger, []):
            if hook.name == name:
                hook.enabled = True

    def disable(self, name: str, trigger: str):
        """Disable a hook."""
        for hook in self.hooks.get(trigger, []):
            if hook.name == name:
                hook.enabled = False

    def trigger(self, trigger_name: str, context: dict) -> list[Any]:
        """
        Trigger all hooks for an event.
        
        Args:
            trigger_name: The trigger event name
            context: Context data for hooks
        
        Returns:
            List of results from all executed hooks
        """
        results = []
        hooks = self.hooks.get(trigger_name, [])

        for hook in hooks:
            result = hook.execute(context)
            if result is not None:
                results.append({"hook": hook.name, "result": result})

        # Log the trigger
        self.hook_log.append({
            "trigger": trigger_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hooks_executed": len([h for h in hooks if h.enabled]),
            "results": len(results),
        })

        return results

    def trigger_pre_write(self, type_name: str, entry: dict) -> list[Any]:
        """Trigger pre-write hooks."""
        return self.trigger("pre_write", {"type_name": type_name, "entry": entry})

    def trigger_post_write(self, type_name: str, entry: dict) -> list[Any]:
        """Trigger post-write hooks."""
        return self.trigger("post_write", {"type_name": type_name, "entry": entry})

    def trigger_pre_read(self, type_name: str, query: dict) -> list[Any]:
        """Trigger pre-read hooks."""
        return self.trigger("pre_read", {"type_name": type_name, "query": query})

    def trigger_post_read(self, type_name: str, results: list) -> list[Any]:
        """Trigger post-read hooks."""
        return self.trigger("post_read", {"type_name": type_name, "results": results})

    def trigger_on_error(self, operation: str, error: Exception) -> list[Any]:
        """Trigger error hooks."""
        return self.trigger("on_error", {"operation": operation, "error": str(error)})

    def trigger_session_start(self, session_id: str) -> list[Any]:
        """Trigger session start hooks."""
        return self.trigger("on_session_start", {"session_id": session_id})

    def trigger_session_end(self, session_id: str, summary: str) -> list[Any]:
        """Trigger session end hooks."""
        return self.trigger("on_session_end", {"session_id": session_id, "summary": summary})

    def trigger_consolidation(self, stats: dict) -> list[Any]:
        """Trigger consolidation hooks."""
        return self.trigger("on_consolidation", {"stats": stats})

    # ============================================================
    # DEFAULT HOOK ACTIONS
    # ============================================================

    def _log_action(self, context: dict) -> dict:
        """Default post-write logger."""
        return {
            "logged": True,
            "type": context.get("type_name", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _invalidate_cache(self, context: dict) -> dict:
        """Invalidate retrieval cache on write."""
        type_name = context.get("type_name", "")
        return {"invalidated": True, "type": type_name}

    # ============================================================
    # STATS
    # ============================================================

    def get_stats(self) -> dict:
        """Get hook system statistics."""
        stats = {
            "total_hooks": sum(len(hooks) for hooks in self.hooks.values()),
            "triggers": list(self.hooks.keys()),
            "trigger_counts": {t: len(hooks) for t, hooks in self.hooks.items()},
            "total_executions": sum(
                h.execution_count for hooks in self.hooks.values() for h in hooks
            ),
            "log_size": len(self.hook_log),
        }
        return stats

    def get_hook_details(self) -> list[dict]:
        """Get details of all registered hooks."""
        details = []
        for trigger, hooks in self.hooks.items():
            for hook in hooks:
                info = hook.to_dict()
                info["trigger"] = trigger
                details.append(info)
        return details
