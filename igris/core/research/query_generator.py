"""
igris.core.research.query_generator
--------------------------------------
Stage 2: Generate 20-50 targeted search queries per research area.

Each area gets multiple query variants targeting different source types:
- Official docs queries (framework X documentation)
- GitHub queries (framework X best practices, framework X production)
- Community queries (framework X vs Y, framework X problems)
- Trend queries (framework X 2024 2025, modern framework X)
"""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from . import GeneratedQuery, ResearchArea, SourceType

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

QUERY_SYSTEM = """You are a research query generator. For each research area,
generate 20-30 diverse search queries that would find high-quality information.

Types of queries to generate:
1. Official documentation queries (3-5)
2. GitHub/open-source queries (5-8)
3. Comparison queries (X vs Y) (3-5)
4. Best practices queries (3-5)
5. Problem/pitfall queries (2-3)
6. Trend queries (2-3)
7. Community discussion queries (2-3)

For each query, specify:
- text: the search query string
- source_hints: which sources this query targets (official_docs, github, stackoverflow, reddit, medium, blog)

Return a JSON array of query objects. No markdown fences."""

SOURCE_HINT_MAP = {
    "official_docs": SourceType.OFFICIAL_DOCS,
    "github": SourceType.GITHUB,
    "stackoverflow": SourceType.STACKOVERFLOW,
    "reddit": SourceType.REDDIT,
    "medium": SourceType.MEDIUM,
    "blog": SourceType.BLOG,
    "youtube": SourceType.YOUTUBE,
    "rfc": SourceType.RFC,
    "paper": SourceType.PAPER,
    "npm": SourceType.NPM,
    "pypi": SourceType.PYPI,
}


async def generate_queries(
    llm: OpenAICompatibleClient,
    area: ResearchArea,
    max_queries: int = 30,
) -> list[GeneratedQuery]:
    """Generate targeted search queries for one research area."""
    sub_area_text = ""
    if area.sub_areas:
        sub_area_text = f"\nSub-areas to cover: {', '.join(area.sub_areas)}"

    prompt = (
        f"Research area: {area.name}\n"
        f"Description: {area.description}{sub_area_text}\n\n"
        f"Generate up to {max_queries} diverse search queries."
    )

    messages = [
        {"role": "system", "content": QUERY_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        queries_data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        queries_data = _fallback_queries(area)

    queries = []
    seen = set()
    for item in queries_data[:max_queries]:
        text = item.get("text", "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        hints = []
        for h in item.get("source_hints", []):
            st = SOURCE_HINT_MAP.get(h.lower().strip())
            if st:
                hints.append(st)
        queries.append(GeneratedQuery(text=text, area=area.name, source_hints=hints))

    return queries


def _fallback_queries(area: ResearchArea) -> list[dict]:
    """Generate basic queries when LLM output fails."""
    name = area.description or area.name.replace("_", " ")
    return [
        {"text": f"{name} documentation", "source_hints": ["official_docs"]},
        {"text": f"{name} best practices 2025", "source_hints": ["blog", "medium"]},
        {"text": f"{name} github production examples", "source_hints": ["github"]},
        {"text": f"{name} vs alternatives comparison", "source_hints": ["stackoverflow", "reddit"]},
        {"text": f"{name} common mistakes pitfalls", "source_hints": ["stackoverflow", "blog"]},
        {"text": f"{name} enterprise architecture", "source_hints": ["blog", "medium"]},
        {"text": f"modern {name} stack 2025", "source_hints": ["blog", "medium"]},
        {"text": f"{name} performance optimization", "source_hints": ["blog", "stackoverflow"]},
    ]


async def generate_all_queries(
    llm: OpenAICompatibleClient,
    areas: list[ResearchArea],
    max_per_area: int = 30,
) -> list[GeneratedQuery]:
    """Generate queries for all research areas in parallel."""
    sem = asyncio.Semaphore(4)

    async def _one(area: ResearchArea) -> list[GeneratedQuery]:
        async with sem:
            return await generate_queries(llm, area, max_per_area)

    results = await asyncio.gather(*[_one(a) for a in areas], return_exceptions=True)
    all_queries = []
    for r in results:
        if isinstance(r, list):
            all_queries.extend(r)
    return all_queries
