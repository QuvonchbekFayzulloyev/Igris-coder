"""
Tests for igris.core.loop_generator.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.loop_generator import generate
from igris.core.task_analyzer import Complexity, analyze


def test_bug_fix_gets_debug_template():
    complexity = Complexity(tier="simple")
    plan = generate("bug_fix", complexity)
    assert plan.stages == ["Observe", "Locate", "Hypothesis", "Patch", "Test"]
    assert not plan.is_multi_branch


def test_research_gets_research_template():
    complexity = Complexity(tier="medium")
    plan = generate("research", complexity)
    assert plan.stages == ["Collect", "Analyze", "Compare", "Reason", "Find Gap"]


def test_complex_code_task_gets_extra_scoping_stage():
    complexity = Complexity(tier="complex")
    plan = generate("code_task", complexity)
    assert plan.stages[0] == "Clarify Scope"
    assert "Generate" in plan.stages


def test_multi_agent_produces_parallel_branches():
    complexity = analyze("build an ecommerce site with frontend, backend, and database")
    assert complexity.tier == "multi_agent"
    plan = generate("code_task", complexity)
    assert plan.is_multi_branch
    assert set(plan.branches.keys()) == set(complexity.subsystems)
    assert plan.branches["frontend"] == ["Design", "Components", "Routing", "Review", "Improve"]


def test_unknown_category_falls_back_to_default_template():
    complexity = Complexity(tier="simple")
    plan = generate("some_new_category", complexity)
    assert plan.stages == ["Understand", "Plan", "Execute", "Verify"]


def test_prompt_block_renders_readable_sequence():
    complexity = Complexity(tier="simple")
    plan = generate("command", complexity)
    block = plan.to_prompt_block()
    assert "Prepare -> Execute -> Verify" in block


def test_multi_branch_prompt_block_lists_each_branch():
    complexity = analyze("build frontend and backend for this app")
    plan = generate("code_task", complexity)
    block = plan.to_prompt_block()
    assert "frontend:" in block
    assert "backend:" in block
