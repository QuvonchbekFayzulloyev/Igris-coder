"""
igris.core.research.evidence_extractor
----------------------------------------
Stage 4: Extract structured evidence from raw page content.

Raw HTML/markdown is reduced to only the useful parts:
- Architecture patterns
- Code examples
- Best practices
- Warnings/pitfalls
- Performance data
- API examples
- Folder structures
- Dependencies

The LLM does the extraction (it understands context), but the pipeline
controls what it looks for.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING

from . import CollectedSource, Evidence, SourceType, SOURCE_WEIGHTS

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

EXTRACTOR_SYSTEM = """You are an evidence extraction agent. Given raw web content,
extract ONLY factual, actionable evidence. Discard fluff, ads, navigation, etc.

For each piece of evidence, provide:
- category: one of (architecture, best_practice, warning, performance, code_snippet,
  api_example, folder_structure, dependency, config, tool, pattern, limitation, trend,
  visual_asset, ui_design, color_scheme, typography, icon_set, illustration, mockup)
- content: the specific evidence (concise, factual)
- confidence: 0.0-1.0 (how confident you are this is accurate)

Return a JSON array of evidence objects. No markdown fences.
Be aggressive about filtering: only keep things that would help someone
make a concrete technical decision.
Also extract visual asset references: logo URLs, icon packages, UI kits,
color palettes, font recommendations, illustration sources, mockup links."""

CATEGORY_KEYWORDS = {
    "architecture": ["architecture", "structure", "pattern", "layer", "module", "monolith", "microservice"],
    "best_practice": ["best practice", "recommend", "should", "convention", "standard", "guide"],
    "warning": ["warning", "pitfall", "avoid", "don't", "never", "risk", "gotcha", "trap"],
    "performance": ["performance", "speed", "fast", "slow", "benchmark", "optimize", "cache", "memory"],
    "code_snippet": ["```", "function ", "class ", "import ", "const ", "def ", "async "],
    "api_example": ["api", "endpoint", "fetch", "request", "response", "method"],
    "folder_structure": ["src/", "app/", "components/", "├", "└", "tree", "folder"],
    "dependency": ["package", "dependency", "install", "npm", "pip", "require"],
    "config": ["config", "setting", "env", "environment", "variable", "option"],
    "tool": ["tool", "library", "framework", "plugin", "extension", "package"],
    "pattern": ["pattern", "approach", "strategy", "method", "technique", "solution"],
    "limitation": ["limitation", "limit", "issue", "problem", "bug", "tradeoff", "downside"],
    "trend": ["trend", "popular", "growing", "declining", "future", "2024", "2025", "modern"],
    "visual_asset": ["logo", "icon", "illustration", "mockup", "screenshot", "3d", "model", "asset"],
    "ui_design": ["ui kit", "design system", "component library", "figma", "sketch", "adobe xd"],
    "color_scheme": ["color palette", "color scheme", "primary color", "secondary color", "brand color"],
    "typography": ["font", "typeface", "heading font", "body font", "font pairing", "google fonts"],
    "icon_set": ["icon set", "icon library", "icon pack", "svg icons", "lucide", "heroicons", "fontawesome"],
    "illustration": ["illustration", "drawing", "artwork", "vector", "svg illustration"],
    "mockup": ["mockup", "wireframe", "prototype", "layout", "dashboard design"],
}


def _heuristic_extract(source: CollectedSource) -> list[Evidence]:
    """Extract evidence using keyword matching when LLM is unavailable."""
    evidence = []
    content = source.raw_content
    lines = content.split("\n")

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if len(line.strip()) < 20:
            continue

        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in line_lower for kw in keywords):
                context = "\n".join(lines[max(0, i-1):i+2]).strip()
                if len(context) > 20:
                    evidence.append(Evidence(
                        source_url=source.url,
                        source_type=source.source_type,
                        source_weight=SOURCE_WEIGHTS.get(source.source_type, 0.5),
                        category=category,
                        content=context[:500],
                        confidence=0.5,
                    ))
                break

    return evidence[:20]


async def extract_evidence(
    llm: OpenAICompatibleClient,
    source: CollectedSource,
    max_evidence: int = 3,
) -> list[Evidence]:
    """Extract structured evidence from a collected source."""
    content = source.raw_content[:1500]
    if not content.strip():
        return []

    prompt = (
        f"Source: {source.url}\n"
        f"Type: {source.source_type.value}\n"
        f"Title: {source.title}\n\n"
        f"Content:\n{content}\n\n"
        f"Extract up to {max_evidence} pieces of actionable evidence."
    )

    messages = [
        {"role": "system", "content": EXTRACTOR_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await asyncio.wait_for(llm.chat(messages=messages), timeout=30.0)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        evidence_data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return _heuristic_extract(source)

    evidence = []
    seen = set()
    weight = SOURCE_WEIGHTS.get(source.source_type, 0.5)
    for item in evidence_data[:max_evidence]:
        cat = item.get("category", "best_practice")
        content_text = item.get("content", "").strip()
        if not content_text or content_text in seen:
            continue
        seen.add(content_text)
        evidence.append(Evidence(
            source_url=source.url,
            source_type=source.source_type,
            source_weight=weight,
            category=cat,
            content=content_text,
            confidence=min(1.0, max(0.0, item.get("confidence", 0.5))),
        ))

    return evidence


async def extract_all(
    llm: OpenAICompatibleClient,
    sources: list[CollectedSource],
    max_per_source: int = 15,
) -> list[Evidence]:
    """Extract evidence from all collected sources."""
    import asyncio
    sem = asyncio.Semaphore(10)

    async def _bounded(s: CollectedSource) -> list[Evidence]:
        async with sem:
            return await extract_evidence(llm, s, max_per_source)

    tasks = [_bounded(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_evidence = []
    for r in results:
        if isinstance(r, list):
            all_evidence.extend(r)
    return all_evidence
