"""
igris.core.knowledge_router
-----------------------------
Routes a free-text query to the most relevant module scope in the
hierarchical knowledge base (KnowledgeStore), so a search only ever
touches the smallest relevant slice of the tree. Keyword-based and
deterministic, same style as intent_resolver's heuristic classifier --
no LLM call needed for routing itself.

The module map mirrors architecture-layer-classification's actual
findings for igris: backend and frontend are the two main modules, each
with real sub-modules underneath.
"""
from __future__ import annotations

import re

# Ordered narrowest-first so a more specific sub-module wins over its
# parent when both match (checked in this order, first sufficiently
# strong match returned).
MODULE_KEYWORDS: dict[str, list[str]] = {
    "backend.core": [r"\breprompt\b", r"\bloop\b", r"\bintent\b", r"\btask.?analyzer\b", r"\bspec\b", r"\bexecution.?graph\b"],
    "backend.mcp_servers": [r"\bmcp\b", r"\bfilesystem\b", r"\bterminal\b", r"\bgit\b", r"\btool\b"],
    "backend.providers": [r"\bprovider\b", r"\bollama\b", r"\blm.?studio\b", r"\bopenrouter\b", r"\bgateway\b"],
    "backend.server": [r"\bserver\b", r"\bapi\b", r"\bwebsocket\b", r"\bfastapi\b", r"\bendpoint\b"],
    "backend": [r"\bbackend\b", r"\bpython\b", r"\bpytest\b"],
    "frontend.components": [r"\bcomponent\b", r"\bui\b", r"\bsidebar\b", r"\bstatusbar\b", r"\bconversation\b"],
    "frontend.lib": [r"\bapi client\b", r"\bfetch\b", r"\btypes?\.ts\b"],
    "frontend": [r"\bfrontend\b", r"\breact\b", r"\btauri\b", r"\bdesktop\b", r"\bvitest\b", r"\btailwind\b"],
}


def route(query: str) -> str | None:
    """Returns the best-matching module path, or None for project-level (no specific module matched)."""
    lowered = query.lower()
    best_module: str | None = None
    best_hits = 0
    for module_path, patterns in MODULE_KEYWORDS.items():
        hits = sum(1 for p in patterns if re.search(p, lowered))
        if hits > best_hits:
            best_hits = hits
            best_module = module_path
    return best_module
