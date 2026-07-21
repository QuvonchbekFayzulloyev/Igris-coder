"""
Integration test: a request naming multiple independent subsystems should
flow all the way through complexity=multi_agent -> loop_generator branches
-> ExecutionGraph parallel execution -> a single merged, reviewed response.
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
from igris.core.reprompt_loop import RepromptLoop
from igris.core.skill_loader import SkillLoader

from mock_llm import MockLLM


@pytest.fixture
def project(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    return config


def make_loop(config, llm):
    memory = Memory(config)
    context_engine = ContextEngine(config, memory)
    intent_resolver = IntentResolver(config, llm=llm)
    skills = SkillLoader(config)
    return RepromptLoop(config, llm, None, skills, context_engine, intent_resolver, memory)


def test_multi_subsystem_request_runs_branches_and_merges(project):
    # sorted branch order for {frontend, backend, database} is:
    # backend, database, frontend -- ExecutionGraph._layers() sorts each layer.
    llm = MockLLM(
        chat_responses=["PASS\nall subsystems covered"],
        run_responses=["backend done: API + schema", "database done: migrations", "frontend done: components"],
    )
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run(
        "build an ecommerce site with frontend, backend, and a database schema"
    ))

    assert result.needs_clarification is False
    assert "## Backend" in result.final_response
    assert "## Database" in result.final_response
    assert "## Frontend" in result.final_response
    assert "backend done" in result.final_response
    assert "database done" in result.final_response
    assert "frontend done" in result.final_response
    # 3 branches ran (run_with_tools called 3x) + 1 review chat call
    assert len(llm.run_calls) == 3
    assert len(llm.chat_calls) == 1


def test_multi_agent_trace_records_branch_names(project):
    llm = MockLLM(run_responses=["b", "d", "f"])
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("build frontend and backend and database for this app"))

    stages = dict(result.trace)
    assert "multi_agent" in stages
    assert "backend" in stages["multi_agent"]
    assert "frontend" in stages["multi_agent"]


def test_single_subsystem_request_does_not_trigger_multi_agent(project):
    """Sanity check: naming only one subsystem should NOT fan out into branches."""
    llm = MockLLM(run_responses=["added the endpoint"])
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("add a new API endpoint for user login"))

    assert "## Backend" not in result.final_response
    assert len(llm.run_calls) == 1


def test_multi_agent_tokens_sum_across_all_branches(project):
    # sorted branch order for {frontend, backend, database} is:
    # backend, database, frontend
    llm = MockLLM(
        chat_responses=["PASS\nall covered"],
        run_responses=["backend done", "database done", "frontend done"],
        chat_tokens=[(40, 12)],
        run_tokens=[(100, 20), (110, 22), (120, 25)],
    )
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run(
        "build an ecommerce site with frontend, backend, and a database schema"
    ))

    assert result.prompt_tokens == 100 + 110 + 120 + 40
    assert result.completion_tokens == 20 + 22 + 25 + 12


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
