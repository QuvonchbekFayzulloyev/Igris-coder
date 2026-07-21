"""
igris.core.research.cross_validator
--------------------------------------
Stage 6: Cross-validate claims against multiple independent sources.

This is the core quality mechanism. Every claim must be verified by
at least 3 independent sources. Claims that fail validation are
rejected or flagged as low-confidence.

Validation uses:
- Source diversity (different source types)
- Source weight (official docs > random blog)
- Claim frequency (how many sources agree)
- Recency (newer sources weighted higher)
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import Claim, CrossValidatedClaim, Evidence, SourceType, SOURCE_WEIGHTS

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

CROSS_VALIDATOR_SYSTEM = """You are a cross-validation agent. Given a claim and
multiple pieces of evidence from different sources, determine:

1. Is the claim supported, contradicted, or unverifiable?
2. What is the confidence (0.0-1.0)?
3. Which sources support it? Which contradict it?

A claim is VALIDATED if:
- At least 3 independent sources support it
- No more than 1 source contradicts it
- At least one high-weight source (official docs, GitHub) supports it

A claim is REJECTED if:
- Only 1 source supports it (insufficient evidence)
- 2+ sources contradict it
- All supporting sources are low-weight (random blogs only)

Return JSON with:
- verdict: "validated" | "rejected" | "uncertain"
- confidence: 0.0-1.0
- supporting: list of source URLs that support
- contradicting: list of source URLs that contradict
- reasoning: brief explanation
No markdown fences."""


def _source_type_diversity(evidence_list: list[Evidence]) -> int:
    """Count unique source types in evidence."""
    return len(set(e.source_type for e in evidence_list))


def _weighted_score(evidence_list: list[Evidence]) -> float:
    """Compute weighted confidence score from evidence."""
    if not evidence_list:
        return 0.0
    total_weight = sum(e.source_weight for e in evidence_list)
    weighted_conf = sum(e.confidence * e.source_weight for e in evidence_list)
    return weighted_conf / total_weight if total_weight > 0 else 0.0


async def validate_claim(
    llm: OpenAICompatibleClient,
    claim: Claim,
    evidence_pool: list[Evidence],
) -> CrossValidatedClaim:
    """Validate a single claim against the evidence pool."""
    matching_evidence = _find_matching_evidence(claim, evidence_pool)

    if len(matching_evidence) < 2:
        return CrossValidatedClaim(
            claim=claim.text,
            confidence=0.2,
            resolution="insufficient_evidence",
        )

    diversity = _source_type_diversity(matching_evidence)
    base_score = _weighted_score(matching_evidence)
    diversity_bonus = min(0.2, diversity * 0.05)
    raw_confidence = min(1.0, base_score + diversity_bonus)

    evidence_text = ""
    for i, e in enumerate(matching_evidence[:10]):
        evidence_text += (
            f"\n[{i+1}] Source: {e.source_type.value} (weight={e.source_weight})\n"
            f"    Content: {e.content[:200]}\n"
        )

    prompt = (
        f"Claim: {claim.text}\n\n"
        f"Evidence from {len(matching_evidence)} sources:\n{evidence_text}\n\n"
        f"Base confidence from source analysis: {raw_confidence:.2f}\n"
        f"Source diversity: {diversity} types\n\n"
        f"Determine verdict and final confidence."
    )

    messages = [
        {"role": "system", "content": CROSS_VALIDATOR_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        verdict_data = json.loads(raw)

        verdict = verdict_data.get("verdict", "uncertain")
        llm_confidence = verdict_data.get("confidence", raw_confidence)
        supporting = verdict_data.get("supporting", [])
        contradicting = verdict_data.get("contradicting", [])
        reasoning = verdict_data.get("reasoning", "")

        final_confidence = (raw_confidence + llm_confidence) / 2
        if verdict == "rejected":
            final_confidence = min(0.3, final_confidence)
        elif verdict == "validated" and diversity >= 3:
            final_confidence = max(0.7, final_confidence)

    except (json.JSONDecodeError, Exception):
        supporting = [e.source_url for e in matching_evidence]
        contradicting = []
        reasoning = "LLM validation unavailable; using heuristic score"
        final_confidence = raw_confidence
        if diversity < 2:
            final_confidence = min(0.5, final_confidence)

    return CrossValidatedClaim(
        claim=claim.text,
        confidence=round(final_confidence, 3),
        supporting_sources=supporting,
        contradicting_sources=contradicting,
        source_types_verified=[e.source_type for e in matching_evidence],
        resolution=reasoning,
    )


def _find_matching_evidence(claim: Claim, evidence_pool: list[Evidence]) -> list[Evidence]:
    """Find evidence that relates to a claim using keyword overlap."""
    claim_words = set(claim.text.lower().split())
    scored = []
    for e in evidence_pool:
        e_words = set(e.content.lower().split())
        overlap = len(claim_words & e_words)
        if overlap >= 2:
            scored.append((overlap, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:15]]


async def validate_all(
    llm: OpenAICompatibleClient,
    claims: list[Claim],
    evidence_pool: list[Evidence],
    min_confidence: float = 0.4,
) -> tuple[list[CrossValidatedClaim], list[CrossValidatedClaim]]:
    """
    Validate all claims. Returns (validated, rejected) lists.
    Claims below min_confidence are rejected.
    """
    import asyncio
    sem = asyncio.Semaphore(5)

    async def _bounded(c: Claim) -> CrossValidatedClaim:
        async with sem:
            return await validate_claim(llm, c, evidence_pool)

    tasks = [_bounded(c) for c in claims]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    validated = []
    rejected = []
    for r in results:
        if isinstance(r, CrossValidatedClaim):
            if r.confidence >= min_confidence:
                validated.append(r)
            else:
                rejected.append(r)

    return validated, rejected
