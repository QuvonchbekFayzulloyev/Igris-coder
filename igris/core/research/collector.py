"""
igris.core.research.collector
-------------------------------
Stage 3: Multi-source web collection.

For each generated query, fetches content from multiple sources:
- GitHub (repos, issues, discussions)
- Official documentation (direct HTTP fetch)
- StackOverflow (direct search)
- Reddit (direct search)
- Medium / Blogs (direct HTTP)
- npm/PyPI

Uses httpx for async fetching with rate limiting and timeout protection.
"""
from __future__ import annotations

import asyncio
import re
import time
import urllib.parse
from typing import TYPE_CHECKING

import httpx

from . import CollectedSource, GeneratedQuery, SourceType

if TYPE_CHECKING:
    pass

_GLOBAL_SEMAPHORE = asyncio.Semaphore(8)
_DOMAIN_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
_FETCH_TIMEOUT = 15.0
_MAX_CONTENT_LENGTH = 200_000
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) igris-research/1.0"


def _domain_sem(domain: str) -> asyncio.Semaphore:
    if domain not in _DOMAIN_SEMAPHORES:
        _DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(2)
    return _DOMAIN_SEMAPHORES[domain]


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    async with _GLOBAL_SEMAPHORE:
        async with _domain_sem(domain):
            try:
                resp = await client.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
                if resp.status_code == 200:
                    return resp.text[:_MAX_CONTENT_LENGTH]
            except Exception:
                pass
    return ""


def _extract_text(html: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:10000]


async def _search_github(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&per_page=5"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
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
                        "topics": repo.get("topics", []),
                    },
                ))
    except Exception:
        pass
    return sources


