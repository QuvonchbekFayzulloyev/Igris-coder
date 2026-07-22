"""
igris.core.spec
----------------
Stage 6 of the mini-loop: turn a raw, possibly-vague user message into a
structured TaskSpec -- this *is* the "reprompt" the user asked for. The
model never sees the raw message alone; it sees this synthesized spec,
which is what actually drives higher-quality output.

The system prompt is built from the Universal Autonomous Expert Agent
Constitution: the agent is not just a coding assistant, but an autonomous
expert that dynamically adapts to any domain (software engineering,
research, data science, writing, DevOps, design, etc.) and acquires
whatever resources and workflow the task requires.
"""
from __future__ import annotations

from dataclasses import dataclass, field


DOMAIN_CATEGORIES = {
    "software_engineering": {"code_task", "bug_fix", "review", "command"},
    "research": {"research", "question"},
    "data_science": set(),
    "devops": set(),
    "writing": set(),
    "design": set(),
}


UNIVERSAL_CONSTITUTION = [
    "You are a universal autonomous expert — not limited to coding. Adapt your workflow to the domain the task requires: software engineering, research, data science, writing, DevOps, UI/UX design, or any other field.",
    "Documentation first: before making important decisions, read official docs, specs, API references, source code, or research papers. Never rely solely on memory.",
    "Autonomous resource acquisition: if the task requires missing tools, SDKs, packages, runtimes, APIs, MCP servers, or other resources, acquire them from official sources, configure, verify, then continue.",
    "Task decomposition: break every objective into the smallest meaningful units. Complete them incrementally. Monitor progress and re-plan as needed.",
    "Self-critique: act as your own reviewer. Search for mistakes, weak assumptions, and better alternatives. Improve continuously.",
    "Verify everything: check correctness, performance, security, accuracy, consistency, maintainability, compatibility, and quality. Assume the first answer is incomplete.",
    "Quality over speed: optimize for correctness, clarity, robustness, maintainability, reliability, and reproducibility.",
    "Minimize user questions: discover information automatically whenever possible. Ask only when a genuine human decision is required.",
    "Never stop at the first obstacle: diagnose, research, adapt, retry, continue. Only conclude failure after exhausting multiple reasonable strategies.",
]

DEFAULT_CONSTRAINTS = UNIVERSAL_CONSTITUTION + [
    "Windows-first: assume native Windows unless the user explicitly asks for WSL/Linux.",
    "Keep code and technical documentation in English even if the conversation is in Uzbek.",
    "Prefer complete, directly runnable output over partial snippets or placeholders.",
]


CONVERSATION_SYSTEM_PROMPT = (
    "You are igris, a universal autonomous expert assistant.\n\n"
    "This is conversation mode — you answer questions directly using supplied context. "
    "Tools are unavailable in this mode; if the user asks you to perform work, "
    "let the request be handled by the agentic task flow instead.\n\n"
    "## Operating principles\n"
    + "\n".join(f"- {c}" for c in UNIVERSAL_CONSTITUTION)
)


