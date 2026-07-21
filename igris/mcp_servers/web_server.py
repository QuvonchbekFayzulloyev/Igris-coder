"""MCP surface for web search and fetch operations.

Provides two tools:
- web_search: search the web via DuckDuckGo (no API key needed)
- web_fetch: fetch and extract text content from a URL

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


if __name__ == "__main__":
    mcp.run()
