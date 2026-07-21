"""
igris.core.research.visual_asset_collector
---------------------------------------------
Discovers visual assets: logos, icons, illustrations, mockups, 3D models.

Searches multiple sources:
- GitHub (SVG logos in repos)
- npm (icon packages, UI kits)
- Unsplash (photos)
- Figma community (UI kits, mockups)
- Dribbble/Behance (design inspiration)
- Sketchfab (3D models)
- IconFinder/Flaticon (icons)
- cdn.jsdelivr / unpkg (delivered assets)

The LLM identifies which visual assets the project needs, then this
module finds concrete URLs and formats.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, Any

import httpx

from . import (
    AssetType, CollectedSource, GeneratedQuery, ResearchArea,
    SourceType, VisualAsset, SOURCE_WEIGHTS,
)

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

_TIMEOUT = 15.0
_MAX_CONTENT = 20_000
_USER_AGENT = "igris-research/1.0"


# ---------------------------------------------------------------------------
# LLM: identify which visual assets the project needs
# ---------------------------------------------------------------------------
ASSET_PLANNER_SYSTEM = """You are a visual asset planner. Given a project description,
list the visual assets this project will need.

For each asset, provide:
- name: what it is (e.g. "company_logo", "dashboard_icon_set", "login_page_mockup")
- asset_type: one of (logo, icon, illustration, mockup, screenshot, 3d_model, ui_kit,
  component_library, color_palette, font, animation, photo, background, pattern, diagram)
- search_terms: 2-3 search queries to find this asset
- format_preferred: preferred format (svg, png, glb, fbx, etc.)
- description: brief description of what's needed

Always consider:
- App logo / brand mark
- Navigation icons (home, settings, user, search, etc.)
- Dashboard mockup / UI inspiration
- Empty state illustrations
- Error page illustrations
- Loading animations
- Color palette
- Font pairing
- 3D elements if the project is modern/immersive

