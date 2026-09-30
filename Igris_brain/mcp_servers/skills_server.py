"""
IGRIS BRAIN — MCP Server: skills
================================
Model Context Protocol server (stdio) that exposes the agent's meta-tools as
MCP tools, so the LLM can:

    skills__list              — available skills (S1..S6 catalog)
    skills__load(name)        — load a skill's full instructions (plan-first-fix,
                                rag-recall, cag-cache, mag-memory, preview-live-usage,
                                progressive-visual-construction, svg-artist)
    skills__plan(task)        — plan-first: break a task into an ordered plan
    skills__recall(query)     — RAG recall from Igris_Memory (L1+L2+retrieval)
    skills__cag_status()      — CAG response-cache stats
    skills__cag_invalidate()  — clear the CAG cache (after context changes)
    skills__mag_context(q)    — memory-augmented context assembly

Run by McpBridge as a subprocess (mcp_servers.json).
"""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

mcp = FastMCP("meta")


# MemoryBridge yuklanishi qimmat (BM25/FAISS indeks qurish) — har tool
# chaqiruvida qayta qurilmaydi, bir marta qurilgan singleton ishlatiladi.
_MEMORY_BRIDGE = None


def _get_memory():
    """Lazy MemoryBridge singleton (bir marta yuklanadi)."""
    global _MEMORY_BRIDGE
    if _MEMORY_BRIDGE is None:
        from agent.memory_bridge import MemoryBridge
        _MEMORY_BRIDGE = MemoryBridge(enabled=True)
    return _MEMORY_BRIDGE if _MEMORY_BRIDGE.enabled else None


# ---------------------------------------------------------------------- #
# Skills catalog
# ---------------------------------------------------------------------- #

@mcp.tool()
def skills_list() -> str:
    """List the agent's available skills (the S1..S6 catalog) with short
    descriptions. Call this first to see which skill fits the current task."""
    from skills import DEFAULT_MANAGER
    return DEFAULT_MANAGER.describe_all()


@mcp.tool()
def skills_load(name: str) -> str:
    """Load a skill's full step-by-step instructions by name. When the task
    needs a capability (planning before fixing, memory recall, caching,
    preview construction, drawing, UI build), load the matching skill first.

    Args:
        name: skill name from skills_list (e.g. plan-first-fix, rag-recall,
              cag-cache, mag-memory, preview-live-usage,
              progressive-visual-construction, svg-artist)

    Returns:
        the skill's full instruction text, or an error message.
    """
    from skills import DEFAULT_MANAGER
    skill = DEFAULT_MANAGER.get(name)
    if skill is None:
        return f"unknown skill '{name}'. Available: {DEFAULT_MANAGER.names()}"
    return skill.full_text()


# ---------------------------------------------------------------------- #
# Plan-first
# ---------------------------------------------------------------------- #

@mcp.tool()
def skills_plan(task: str) -> str:
    """PLAN-FIRST: break a task/problem into an ordered, concrete plan
    (1-3 steps: what to read/create/fix, which files, which tools) BEFORE
    touching any code. The agent must restate the problem, write the plan,
    execute step by step, verify against the plan, and fix only per-plan.

    Args:
        task: the user's task or problem description

    Returns:
        a JSON plan with goal + ordered steps.
    """
    from planning.planner import TaskPlanner
    planner = TaskPlanner(llm=None)
    import json
    return json.dumps(planner.plan(task), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------- #
# RAG recall
# ---------------------------------------------------------------------- #

@mcp.tool()
def skills_recall(query: str, top_k: int = 3) -> str:
    """RAG recall: search Igris_Memory (L1 runtime + L2 persistent + BM25/FAISS
    retrieval) for knowledge relevant to the query BEFORE answering. Use when
    the answer may exist in past solutions, facts or patterns.

    Args:
        query: short search query derived from the task
        top_k: number of hits to return (default 3)

    Returns:
        recalled context text with sources, or an empty note.
    """
    mem = _get_memory()
    if mem is None:
        return "(memory disabled - no recall available)"
    ctx, hits = mem.recall(query, top_k=top_k, max_chars=1600)
    return ctx if ctx else "(no relevant memory found)"


# ---------------------------------------------------------------------- #
# CAG cache
# ---------------------------------------------------------------------- #

@mcp.tool()
def skills_cag_status() -> str:
    """CAG (Cache-Augmented Generation) response-cache stats: size, hit rate,
    TTL. Use to decide whether caching is effective for repeated queries."""
    from agent.cag import DEFAULT_CAG
    import json
    return json.dumps(DEFAULT_CAG.status(), ensure_ascii=False)


@mcp.tool()
def skills_cag_invalidate() -> str:
    """Clear the CAG response cache. Call after context changes (files edited,
    new info learned) so stale cached answers are not reused."""
    from agent.cag import DEFAULT_CAG
    cleared = DEFAULT_CAG.invalidate()
    return f"cleared {cleared} cached responses"


# ---------------------------------------------------------------------- #
# MAG context
# ---------------------------------------------------------------------- #

@mcp.tool()
def skills_mag_context(query: str) -> str:
    """MAG (Memory-Augmented Generation): assemble a memory context for the
    query from all memory layers (L1 runtime + L2 persistent + RAG retrieval).
    Use for continuing work / decisions that depend on past session history."""
    from agent.mag import MagAssembler
    mem = _get_memory()
    mag = MagAssembler(memory=mem)
    res = mag.assemble(query)
    if not res["context"]:
        return "(no memory context - memory disabled or empty)"
    return f"[hits={res['hits']}] {res['context']}"


if __name__ == "__main__":
    mcp.run()
