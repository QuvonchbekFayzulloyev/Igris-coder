"""
CODER AGENT MEMORY — Agent-Writable Memory API (L6)
Agent tizim bilan shu orqali gaplashadi.

API endpoints:
- remember: Memory saqlash
- recall: Memory qidirish
- search: Full-text search
- context: Context yig'ish
- status: Memory holati
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional


class MemoryAPI:
    """
    Agent-Writable Memory API.
    
    Agent uchun yagona kirish nuqtasi:
    - /memory-remember — xotiraga yozish
    - /memory-recall — xotiradan o'qish
    - /memory-search — qidirish
    - /memory-context — kontekst yig'ish
    - /memory-status — holat
    """

    def __init__(self, memory_manager=None):
        """
        Args:
            memory_manager: MemoryManager instance (optional)
        """
        self.manager = memory_manager
        self._api_log: list[dict] = []

    def remember(
        self,
        content: str,
        memory_type: str = "long-term",
        layer: str = "l2",
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        summary: str = "",
    ) -> dict:
        """
        Save a memory entry.
        
        Args:
            content: The content to remember
            memory_type: Type of memory (long-term, error, solution, etc.)
            layer: Which layer (l1=runtime, l2=persistent)
            metadata: Optional metadata
            tags: Optional tags for categorization
            summary: Short summary (max 200 chars)
        
        Returns:
            Status dict with id and confirmation
        """
        entry = {
            "content": content[:2000],
            "type": memory_type,
            "tags": tags or [],
            "metadata": metadata or {},
            "summary": summary[:200] or content[:200],
            "remembered_at": datetime.now(timezone.utc).isoformat(),
        }

        result = {"status": "error", "message": ""}

        if layer == "l1" and self.manager and hasattr(self.manager, "runtime"):
            entry["id"] = f"agent-{memory_type}-{int(time.time())}"
            self.manager.runtime.write(memory_type, entry)
            result = {"status": "ok", "id": entry["id"], "layer": "l1", "type": memory_type}

        elif layer == "l2" and self.manager and hasattr(self.manager, "persistent"):
            entry["id"] = f"agent-{memory_type}-{int(time.time())}"
            self.manager.persistent.write(memory_type, entry, check_duplicate=True)
            result = {"status": "ok", "id": entry["id"], "layer": "l2", "type": memory_type}

        else:
            # Store in local buffer if no manager available
            entry["id"] = f"local-{memory_type}-{int(time.time())}"
            if not hasattr(self, "_local_buffer"):
                self._local_buffer: list[dict] = []
            self._local_buffer.append(entry)
            result = {"status": "ok", "id": entry["id"], "layer": "local", "type": memory_type, "warning": "Stored in local buffer only (no manager connected)"}

        self._log("remember", result)
        return result

    def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        layer: str = "all",
        limit: int = 5,
    ) -> dict:
        """
        Recall memories matching a query.
        
        Args:
            query: Search query
            memory_type: Optional type filter
            layer: Which layer to search (l1, l2, all)
            limit: Max results
        
        Returns:
            Dict with matching memories
        """
        results = {"query": query, "memories": [], "count": 0}

        if not self.manager:
            return results

        # Search L1 (runtime)
        if layer in ("l1", "all") and hasattr(self.manager, "runtime"):
            types_to_search = [memory_type] if memory_type else [
                "short-turn", "active-context", "task-memory",
                "observation-memory", "decision-log",
            ]
            for t in types_to_search:
                entries = self.manager.runtime.read(t, limit=2)
                for entry in entries:
                    entry_str = json.dumps(entry, ensure_ascii=False).lower()
                    if query.lower() in entry_str:
                        results["memories"].append({
                            "layer": "l1",
                            "type": t,
                            "entry": entry,
                        })

        # Search L2 (persistent)
        if layer in ("l2", "all") and hasattr(self.manager, "persistent"):
            l2_results = self.manager.persistent.search(query, limit=limit)
            for r in l2_results:
                results["memories"].append({
                    "layer": "l2",
                    "type": r.get("type", "unknown"),
                    "entry": r.get("entry", r),
                })

        results["count"] = len(results["memories"])
        self._log("recall", {"query": query, "count": results["count"]})
        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_retrieval: bool = True,
    ) -> dict:
        """
        Full-text search across all memory layers.
        
        Args:
            query: Search query
            top_k: Max results
            use_retrieval: Whether to use retrieval pipeline
        
        Returns:
            Search results dict
        """
        results = {"query": query, "results": [], "count": 0}

        if not self.manager:
            return results

        # Use retrieval pipeline if available
        if use_retrieval and hasattr(self.manager, "retrieval"):
            retrieval_results = self.manager.retrieval.search(query, top_k=top_k)
            for r in retrieval_results:
                results["results"].append({
                    "source": r.get("source", ""),
                    "score": r.get("score", 0),
                    "metadata": r.get("metadata", {}),
                })

        # Also search L1 + L2
        recall_results = self.recall(query, limit=top_k)
        seen_ids = {r.get("source", r.get("entry", {}).get("id", "")) for r in results["results"]}
        for mem in recall_results.get("memories", []):
            mem_id = mem.get("entry", {}).get("id", "")
            if mem_id not in seen_ids:
                results["results"].append(mem)
                seen_ids.add(mem_id)

        results["count"] = len(results["results"])
        self._log("search", {"query": query, "count": results["count"]})
        return results

    def context(self, task: str = "", max_tokens: int = 2000) -> dict:
        """
        Assemble context for the current task.
        
        Args:
            task: Current task description
            max_tokens: Max tokens for context
        
        Returns:
            Context dict with all relevant memories
        """
        context = {
            "task": task,
            "sections": {},
            "total_tokens_estimate": 0,
        }

        if not self.manager:
            return context

        # L1 context (runtime)
        if hasattr(self.manager, "runtime"):
            l1_summary = self.manager.runtime.get_context_summary(max_tokens=max_tokens // 2)
            context["sections"]["runtime"] = l1_summary
            context["total_tokens_estimate"] += len(l1_summary.split()) * 1.3

        # L3 config context
        if hasattr(self.manager, "config"):
            config_str = self.manager.config.to_context_string()
            context["sections"]["config"] = config_str
            context["total_tokens_estimate"] += len(config_str.split()) * 1.3

        # L2 relevant memories
        if task and hasattr(self.manager, "persistent"):
            l2_results = self.manager.persistent.search(task, limit=3)
            if l2_results:
                l2_str = "\n".join(
                    f"- {r.get('entry', r).get('summary', '')[:200]}"
                    for r in l2_results
                )
                context["sections"]["persistent"] = l2_str
                context["total_tokens_estimate"] += len(l2_str.split()) * 1.3

        self._log("context", {"task": task, "sections": len(context["sections"])})
        return context

    def status(self) -> dict:
        """
        Get memory system status.
        
        Returns:
            Status dict with stats from all layers
        """
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "layers": {},
        }

        if not self.manager:
            status["message"] = "No memory manager connected"
            return status

        # L1 status
        if hasattr(self.manager, "runtime"):
            status["layers"]["l1_runtime"] = self.manager.runtime.get_stats()

        # L2 status
        if hasattr(self.manager, "persistent"):
            status["layers"]["l2_persistent"] = self.manager.persistent.get_stats()

        # L3 status
        if hasattr(self.manager, "config"):
            status["layers"]["l3_config"] = {
                "configs": self.manager.config.list_configs(),
            }

        # L4 status
        if hasattr(self.manager, "retrieval"):
            status["layers"]["l4_retrieval"] = self.manager.retrieval.get_stats()

        # Hooks status
        if hasattr(self.manager, "hooks"):
            status["layers"]["hooks"] = self.manager.hooks.get_stats()

        return status

    def forget(self, memory_id: str, layer: str = "l2") -> dict:
        """
        Delete a memory entry (GDPR compliance).
        
        Args:
            memory_id: ID of the memory to forget
            layer: Which layer (l1, l2)
        
        Returns:
            Deletion status
        """
        result = {"status": "error", "message": "Not implemented"}

        if layer == "l2" and self.manager and hasattr(self.manager, "persistent"):
            success = self.manager.persistent.delete("long-term", memory_id)
            if success:
                result = {"status": "ok", "deleted": memory_id, "layer": "l2"}
            else:
                result = {"status": "not_found", "message": f"Memory {memory_id} not found"}

        self._log("forget", result)
        return result

    def export_memory(self, format: str = "json") -> str:
        """
        Export all memory data.
        
        Args:
            format: Export format (json, markdown)
        
        Returns:
            Exported data as string
        """
        if not self.manager:
            return "{}"

        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "layers": {},
        }

        if hasattr(self.manager, "config"):
            data["layers"]["config"] = self.manager.config.get_all("agent")

        if format == "json":
            return json.dumps(data, ensure_ascii=False, indent=2)
        elif format == "markdown":
            return self._to_markdown(data)
        return json.dumps(data, ensure_ascii=False)

    def _to_markdown(self, data: dict) -> str:
        """Convert data to markdown format."""
        lines = [f"# Memory Export", f"*Exported: {data.get('exported_at', '')}*", ""]
        for layer, content in data.get("layers", {}).items():
            lines.append(f"## {layer.title()}")
            lines.append(json.dumps(content, ensure_ascii=False, indent=2))
            lines.append("")
        return "\n".join(lines)

    def _log(self, operation: str, details: dict):
        """Log API operations."""
        self._api_log.append({
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        })
        # Keep log bounded
        if len(self._api_log) > 1000:
            self._api_log = self._api_log[-500:]

    def get_log(self, limit: int = 50) -> list[dict]:
        """Get recent API log entries."""
        return self._api_log[-limit:]
