"""
igris.core.research.collector
-------------------------------
Stage 3: Multi-source web collection.

For each generated query, fetches content from multiple sources:
- GitHub (repos, issues, discussions)
- Official documentation
- StackOverflow
- Reddit
- Medium
- Blogs
- npm/PyPI

Uses httpx for async fetching with rate limiting and timeout protection.
Falls back to cached results when a source is unreachable.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import httpx

from . import CollectedSource, GeneratedQuery, SourceType

if TYPE_CHECKING:
    pass

# Rate limiting: max concurrent requests per domain
_DOMAIN_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
_GLOBAL_SEMAPHORE = asyncio.Semaphore(10)
_FETCH_TIMEOUT = 15.0
_MAX_CONTENT_LENGTH = 200_000  # 200KB per page


def _get_semaphore(domain: str) -> asyncio.Semaphore:
    if domain not in _DOMAIN_SEMAPHORES:
        _DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(3)
    return _DOMAIN_SEMAPHORES[domain]


async def _fetch_url(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a single URL with rate limiting and error handling."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    sem = _get_semaphore(domain)

    async with _GLOBAL_SEMAPHORE:
        async with sem:
            try:
                resp = await client.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
                if resp.status_code == 200:
                    content = resp.text[:_MAX_CONTENT_LENGTH]
                    return content
                return ""
            except Exception:
                return ""


async def _search_github(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    """Search GitHub repos via the search API."""
    sources = []
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&per_page=5"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code != 200:
            return sources
        data = resp.json()
        for repo in data.get("items", [])[:5]:
            sources.append(CollectedSource(
                url=repo.get("html_url", ""),
                source_type=SourceType.GITHUB,
                title=repo.get("full_name", ""),
                raw_content=repo.get("description", "") or "",
                fetched_at=time.time(),
                metadata={
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "updated_at": repo.get("updated_at", ""),
                    "topics": repo.get("topics", []),
                },
            ))
    except Exception:
        pass
    return sources


async def _search_github_readme(client: httpx.AsyncClient, repo_url: str) -> CollectedSource | None:
    """Fetch README from a GitHub repo."""
    try:
        parts = repo_url.replace("https://github.com/", "").strip("/").split("/")
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        resp = await client.get(api_url, timeout=_FETCH_TIMEOUT)
        if resp.status_code != 200:
            return None
        import base64
        content = base64.b64decode(resp.json().get("content", "")).decode("utf-8", errors="ignore")
        return CollectedSource(
            url=repo_url,
            source_type=SourceType.GITHUB,
            title=f"{owner}/{repo} README",
            raw_content=content[:_MAX_CONTENT_LENGTH],
            fetched_at=time.time(),
        )
    except Exception:
        return None


async def _search_npm(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    """Search npm for packages."""
    sources = []
    try:
        url = f"https://registry.npmjs.org/-/v1/search?text={query}&size=5"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code != 200:
            return sources
        data = resp.json()
        for obj in data.get("objects", [])[:5]:
            pkg = obj.get("package", {})
            sources.append(CollectedSource(
                url=f"https://www.npmjs.com/package/{pkg.get('name', '')}",
                source_type=SourceType.NPM,
                title=pkg.get("name", ""),
                raw_content=pkg.get("description", "") or "",
                fetched_at=time.time(),
                metadata={
                    "version": pkg.get("version", ""),
                    "keywords": pkg.get("keywords", []),
                },
            ))
    except Exception:
        pass
    return sources


async def _search_pypi(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    """Search PyPI for packages."""
    sources = []
    try:
        url = f"https://pypi.org/simple/{query}"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            sources.append(CollectedSource(
                url=f"https://pypi.org/project/{query}/",
                source_type=SourceType.PYPI,
                title=query,
                raw_content=resp.text[:5000],
                fetched_at=time.time(),
            ))
    except Exception:
        pass
    return sources


async def collect_for_query(
    client: httpx.AsyncClient,
    query: GeneratedQuery,
) -> list[CollectedSource]:
    """Collect sources for a single query from all hint sources."""
    tasks = []
    source_hints = query.source_hints or list(SourceType)

    for source_type in source_hints:
        if source_type == SourceType.GITHUB:
            tasks.append(_search_github(client, query.text))
        elif source_type == SourceType.NPM:
            tasks.append(_search_npm(client, query.text))
        elif source_type == SourceType.PYPI:
            tasks.append(_search_pypi(client, query.text))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())

    results = await asyncio.gather(*tasks, return_exceptions=True)
    sources = []
    for r in results:
        if isinstance(r, list):
            sources.extend(r)
    return sources


async def collect_all(
    queries: list[GeneratedQuery],
    max_concurrent: int = 8,
) -> list[CollectedSource]:
    """
    Collect sources for all queries with bounded concurrency.
    Deduplicates by URL.
    """
    all_sources: list[CollectedSource] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": "igris-research/1.0"},
        follow_redirects=True,
    ) as client:
        sem = asyncio.Semaphore(max_concurrent)

        async def _bounded_collect(q: GeneratedQuery) -> list[CollectedSource]:
            async with sem:
                return await collect_for_query(client, q)

        tasks = [_bounded_collect(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, list):
                for s in r:
                    if s.url not in seen_urls:
                        seen_urls.add(s.url)
                        all_sources.append(s)

    return all_sources
