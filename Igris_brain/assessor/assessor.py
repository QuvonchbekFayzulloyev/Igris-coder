"""
IGRIS BRAIN — Assessor
======================
Scores any knowledge item (brick, rule, chain, experience, observation)
on the four standard dimensions:

    situation   (contextual relevance / how bound to a context)
    information (intrinsic completeness / accuracy)
    volume      (granularity / atomicity, inverted)
    semantics   (meaning richness / interpretability)

and computes an overall QualityIndex in [0, 1] using the standard weights.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .standards import DEFAULT_WEIGHTS, DIMENSIONS, quality_band

# ---------------------------------------------------------------- #
# KnowledgeItem (normalized input)
# ---------------------------------------------------------------- #

@dataclass
class KnowledgeItem:
    """Normalized view of anything the agent holds."""

    id: str = ""
    kind: str = "item"            # brick | rule | chain | experience | observation | memory
    content: str = ""
    surface_forms: dict = field(default_factory=dict)   # lang -> [forms]
    domains: list = field(default_factory=list)
    code_template: Optional[str] = None
    # context-bound signals
    sessions: list = field(default_factory=list)        # episodic anchor
    timestamps: list = field(default_factory=list)      # time anchor
    files: list = field(default_factory=list)           # file anchor
    # completeness signals
    summary: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeItem":
        return cls(
            id=d.get("id", ""),
            kind=d.get("kind", d.get("type", "item")),
            content=d.get("content", d.get("description", "")),
            surface_forms=d.get("surface_forms", {}),
            domains=d.get("domains", []),
            code_template=d.get("code_template"),
            sessions=d.get("sessions", []),
            timestamps=d.get("timestamps", []),
            files=d.get("files", []),
            summary=d.get("summary", ""),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------- #
# Assessment result
# ---------------------------------------------------------------- #

@dataclass
class Assessment:
    """Result of scoring one knowledge item / query."""

    item_id: str
    kind: str
    scores: dict[str, float] = field(default_factory=dict)   # dimension -> 0..1
    quality: float = 0.0
    band: str = ""
    band_desc: str = ""
    signals: dict[str, list] = field(default_factory=dict)   # evidence per dim

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "kind": self.kind,
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
            "quality": round(self.quality, 3),
            "band": self.band,
            "band_desc": self.band_desc,
        }


# ---------------------------------------------------------------- #
# Scoring helpers
# ---------------------------------------------------------------- #

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _token_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


# ---------------------------------------------------------------- #
# KnowledgeAssessor
# ---------------------------------------------------------------- #

class KnowledgeAssessor:
    """The Refactor Machine's scoring engine."""

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        # normalize weights
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}

    # ---- dimension scorers ------------------------------------ #

    def _score_situation(self, item: KnowledgeItem) -> tuple[float, list[str]]:
        """situation-dependency: HIGH when anchored to session/time/files.

        Brick ideal = 0 (context-free). We report the dependency itself;
        the classifier converts it.
        """
        evidence: list[str] = []
        score = 0.0
        if item.sessions:
            score += 0.4
            evidence.append(f"{len(item.sessions)} session(s)")
        if item.timestamps:
            score += 0.3
            evidence.append(f"{len(item.timestamps)} timestamp(s)")
        if item.files:
            score += 0.2
            evidence.append(f"{len(item.files)} file(s)")
        # episodic types score high by nature
        if item.kind in ("experience", "observation", "short-turn", "decision-log"):
            score += 0.3
            evidence.append(f"kind={item.kind}")
        return _clamp(score), evidence

    def _score_information(self, item: KnowledgeItem) -> tuple[float, list[str]]:
        """intrinsic completeness: self-contained + accurate-looking."""
        evidence: list[str] = []
        score = 0.0
        n = _token_count(item.content)
        if n >= 3:
            score += 0.3
            evidence.append(f"content {n} tokens")
        if item.summary:
            score += 0.2
            evidence.append("has summary")
        if item.code_template:
            score += 0.2
            evidence.append("has code template")
        if item.domains:
            score += 0.15
            evidence.append(f"{len(item.domains)} domain(s)")
        if item.surface_forms:
            score += 0.15
            evidence.append(f"{len(item.surface_forms)} language(s)")
        return _clamp(score), evidence

    def _score_volume(self, item: KnowledgeItem) -> tuple[float, list[str]]:
        """atomicity: small + single-purpose is brick-like (HIGH)."""
        evidence: list[str] = []
        n = _token_count(item.content)
        # atomic items are short: 1..30 tokens -> high score
        if n <= 5:
            score = 0.9
        elif n <= 15:
            score = 0.7
        elif n <= 50:
            score = 0.5
        elif n <= 200:
            score = 0.3
        else:
            score = 0.1
        evidence.append(f"{n} tokens")
        # composite kinds are low-atomicity
        if item.kind in ("experience", "solution-memory", "session"):
            score -= 0.2
            evidence.append(f"composite kind={item.kind}")
        return _clamp(score), evidence

    def _score_semantics(self, item: KnowledgeItem) -> tuple[float, list[str]]:
        """meaning richness: multi-language forms, links, traceability."""
        evidence: list[str] = []
        score = 0.0
        if item.surface_forms:
            langs = len(item.surface_forms)
            forms = sum(len(v) for v in item.surface_forms.values())
            score += min(0.4, 0.15 * langs + 0.05 * forms)
            evidence.append(f"{langs} lang(s), {forms} form(s)")
        if item.code_template:
            score += 0.25
            evidence.append("code mapping")
        if item.metadata.get("trace"):
            score += 0.2
            evidence.append("traceable")
        if item.domains:
            score += 0.15
            evidence.append("domain-tagged")
        if item.metadata.get("linked_to"):
            score += 0.15
            evidence.append(f"linked to {len(item.metadata['linked_to'])}")
        return _clamp(score), evidence

    # ---- main entry ------------------------------------------- #

    def assess(self, item: KnowledgeItem) -> Assessment:
        """Score an item on all four dimensions + overall quality."""
        scores: dict[str, float] = {}
        signals: dict[str, list] = {}
        scorers = {
            "situation": self._score_situation,
            "information": self._score_information,
            "volume": self._score_volume,
            "semantics": self._score_semantics,
        }
        for key, scorer in scorers.items():
            val, ev = scorer(item)
            scores[key] = val
            signals[key] = ev

        quality = sum(self.weights[k] * scores[k] for k in scores)
        band, desc = quality_band(quality)
        return Assessment(
            item_id=item.id,
            kind=item.kind,
            scores=scores,
            quality=quality,
            band=band,
            band_desc=desc,
            signals=signals,
        )

    def assess_dict(self, d: dict) -> Assessment:
        return self.assess(KnowledgeItem.from_dict(d))


# ---------------------------------------------------------------- #
# QueryAssessor (query semantics, part of dimension 4)
# ---------------------------------------------------------------- #

class QueryAssessor:
    """Scores a user query for semantic clarity and ambiguity."""

    def __init__(self):
        self.ambiguity_words = {
            "uz": ["nima", "qanday", "yaxshi", "kerak", "balki", "xohlayman", "shunaqa"],
            "en": ["what", "how", "maybe", "something", "like", "want", "sort of"],
        }

    def assess(self, query: str, lang: str = "en") -> dict:
        tokens = re.findall(r"[a-zA-Z'’\-]+", query.lower())
        n = len(tokens)
        lang_amb = self.ambiguity_words.get(lang, [])
        amb_count = sum(1 for t in tokens if t in lang_amb)
        # ambiguity: 0 when none, 1 when mostly vague
        ambiguity = min(1.0, (amb_count / max(n, 1)) * 3.0)
        # clarity inverse of ambiguity, penalized by very short queries
        clarity = _clamp(1.0 - ambiguity - (0.3 if n < 2 else 0.0))
        return {
            "tokens": n,
            "ambiguity": round(ambiguity, 3),
            "semantic_clarity": round(clarity, 3),
            "language": lang,
        }
