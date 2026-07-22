"""
igris.core.loop_generator
---------------------------
The "Loop Generator" from the architecture plan: given an intent category
and complexity tier, produce a concrete set of mini work cycles (branches).

Instead of ONE big agentic loop, every task is decomposed into focused
mini work cycles:
  - Each cycle has a specific goal and relevant tool subset
  - Cycles run sequentially (or parallel for independent subsystems)
  - Each cycle is verified before the next starts
  - No single cycle does "everything"

This prevents the model from getting confused by too much context,
reduces token waste, and improves output quality.

Deterministic and rule-based -- no LLM call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .task_analyzer import Complexity

TOOL_SUBSETS: dict[str, list[str]] = {
    "read": ["read", "glob", "grep"],
    "plan": ["read", "glob", "grep", "question"],
    "write": ["read", "write", "edit", "glob"],
    "code": ["read", "write", "edit", "glob", "grep", "bash", "git", "terminal"],
    "test": ["read", "bash", "terminal", "glob", "grep"],
    "review": ["read", "glob", "grep"],
    "research": ["read", "glob", "grep", "websearch", "webfetch"],
    "deps": ["read", "bash", "terminal", "glob", "grep"],
    "validate": ["read", "bash", "terminal", "glob", "grep"],
    "security": ["read", "grep", "glob", "bash"],
    "performance": ["read", "bash", "terminal", "glob", "grep"],
    "diff": ["read", "bash", "git"],
    "docs": ["read", "write", "edit", "glob"],
    "report": ["read", "write"],
    "preview": ["read", "bash", "terminal", "browser", "desktop"],
    "analyze_preview": ["read", "bash", "desktop", "browser"],
}

# Full 14-stage pipeline for complex code tasks
FULL_PIPELINE = [
    {"name": "objective", "goal": "Analyze objective: clarify goal and identify constraints", "tools": "plan"},
    {"name": "research", "goal": "Read official docs, API references, and source code for the relevant technologies", "tools": "research"},
    {"name": "dependencies", "goal": "Detect missing packages, SDKs, MCP servers; install what is available", "tools": "deps"},
    {"name": "plan", "goal": "Design architecture and create execution plan", "tools": "plan"},
    {"name": "scaffold", "goal": "Create project structure and config files", "tools": "code"},
    {"name": "backend", "goal": "Implement backend logic", "tools": "code"},
    {"name": "frontend", "goal": "Implement frontend UI", "tools": "code"},
    {"name": "diff", "goal": "Show only changed files and lines using git diff", "tools": "diff"},
    {"name": "test", "goal": "Write and run unit/integration tests", "tools": "test"},
    {"name": "validate", "goal": "Run lint, type-check, build to verify code quality", "tools": "validate"},
    {"name": "security", "goal": "Check for common security vulnerabilities", "tools": "security"},
    {"name": "preview", "goal": "Run live preview: start server, auto-detect project type (web/api/cli/desktop), run tests", "tools": "preview"},
    {"name": "analyze_preview", "goal": "Analyze preview results: screenshots, console/network logs, test reports", "tools": "analyze_preview"},
    {"name": "performance", "goal": "Evaluate performance implications and optimize", "tools": "performance"},
    {"name": "documentation", "goal": "Update README, API docs, usage guides", "tools": "docs"},
    {"name": "report", "goal": "Summarize what was done, what remains, and how to use the result", "tools": "report"},
]

MINI_CYCLE_TEMPLATES: dict[str, list[dict]] = {
    "code_task": [
        {"name": "plan", "goal": "Plan architecture and structure", "tools": "plan"},
        {"name": "scaffold", "goal": "Create project structure and config files", "tools": "code"},
        {"name": "backend", "goal": "Implement backend logic", "tools": "code"},
        {"name": "frontend", "goal": "Implement frontend UI", "tools": "code"},
        {"name": "diff", "goal": "Show only changed files and lines using git diff", "tools": "diff"},
        {"name": "test", "goal": "Write and run tests", "tools": "test"},
        {"name": "validate", "goal": "Run lint, type-check, build to verify code quality", "tools": "validate"},
        {"name": "review", "goal": "Review and fix issues", "tools": "review"},
    ],
    "bug_fix": [
        {"name": "observe", "goal": "Reproduce the bug and gather context", "tools": "read"},
        {"name": "diagnose", "goal": "Find root cause", "tools": "read"},
        {"name": "patch", "goal": "Implement the fix", "tools": "code"},
        {"name": "diff", "goal": "Show only changed lines using git diff", "tools": "diff"},
        {"name": "verify", "goal": "Verify the fix works", "tools": "test"},
        {"name": "validate", "goal": "Check code quality with lint and type-check", "tools": "validate"},
    ],
    "research": [
        {"name": "collect", "goal": "Gather information from docs and web", "tools": "research"},
        {"name": "analyze", "goal": "Analyze collected data", "tools": "plan"},
        {"name": "summarize", "goal": "Summarize findings", "tools": "write"},
    ],
    "review": [
        {"name": "read", "goal": "Read the code being reviewed", "tools": "read"},
        {"name": "analyze", "goal": "Check correctness, security, performance, style", "tools": "review"},
        {"name": "report", "goal": "Write review report with actionable feedback", "tools": "write"},
    ],
    "command": [
        {"name": "prepare", "goal": "Understand the command and context", "tools": "read"},
        {"name": "execute", "goal": "Run the command", "tools": "code"},
        {"name": "verify", "goal": "Check the result", "tools": "test"},
    ],
}

DEFAULT_CYCLES = [
    {"name": "understand", "goal": "Understand the request", "tools": "read"},
    {"name": "plan", "goal": "Plan the approach", "tools": "plan"},
    {"name": "execute", "goal": "Execute the plan", "tools": "code"},
    {"name": "verify", "goal": "Verify the result", "tools": "test"},
]

# Domain-adaptive templates that override per-domain when matched
DOMAIN_CYCLE_TEMPLATES: dict[str, list[dict]] = {
    "data_science": [
        {"name": "objective", "goal": "Analyze objective: clarify goal and identify constraints", "tools": "plan"},
        {"name": "explore", "goal": "Explore and understand the data", "tools": "read"},
        {"name": "dependencies", "goal": "Check and install missing data science packages", "tools": "deps"},
        {"name": "preprocess", "goal": "Clean and preprocess data", "tools": "code"},
        {"name": "analyze", "goal": "Run analysis or build models", "tools": "code"},
        {"name": "evaluate", "goal": "Evaluate results and validate", "tools": "test"},
        {"name": "validate", "goal": "Check code quality and reproducibility", "tools": "validate"},
        {"name": "report", "goal": "Document findings and visuals", "tools": "write"},
    ],
    "devops": [
        {"name": "objective", "goal": "Analyze objective: clarify goal and identify constraints", "tools": "plan"},
        {"name": "research", "goal": "Research infrastructure docs and best practices", "tools": "research"},
        {"name": "dependencies", "goal": "Check and install missing CLI tools and SDKs", "tools": "deps"},
        {"name": "plan", "goal": "Plan infrastructure changes", "tools": "plan"},
        {"name": "configure", "goal": "Implement configuration or pipeline", "tools": "code"},
        {"name": "deploy", "goal": "Deploy and verify", "tools": "test"},
        {"name": "validate", "goal": "Validate configs and syntax", "tools": "validate"},
        {"name": "security", "goal": "Check security posture of configs", "tools": "security"},
        {"name": "monitor", "goal": "Set up monitoring and alerting", "tools": "code"},
        {"name": "report", "goal": "Summarize what was configured and how to use it", "tools": "report"},
    ],
    "writing": [
        {"name": "objective", "goal": "Analyze objective: clarify goal and audience", "tools": "plan"},
        {"name": "research", "goal": "Research topic and gather references", "tools": "research"},
        {"name": "outline", "goal": "Create content outline", "tools": "plan"},
        {"name": "draft", "goal": "Write the first draft", "tools": "write"},
        {"name": "review", "goal": "Review and polish for clarity and accuracy", "tools": "review"},
        {"name": "report", "goal": "Summarize what was created", "tools": "report"},
    ],
    "design": [
        {"name": "objective", "goal": "Analyze objective: clarify goal and constraints", "tools": "plan"},
        {"name": "research", "goal": "Research design patterns and references", "tools": "research"},
        {"name": "wireframe", "goal": "Create wireframes or layout plan", "tools": "plan"},
        {"name": "dependencies", "goal": "Check and install design/build tools", "tools": "deps"},
        {"name": "implement", "goal": "Implement the design", "tools": "code"},
        {"name": "validate", "goal": "Validate output quality", "tools": "validate"},
        {"name": "review", "goal": "Review design consistency", "tools": "review"},
        {"name": "report", "goal": "Summarize what was designed", "tools": "report"},
    ],
}


@dataclass
class MiniCycle:
    name: str
    goal: str
    tool_group: str
    result: str = ""


@dataclass
class LoopPlan:
    cycles: list[MiniCycle] = field(default_factory=list)
    parallel_groups: list[list[MiniCycle]] = field(default_factory=list)

    @property
    def has_parallel(self) -> bool:
        return bool(self.parallel_groups)

    @property
    def total_cycles(self) -> int:
        return len(self.cycles) + sum(len(g) for g in self.parallel_groups) if self.parallel_groups else len(self.cycles)

    def to_prompt_block(self) -> str:
        lines = ["Execute the task as focused mini work cycles, one at a time:"]
        for i, c in enumerate(self.cycles, 1):
            lines.append(f"  {i}. [{c.tool_group}] {c.name}: {c.goal}")
        if self.parallel_groups:
            lines.append("Parallel groups (run concurrently):")
            for group in self.parallel_groups:
                names = ", ".join(c.name for c in group)
                lines.append(f"  - {names}")
        return "\n".join(lines)


def _select_cycles(intent_category: str, complexity: Complexity) -> list[dict]:
    """Pick a template. Domain-adaptive templates take priority over intent-based ones.

    For complex code tasks use the full 14-stage pipeline.
    For complex domain tasks use the full domain-specific template.
    For medium: first half of the template.
    For simple: single do cycle.
    """
    if complexity.tier == "complex" and complexity.domain == "software_engineering":
        return FULL_PIPELINE

    domain_templates = DOMAIN_CYCLE_TEMPLATES.get(complexity.domain)
    if domain_templates:
        template = domain_templates
    else:
        template = MINI_CYCLE_TEMPLATES.get(intent_category, DEFAULT_CYCLES)

    if complexity.tier == "simple":
        return [{"name": "do", "goal": template[0]["goal"], "tools": "code"}]
    elif complexity.tier == "medium":
        return template[:2]
    else:
        return template


def generate(intent_category: str, complexity: Complexity) -> LoopPlan:
    if complexity.tier == "multi_agent" and complexity.subsystems:
        groups = []
        for sub in complexity.subsystems:
            domain_templates = DOMAIN_CYCLE_TEMPLATES.get(complexity.domain)
            template = (domain_templates or
                       MINI_CYCLE_TEMPLATES.get(sub if sub in MINI_CYCLE_TEMPLATES else intent_category,
                                                DEFAULT_CYCLES))
            groups.append([MiniCycle(name=f"{sub}_{c['name']}", goal=c['goal'], tool_group=c['tools']) for c in template])
        return LoopPlan(parallel_groups=groups)

    cycles_raw = _select_cycles(intent_category, complexity)
    cycles = [MiniCycle(name=c["name"], goal=c["goal"], tool_group=c["tools"]) for c in cycles_raw]
    return LoopPlan(cycles=cycles)