def build_conversation_messages(user_input: str, conversation_context: str = "") -> list[dict[str, str]]:
    """Build the complete message contract for a non-agentic chat turn.

    Context remains in the user message instead of the system message: it is
    reference material, not a source of authority that can override the
    assistant's operating rules. Keeping this shape shared and explicit makes
    small local models less likely to confuse a conversational answer with a
    workspace action.
    """
    user_parts = ["## User message", user_input]
    if conversation_context:
        user_parts += ["", "## Conversation and workspace context", conversation_context]
    return [
        {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


@dataclass
class TaskSpec:
    original_input: str
    intent_category: str
    domain: str = "software_engineering"
    acceptance_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=lambda: list(DEFAULT_CONSTRAINTS))
    context_block: str = ""
    conversation_context: str = ""
    skill_block: str = ""
    loop_block: str = ""  # rendered from loop_generator.LoopPlan.to_prompt_block()
    feedback_history: list[str] = field(default_factory=list)

    def with_feedback(self, feedback: str) -> "TaskSpec":
        new = TaskSpec(
            original_input=self.original_input,
            intent_category=self.intent_category,
            domain=self.domain,
            acceptance_criteria=self.acceptance_criteria,
            constraints=self.constraints,
            context_block=self.context_block,
            conversation_context=self.conversation_context,
            skill_block=self.skill_block,
            loop_block=self.loop_block,
            feedback_history=self.feedback_history + [feedback],
        )
        return new

    def to_system_prompt(self, tool_description: str = "") -> str:
        parts = [
            "You are igris, a universal autonomous expert running against a local or "
            "gateway-routed LLM. This is agentic task-execution mode.",
            "",
            f"## Current domain: {self.domain}",
            f"Task type: {self.intent_category}",
            "",
            "### Constitution (operating principles)",
            *[f"- {c}" for c in UNIVERSAL_CONSTITUTION],
            "",
            "### Task constraints",
            *[f"- {c}" for c in self.constraints],
            "",
            "### Pipeline stages",
            "Each mini-cycle targets one stage. Respect the stage boundaries:",
            "- **Objective analysis**: state your understanding of the goal and constraints before acting.",
            "- **Research**: read official docs, API refs, source code. Never rely solely on memory.",
            "- **Dependencies**: detect missing packages/SDKs/MCPs and install them automatically.",
            "- **Plan**: propose architecture before writing code.",
            "- **Diff**: after each implementation cycle, show exactly what changed (git diff style).",
            "- **Test**: write and run tests that validate correctness.",
            "- **Validation**: run lint, type-check, build. Fix all issues.",
            "- **Security**: check for OWASP Top 10, hardcoded secrets, injection risks.",
            "- **Performance**: evaluate query count, bundle size, algorithmic complexity.",
            "- **Documentation**: update README, API docs, inline comments for new code.",
            "- **Report**: end with a summary of what was done, what remains, and how to use the result.",
        ]
        if self.loop_block:
            parts += ["", "### Methodology", self.loop_block]
        if tool_description:
            parts += ["", "### Available tools", tool_description]
        if self.skill_block:
            parts += ["", "### Relevant skill guidance", self.skill_block]
        if self.feedback_history:
            parts += ["", "### Feedback from previous attempt(s) — address these"]
            parts += [f"- {fb}" for fb in self.feedback_history]
        return "\n".join(parts)


    def to_user_prompt(self) -> str:
        parts = [
            f"## Task ({self.intent_category})",
            self.original_input,
        ]
        if self.acceptance_criteria:
            parts += ["", "## Acceptance criteria (your output should satisfy all of these)"]
            parts += [f"- {c}" for c in self.acceptance_criteria]
        if self.conversation_context:
            parts += ["", "## Conversation and workspace context", self.conversation_context]
        if self.context_block:
            parts += ["", "## Relevant project context", self.context_block]
        return "\n".join(parts)


def synthesize_acceptance_criteria(intent_category: str, user_text: str) -> list[str]:
    """
    Deterministic, category-specific acceptance criteria. Kept rule-based
    (no LLM call) so spec synthesis is fast and reproducible; the self-review
    stage is where the model actually gets judged against these.
    """
    base = {
        "code_task": [
            "Output is complete and directly usable, not a fragment requiring the user to fill gaps.",
            "Any new files or commands needed to run the result are stated explicitly.",
            "Documentation (README or inline) is updated to reflect changes.",
            "Lint and type-check pass; no new warnings introduced.",
            "No hardcoded secrets, credentials, or security-sensitive data.",
            "Performance implications are considered (query count, bundle size, runtime complexity).",
        ],
        "bug_fix": [
            "Root cause is identified, not just a symptom patch.",
            "Explains what was wrong before showing the fix.",
            "Fix is verified to resolve the original issue.",
            "No regressions introduced (lint, type-check, tests pass).",
        ],
        "review": [
            "Covers correctness, then security, then performance, then style/structure -- in that order.",
            "Every criticism is actionable (says what to change, not just that something is wrong).",
            "Security vulnerabilities are flagged with severity.",
        ],
        "research": [
            "Directly answers the question asked before adding tangential detail.",
            "Distinguishes well-established facts from anything uncertain.",
            "Sources are cited where applicable.",
        ],
        "command": [
            "States the exact command(s) to run and what output to expect.",
            "Flags anything destructive or irreversible before running it.",
        ],
        "question": [
            "Answers directly first; elaborates only after the direct answer.",
        ],
    }
    return base.get(intent_category, ["Directly addresses what the user asked, without padding."])
