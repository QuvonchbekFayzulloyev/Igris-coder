"""
Progressive context builder: loads memory at appropriate detail level
within a strict token budget. Merged from CIA ContextBuilder pattern.

Levels:
  L1_SUMMARY  (~20 tokens)  - one-line essence
  L2_REASONING (~100 tokens) - key reasoning
  L3_EVIDENCE (~1000+ tokens) - full detail

Priority budget allocation (from CIA):
  P0_CURRENT:     35%
  P1_API:         20%
  P2_ARCHITECTURE: 15%
  P3_COMPONENT:   12%
  P4_RESEARCH:     8%
  P5_REFERENCE:    6%
  P6_HISTORICAL:   4%
"""
from __future__ import annotations

from .entries import (
    KnowledgeLevel,
    MemoryEntry,
    MemoryPriority,
    QAEntry,
    MemoEntry,
    DecisionEntry,
    PatternEntry,
)
from .store import MemoryStore


TOKEN_BUDGETS = {"1.5b": 4096, "7b": 8192, "8b": 16384}
SYSTEM_OVERHEAD = 1500

PRIORITY_BUDGET = {
    MemoryPriority.P0_CURRENT: 0.35,
    MemoryPriority.P1_API: 0.20,
    MemoryPriority.P2_ARCHITECTURE: 0.15,
    MemoryPriority.P3_COMPONENT: 0.12,
    MemoryPriority.P4_RESEARCH: 0.08,
    MemoryPriority.P5_REFERENCE: 0.06,
    MemoryPriority.P6_HISTORICAL: 0.04,
}


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _extract_level(entry: MemoryEntry, level: KnowledgeLevel) -> str:
    if isinstance(entry, QAEntry):
        if level == KnowledgeLevel.L1_SUMMARY:
            return entry.question[:80]
        elif level == KnowledgeLevel.L2_REASONING:
            return f"Q: {entry.question[:120]}\nA: {entry.answer[:300]}"
        return f"Q: {entry.question}\nA: {entry.answer}"
    if isinstance(entry, MemoEntry):
        if level == KnowledgeLevel.L1_SUMMARY:
            return entry.level1 or entry.content[:80]
        elif level == KnowledgeLevel.L2_REASONING:
            return entry.level2 or entry.content[:300]
        return entry.level3 or entry.content
    if isinstance(entry, DecisionEntry):
        if level == KnowledgeLevel.L1_SUMMARY:
            return f"Decision: {entry.answer[:80]}"
        elif level == KnowledgeLevel.L2_REASONING:
            return f"Decision: {entry.answer}\nWhy: {entry.reasoning[:200]}"
        alts = "; ".join(f"{n}: {r}" for n, r in entry.alternatives[:3])
        return f"Decision: {entry.answer}\nWhy: {entry.reasoning}\nAlternatives: {alts}"
    if isinstance(entry, PatternEntry):
        if level == KnowledgeLevel.L1_SUMMARY:
            return f"Pattern: {entry.name} ({entry.category})"
        elif level == KnowledgeLevel.L2_REASONING:
            return f"Pattern: {entry.name}\n{entry.description[:200]}"
        ex = "\n".join(entry.examples[:3])
        return f"Pattern: {entry.name}\n{entry.description}\nExamples:\n{ex}"
    return entry.content if hasattr(entry, "content") else str(entry)[:100]


class ContextBuilder:
    def __init__(self, store: MemoryStore, model_size: str = "7b"):
        budget = TOKEN_BUDGETS.get(model_size, 8192)
        self._total_budget = budget - SYSTEM_OVERHEAD
        self._store = store

    def build(self, task: str, top_k: int = 10, include_decisions: bool = True) -> str:
        scored = self._store.search(task, top_k=top_k)
        scored.sort(key=lambda x: (x[1].priority.value if isinstance(x[1].priority, MemoryPriority) else 99, -x[0]))

        parts = []
        remaining = self._total_budget

        for score, entry in scored:
            priority = entry.priority if isinstance(entry.priority, MemoryPriority) else MemoryPriority.P4_RESEARCH
            budget_ratio = PRIORITY_BUDGET.get(priority, 0.08)
            entry_budget = int(self._total_budget * budget_ratio)
            entry_budget = min(entry_budget, remaining)
            if entry_budget < 10:
                continue

            if entry_budget >= 100:
                text = _extract_level(entry, KnowledgeLevel.L3_EVIDENCE)
            elif entry_budget >= 30:
                text = _extract_level(entry, KnowledgeLevel.L2_REASONING)
            else:
                text = _extract_level(entry, KnowledgeLevel.L1_SUMMARY)

            tokens_needed = _estimate_tokens(text)
            if tokens_needed > remaining:
                text = text[:remaining * 4]
            remaining -= _estimate_tokens(text)

            type_tag = f"[{entry.type}]"
            parts.append(f"{type_tag} {text}")

        if include_decisions:
            for entry in self._store._entries.values():
                if entry.type == "decision" and remaining > 20:
                    line = f"[Decision] {entry.question} -> {entry.answer}"
                    if _estimate_tokens(line) <= remaining:
                        parts.append(line)
                        remaining -= _estimate_tokens(line)

        return "\n\n".join(parts)

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for e in self._store._entries.values():
            pname = e.priority.name if isinstance(e.priority, MemoryPriority) else "?"
            counts[pname] = counts.get(pname, 0) + 1
        return "Memory: " + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
