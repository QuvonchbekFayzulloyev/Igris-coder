"""
igris.core.task_analyzer
---------------------------
Extends intent classification with a complexity tier -- the "Task
Analyzer" from the architecture plan. Runs after IntentResolver has
already resolved a confident category; this only decides *how big* the
job is, which the Loop Generator uses to pick (and possibly expand) a
stage template.

Tiers, cheapest signal to most expensive:
    simple       short, single clear ask, touches ~0-1 files
    medium       a few steps or a couple of files, still one subsystem
    complex      long/detailed ask, several files, or explicit
                 architecture/design-system language
    multi_agent  the ask spans multiple independent subsystems
                 (frontend + backend + database, etc.) -- these can run
                 as parallel branches in the Execution Graph

Purely heuristic (word/connector/subsystem counting) -- no LLM call, so
it's free to run on every turn.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CONNECTOR_PATTERNS = [
    r"\band\b", r"\bthen\b", r"\balso\b", r"\bafter that\b",
    r"\bva\b", r"\bkeyin\b", r"so'ngra", r"\bhamda\b",
]

SUBSYSTEM_KEYWORDS = {
    "frontend": [r"\bfrontend\b", r"\bui\b", r"\bcomponent(s)?\b", r"\bpage(s)?\b"],
    "backend": [r"\bbackend\b", r"\bapi\b", r"\bserver\b", r"\bendpoint(s)?\b"],
    "database": [r"\bdatabase\b", r"\bschema\b", r"\bmigration(s)?\b", r"\bsql\b"],
    "testing": [r"\btest(s|ing)?\b"],
    "deployment": [r"\bdeploy(ment)?\b", r"\bci/?cd\b", r"\bdocker\b"],
}

ARCHITECTURE_LANGUAGE = [
    r"\barchitecture\b", r"\bdesign system\b", r"\bend[- ]to[- ]end\b",
    r"\bfull(-| )stack\b", r"\bfrom scratch\b", r"\bmicroservice(s)?\b",
]

PATH_PATTERN = re.compile(r"[\w\-./\\]+\.\w{1,6}")

TIERS = ("simple", "medium", "complex", "multi_agent")


@dataclass
class Complexity:
    tier: str
    reasons: list[str] = field(default_factory=list)
    subsystems: list[str] = field(default_factory=list)  # populated only for multi_agent


def _count_matches(patterns: list[str], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text))


def analyze(text: str, intent=None) -> Complexity:
    lowered = text.lower()
    word_count = len(text.split())
    connector_hits = _count_matches(CONNECTOR_PATTERNS, lowered)
    file_hits = len(PATH_PATTERN.findall(text))
    architecture_hits = _count_matches(ARCHITECTURE_LANGUAGE, lowered)

    subsystems_hit = [
        name for name, patterns in SUBSYSTEM_KEYWORDS.items() if _count_matches(patterns, lowered) > 0
    ]

    reasons = []

    # multi_agent: at least 2 independent subsystems explicitly named
    if len(subsystems_hit) >= 2:
        reasons.append(f"mentions {len(subsystems_hit)} independent subsystems: {', '.join(subsystems_hit)}")
        return Complexity(tier="multi_agent", reasons=reasons, subsystems=subsystems_hit)

    # complex: architecture-scale language, touching many files outright,
    # or long + several files/connectors together
    if architecture_hits > 0:
        reasons.append("uses architecture/full-stack/from-scratch language")
        return Complexity(tier="complex", reasons=reasons)
    if file_hits >= 4:
        reasons.append(f"touches many files ({file_hits})")
        return Complexity(tier="complex", reasons=reasons)
    if word_count > 40 and (connector_hits >= 2 or file_hits >= 3):
        reasons.append(f"long request ({word_count} words) with {connector_hits} connectors, {file_hits} files")
        return Complexity(tier="complex", reasons=reasons)

    # medium: some multi-step structure or a couple of files
    if connector_hits >= 1 or file_hits >= 2 or word_count > 18:
        reasons.append(f"{connector_hits} connectors, {file_hits} files, {word_count} words")
        return Complexity(tier="medium", reasons=reasons)

    reasons.append(f"short, single-step request ({word_count} words)")
    return Complexity(tier="simple", reasons=reasons)
