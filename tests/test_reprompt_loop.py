"""
Tests for the mini-loop (RepromptLoop). Run with:
    python -m pytest tests/ -v
No live Ollama server is needed -- MockLLM stands in for OllamaClient.
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
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


def make_loop(config, llm, mcp_manager=None):
    memory = Memory(config)
    context_engine = ContextEngine(config, memory)
    intent_resolver = IntentResolver(config, llm=llm)
    skills = SkillLoader(config)
    return RepromptLoop(config, llm, mcp_manager, skills, context_engine, intent_resolver, memory)


def test_ambiguous_input_triggers_clarification(project):
    llm = MockLLM()
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("hmm"))

    assert result.needs_clarification is True
    assert result.clarifying_question
    assert len(llm.run_calls) == 0  # never reached execution stage


def test_clear_code_task_runs_and_passes_review(project):
    llm = MockLLM(chat_responses=["PASS\nlooks good"], run_responses=["def foo(): return 42"])
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function that returns 42, fix the bug in main.py"))

    assert result.needs_clarification is False
    assert "42" in result.final_response
    assert len(llm.run_calls) == 1  # passed on first attempt, no retry
    assert result.iterations == 1


def test_question_uses_context_aware_system_prompt_without_tools(project):
    llm = MockLLM(chat_responses=["Use a TaskSpec to structure agent work."])
    loop = make_loop(project, llm)
    loop.memory.log_turn("user", "We are designing the local coding agent.")

    result = asyncio.run(loop.run("What is the purpose of a TaskSpec?"))

    assert result.final_response.startswith("Use a TaskSpec")
    assert len(llm.run_calls) == 0
    assert len(llm.chat_calls) == 1
    system_message, user_message = llm.chat_calls[0]
    assert "conversation mode" in system_message["content"].lower()
    assert "purpose of a TaskSpec" in user_message["content"]
    assert "designing the local coding agent" in user_message["content"]


def test_agentic_prompt_receives_snapshot_context_and_system_boundaries(project):
    llm = MockLLM(chat_responses=["PASS\nlooks good"], run_responses=["done"])
    loop = make_loop(project, llm)
    loop.memory.log_turn("assistant", "We use MCP for workspace actions.")

    asyncio.run(loop.run("implement a system prompt for the agent"))

    system_prompt, user_prompt = llm.run_calls[0]
    assert "agentic task-execution mode" in system_prompt
    assert "destructive action" in system_prompt
    assert "Coder Memory" in system_prompt
    assert "Working directory:" in user_prompt
    assert "We use MCP for workspace actions" in user_prompt


def test_review_failure_triggers_bounded_retry(project):
    # First review FAILs with feedback, second PASSes.
    llm = MockLLM(
        chat_responses=["FAIL\nmissing edge case handling", "PASS\ngood now"],
        run_responses=["first draft", "second draft with edge cases"],
    )
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function to fix the bug, add validation"))

    assert len(llm.run_calls) == 2
    assert result.iterations == 2
    assert result.final_response == "second draft with edge cases"
    # feedback from the failed review should have been folded into attempt 2's system prompt
    second_system_prompt = llm.run_calls[1][0]
    assert "missing edge case handling" in second_system_prompt


def test_review_always_fails_is_bounded_by_max_iterations(project):
    project.data["loop"]["max_review_iterations"] = 2
    llm = MockLLM(chat_responses=["FAIL\nstill not right"], run_responses=["draft"])
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function to fix the bug"))

    assert len(llm.run_calls) == 2  # capped, never runs forever
    assert result.iterations == 2


def test_self_review_can_be_disabled(project):
    project.data["loop"]["enable_self_review"] = False
    llm = MockLLM(run_responses=["draft, no review needed"])
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function to fix the bug"))

    assert len(llm.chat_calls) == 0  # review path never invoked
    assert len(llm.run_calls) == 1


def test_skill_routing_selects_relevant_skill(project):
    llm = MockLLM()
    loop = make_loop(project, llm)
    skills = loop.skills.select(
        loop.intent_resolver._heuristic("please review my code_task changes"),
        "please review my code_task changes",
    )
    names = {s.name for s in skills}
    assert "quality-reviewer" in names or "specification-expander" in names


def test_token_usage_sums_across_attempt_and_review_calls(project):
    llm = MockLLM(
        chat_responses=["PASS\nlooks good"],
        run_responses=["def foo(): return 42"],
        chat_tokens=[(50, 10)],   # the self-review call
        run_tokens=[(200, 40)],   # the run_with_tools call
    )
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function that returns 42"))

    assert result.prompt_tokens == 200 + 50
    assert result.completion_tokens == 40 + 10


def test_token_usage_accumulates_across_retries(project):
    llm = MockLLM(
        chat_responses=["FAIL\nneeds work", "PASS\ngood now"],
        run_responses=["first draft", "second draft"],
        chat_tokens=[(30, 8), (35, 9)],
        run_tokens=[(100, 20), (120, 25)],
    )
    loop = make_loop(project, llm)

    result = asyncio.run(loop.run("implement a function to fix the bug"))

    assert result.iterations == 2
    assert result.prompt_tokens == 100 + 30 + 120 + 35
    assert result.completion_tokens == 20 + 8 + 25 + 9


def test_no_tokens_reported_when_clarification_is_needed(project):
    llm = MockLLM()
    loop = make_loop(project, llm)
    result = asyncio.run(loop.run("hmm"))
    assert result.needs_clarification is True
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
