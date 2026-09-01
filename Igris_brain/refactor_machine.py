"""
IGRIS BRAIN — Refactor Machine
==============================
The meta-engine that continuously evaluates the brain itself:

    1. ASSESS   every knowledge item & query on 4 dimensions
    2. CLASSIFY brick vs experience vs derived
    3. LINK     items into a knowledge graph
    4. ANALYZE  the process stream (telemetry)
    5. SUGGEST  concrete refactor actions

This is what turns the static brick system into a self-improving
"refactor machine" that can answer: WHEN is this a brick, WHEN is this
experience — by fully evaluating situation, information, volume, and
query semantics.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from assessor.assessor import (
    KnowledgeAssessor,
    KnowledgeItem,
    QueryAssessor,
    Assessment,
)
from assessor.classifier import BrickExperienceClassifier, Classification
from assessor.linker import RelationshipLinker, KnowledgeLink
from assessor.telemetry import ProcessAnalyzer, ResolutionEvent, ProcessSnapshot
from assessor.standards import standard_summary, DEFAULT_WEIGHTS, DIMENSIONS

# ---------------------------------------------------------------- #
# Convenience converters from brain objects
# ---------------------------------------------------------------- #

def item_from_brick(brick) -> KnowledgeItem:
    """Convert a brain Brick into an assessable KnowledgeItem.

    Content is built from the brick's actual knowledge: code template +
    surface forms — not the bare canonical_id — so the information score
    reflects what the brick really holds.
    """
    forms = [f for v in brick.surface_forms.values() for f in v]
    content = " ".join(filter(None, [brick.code_template, " ".join(forms)]))
    return KnowledgeItem(
        id=brick.canonical_id,
        kind=brick.kind,
        content=content or brick.canonical_id,
        surface_forms=brick.surface_forms,
        domains=brick.domains,
        code_template=brick.code_template,
        metadata={"trace": True},
    )


def item_from_rule(rule) -> KnowledgeItem:
    """Convert a brain Rule into a KnowledgeItem.

    `uses` lists referenced brick ids so the linker can create composition
    links (brick -> rule).
    """
    referenced = [m.get("id") for m in rule.pattern if "id" in m]
    return KnowledgeItem(
        id=rule.name,
        kind="rule",
        content=f"{rule.pattern} -> {rule.action}",
        domains=rule.domains,
        metadata={"trace": True, "uses": referenced},
    )


def item_from_chain(chain) -> KnowledgeItem:
    return KnowledgeItem(
        id=chain.name,
        kind="chain",
        content=", ".join(r.name for r in chain.rules),
        domains=[],
        metadata={"uses": [r.name for r in chain.rules]},
    )


# ---------------------------------------------------------------- #
# RefactorMachine
# ---------------------------------------------------------------- #

class RefactorMachine:
    """Continuously assesses and refactors the brain's knowledge."""

    def __init__(self, agent=None, telemetry_path: Optional[str] = None):
        self.agent = agent                     # optional IgrisAgent back-ref
        self.assessor = KnowledgeAssessor()
        self.classifier = BrickExperienceClassifier(self.assessor)
        self.query_assessor = QueryAssessor()
        self.linker = RelationshipLinker()
        # Telemetry faylga saqlanadi (server qayta ishga tushganda tarix yo'qolmaydi)
        if telemetry_path is None:
            telemetry_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "reports", "telemetry.jsonl"
            )
        self.telemetry = ProcessAnalyzer(persist_path=telemetry_path)
        self._last_link_items: list[KnowledgeItem] = []
        self._last_links: list[KnowledgeLink] = []

    # =========================================================== #
    # 1. ASSESS
    # =========================================================== #

    def assess_item(self, item: KnowledgeItem) -> Assessment:
        return self.assessor.assess(item)

    def assess_query(self, query: str, lang: str = "en") -> dict:
        return self.query_assessor.assess(query, lang)

    def inspect_agent(self) -> list[KnowledgeItem]:
        """Collect all knowledge items from the attached brain agent."""
        items: list[KnowledgeItem] = []
        if not self.agent:
            return items
        for brick in self.agent.bricks.bricks.values():
            items.append(item_from_brick(brick))
        for rule in self.agent.knowledge.rules.values():
            items.append(item_from_rule(rule))
        for chain in self.agent.chains.chains.values():
            items.append(item_from_chain(chain))
        return items

    # =========================================================== #
    # 2. CLASSIFY
    # =========================================================== #

    def classify_item(self, item: KnowledgeItem) -> Classification:
        return self.classifier.classify(item)

    def classify_agent(self) -> list[Classification]:
        items = self.inspect_agent()
        return self.classifier.classify_batch(items)

    # =========================================================== #
    # 3. LINK
    # =========================================================== #

    def link_agent(self) -> list[KnowledgeLink]:
        self._last_link_items = self.inspect_agent()
        self._last_links = self.linker.link_all(self._last_link_items)
        return self._last_links

    # =========================================================== #
    # 4. ANALYZE (continuous)
    # =========================================================== #

    def observe(self, query: str, result: dict) -> ProcessSnapshot:
        """Feed one agent resolution into the telemetry stream."""
        event = ResolutionEvent(
            query=query,
            status=result.get("status", "ok"),
            confidence=result.get("confidence", 0.0),
            engine=result.get("engine", "deterministic"),
            chains=result.get("chains", []),
            duration_ms=result.get("duration_ms", 0.0),
        )
        return self.telemetry.record(event)

    # =========================================================== #
    # 5. SUGGEST (refactor report)
    # =========================================================== #

    def refactor_report(self) -> dict:
        """Full assessment of the brain + process + suggestions."""
        items = self.inspect_agent()
        assessments = [self.assessor.assess(i) for i in items]
        classifications = self.classifier.classify_batch(items)
        self._last_link_items = items
        links = self.linker.link_all(items)

        # aggregate
        by_category: dict[str, int] = {}
        avg_quality = 0.0
        for c, a in zip(classifications, assessments):
            by_category[c.category] = by_category.get(c.category, 0) + 1
            avg_quality += a.quality
        avg_quality = avg_quality / max(len(assessments), 1)

        # dimension averages
        dim_avg: dict[str, float] = {}
        for key in DIMENSIONS:
            dim_avg[key] = sum(a.scores.get(key, 0) for a in assessments) / max(len(assessments), 1)

        return {
            "standard": standard_summary(),
            "inventory": {
                "items": len(items),
                "by_category": by_category,
                "avg_quality": round(avg_quality, 3),
                "dimension_averages": {k: round(v, 3) for k, v in dim_avg.items()},
            },
            "links": self.linker.stats(),
            "telemetry": self.telemetry.stats(),
            "classifications": [c.to_dict() for c in classifications[:20]],
            "top_links": [l.to_dict() for l in links[:15]],
        }

    # =========================================================== #
    # Top-level: evaluate one query end-to-end
    # =========================================================== #

    def evaluate_query(self, query: str, lang: str = "en") -> dict:
        """Assess query semantics + (if agent) resolve.

        Note: agent.resolve() already feeds telemetry via observe(), so we
        do NOT observe again here (avoid double-counting). We only attach
        the latest telemetry snapshot to the result.
        """
        qa = self.query_assessor.assess(query, lang)
        out: dict = {"query": query, "query_semantics": qa}
        if self.agent:
            t0 = time.time()
            result = self.agent.resolve(query)
            result["duration_ms"] = (time.time() - t0) * 1000.0
            out["resolution"] = result
            out["telemetry_snapshot"] = self.telemetry.snapshot().to_dict()
        return out

    def standards(self) -> str:
        return standard_summary()
