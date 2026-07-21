"""MCP surface for the reusable Coder Knowledge Memory.

Unlike session history, this server stores source-backed artefacts such as
ADRs, project structure, tested snippets, API patterns, and lessons learned.
It is intentionally safe to use without Ollama: its metadata/lexical index
still retrieves useful material when vector embeddings are unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from igris.config import Config
from igris.core.coder_memory import CoderMemoryStore, MEMORY_CATEGORIES, ProjectMemoryCollector


mcp = FastMCP("memory")
_CONFIG = Config.load(project_root=Path.cwd())
_STORE = CoderMemoryStore(_CONFIG)


def _error(exc: Exception) -> str:
    return f"ERROR: Coder Memory operation failed: {exc}"


def _render_artifact(artifact, include_content: bool = False) -> str:
    data = {
        "id": artifact.id,
        "title": artifact.title,
        "category": artifact.category,
        "subcategory": artifact.subcategory,
        "tags": artifact.tags,
        "language": artifact.language,
        "framework": artifact.framework,
        "source": artifact.source,
        "source_uri": artifact.source_uri,
        "version": artifact.version,
        "quality_score": artifact.quality_score,
        "trust_score": artifact.trust_score,
        "reuse_score": artifact.reuse_score,
        "related_items": artifact.related_items,
        "details": artifact.details,
    }
    if include_content:
        data["content"] = _STORE.read_content(artifact)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def memory_collect_project(max_files: int = 80, max_tree_entries: int = 300) -> str:
    """Collect stable project artefacts: overview/docs, ADRs, configs, and folder tree.

    This deterministic collector reads only project-owned files and upserts by
    source path/content hash; it does not scrape the web or store chat turns.
    """
    try:
        collector = ProjectMemoryCollector(_CONFIG, _STORE)
        result = collector.collect(max_files=max(1, min(max_files, 200)), max_tree_entries=max(10, min(max_tree_entries, 1_000)))
        return "OK: " + json.dumps(result, ensure_ascii=False)
    except (OSError, ValueError, TypeError) as exc:
        return _error(exc)


@mcp.tool()
def memory_ingest(
    title: str,
    category: str,
    content: str,
    subcategory: str = "",
    tags: str = "",
    language: str = "",
    framework: str = "",
    source: str = "manual",
    source_uri: str = "",
    author: str = "",
    version: str = "",
    license_name: str = "",
    quality_score: float = 0.5,
    trust_score: float = -1.0,
    reuse_score: float = 0.5,
    related_items: str = "",
    format_name: str = "markdown",
    details_json: str = "{}",
) -> str:
    """Persist a source-backed reusable artefact with standard metadata.

    category must be one of the documented Coder Memory categories. Use
    source=official/web_verified/project/internal/manual/github/llm and set
    quality/trust/reuse scores from 0 to 1. `details_json` holds category-
    specific schemas such as code complexity/tests or architecture diagrams.
    """
    try:
        details = json.loads(details_json or "{}")
        if not isinstance(details, dict):
            return "ERROR: details_json must decode to an object"
        artifact, status = _STORE.ingest(
            title=title,
            category=category,
            content=content,
            subcategory=subcategory,
            tags=tags,
            language=language,
            framework=framework,
            source=source,
            source_uri=source_uri,
            author=author,
            version=version,
            license_name=license_name,
            quality_score=quality_score,
            trust_score=None if trust_score < 0 else trust_score,
            reuse_score=reuse_score,
            related_items=related_items,
            format_name=format_name,
            details=details,
        )
        return f"OK: {status} {artifact.category} artefact {artifact.id}\n{_render_artifact(artifact)}"
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _error(exc)


@mcp.tool()
def memory_search(
    query: str,
    category: str = "",
    language: str = "",
    framework: str = "",
    tags: str = "",
    source: str = "",
    top_k: int = 5,
) -> str:
    """Hybrid metadata/content retrieval over reusable Coder Memory artefacts.

    Filter by category, language, framework, tags, or source when the task is
    specific. Results are ranked by title/tag/content relevance plus quality,
    trust, and reuse scores, so low-trust snippets do not outrank official
    project rules merely because they share a word.
    """
    try:
        hits = _STORE.search(
            query,
            category=category,
            language=language,
            framework=framework,
            tags=tags,
            source=source,
            top_k=top_k,
        )
        if not hits:
            return "(no Coder Memory artefacts matched; use memory_collect_project or memory_ingest first)"
        lines = ["[Coder Memory results]"]
        for hit in hits:
            artifact = hit.artifact
            lines.append(
                f"- score={hit.score:.2f} id={artifact.id} category={artifact.category} "
                f"source={artifact.source} trust={artifact.trust_score:.2f} title={artifact.title}\n"
                f"  {hit.excerpt}"
            )
        return "\n".join(lines)
    except (OSError, ValueError, TypeError) as exc:
        return _error(exc)


@mcp.tool()
def memory_get(artifact_id: str, include_content: bool = False) -> str:
    """Fetch one artefact's standard metadata and, optionally, its stored content."""
    try:
        artifact = _STORE.get(artifact_id)
        if artifact is None:
            return f"ERROR: Coder Memory artefact '{artifact_id}' does not exist"
        return _render_artifact(artifact, include_content=include_content)
    except (OSError, ValueError, TypeError) as exc:
        return _error(exc)


@mcp.tool()
def memory_record_lesson(problem: str, cause: str, fix: str, tags: str = "", related_items: str = "") -> str:
    """Record a reusable, evidence-backed Error -> Cause -> Fix lesson.

    Use this only after the fix has been verified. It deliberately creates a
    structured lesson rather than appending an unreviewed chat transcript.
    """
    if not problem.strip() or not cause.strip() or not fix.strip():
        return "ERROR: problem, cause, and fix must all be non-empty"
    content = f"# Problem\n{problem.strip()}\n\n# Root cause\n{cause.strip()}\n\n# Verified fix\n{fix.strip()}\n"
    try:
        artifact, status = _STORE.ingest(
            title=f"Lesson: {problem.strip()[:90]}",
            category="lesson",
            subcategory="error-cause-fix",
            content=content,
            tags=["lesson", "verified", *[tag.strip() for tag in tags.split(",") if tag.strip()]],
            source="internal",
            quality_score=0.75,
            trust_score=0.8,
            reuse_score=0.8,
            related_items=related_items,
            details={"problem": problem.strip(), "cause": cause.strip(), "fix": fix.strip()},
        )
        return f"OK: {status} verified lesson {artifact.id}"
    except (OSError, ValueError, TypeError) as exc:
        return _error(exc)


@mcp.tool()
def memory_list_categories() -> str:
    """List supported Coder Memory categories and stored counts."""
    try:
        counts = {category: len(_STORE.list(category)) for category in sorted(MEMORY_CATEGORIES)}
        return json.dumps(counts, ensure_ascii=False, indent=2)
    except OSError as exc:
        return _error(exc)


if __name__ == "__main__":
    mcp.run()
