"""MCP surface for web search, fetch, and trending operations.

Provides three tools:
- web_search: search the web via DuckDuckGo (no API key needed)
- web_fetch: fetch and extract text content from a URL
- web_trending: find trending GitHub repositories by topic / language

Used by the research pipeline and available as standalone MCP tools.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web")

_TIMEOUT = 15.0
_MAX_CONTENT = 50_000
_USER_AGENT = "igris-web/1.0 (research agent)"


def _clean_html(html: str) -> str:
    """Strip HTML tags and extract readable text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:_MAX_CONTENT]


@mcp.tool()
async def web_search(query: str, num_results: int = 8) -> str:
    """Search the web using DuckDuckGo. Returns titles, URLs, and snippets.

    Args:
        query: search query string
        num_results: number of results to return (default 8, max 20)
    """
    num_results = min(20, max(1, num_results))
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return f"ERROR: search returned status {resp.status_code}"

            html = resp.text

            results = []
            links = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

            for i, (link, title) in enumerate(links[:num_results]):
                title_clean = re.sub(r"<[^>]+>", "", title).strip()
                snippet = ""
                if i < len(snippets):
                    snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                results.append(f"{i+1}. {title_clean}\n   URL: {link}\n   {snippet}")

            if not results:
                alt_links = re.findall(r'href="(https?://[^"]+)"', html)
                alt_titles = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
                for i, (link, title) in enumerate(zip(alt_links[:num_results], alt_titles[:num_results])):
                    title_clean = re.sub(r"<[^>]+>", "", title).strip()
                    results.append(f"{i+1}. {title_clean}\n   URL: {link}")

            if not results:
                return "(no search results found)"

            return f"Search results for: {query}\n\n" + "\n\n".join(results)

    except Exception as e:
        return f"ERROR: search failed: {e}"


@mcp.tool()
async def web_fetch(url: str, max_chars: int = 15000) -> str:
    """Fetch a URL and return its text content (HTML stripped).

    Args:
        url: the URL to fetch
        max_chars: maximum characters to return (default 15000)
    """
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return f"ERROR: fetch returned status {resp.status_code}"

            content_type = resp.headers.get("content-type", "")
            if "text" not in content_type and "html" not in content_type and "json" not in content_type:
                return f"(binary content, {len(resp.content)} bytes, cannot display)"

            text = resp.text[:_MAX_CONTENT]
            cleaned = _clean_html(text)
            return cleaned[:max_chars]

    except Exception as e:
        return f"ERROR: fetch failed: {e}"


@mcp.tool()
async def web_trending(topic: str = "", language: str = "", since: str = "weekly") -> str:
    """Find trending GitHub repositories.

    Scrapes GitHub trending page for the given topic/language/period.
    Returns repo names, descriptions, stars, and URLs.

    Args:
        topic: Optional topic keyword (e.g. "machine learning", "react", "rust").
        language: Optional language filter (e.g. "python", "typescript", "rust").
        since: Time range — "daily", "weekly", "monthly" (default weekly).
    """
    params = {}
    if language:
        params["spoken_language_code"] = ""
        params["since"] = since
    base = "https://github.com/trending"
    path = f"/{language}" if language else ""
    param_str = f"?since={since}" if not language else ""
    if topic:
        param_str = f"?since={since}&q={quote_plus(topic)}" if not language else f"&q={quote_plus(topic)}"
    url = f"{base}{path}{param_str}"

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return f"ERROR: trending returned status {resp.status_code}"

            html = resp.text
            repos = []
            articles = re.findall(
                r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
                html, re.DOTALL,
            )

            for article in articles[:20]:
                href_match = re.search(r'href="/([^/"]+/[^/"]+)"', article)
                if not href_match:
                    continue
                full_name = href_match.group(1)

                desc_match = re.search(
                    r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
                    article, re.DOTALL,
                )
                description = ""
                if desc_match:
                    description = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()

                stars_match = re.search(
                    r'<span[^>]*class="[^"]*d-inline-block[^"]*float-sm-right[^"]*"[^>]*>\s*(.*?)\s*</span>',
                    article, re.DOTALL,
                )
                stars = ""
                if stars_match:
                    stars = re.sub(r"<[^>]+>", "", stars_match.group(1)).strip()

                lang_match = re.search(
                    r'<span[^>]*itemprop="programmingLanguage"[^>]*>(.*?)</span>',
                    article, re.DOTALL,
                )
                lang = ""
                if lang_match:
                    lang = re.sub(r"<[^>]+>", "", lang_match.group(1)).strip()

                repos.append({
                    "name": full_name,
                    "url": f"https://github.com/{full_name}",
                    "description": description[:200] if description else "",
                    "language": lang,
                    "stars": stars,
                })

            if not repos:
                return "(no trending repos found)"

            lines = [f"Trending repositories{f' -- {topic}' if topic else ''} ({since}):"]
            for r in repos:
                stars_str = r.get('stars', '') or ''
                lang_str = f" [{r['language']}]" if r.get('language') else ''
                lines.append(f"  {r['name']}  *{stars_str}{lang_str}")
                if r['description']:
                    lines.append(f"    {r['description']}")
                lines.append(f"    {r['url']}")
                lines.append("")

            return "\n".join(lines)

    except Exception as e:
        return f"ERROR: trending fetch failed: {e}"


if __name__ == "__main__":
    mcp.run()
