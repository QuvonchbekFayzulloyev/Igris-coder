"""
IGRIS BRAIN — Linker
====================
Connects knowledge items into a graph: aloqalarni bir-biri bilan bog'lash.

Link types (standard):
  - semantic     : close meaning (surface-form overlap / vector similarity)
  - domain       : same knowledge domain
  - composition  : a brick is used by a rule / chain
  - sequence     : experiences sharing a session/time anchor

Rules: see standards.LINK_RULES (same_semantic_min, max_links_per_item, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .assessor import KnowledgeItem
from .standards import LINK_RULES


# ---------------------------------------------------------------- #
# Link
# ---------------------------------------------------------------- #

@dataclass
class KnowledgeLink:
    source: str
    target: str
    link_type: str          # semantic | domain | composition | sequence
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.link_type,
            "weight": round(self.weight, 3),
        }


# ---------------------------------------------------------------- #
# Surface-form similarity (cheap, deterministic)
# ---------------------------------------------------------------- #

def _surface_overlap(a: KnowledgeItem, b: KnowledgeItem) -> float:
    """Containment similarity of surface forms across languages.

    Uses max(|A∩B|/|A|, |A∩B|/|B|): one item's full form set contained in
    the other's is a strong semantic signal (e.g. {inverse} vs
    {inverse, invert}). Jaccard is too strict for small sets.
    """
    forms_a = {f for v in a.surface_forms.values() for f in v}
    forms_b = {f for v in b.surface_forms.values() for f in v}
    if not forms_a or not forms_b:
        return 0.0
    inter = forms_a & forms_b
    if not inter:
        return 0.0
    return max(len(inter) / len(forms_a), len(inter) / len(forms_b))


def _domain_overlap(a: KnowledgeItem, b: KnowledgeItem) -> bool:
    return bool(set(a.domains) & set(b.domains))


def _session_overlap(a: KnowledgeItem, b: KnowledgeItem) -> bool:
    return bool(set(a.sessions) & set(b.sessions))


# ---------------------------------------------------------------- #
# RelationshipLinker
# ---------------------------------------------------------------- #

class RelationshipLinker:
    """Builds and queries the knowledge graph."""

    def __init__(self, max_links: int = LINK_RULES.max_links_per_item):
        self.max_links = max_links
        self.links: list[KnowledgeLink] = []
        self.graph: dict[str, list[KnowledgeLink]] = {}   # item_id -> links

    def reset(self):
        self.links.clear()
        self.graph.clear()

    # ---- linking ---------------------------------------------- #

    def link_pair(self, a: KnowledgeItem, b: KnowledgeItem) -> Optional[KnowledgeLink]:
        """Create the best single link between two items, if any."""
        best: Optional[KnowledgeLink] = None

        # composition: brick used by rule/chain
        if a.kind in ("brick", "concept") and b.kind in ("rule", "chain", "concept"):
            used = False
            if b.metadata.get("uses"):
                used = a.id in b.metadata["uses"]
            elif a.code_template and a.id in (b.content or ""):
                used = True
            if used:
                best = KnowledgeLink(a.id, b.id, "composition", 1.0)

        # semantic similarity
        sim = _surface_overlap(a, b)
        if sim >= LINK_RULES.same_semantic_min:
            candidate = KnowledgeLink(a.id, b.id, "semantic", sim)
            if best is None or candidate.weight > best.weight:
                best = candidate

        # domain link
        if _domain_overlap(a, b):
            candidate = KnowledgeLink(a.id, b.id, "domain",
                                      LINK_RULES.same_domain_weight)
            if best is None or candidate.weight > best.weight:
                best = candidate

        # sequence link (experiences sharing a session)
        if _session_overlap(a, b) and (a.kind in ("experience", "observation")
                                       or b.kind in ("experience", "observation")):
            candidate = KnowledgeLink(a.id, b.id, "sequence", 0.7)
            if best is None or candidate.weight > best.weight:
                best = candidate

        if best is not None and best.source != best.target:
            best.weight = round(best.weight, 3)
        return best

    def add(self, link: KnowledgeLink) -> "RelationshipLinker":
        self.links.append(link)
        self.graph.setdefault(link.source, []).append(link)
        self.graph.setdefault(link.target, []).append(link)
        return self

    def link_all(self, items: list[KnowledgeItem]) -> list[KnowledgeLink]:
        """Link every pair, respecting per-item link cap."""
        self.reset()
        degree: dict[str, int] = {}
        pairs = [(a, b) for i, a in enumerate(items) for b in items[i + 1:]]

        # sort candidates by potential weight so the strongest links survive
        candidates = []
        for a, b in pairs:
            link = self.link_pair(a, b)
            if link:
                candidates.append((link.weight, link))
        candidates.sort(key=lambda x: -x[0])

        for _, link in candidates:
            if degree.get(link.source, 0) >= self.max_links:
                continue
            if degree.get(link.target, 0) >= self.max_links:
                continue
            self.add(link)
            degree[link.source] = degree.get(link.source, 0) + 1
            degree[link.target] = degree.get(link.target, 0) + 1
        return self.links

    # ---- query ------------------------------------------------ #

    def neighbors(self, item_id: str) -> list[KnowledgeLink]:
        return self.graph.get(item_id, [])

    def links_of_type(self, link_type: str) -> list[KnowledgeLink]:
        return [l for l in self.links if l.link_type == link_type]

    def stats(self) -> dict:
        types: dict[str, int] = {}
        for l in self.links:
            types[l.link_type] = types.get(l.link_type, 0) + 1
        return {
            "total_links": len(self.links),
            "nodes": len(self.graph),
            "by_type": types,
        }
