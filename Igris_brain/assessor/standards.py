"""
IGRIS BRAIN — Assessment Standards
==================================
The STANDARD for deciding:
  - what a BRICK is vs what EXPERIENCE is,
  - how to score situation, information, volume, and query semantics,
  - when to link knowledge items, and
  - how to analyze the process continuously.

Grounded in:
  * DIKW pyramid (Data -> Information -> Knowledge -> Wisdom)
  * Wang & Strong knowledge-quality dimensions
      (intrinsic / contextual / representational / accessibility)
  * Tulving semantic (brick-like) vs episodic (experience-like) memory

Every score is normalized to [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------- #
# Scales
# ---------------------------------------------------------------- #

SCORE_MIN = 0.0
SCORE_MAX = 1.0


# ---------------------------------------------------------------- #
# The four assessment dimensions (user-specified + standard-aligned)
# ---------------------------------------------------------------- #

@dataclass
class Dimension:
    """One assessment dimension with weight + meaning."""

    key: str                # situation | information | volume | semantics
    label: str
    wang_strong: str        # which Wang & Strong cluster it belongs to
    dijk: str               # DIKW layer it operates on
    description: str


DIMENSIONS: dict[str, Dimension] = {
    "situation": Dimension(
        key="situation",
        label="Vaziyat / Situation (contextual relevance)",
        wang_strong="Contextual (relevance, timeliness, value-added)",
        dijk="Information (know-what) -> Knowledge (know-how)",
        description=(
            "How bound the item is to a concrete situation. High = tied to a "
            "specific context (episodic); low = context-free (semantic). "
            "Experience scores HIGH here; bricks score LOW."
        ),
    ),
    "information": Dimension(
        key="information",
        label="Ma'lumot / Information (intrinsic quality)",
        wang_strong="Intrinsic (accuracy, completeness, believability)",
        dijk="Data (know-nothing) -> Information (know-what)",
        description=(
            "How complete, accurate and self-contained the item is. "
            "A brick is maximally self-contained; a raw observation is not."
        ),
    ),
    "volume": Dimension(
        key="volume",
        label="Hajm / Volume (granularity + size)",
        wang_strong="Representational (concise, consistent)",
        dijk="Data (raw volume)",
        description=(
            "Size and granularity. Atomic/modular items are small and single-"
            "purpose; accumulated experience is large and composite. "
            "Inverted: bricks score HIGH (atomic, small), experience LOW."
        ),
    ),
    "semantics": Dimension(
        key="semantics",
        label="So'rov ma'nosi / Query semantics (meaning richness)",
        wang_strong="Representational (interpretability, ease of understanding)",
        dijk="Knowledge (know-how) -> Wisdom (know-why)",
        description=(
            "How rich and unambiguous the meaning is: surface forms, "
            "multi-language coverage, rule links, traceability."
        ),
    ),
}

# Default weights (sum = 1.0)
DEFAULT_WEIGHTS: dict[str, float] = {
    "situation": 0.25,
    "information": 0.25,
    "volume": 0.20,
    "semantics": 0.30,
}


# ---------------------------------------------------------------- #
# Classification thresholds
# ---------------------------------------------------------------- #

@dataclass
class ClassificationThresholds:
    """Thresholds that decide brick vs experience vs derived."""

    # A pure brick scores LOW on situation-dependency (context-free) and
    # HIGH on information/volume-atomicity/semantics.
    brick_situation_max: float = 0.30   # situation-dependency must be low
    brick_quality_min: float = 0.65     # overall quality must be high
    # Alternative brick path: a terse-but-unambiguous item (e.g. a bare
    # code mapping) can qualify via high brickness even if intrinsic
    # completeness is thin. Brickness = 0.40*(1-situation) + 0.20*info
    # + 0.20*volume + 0.20*semantics.
    brick_brickness_min: float = 0.80
    # A pure experience scores HIGH on situation-dependency.
    experience_situation_min: float = 0.50
    experience_temporality_min: float = 0.40  # tied to time / session
    # When both are borderline -> derived/composite
    derive_threshold: float = 0.40


THRESHOLDS = ClassificationThresholds()


# ---------------------------------------------------------------- #
# Quality index bands (DIKW-aligned)
# ---------------------------------------------------------------- #

QUALITY_BANDS = [
    (0.85, "wisdom", "Wisdom — strategic, reusable, cross-situation"),
    (0.70, "knowledge", "Knowledge — verified, actionable, well-linked"),
    (0.50, "information", "Information — structured but not yet verified"),
    (0.0, "data", "Data — raw, unverified, low structure"),
]


def quality_band(score: float) -> tuple[str, str]:
    """Map a quality score to a DIKW band."""
    for threshold, name, desc in QUALITY_BANDS:
        if score >= threshold:
            return name, desc
    return "data", QUALITY_BANDS[-1][2]


# ---------------------------------------------------------------- #
# Linking rules
# ---------------------------------------------------------------- #

@dataclass
class LinkRules:
    """Rules for connecting knowledge items into a graph."""

    same_semantic_min: float = 0.60     # vector/semantic similarity to link
    same_surface_boost: float = 0.15    # boost if surface forms overlap
    same_domain_weight: float = 0.10    # weight if same domain
    max_links_per_item: int = 8
    link_types: tuple[str, ...] = (
        "semantic",     # close meaning
        "domain",       # same knowledge domain
        "composition",  # brick used by rule / chain
        "sequence",     # experience sequence
    )


LINK_RULES = LinkRules()


# ---------------------------------------------------------------- #
# Telemetry rules (continuous process analysis)
# ---------------------------------------------------------------- #

@dataclass
class TelemetryRules:
    """Rules for continuous process analysis."""

    window_size: int = 50              # rolling window of resolutions
    confidence_decline_threshold: float = 0.10  # drop over window -> alert
    failure_rate_warn: float = 0.30    # >30% failures -> warn
    healing_trigger_min: float = 0.50  # confidence below -> suggest healing
    consolidate_every: int = 25        # suggest consolidation every N items


TELEMETRY = TelemetryRules()


# ---------------------------------------------------------------- #
# Public accessor
# ---------------------------------------------------------------- #

def standard_summary() -> str:
    """Compact machine-readable summary of the standard."""
    lines = ["IGRIS ASSESSMENT STANDARD v1.0", "=" * 40]
    lines.append("Scales: 0.0 .. 1.0 (normalized)")
    lines.append("")
    lines.append("Dimensions (weights):")
    for key, dim in DIMENSIONS.items():
        w = DEFAULT_WEIGHTS[key]
        lines.append(f"  - {key:<11} w={w:<5} {dim.label}")
    lines.append("")
    lines.append("Classification (Tulving semantic vs episodic):")
    t = THRESHOLDS
    lines.append(f"  - brick:        situation<={t.brick_situation_max} AND (quality>={t.brick_quality_min} OR brickness>={t.brick_brickness_min})")
    lines.append(f"  - experience:   situation>={t.experience_situation_min} AND temporality>={t.experience_temporality_min}")
    lines.append(f"  - derived:      otherwise (composite, {t.derive_threshold} boundary)")
    lines.append("")
    lines.append("Quality bands (DIKW):")
    for threshold, name, _ in QUALITY_BANDS:
        lines.append(f"  - {name:<11} >= {threshold}")
    lines.append("")
    lines.append("Linking:")
    lines.append(f"  - semantic similarity >= {LINK_RULES.same_semantic_min}")
    lines.append(f"  - max {LINK_RULES.max_links_per_item} links/item")
    lines.append("")
    lines.append("Telemetry:")
    lines.append(f"  - window={TELEMETRY.window_size}, conf decline>{TELEMETRY.confidence_decline_threshold}, fail rate>{TELEMETRY.failure_rate_warn}")
    return "\n".join(lines)
