"""
igris.core.cia.decision_cache
--------------------------------
Decision Memory — CIA Level 6.

Caches every architecture decision so the LLM never re-evaluates the same
choice twice. Keyed by normalized question text.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import CIAStore, Decision

if TYPE_CHECKING:
    pass


def _normalize(question: str) -> str:
    """Normalize a question for lookup."""
    return question.lower().strip().rstrip("?").strip()


class DecisionCache:
    """Cache for architecture decisions. Never re-think the same question."""

    def __init__(self, store: CIAStore):
        self.store = store

    def get_or_compute(
        self,
        question: str,
        compute_fn,
        reasoning: str = "",
        alternatives: list[tuple[str, str]] | None = None,
    ) -> Decision:
        """Return cached decision if available, otherwise compute and cache."""
        existing = self.store.find_decision(question)
        if existing:
            existing.touch()
            self.store._save_decision(existing)
            return existing

        answer = compute_fn()
        decision = Decision(
            id=f"dec_{_normalize(question).replace(' ', '_')[:40]}",
            question=question,
            answer=answer,
            reasoning=reasoning,
            alternatives=alternatives or [],
            created_at=time.time(),
        )
        self.store.put_decision(decision)
        return decision

    def find(self, question: str) -> Decision | None:
        """Look up a decision by question similarity."""
        norm = _normalize(question)
        for d in self.store._decisions.values():
            if norm in _normalize(d.question) or _normalize(d.question) in norm:
                return d
        return None

    def all_decisions(self) -> list[Decision]:
        return sorted(
            self.store._decisions.values(),
            key=lambda d: d.last_used,
            reverse=True,
        )
