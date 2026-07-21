"""
igris.core.loop_generator
----------------------------
The "Loop Generator" from the architecture plan: given an intent category
and complexity tier, produce a concrete, named stage sequence -- the
Coding/Research/Debug/Writing loop templates described in the doc,
verbatim where they map cleanly onto igris's existing categories.

This does NOT replace RepromptLoop's own pipeline (snapshot -> intent ->
clarify -> skills -> gather -> spec -> execute -> review) -- that's the
meta-loop that always runs. What this generates is *domain* guidance
injected into the spec so the model follows a recognizable methodology
for the specific kind of work, and (for multi_agent complexity) a set of
independent subsystem branches that ExecutionGraph can run in parallel.

Deterministic and rule-based -- no LLM call -- so which template a task
gets is predictable from its category+tier alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .task_analyzer import Complexity

# Single-branch stage templates, keyed by intent category.
STAGE_TEMPLATES: dict[str, list[str]] = {
    "code_task": ["Read", "Analyze", "Think", "Plan", "Generate", "Review", "Fix", "Verify"],
    "bug_fix": ["Observe", "Locate", "Hypothesis", "Patch", "Test"],
    "research": ["Collect", "Analyze", "Compare", "Reason", "Find Gap"],
    "review": ["Read", "Analyze", "Compare to standard", "Report"],
    "command": ["Prepare", "Execute", "Verify"],
    "question": ["Answer directly", "Elaborate if useful"],
}

# Writing isn't one of igris's intent categories yet, but the doc names it
# explicitly -- kept available for skills/spec code that wants it.
WRITING_TEMPLATE = ["Goal", "Audience", "Outline", "Draft", "Improve", "Grammar", "Finalize"]

DEFAULT_TEMPLATE = ["Understand", "Plan", "Execute", "Verify"]

# Subsystem sub-loops used when complexity is multi_agent -- mirrors the
# doc's ecommerce-site example (Frontend / Backend / Database, each its
# own loop, run independently).
SUBSYSTEM_TEMPLATES: dict[str, list[str]] = {
    "frontend": ["Design", "Components", "Routing", "Review", "Improve"],
    "backend": ["Schema", "API", "Business Logic", "Security", "Testing"],
    "database": ["Schema", "Migrations", "Indexes", "Review"],
    "testing": ["Test Plan", "Write Tests", "Run", "Report"],
    "deployment": ["Build", "Configure", "Deploy", "Verify"],
}


@dataclass
class LoopPlan:
    stages: list[str] = field(default_factory=list)
    # only set for multi_agent complexity: name -> stage list, each branch
    # independent enough to run concurrently via ExecutionGraph.
    branches: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_multi_branch(self) -> bool:
        return bool(self.branches)

    def to_prompt_block(self) -> str:
        if self.is_multi_branch:
            parts = ["This task spans independent subsystems, handled as parallel branches:"]
            for name, stages in self.branches.items():
                parts.append(f"- {name}: {' -> '.join(stages)}")
            return "\n".join(parts)
        return f"Follow this stage sequence: {' -> '.join(self.stages)}"


def generate(intent_category: str, complexity: Complexity) -> LoopPlan:
    if complexity.tier == "multi_agent" and complexity.subsystems:
        branches = {
            name: SUBSYSTEM_TEMPLATES.get(name, DEFAULT_TEMPLATE)
            for name in complexity.subsystems
        }
        return LoopPlan(branches=branches)

    stages = list(STAGE_TEMPLATES.get(intent_category, DEFAULT_TEMPLATE))

    # complex (single-subsystem) tasks get an extra up-front planning stage
    # that simple/medium tasks skip, to avoid over-processing quick asks.
    if complexity.tier == "complex" and stages and stages[0] != "Plan":
        stages = ["Clarify Scope"] + stages

    return LoopPlan(stages=stages)
