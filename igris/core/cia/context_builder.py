"""
igris.core.cia.context_builder
--------------------------------
Progressive Context Loader — CIA Level 4.

Builds a compact context for the LLM by:
1. Starting with the current task (P0)
2. Adding only related memories (by priority)
3. Loading knowledge level L1 first, then L2, then L3 on demand
4. Strict token budget enforcement

Token budget per model size:
  1.5B model: 4096 tokens max
  7B model: 8192 tokens max
  8B model: 16384 tokens max
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import (
    CIAStore,
    KnowledgeLevel,
    MemoryEntry,
    MemoryPriority,
    MemoryStatus,
)

if TYPE_CHECKING:
    pass

# Token budgets per model size
TOKEN_BUDGETS = {
    "1.5b": 4096,
    "7b": 8192,
    "8b": 16384,
}

# Memory overhead for system prompt + user input
SYSTEM_OVERHEAD = 1500

# What fraction of budget each priority level gets
PRIORITY_BUDGET: dict[MemoryPriority, float] = {
    MemoryPriority.P0_CURRENT: 0.35,
    MemoryPriority.P1_API: 0.20,
    MemoryPriority.P2_ARCHITECTURE: 0.15,
    MemoryPriority.P3_COMPONENT: 0.12,
    MemoryPriority.P4_RESEARCH: 0.08,
    MemoryPriority.P5_REFERENCE: 0.06,
    MemoryPriority.P6_HISTORICAL: 0.04,
}

# Rough token estimator (4 chars ≈ 1 token for code/text)
def _estimate_tokens(text: str) -> int:
    return len(text) // 4


class ContextBuilder:
    """Builds progressive context with strict token budgets."""

    def __init__(self, store: CIAStore, model_size: str = "1.5b"):
        self.store = store
        self.total_budget = TOKEN_BUDGETS.get(model_size, 4096) - SYSTEM_OVERHEAD

    def build_context(
        self,
        task: str,
        related_topics: list[str] | None = None,
        include_decisions: bool = True,
    ) -> str:
        """Build a compact context block for the given task."""
        parts: list[str] = []
        used = 0

        # 1. Find relevant memories
        memories = self.store.query(task, top_k=10)
        if related_topics:
            for topic in related_topics:
                memories.extend(self.store.query(topic, top_k=5))

        seen_ids = set()
        sorted_memories = sorted(
            memories,
            key=lambda e: (e.priority.value, -e.access_score),
        )

        for entry in sorted_memories:
            if entry.id in seen_ids or entry.status != MemoryStatus.ACTIVE:
                continue
            seen_ids.add(entry.id)

            budget_for_priority = int(self.total_budget * PRIORITY_BUDGET.get(entry.priority, 0.08))
            if used >= self.total_budget or budget_for_priority <= 0:
                continue

            # Load L1 only by default
            text = self._get_text_for_budget(entry, budget_for_priority)
            estimated = _estimate_tokens(text)

            if used + estimated > self.total_budget:
                text = text[:max(50, (self.total_budget - used) * 4)]
                estimated = _estimate_tokens(text)
                if estimated <= 0:
                    break

            parts.append(text)
            used += estimated

        # 2. Add decisions if requested
        if include_decisions:
            for dec in self.store._decisions.values():
                dec_text = f"[DECISION] {dec.question} → {dec.answer}"
                estimated = _estimate_tokens(dec_text)
                if used + estimated > self.total_budget:
                    break
                parts.append(dec_text)
                used += estimated

        return "\n\n".join(parts)

    def _get_text_for_budget(self, entry: MemoryEntry, budget: int) -> str:
        """Get the right knowledge level for the available budget."""
        target_chars = budget * 4

        if budget >= 200:
            return entry.text[:target_chars]
        elif budget >= 50:
            lines = entry.text.split("\n")
            for line in lines:
                if line.startswith("L1:") or line.startswith("1:"):
                    return line[:target_chars]
            return entry.text[:target_chars]
        else:
            for line in entry.text.split("\n"):
                if line.startswith("L1:") or line.startswith("1:"):
                    return line[:80]
            return entry.text[:80]

    def summary(self, max_chars: int = 200) -> str:
        """Return a summary of all active context."""
        active = self.store.list_active()
        parts = []
        for p in sorted(MemoryPriority, key=lambda x: x.value):
            count = sum(1 for e in active if e.priority == p)
            if count:
                parts.append(f"{p.name}:{count}")
        return f"Context: {', '.join(parts)}"[:max_chars]