async def _search_github_readme(client: httpx.AsyncClient, repo_url: str) -> CollectedSource | None:
    try:
        parts = repo_url.replace("https://github.com/", "").strip("/").split("/")
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        resp = await client.get(api_url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
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
        pass
    return None


async def _search_npm(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(query)}&size=5"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            for obj in data.get("objects", [])[:5]:
                pkg = obj.get("package", {})
                sources.append(CollectedSource(
                    url=f"https://www.npmjs.com/package/{pkg.get('name', '')}",
                    source_type=SourceType.NPM,
                    title=pkg.get("name", ""),
                    raw_content=pkg.get("description", "") or "",
                    fetched_at=time.time(),
                    metadata={"version": pkg.get("version", ""), "keywords": pkg.get("keywords", [])},
                ))
    except Exception:
        pass
    return sources


async def _search_pypi(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://pypi.org/simple/{urllib.parse.quote(query)}/"
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


async def _search_duckduckgo(client: httpx.AsyncClient, query: str, source_type: SourceType) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            html = resp.text
            # Extract result links and snippets
            results = re.findall(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            for href, title_html, snippet_html in results[:5]:
                title = re.sub(r'<[^>]+>', '', title_html).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_html).strip()
                if title and href:
                    clean_href = href
                    if "duckduckgo.com/l/" in href:
                        from urllib.parse import parse_qs, urlparse
                        parsed = urlparse(href)
                        qs = parse_qs(parsed.query)
                        clean_href = qs.get("uddg", [href])[0]
                    sources.append(CollectedSource(
                        url=clean_href,
                        source_type=source_type,
                        title=title,
                        raw_content=snippet,
                        fetched_at=time.time(),
                    ))
    except Exception:
        pass
    return sources


async def _search_stackoverflow(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://api.stackexchange.com/2.3/search?order=desc&sort=votes&intitle={urllib.parse.quote(query)}&site=stackoverflow&pagesize=5"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", [])[:5]:
                sources.append(CollectedSource(
                    url=item.get("link", ""),
                    source_type=SourceType.STACKOVERFLOW,
                    title=item.get("title", ""),
                    raw_content=item.get("body_markdown", "")[:3000] if "body_markdown" in item else item.get("title", ""),
                    fetched_at=time.time(),
                    metadata={
                        "score": item.get("score", 0),
                        "answer_count": item.get("answer_count", 0),
                        "tags": item.get("tags", []),
                    },
                ))
    except Exception:
        pass
    return sources


async def _search_reddit(client: httpx.AsyncClient, query: str) -> list[CollectedSource]:
    sources = []
    try:
        url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(query)}&sort=relevance&limit=5&restrict_sr=on"
        resp = await client.get(url, timeout=_FETCH_TIMEOUT, headers={"User-Agent": _USER_AGENT})
        if resp.status_code == 200:
            data = resp.json()
            for child in data.get("data", {}).get("children", [])[:5]:
                d = child.get("data", {})
                sources.append(CollectedSource(
                    url=f"https://www.reddit.com{d.get('permalink', '')}",
                    source_type=SourceType.REDDIT,
                    title=d.get("title", ""),
                    raw_content=d.get("selftext", "")[:3000] or d.get("title", ""),
                    fetched_at=time.time(),
                    metadata={
                        "score": d.get("score", 0),
                        "num_comments": d.get("num_comments", 0),
                        "subreddit": d.get("subreddit", ""),
                    },
                ))
    except Exception:
        pass
    return sources


async def _fetch_web_page(client: httpx.AsyncClient, url: str, source_type: SourceType) -> list[CollectedSource]:
    sources = []
    try:
        html = await _fetch(client, url)
        if html:
            text = _extract_text(html)
            if len(text) > 100:
                sources.append(CollectedSource(
                    url=url,
                    source_type=source_type,
                    title=url.rsplit("/", 1)[-1][:80],
                    raw_content=text,
                    fetched_at=time.time(),
                ))
    except Exception:
        pass
    return sources


async def collect_for_query(
    client: httpx.AsyncClient,
    query: GeneratedQuery,
) -> list[CollectedSource]:
    """Collect sources for a single query from all relevant source types."""
    tasks = []
    source_hints = query.source_hints or [SourceType.GITHUB, SourceType.STACKOVERFLOW, SourceType.OFFICIAL_DOCS]

    for source_type in source_hints:
        if source_type == SourceType.GITHUB:
            tasks.append(_search_github(client, query.text))
        elif source_type == SourceType.NPM:
            tasks.append(_search_npm(client, query.text))
        elif source_type == SourceType.PYPI:
            tasks.append(_search_pypi(client, query.text))
        elif source_type == SourceType.STACKOVERFLOW:
            tasks.append(_search_stackoverflow(client, query.text))
        elif source_type == SourceType.REDDIT:
            tasks.append(_search_reddit(client, query.text))
        elif source_type in (SourceType.OFFICIAL_DOCS, SourceType.BLOG, SourceType.MEDIUM):
            tasks.append(_search_duckduckgo(client, query.text, source_type))
        else:
            tasks.append(_search_duckduckgo(client, query.text, source_type))

    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
    sources = []
    for r in results:
        if isinstance(r, list):
            sources.extend(r)
    return sources


async def collect_all(
    queries: list[GeneratedQuery],
    max_concurrent: int = 6,
) -> list[CollectedSource]:
    """
    Collect sources for all queries with bounded concurrency.
    Deduplicates by URL.
    """
    all_sources: list[CollectedSource] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
        timeout=_FETCH_TIMEOUT,
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
                    if s.url and s.url not in seen_urls:
                        seen_urls.add(s.url)
                        all_sources.append(s)

        # Enrich thin sources (snippets only) with full page content
        enrich_tasks = []
        for s in all_sources:
            if len(s.raw_content) < 500 and not s.url.startswith("https://api.github.com"):
                enrich_tasks.append(_enrich_source(client, s))
        if enrich_tasks:
            batch_size = 5
            for i in range(0, len(enrich_tasks), batch_size):
                batch = enrich_tasks[i:i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)

    return all_sources


async def _enrich_source(client: httpx.AsyncClient, source: CollectedSource) -> None:
    """Fetch full page content for a source that only has a snippet."""
    content = await _fetch(client, source.url)
    if content and len(content) > 500:
        text = _extract_text(content)
        if len(text) > len(source.raw_content):
            source.raw_content = text
