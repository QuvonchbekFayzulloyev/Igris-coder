"""
igris.core.research.pattern_miner
-----------------------------------
Stage 9: Mine patterns from real GitHub repositories.

Analyzes 100+ repos to find:
- Most common folder structures
- Dependency patterns
- Testing patterns
- Architecture patterns
- State management patterns
- API patterns

This is the "Data Analyst" role: pure statistics, no LLM opinion.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter, defaultdict
from typing import Any

import httpx

from . import Pattern

_FETCH_TIMEOUT = 15.0
_MAX_REPOS = 100
_MAX_CONTENT = 50_000


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        if resp.status_code == 200:
            return resp.text[:_MAX_CONTENT]
    except Exception:
        pass
    return ""


async def _search_repos(
    client: httpx.AsyncClient,
    query: str,
    max_repos: int = _MAX_REPOS,
) -> list[dict]:
    """Search GitHub for repos matching a query."""
    repos = []
    page = 1
    while len(repos) < max_repos and page <= 5:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&per_page=20&page={page}"
        data = await _fetch_json(client, url)
        if not data or not data.get("items"):
            break
        for item in data["items"]:
            repos.append({
                "name": item.get("full_name", ""),
                "url": item.get("html_url", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "topics": item.get("topics", []),
            })
        page += 1
    return repos[:max_repos]


async def _get_repo_tree(
    client: httpx.AsyncClient,
    repo_name: str,
    max_entries: int = 100,
) -> str:
    """Get the folder tree of a repo."""
    url = f"https://api.github.com/repos/{repo_name}/git/trees/HEAD?recursive=1"
    data = await _fetch_json(client, url)
    if not data:
        return ""

    tree = data.get("tree", [])
    lines = []
    for item in tree[:max_entries]:
        path = item.get("path", "")
        if item.get("type") == "tree":
            lines.append(f"{path}/")
        else:
            lines.append(path)
    return "\n".join(lines)


async def _get_package_json(client: httpx.AsyncClient, repo_name: str) -> dict | None:
    """Get package.json from a repo."""
    url = f"https://raw.githubusercontent.com/{repo_name}/HEAD/package.json"
    text = await _fetch_text(client, url)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return None


async def _analyze_one_repo(
    client: httpx.AsyncClient,
    repo: dict,
) -> dict[str, Any]:
    """Analyze a single repo for patterns."""
    analysis: dict[str, Any] = {
        "name": repo["name"],
        "stars": repo["stars"],
        "language": repo["language"],
        "folder_structure": [],
        "dependencies": [],
        "dev_dependencies": [],
        "scripts": [],
        "has_tests": False,
        "has_ci": False,
        "has_docker": False,
        "has_docs": False,
        "state_management": "",
        "css_solution": "",
    }

    tree = await _get_repo_tree(client, repo["name"])
    if tree:
        analysis["folder_structure"] = tree.split("\n")

        dirs = [line.rstrip("/") for line in tree.split("\n") if line.endswith("/")]
        root_dirs = [d.split("/")[0] for d in dirs if "/" not in d.rstrip("/")]
        analysis["has_tests"] = any(t in " ".join(root_dirs).lower() for t in ["test", "tests", "__tests__", "spec"])
        analysis["has_ci"] = any(".github" in d or "ci" in d.lower() for d in root_dirs)
        analysis["has_docker"] = any("docker" in " ".join(analysis["folder_structure"]).lower())
        analysis["has_docs"] = any(d in root_dirs for d in ["docs", "documentation"])

    pkg = await _get_package_json(client, repo["name"])
    if pkg:
        deps = list(pkg.get("dependencies", {}).keys())
        dev_deps = list(pkg.get("devDependencies", {}).keys())
        scripts = list(pkg.get("scripts", {}).keys())

        analysis["dependencies"] = deps
        analysis["dev_dependencies"] = dev_deps
        analysis["scripts"] = scripts

        sm_libs = ["redux", "@reduxjs/toolkit", "zustand", "jotai", "recoil", "mobx", "valtio"]
        for lib in sm_libs:
            if lib in [d.lower() for d in deps]:
                analysis["state_management"] = lib
                break

        css_libs = ["tailwindcss", "styled-components", "@emotion/react", "sass", "less", "postcss"]
        for lib in css_libs:
            if lib in [d.lower() for d in deps]:
                analysis["css_solution"] = lib
                break

    return analysis


def _mine_folder_patterns(analyses: list[dict]) -> Pattern:
    """Find the most common folder structure patterns."""
    dir_counter: Counter = Counter()
    structure_counter: Counter = Counter()

    for a in analyses:
        dirs = [d.rstrip("/") for d in a["folder_structure"] if d.endswith("/")]
        root_dirs = set()
        for d in dirs:
            root = d.split("/")[0]
            if root and not root.startswith("."):
                root_dirs.add(root)
        structure_counter[frozenset(root_dirs)] += 1

        for d in dirs:
            parts = d.split("/")
            if len(parts) <= 2:
                dir_counter[d] += 1

    total = len(analyses) or 1
    top_dirs = [(d, count / total) for d, count in dir_counter.most_common(20)]

    top_structures = structure_counter.most_common(5)
    examples = []
    for frozen_dirs, count in top_structures:
        examples.append(f"  ({count} repos): {' / '.join(sorted(frozen_dirs)[:10])}")

    description = f"Most common directories (out of {total} repos analyzed):\n"
    for d, freq in top_dirs[:10]:
        description += f"  {d}: {freq:.0%}\n"
    description += "\nMost common top-level structures:\n"
    description += "\n".join(examples)

    return Pattern(
        name="folder_structure",
        frequency=top_dirs[0][1] if top_dirs else 0.0,
        examples=[d for d, _ in top_dirs[:10]],
        description=description,
        category="folder_structure",
    )


def _mine_dependency_patterns(analyses: list[dict]) -> list[Pattern]:
    """Find the most common dependency patterns."""
    dep_counter: Counter = Counter()
    for a in analyses:
        for dep in a["dependencies"]:
            dep_counter[dep.lower()] += 1

    total = len(analyses) or 1
    patterns = []
    for dep, count in dep_counter.most_common(20):
        freq = count / total
        if freq >= 0.05:
            patterns.append(Pattern(
                name=f"dependency:{dep}",
                frequency=freq,
                examples=[dep],
                description=f"{dep} used in {freq:.0%} of analyzed repos",
                category="dependency",
            ))

    return patterns


def _mine_testing_patterns(analyses: list[dict]) -> Pattern:
    """Find testing patterns."""
    test_frameworks = Counter()
    has_tests_count = sum(1 for a in analyses if a["has_tests"])

    for a in analyses:
        for dep in a["dev_dependencies"]:
            dep_lower = dep.lower()
            if any(t in dep_lower for t in ["jest", "vitest", "mocha", "cypress", "playwright"]):
                test_frameworks[dep_lower] += 1

    total = len(analyses) or 1
    top_frameworks = test_frameworks.most_common(5)

    description = f"Testing adoption: {has_tests_count}/{total} repos have tests ({has_tests_count/total:.0%})\n"
    description += "Framework distribution:\n"
    for fw, count in top_frameworks:
        description += f"  {fw}: {count/total:.0%}\n"

    return Pattern(
        name="testing",
        frequency=has_tests_count / total,
        examples=[fw for fw, _ in top_frameworks],
        description=description,
        category="testing",
    )


def mine_patterns_from_analyses(analyses: list[dict]) -> list[Pattern]:
    """Extract patterns from analyzed repos."""
    patterns = []
    patterns.append(_mine_folder_patterns(analyses))
    patterns.extend(_mine_dependency_patterns(analyses))
    patterns.append(_mine_testing_patterns(analyses))
    return patterns


async def mine_patterns(
    query: str,
    max_repos: int = _MAX_REPOS,
) -> list[Pattern]:
    """
    Main entry point: search GitHub, analyze repos, extract patterns.
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": "igris-research/1.0"},
        follow_redirects=True,
    ) as client:
        repos = await _search_repos(client, query, max_repos)
        if not repos:
            return []

        sem = asyncio.Semaphore(5)

        async def _bounded_analyze(r: dict) -> dict:
            async with sem:
                return await _analyze_one_repo(client, r)

        tasks = [_bounded_analyze(r) for r in repos]
        analyses = await asyncio.gather(*tasks, return_exceptions=True)

        valid_analyses = [a for a in analyses if isinstance(a, dict)]

        return mine_patterns_from_analyses(valid_analyses)
