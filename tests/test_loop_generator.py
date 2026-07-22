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
    names = [c.name for c in plan.cycles]
    assert names == ["do"]
    assert not plan.has_parallel


def test_research_gets_research_template():
    complexity = Complexity(tier="medium")
    plan = generate("research", complexity)
    names = [c.name for c in plan.cycles]
    assert "collect" in names
    assert "analyze" in names
    assert "summarize" in names or len(names) == 2


def test_complex_code_task_gets_full_pipeline():
    complexity = Complexity(tier="complex")
    plan = generate("code_task", complexity)
    names = [c.name for c in plan.cycles]
    assert names == [
        "objective", "research", "dependencies", "plan", "scaffold",
        "backend", "frontend", "diff", "test", "validate",
        "security", "preview", "analyze_preview", "performance",
        "documentation", "report",
    ]


def test_multi_agent_produces_parallel_branches():
    complexity = analyze("build an ecommerce site with frontend, backend, and database")
    assert complexity.tier == "multi_agent"
    plan = generate("code_task", complexity)
    assert plan.has_parallel
    group_names = set()
    for group in plan.parallel_groups:
        for c in group:
            prefix = c.name.split("_")[0]
            group_names.add(prefix)
    assert group_names == set(complexity.subsystems)


def test_unknown_category_falls_back_to_default_template():
    complexity = Complexity(tier="simple")
    plan = generate("some_new_category", complexity)
    names = [c.name for c in plan.cycles]
    assert names == ["do"]


def test_prompt_block_renders_readable_sequence():
    complexity = Complexity(tier="simple")
    plan = generate("command", complexity)
    block = plan.to_prompt_block()
    assert "do: Understand" in block


def test_multi_branch_prompt_block_lists_each_branch():
    complexity = analyze("build frontend and backend for this app")
    plan = generate("code_task", complexity)
    block = plan.to_prompt_block()
    assert "frontend" in block
    assert "backend" in block
