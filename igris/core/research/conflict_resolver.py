"""
igris.core.research.conflict_resolver
----------------------------------------
Stage 7: Resolve conflicting claims using weighted voting.

When sources disagree (e.g., "Redux is best" vs "Redux is dead"),
the resolver uses:
- Source weight (official docs > blogs)
- Recency (newer info weighted higher)
- Community signals (GitHub stars, npm downloads)
- Consensus (majority wins when weights are similar)
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import CrossValidatedClaim, SourceType, SOURCE_WEIGHTS

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

CONFLICT_RESOLVER_SYSTEM = """You are a conflict resolution agent. Given conflicting
claims about the same topic, determine the correct conclusion.

Consider:
1. Official documentation is the highest authority
2. Recency matters (2025 info beats 2022 info)
3. Community adoption (npm downloads, GitHub stars) indicates real-world usage
4. Majority of high-weight sources wins

For each conflict, provide:
- topic: what the conflict is about
- conclusion: the resolution
- winner: which claim is more accurate
- confidence: 0.0-1.0
- evidence: brief reasoning

Return a JSON array of resolution objects. No markdown fences."""


def _group_conflicts(claims: list[CrossValidatedClaim]) -> dict[str, list[CrossValidatedClaim]]:
    """Group claims that contradict each other."""
    groups: dict[str, list[CrossValidatedClaim]] = {}
    for claim in claims:
        if claim.contradicting_sources:
            key = _topic_key(claim.claim)
            if key not in groups:
                groups[key] = []
            groups[key].append(claim)
    return groups


def _topic_key(text: str) -> str:
    """Extract a topic key from claim text for grouping."""
    words = text.lower().split()
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "for", "in", "of", "to", "and", "or", "but", "not", "with"}
    content_words = [w for w in words if w not in stop_words and len(w) > 2]
    return " ".join(sorted(content_words[:5]))


async def resolve_conflicts(
    llm: OpenAICompatibleClient,
    validated_claims: list[CrossValidatedClaim],
) -> list[CrossValidatedClaim]:
    """
    Find and resolve conflicting claims.
    Returns the original claims with updated confidences.
    """
    conflict_groups = _group_conflicts(validated_claims)

    if not conflict_groups:
        return validated_claims

    for topic_key, group in conflict_groups.items():
        if len(group) < 2:
            continue

        claims_text = ""
        for i, c in enumerate(group):
            src_types = [s.value for s in c.source_types_verified]
            claims_text += (
                f"\n[{i+1}] Claim: {c.claim}\n"
                f"    Confidence: {c.confidence}\n"
                f"    Supporting: {len(c.supporting_sources)} sources ({', '.join(src_types)})\n"
                f"    Contradicting: {len(c.contradicting_sources)} sources\n"
            )

        prompt = (
            f"Conflicting claims on topic '{topic_key}':\n{claims_text}\n\n"
            f"Resolve the conflict. Which claim is more accurate and why?"
        )

        messages = [
            {"role": "system", "content": CONFLICT_RESOLVER_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await llm.chat(messages=messages)
            raw = result.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            resolutions = json.loads(raw)

            if isinstance(resolutions, list) and resolutions:
                best = resolutions[0]
                winner_text = best.get("winner", "")
                for c in group:
                    if winner_text and winner_text.lower() in c.claim.lower():
                        c.confidence = min(1.0, c.confidence + 0.2)
                        c.resolution = best.get("conclusion", "")
                    else:
                        c.confidence = max(0.1, c.confidence - 0.3)

        except (json.JSONDecodeError, Exception):
            pass

    return validated_claims


def apply_weight_adjustments(
    claims: list[CrossValidatedClaim],
    recency_map: dict[str, float] | None = None,
    popularity_map: dict[str, float] | None = None,
) -> list[CrossValidatedClaim]:
    """
    Apply heuristic weight adjustments based on external signals.
    recency_map: claim_text -> recency_score (0.0=old, 1.0=newest)
    popularity_map: claim_text -> popularity_score (0.0=unpopular, 1.0=most popular)
    """
    for claim in claims:
        if recency_map and claim.claim in recency_map:
            recency_bonus = recency_map[claim.claim] * 0.1
            claim.confidence = min(1.0, claim.confidence + recency_bonus)

        if popularity_map and claim.claim in popularity_map:
            pop_bonus = popularity_map[claim.claim] * 0.1
            claim.confidence = min(1.0, claim.confidence + pop_bonus)

    return claims
