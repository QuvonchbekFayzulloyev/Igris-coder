"""
IGRIS BRAIN — Classifier
========================
Decides, per item, whether it is a BRICK (semantic/atomic), EXPERIENCE
(episodic/accumulated), or DERIVED (composite, in-between).

Decision matrix (Tulving semantic vs episodic, grounded in the standards):

  criterion          brick (semantic)          experience (episodic)
  ----------------   ------------------------  -------------------------
  granularity        atomic / modular          holistic / composite
  context-dependency context-free (low)        context-heavy (high)
  decay              stable                    plastic / evolving
  retrieval          declarative / direct      procedural / associative
  quality band       knowledge/wisdom          information/data
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .assessor import Assessment, KnowledgeItem, KnowledgeAssessor
from .standards import THRESHOLDS


# ---------------------------------------------------------------- #
# Classification result
# ---------------------------------------------------------------- #

@dataclass
class Classification:
    """Result of classifying one item."""

    item_id: str
    category: str = "derived"          # brick | experience | derived
    brickness: float = 0.0             # 0..1 how much it behaves as brick
    experientiality: float = 0.0       # 0..1 how much it behaves as experience
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "category": self.category,
            "brickness": round(self.brickness, 3),
            "experientiality": round(self.experientiality, 3),
            "reasons": self.reasons,
        }


# ---------------------------------------------------------------- #
# Classifier
# ---------------------------------------------------------------- #

class BrickExperienceClassifier:
    """Applies the standard decision matrix to an assessment."""

    def __init__(self, assessor: Optional[KnowledgeAssessor] = None):
        self.assessor = assessor or KnowledgeAssessor()

    # ---- score composition ------------------------------------ #

    def _brickness(self, a: Assessment) -> float:
        """Brick-like = low situation-dependency + high quality.

        Brickness blends: (1 - situation) heavily, plus information,
        volume (atomicity) and semantics.
        """
        s = a.scores
        return (
            0.40 * (1.0 - s.get("situation", 0))
            + 0.20 * s.get("information", 0)
            + 0.20 * s.get("volume", 0)
            + 0.20 * s.get("semantics", 0)
        )

    def _experientiality(self, a: Assessment, item: KnowledgeItem) -> float:
        """Experience-like = high situation-dependency + temporality + size."""
        s = a.scores
        temporal = min(1.0, len(item.timestamps) * 0.2 + len(item.sessions) * 0.3)
        return (
            0.45 * s.get("situation", 0)
            + 0.25 * temporal
            + 0.30 * (1.0 - s.get("volume", 0))   # composite = not atomic
        )

    # ---- decision --------------------------------------------- #

    def classify(self, item: KnowledgeItem) -> Classification:
        a = self.assessor.assess(item)
        return self.classify_assessment(a, item)

    def classify_assessment(
        self, a: Assessment, item: Optional[KnowledgeItem] = None
    ) -> Classification:
        item = item or KnowledgeItem(id=a.item_id, kind=a.kind)
        brickness = self._brickness(a)
        experientiality = self._experientiality(a, item)
        reasons: list[str] = []

        t = THRESHOLDS
        is_brick = (
            a.scores.get("situation", 1.0) <= t.brick_situation_max
            and (a.quality >= t.brick_quality_min
                 or brickness >= t.brick_brickness_min)
        )
        is_experience = (
            a.scores.get("situation", 0.0) >= t.experience_situation_min
            and experientiality >= t.experience_temporality_min
        )

        if is_brick and not is_experience:
            category = "brick"
            reasons.append("context-free + high intrinsic quality")
            reasons.append(f"brickness={brickness:.2f}")
        elif is_experience and not is_brick:
            category = "experience"
            reasons.append("context-bound + episodic anchors")
            reasons.append(f"experientiality={experientiality:.2f}")
        elif is_brick and is_experience:
            category = "derived"
            reasons.append("both brick-like and experience-like (composite)")
        else:
            category = "derived"
            reasons.append("below both thresholds (raw/transitional)")

        if a.band in ("data", "information"):
            reasons.append(f"band={a.band} — not yet consolidated to knowledge")

        return Classification(
            item_id=a.item_id,
            category=category,
            brickness=brickness,
            experientiality=experientiality,
            reasons=reasons,
        )

    def classify_dict(self, d: dict) -> Classification:
        item = KnowledgeItem.from_dict(d)
        return self.classify(item)

    # ---- batch ------------------------------------------------- #

    def classify_batch(self, items: list[KnowledgeItem]) -> list[Classification]:
        return [self.classify(i) for i in items]
