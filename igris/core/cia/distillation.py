"""
igris.core.cia.distillation
-----------------------------
Knowledge Distillation — CIA Level 5.

Compresses research evidence into 3 levels:
  L1 (20 tokens): Executive summary
  L2 (100 tokens): Reasoning with key facts
  L3 (1000+ tokens): Full evidence with sources

The Context Builder loads L1 first. Only if more detail is needed
does it load L2, and only for critical decisions does it load L3.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import CIAStore, DistilledKnowledge, KnowledgeLevel, MemoryEntry, MemoryPriority, MemoryStatus

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient


DISTILL_L1_SYSTEM = "Condense the following to ONE short sentence (max 20 words). State only the core fact."
DISTILL_L2_SYSTEM = "Summarize the following in 2-3 sentences (max 100 words). Include the key reasoning and most important supporting point."
DISTILL_L3_SYSTEM = ""  # Keep original as L3


async def distill_knowledge(
    llm: OpenAICompatibleClient | None,
    topic: str,
    full_text: str,
    source: str = "",
    confidence: float = 0.0,
    tags: list[str] | None = None,
) -> DistilledKnowledge:
    """Compress full text into 3 knowledge levels."""
    import asyncio

    l1_text = full_text[:200]
    l2_text = full_text[:500]
    l3_text = full_text[:5000]

    if llm:
        async def _distill(system: str, text: str, timeout: float = 15.0) -> str:
            if not system:
                return text
            try:
                result = await asyncio.wait_for(
                    llm.chat(messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": text[:2000]},
                    ]),
                    timeout=timeout,
                )
                return result.content.strip()[:500]
            except Exception:
                return text[:200]

        l1_task = _distill(DISTILL_L1_SYSTEM, full_text)
        l2_task = _distill(DISTILL_L2_SYSTEM, full_text)

        l1_text = await l1_task
        l2_text = await l2_task
    else:
        l1_text = full_text[:150]
        l2_text = full_text[:400]

    return DistilledKnowledge(
        topic=topic,
        level1=l1_text[:200],
        level2=l2_text[:500],
        level3=l3_text,
        source=source,
        confidence=confidence,
        tags=tags or [],
        created_at=time.time(),
    )


class KnowledgeDistiller:
    """Manages distillation and storage of knowledge."""

    def __init__(self, store: CIAStore):
        self.store = store

    def store_distilled(
        self,
        topic: str,
        full_text: str,
        memory_type: str = "research",
        source: str = "",
        confidence: float = 0.0,
        tags: list[str] | None = None,
        priority: MemoryPriority = MemoryPriority.P4_RESEARCH,
    ) -> MemoryEntry:
        """Create a memory entry from distilled knowledge (using heuristic compression)."""
        text_lines = full_text.strip().split("\n")
        l1 = text_lines[0][:150] if text_lines else topic
        l2 = "\n".join(text_lines[:5])[:400]
        l3 = full_text[:5000]

        combined = f"L1: {l1}\nL2: {l2}\nL3: {l3}"

        entry = MemoryEntry(
            id=f"k_{topic.lower().replace(' ', '_')[:40]}_{int(time.time())}",
            text=combined,
            memory_type=memory_type,
            priority=priority,
            level=KnowledgeLevel.L3_EVIDENCE,
            tags=tags or [],
        )
        self.store.put_entry(entry)
        return entry

    def get_level(self, entry: MemoryEntry, level: KnowledgeLevel) -> str:
        """Extract a specific knowledge level from an entry."""
        if level == KnowledgeLevel.L3_EVIDENCE:
            return entry.text

        parts = entry.text.split("\nL", 2)
        if level == KnowledgeLevel.L1_SUMMARY:
            for p in parts:
                if p.startswith("1:"):
                    return p[2:].strip()
            return parts[0] if parts else entry.text[:200]

        if level == KnowledgeLevel.L2_REASONING:
            if len(parts) > 1:
                for p in parts[1:]:
                    if p.startswith("2:"):
                        return p[2:].strip()
            return entry.text[:500]

        return entry.text[:200]
