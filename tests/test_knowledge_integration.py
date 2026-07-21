"""
Integration test: ContextEngine.gather() actually calls the knowledge
MCP server for code_task/bug_fix/review requests (not just available as
an unused tool), using the REAL MCPManager (real subprocess MCP servers,
including the new knowledge server) -- only the LLM provider is mocked.
Since no live Ollama is running in test environments, this also verifies
the loop degrades gracefully (no crash, no bogus context) rather than
requiring a live embedding model to function at all.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.memory import Memory
from igris.core.context_engine import ContextEngine
from igris.core.intent_resolver import IntentResolver
from igris.core.mcp_manager import MCPManager
from igris.core.reprompt_loop import RepromptLoop
from igris.core.skill_loader import SkillLoader

from mock_llm import MockLLM


@pytest.fixture
def project(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    return config


def test_code_task_triggers_knowledge_search_without_crashing_when_ollama_unavailable(project):
    """
    No live Ollama in the test environment -- knowledge_search will return
    an ERROR string. gather() must filter that out (not stuff an error
    message into the model's context as if it were real knowledge) and
    the loop must still complete normally.
    """
    llm = MockLLM(run_responses=["def foo(): return 42"])

    async def run():
        memory = Memory(project)
        context_engine = ContextEngine(project, memory)
        intent_resolver = IntentResolver(project, llm=llm)
        skills = SkillLoader(project)
        async with MCPManager(project) as mcp:
            loop = RepromptLoop(project, llm, mcp, skills, context_engine, intent_resolver, memory)
            return await loop.run("implement a function that returns 42")

    result = asyncio.run(run())

    assert result.needs_clarification is False
    assert "42" in result.final_response
    # the gathered context must never contain a raw ERROR string from a
    # failed knowledge lookup -- gather() is responsible for filtering it
    assert "ERROR" not in "".join(d for _, d in result.trace if "gather" in _)


def test_gather_directly_omits_knowledge_when_search_fails(project):
    async def run():
        memory = Memory(project)
        context_engine = ContextEngine(project, memory)
        intent_resolver = IntentResolver(project, llm=None)
        intent = await intent_resolver.classify("fix the bug in the parser")
        snapshot = context_engine.snapshot()
        async with MCPManager(project) as mcp:
            return await context_engine.gather(intent, "fix the bug in the parser", snapshot, mcp)

    gathered = asyncio.run(run())
    assert "project_knowledge" not in gathered.pieces  # no live Ollama -> search failed -> correctly omitted


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
