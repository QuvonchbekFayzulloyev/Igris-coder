"""
Knowledge base MCP server.

Exposes the hierarchical project knowledge base (KnowledgeStore) as MCP
tools: search it (auto-routed to the right module scope, or explicitly
scoped) and add to it (so the DB grows as the project evolves, not just
at initial seed time). Backed by a local Ollama embedding model
(nomic-embed-text by default -- well under 8GB VRAM, see
igris/core/embeddings.py).

Run standalone for debugging:
    python -m igris.mcp_servers.knowledge_server
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

from igris.config import Config
from igris.core import knowledge_router
from igris.core.embeddings import EmbeddingClient
from igris.core.knowledge_base import KnowledgeEntry, KnowledgeStore

mcp = FastMCP("knowledge")

_CONFIG = Config.load(project_root=Path.cwd())
_STORE = KnowledgeStore(_CONFIG)
_EMBEDDER = EmbeddingClient(_CONFIG)


async def _embed_safely(text: str) -> tuple[list[float] | None, str]:
    """
    Wraps EmbeddingClient calls so a connection/timeout failure comes back
    as a clear, actionable tool error instead of an unhandled exception
    that would kill the whole MCP call (see tool-call-reliability skill).
    Returns (vector_or_None, error_message_if_any).
    """
    try:
        vec = await _EMBEDDER.embed_one(text)
    except httpx.ConnectError:
        return None, (
            f"ERROR: could not reach the embedding model at {_EMBEDDER.host} -- "
            f"is Ollama running? (ollama pull {_EMBEDDER.model})"
        )
    except httpx.TimeoutException:
        return None, f"ERROR: embedding request to {_EMBEDDER.host} timed out"
    except httpx.HTTPStatusError as e:
        return None, f"ERROR: embedding model returned {e.response.status_code} -- is '{_EMBEDDER.model}' pulled?"

    if not vec:
        return None, "ERROR: embedding model returned no vector -- is Ollama running with the embeddings model pulled?"
    return vec, ""


@mcp.tool()
async def knowledge_search(query: str, module: str = "", top_k: int = 5) -> str:
    """
    Search the project knowledge base for rules, descriptions, and
    templates relevant to `query`. If `module` is left empty, the query
    is auto-routed to the most relevant module (e.g. "backend.core",
    "frontend.components"); pass an explicit module path to force a
    specific scope. Always also considers project-wide rules.
    """
    scope = module or knowledge_router.route(query)
    query_vec, error = await _embed_safely(query)
    if error:
        return error

    results = _STORE.search(query_vec, module_path=scope, top_k=top_k)
    if not results:
        return f"(no knowledge entries found for scope '{scope or 'project'}' -- try knowledge_add to seed some)"

    lines = [f"[scope searched: {scope or 'project'}]"]
    for score, entry in results:
        lines.append(f"- ({entry.kind}, {entry.source}, score={score:.2f}) {entry.text}")
    return "\n".join(lines)


@mcp.tool()
async def knowledge_add(text: str, module: str = "", kind: str = "rule", source: str = "manual", tags: str = "") -> str:
    """
    Add a new entry to the project knowledge base. module: "" for a
    project-wide rule, or a dot-path like "backend.core" for a
    module-specific one. kind: rule | description | template.
    source: llm | web_verified | manual. tags: comma-separated.
    """
    if kind not in ("rule", "description", "template"):
        return f"ERROR: kind must be rule, description, or template (got '{kind}')"
    if source not in ("llm", "web_verified", "manual"):
        return f"ERROR: source must be llm, web_verified, or manual (got '{source}')"

    vec, error = await _embed_safely(text)
    if error:
        return error

    entry = KnowledgeEntry(
        id=str(uuid.uuid4())[:8],
        text=text,
        module_path=module,
        kind=kind,
        source=source,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        embedding=vec,
        created_at=time.time(),
    )
    _STORE.add(entry)
    return f"OK: added {kind} entry {entry.id} to scope '{module or 'project'}'"


@mcp.tool()
def knowledge_list_modules() -> str:
    """List which module-specific knowledge DBs exist (project-level DB always implicitly exists)."""
    modules = _STORE.list_modules()
    return "\n".join(["project", *modules]) if modules else "project (no module-specific DBs yet)"


if __name__ == "__main__":
    mcp.run()
