"""
igris.core.research.confidence_scorer
----------------------------------------
Stage 12: Score confidence for every recommendation.

Each recommendation gets a confidence score based on:
- Number of supporting sources
- Source diversity (official docs vs blogs)
- Cross-validation result
- Community adoption (npm downloads, GitHub stars)
- Recency of evidence

Recommendations below 40% confidence are NEVER suggested.
"""
from __future__ import annotations

from . import ArchitectureRecommendation, CrossValidatedClaim, QualityIssue

# Confidence thresholds
HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.6
LOW_CONFIDENCE = 0.4
REJECT_THRESHOLD = 0.4


def score_recommendations(
    recommendations: list[ArchitectureRecommendation],
    validated_claims: list[CrossValidatedClaim],
    quality_issues: list[QualityIssue],
) -> list[ArchitectureRecommendation]:
    """
    Adjust confidence scores based on cross-validation and quality review.
    Returns recommendations with updated scores, sorted by confidence.
    """
    claim_map = _build_claim_map(validated_claims)

    for rec in recommendations:
        base_confidence = rec.confidence
        validation_bonus = _calc_validation_bonus(rec, claim_map)
        quality_penalty = _calc_quality_penalty(rec, quality_issues)

        adjusted = base_confidence + validation_bonus - quality_penalty
        rec.confidence = max(0.0, min(1.0, adjusted))

    recommendations.sort(key=lambda r: r.confidence, reverse=True)

    return [r for r in recommendations if r.confidence >= REJECT_THRESHOLD]


def _build_claim_map(claims: list[CrossValidatedClaim]) -> dict[str, list[CrossValidatedClaim]]:
    """Build a map from technology name to related claims."""
    claim_map: dict[str, list[CrossValidatedClaim]] = {}
    for claim in claims:
        words = claim.claim.lower().split()
        for word in words:
            if len(word) > 3:
                if word not in claim_map:
                    claim_map[word] = []
                claim_map[word].append(claim)
    return claim_map


def _calc_validation_bonus(
    rec: ArchitectureRecommendation,
    claim_map: dict[str, list[CrossValidatedClaim]],
) -> float:
    """Calculate confidence bonus from cross-validation evidence."""
    choice_words = set(rec.choice.lower().split())
    matching_claims = []
    for word in choice_words:
        if word in claim_map:
            matching_claims.extend(claim_map[word])

    if not matching_claims:
        return 0.0

    avg_confidence = sum(c.confidence for c in matching_claims) / len(matching_claims)
    source_count = sum(len(c.supporting_sources) for c in matching_claims)

    bonus = avg_confidence * 0.15
    if source_count >= 5:
        bonus += 0.05
    if source_count >= 10:
        bonus += 0.05

    return bonus


def _calc_quality_penalty(
    rec: ArchitectureRecommendation,
    quality_issues: list[QualityIssue],
) -> float:
    """Calculate confidence penalty from quality issues."""
    penalty = 0.0
    component_lower = rec.component.lower()

    for issue in quality_issues:
        if issue.severity == "critical":
            penalty += 0.05
        elif issue.severity == "warning":
            penalty += 0.02

    return min(0.2, penalty)


def score_alternatives(
    rec: ArchitectureRecommendation,
    validated_claims: list[CrossValidatedClaim],
) -> ArchitectureRecommendation:
    """Score and sort alternatives based on evidence."""
    claim_map = _build_claim_map(validated_claims)

    scored_alts = []
    for alt_name, alt_conf in rec.alternatives:
        alt_words = set(alt_name.lower().split())
        matching = []
        for word in alt_words:
            if word in claim_map:
                matching.extend(claim_map[word])

        if matching:
            avg = sum(c.confidence for c in matching) / len(matching)
            final = (alt_conf + avg) / 2
        else:
            final = alt_conf * 0.8

        scored_alts.append((alt_name, final))

    scored_alts.sort(key=lambda x: x[1], reverse=True)
    rec.alternatives = scored_alts
    return rec


def get_confidence_summary(
    recommendations: list[ArchitectureRecommendation],
) -> dict[str, float]:
    """Return a summary of confidence scores by category."""
    summary: dict[str, float] = {}
    for rec in recommendations:
        summary[rec.component] = rec.confidence
    if recommendations:
        summary["__overall__"] = sum(r.confidence for r in recommendations) / len(recommendations)
    return summary


def reject_low_confidence(
    recommendations: list[ArchitectureRecommendation],
    threshold: float = REJECT_THRESHOLD,
) -> tuple[list[ArchitectureRecommendation], list[ArchitectureRecommendation]]:
    """Split recommendations into accepted and rejected based on confidence."""
    accepted = [r for r in recommendations if r.confidence >= threshold]
    rejected = [r for r in recommendations if r.confidence < threshold]
    return accepted, rejected