Return a JSON array of asset objects. No markdown fences."""


async def plan_visual_assets(
    llm: OpenAICompatibleClient,
    user_request: str,
    areas: list[ResearchArea],
) -> list[dict]:
    """Use LLM to identify which visual assets the project needs."""
    area_names = ", ".join(a.name for a in areas[:10])
    prompt = (
        f"Project: {user_request}\n"
        f"Research areas: {area_names}\n\n"
        f"List all visual assets this project needs."
    )

    messages = [
        {"role": "system", "content": ASSET_PLANNER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return _fallback_assets(user_request)


def _fallback_assets(user_request: str) -> list[dict]:
    """Basic asset list when LLM fails."""
    return [
        {"name": "app_logo", "asset_type": "logo", "search_terms": ["app logo modern minimalist"], "format_preferred": "svg", "description": "Main application logo"},
        {"name": "nav_icons", "asset_type": "icon", "search_terms": ["navigation icon set svg"], "format_preferred": "svg", "description": "Navigation bar icons"},
        {"name": "dashboard_mockup", "asset_type": "mockup", "search_terms": ["dashboard UI mockup"], "format_preferred": "png", "description": "Dashboard layout inspiration"},
        {"name": "empty_state", "asset_type": "illustration", "search_terms": ["empty state illustration"], "format_preferred": "svg", "description": "Empty state illustration"},
        {"name": "color_palette", "asset_type": "color_palette", "search_terms": ["modern app color palette"], "format_preferred": "", "description": "Primary and secondary colors"},
        {"name": "font_pairing", "asset_type": "font", "search_terms": ["modern web font pairing"], "format_preferred": "", "description": "Heading and body font combination"},
    ]


# ---------------------------------------------------------------------------
# Multi-source visual asset fetchers
# ---------------------------------------------------------------------------

async def _search_github_svgs(
    client: httpx.AsyncClient, query: str, max_results: int = 5
) -> list[VisualAsset]:
    """Find SVG logos/icons in GitHub repos."""
    assets = []
    try:
        url = f"https://api.github.com/search/code?q={query}+extension:svg&per_page={max_results}"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        data = resp.json()
        for item in data.get("items", [])[:max_results]:
            repo = item.get("repository", {})
            html_url = item.get("html_url", "")
            raw_url = html_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            assets.append(VisualAsset(
                name=item.get("name", "unknown"),
                asset_type=AssetType.ICON,
                source_url=html_url,
                source_type=SourceType.GITHUB,
                download_url=raw_url,
                format="svg",
                tags=[query.split()[0]],
                description=f"SVG from {repo.get('full_name', '')}",
                confidence=0.6,
            ))
    except Exception:
        pass
    return assets


async def _search_npm_icons(
    client: httpx.AsyncClient, query: str, max_results: int = 5
) -> list[VisualAsset]:
    """Find icon/UI packages on npm."""
    assets = []
    try:
        search_query = f"{query} icon svg"
        url = f"https://registry.npmjs.org/-/v1/search?text={search_query}&size={max_results}"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        data = resp.json()
        for obj in data.get("objects", [])[:max_results]:
            pkg = obj.get("package", {})
            name = pkg.get("name", "")
            desc = pkg.get("description", "")
            assets.append(VisualAsset(
                name=name,
                asset_type=AssetType.ICON,
                source_url=f"https://www.npmjs.com/package/{name}",
                source_type=SourceType.NPM,
                download_url=f"https://cdn.jsdelivr.net/npm/{name}/",
                format="svg",
                tags=pkg.get("keywords", []),
                description=desc,
                confidence=0.7,
                metadata={"version": pkg.get("version", "")},
            ))
    except Exception:
        pass
    return assets


async def _search_unsplash(
    client: httpx.AsyncClient, query: str, max_results: int = 3
) -> list[VisualAsset]:
    """Find photos on Unsplash (free to use)."""
    assets = []
    try:
        url = f"https://unsplash.com/s/photos/{query}"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        img_urls = re.findall(r'https://images\.unsplash\.com/[^"\']+', resp.text)
        seen = set()
        for img_url in img_urls[:max_results]:
            clean_url = img_url.split("?")[0]
            if clean_url not in seen:
                seen.add(clean_url)
                assets.append(VisualAsset(
                    name=f"{query} photo",
                    asset_type=AssetType.PHOTO,
                    source_url=url,
                    source_type=SourceType.UNSPLASH,
                    download_url=clean_url,
                    format="jpg",
                    description=f"Photo: {query}",
                    confidence=0.7,
                    license="Unsplash License (free)",
                ))
    except Exception:
        pass
    return assets


async def _search_sketchfab(
    client: httpx.AsyncClient, query: str, max_results: int = 3
) -> list[VisualAsset]:
    """Find 3D models on Sketchfab."""
    assets = []
    try:
        url = f"https://api.sketchfab.com/v3/search?type=models&q={query}&downloadable=true&sort_by=-likeCount&count={max_results}"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        data = resp.json()
        for result in data.get("results", [])[:max_results]:
            thumbnails = result.get("thumbnails", {})
            images = thumbnails.get("images", [])
            preview = images[0]["url"] if images else ""
            viewer_url = result.get("viewerUrl", "")
            assets.append(VisualAsset(
                name=result.get("name", "3D model"),
                asset_type=AssetType.THREED_MODEL,
                source_url=viewer_url,
                source_type=SourceType.SKETCHFAB,
                preview_url=preview,
                format="glb",
                tags=result.get("tags", []),
                description=result.get("description", "")[:200],
                confidence=0.75,
                metadata={
                    "like_count": result.get("likeCount", 0),
                    "view_count": result.get("viewCount", 0),
                    "is_downloadable": result.get("isDownloadable", False),
                },
            ))
    except Exception:
        pass
    return assets


async def _search_figma_community(
    client: httpx.AsyncClient, query: str, max_results: int = 3
) -> list[VisualAsset]:
    """Find UI kits and mockups on Figma Community."""
    assets = []
    try:
        url = f"https://www.figma.com/community/search?resource_type=mixed&sort_by=relevancy&query={query}&editor_type=all&price=all&creators=all"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        titles = re.findall(r'<h2[^>]*>(.*?)</h2>', resp.text)
        links = re.findall(r'href="(/community/file/[^"]+)"', resp.text)
        for i, (title, link) in enumerate(zip(titles[:max_results], links[:max_results])):
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            assets.append(VisualAsset(
                name=clean_title,
                asset_type=AssetType.UI_KIT,
                source_url=f"https://www.figma.com{link}",
                source_type=SourceType.FIGMA,
                format="fig",
                tags=[query.split()[0]],
                description=f"Figma community file: {clean_title}",
                confidence=0.7,
            ))
    except Exception:
        pass
    return assets


async def _search_dribbble(
    client: httpx.AsyncClient, query: str, max_results: int = 3
) -> list[VisualAsset]:
    """Find design inspiration on Dribbble."""
    assets = []
    try:
        url = f"https://dribbble.com/search/{query}"
        resp = await client.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return assets
        img_urls = re.findall(r'https://cdn\.dribbble\.com/[^"\']+', resp.text)
        seen = set()
        for img_url in img_urls[:max_results * 2]:
            if img_url not in seen and ".png" in img_url:
                seen.add(img_url)
                assets.append(VisualAsset(
                    name=f"{query} design",
                    asset_type=AssetType.MOCKUP,
                    source_url=url,
                    source_type=SourceType.DRIBBBLE,
                    preview_url=img_url,
                    format="png",
                    description=f"Dribbble inspiration: {query}",
                    confidence=0.6,
                ))
                if len(assets) >= max_results:
                    break
    except Exception:
        pass
    return assets


# ---------------------------------------------------------------------------
# Main collection function
# ---------------------------------------------------------------------------

async def collect_visual_assets(
    llm: OpenAICompatibleClient,
    user_request: str,
    areas: list[ResearchArea],
    max_per_type: int = 5,
) -> list[VisualAsset]:
    """
    Full visual asset collection pipeline:
    1. LLM plans which assets are needed
    2. Fetch from multiple sources in parallel
    3. Deduplicate and rank by confidence
    """
    asset_plans = await plan_visual_assets(llm, user_request, areas)
    if not asset_plans:
        return []

    all_assets: list[VisualAsset] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        sem = asyncio.Semaphore(6)

        async def _fetch_one(plan: dict) -> list[VisualAsset]:
            async with sem:
                asset_type_str = plan.get("asset_type", "icon")
                try:
                    asset_type = AssetType(asset_type_str)
                except ValueError:
                    asset_type = AssetType.ICON

                search_terms = plan.get("search_terms", [plan.get("name", "")])
                results = []

                for term in search_terms[:2]:
                    tasks = [
                        _search_github_svgs(client, term, max_per_type),
                        _search_npm_icons(client, term, max_per_type),
                        _search_unsplash(client, term, min(3, max_per_type)),
                        _search_sketchfab(client, term, min(3, max_per_type)),
                        _search_figma_community(client, term, min(3, max_per_type)),
                        _search_dribbble(client, term, min(3, max_per_type)),
                    ]
                    fetched = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in fetched:
                        if isinstance(r, list):
                            for asset in r:
                                if asset.source_url not in seen_urls:
                                    seen_urls.add(asset.source_url)
                                    asset.confidence = min(1.0, asset.confidence + 0.1)
                                    results.append(asset)

                return results[:max_per_type * 2]

        tasks = [_fetch_one(plan) for plan in asset_plans]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, list):
                all_assets.extend(r)

    all_assets.sort(key=lambda a: a.confidence, reverse=True)
    return all_assets
