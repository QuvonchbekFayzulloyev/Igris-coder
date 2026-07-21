"""
igris.core.research.claim_extractor
--------------------------------------
Stage 5: Extract verifiable claims from evidence.

A "claim" is a concrete, testable statement like:
- "Redux Toolkit is the recommended state management for React"
- "Feature-based architecture scales better than layer-based"
- "TanStack Query has 81% adoption in 2025"

Claims must be specific enough to be verified against multiple sources.
Vague statements like "React is popular" are rejected.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING

from . import Claim, Evidence

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

CLAIM_SYSTEM = """You are a claim extraction agent. From evidence content,
extract concrete, verifiable claims.

A valid claim must be:
1. Specific (not vague like "X is good")
2. Verifiable (can be confirmed or denied by checking sources)
3. Actionable (helps someone make a technical decision)

Examples of GOOD claims:
- "Redux Toolkit is recommended over plain Redux for new React projects"
- "Feature-based folder structure is used by 92% of enterprise React apps"
- "TanStack Query replaces Redux for server state management"
- "Next.js supports both SSR and SSG in the same project"

Examples of BAD claims (reject these):
- "React is popular" (too vague)
- "X might be useful" (not concrete)
- "Some people prefer Y" (not verifiable)

For each claim, provide:
- text: the specific claim
- confidence: 0.0-1.0 based on source quality and specificity

Return a JSON array of claim objects. No markdown fences."""

_VAGUE_PATTERNS = [
    r"^it(?:'s| is) (?:good|bad|great|nice|popular|fast|slow|easy|hard)$",
    r"^(?:very|really|quite|somewhat|pretty) ",
    r"(?:most|many|some|few) (?:people|developers|users) (?:think|say|believe)",
    r"^(?:yes|no|maybe|perhaps|probably)$",
]

_VAGUE_RE = re.compile("|".join(_VAGUE_PATTERNS), re.IGNORECASE)


def _is_vague(claim_text: str) -> bool:
    """Check if a claim is too vague to be useful."""
    if len(claim_text.strip()) < 15:
        return True
    if _VAGUE_RE.search(claim_text):
        return True
    return False


def _heuristic_claims(evidence: Evidence) -> list[Claim]:
    """Extract claims using pattern matching when LLM is unavailable."""
    claims = []
    content = evidence.content

    sentences = re.split(r"[.!?\n]", content)
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20 or _is_vague(sentence):
            continue

        tech_words = ["use", "recommend", "prefer", "should", "best", "faster",
                       "slower", "scales", "replaces", "supports", "requires",
                       "provides", "enables", "improves", "reduces", "increases"]
        if any(w in sentence.lower() for w in tech_words):
            claims.append(Claim(
                text=sentence,
                evidence=[evidence],
                confidence=evidence.confidence * evidence.source_weight,
            ))

    return claims[:5]


async def extract_claims(
    llm: OpenAICompatibleClient,
    evidence_list: list[Evidence],
    max_claims: int = 50,
) -> list[Claim]:
    """Extract verifiable claims from evidence."""
    evidence_text = ""
    for i, e in enumerate(evidence_list[:30]):
        evidence_text += f"\n[{i+1}] ({e.source_type.value}, {e.category}) {e.content[:300]}\n"

    if not evidence_text.strip():
        return []

    prompt = (
        f"Extract up to {max_claims} concrete, verifiable claims "
        f"from the following evidence:\n{evidence_text}"
    )

    messages = [
        {"role": "system", "content": CLAIM_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await asyncio.wait_for(llm.chat(messages=messages), timeout=30.0)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        claims_data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        all_claims = []
        for e in evidence_list:
            all_claims.extend(_heuristic_claims(e))
        return all_claims[:max_claims]

    claims = []
    seen = set()
    for item in claims_data[:max_claims]:
        text = item.get("text", "").strip()
        if not text or text in seen or _is_vague(text):
            continue
        seen.add(text)
        claims.append(Claim(
            text=text,
            confidence=min(1.0, max(0.0, item.get("confidence", 0.5))),
        ))

    return claims
