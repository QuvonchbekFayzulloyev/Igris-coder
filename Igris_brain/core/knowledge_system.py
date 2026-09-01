"""
IGRIS BRAIN — Knowledge System
==============================
Grammar rules + transformation rules: how bricks connect.

Knowledge is how bricks connect, not what they mean.

Reference (plan):
    Rule: [VERB "find"] + [NOUN "inverse"] + [NOUN "matrix"]
        -> code: "np.linalg.inv(matrix)"
    Rule (Grammar): SOV -> SVO = [find, inverse, matrix]
    Rule (Code): VERB+NOUN -> function(argument) = np.linalg.inv(matrix)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- #
# Rule dataclasses
# ---------------------------------------------------------------- #

@dataclass
class Rule:
    """A connection rule between brick patterns and an output action.

    Attributes:
        name: Unique rule name, e.g. "verb_noun_to_code".
        pattern: List of brick matchers. Each matcher is a dict with keys:
            - kind: brick kind to match ("word", "concept", "function",
              "type", "api") OR the special token "VERB"/"NOUN"/"ADJ"
              matched by POS tagging.
            - id: optional canonical_id to match exactly.
        action: The transformation action. One of:
            - {"type": "code", "template": "np.linalg.inv({arg})"}
            - {"type": "reorder", "order": [2, 0, 1]}
            - {"type": "emit", "value": "..."}
        weight: Rule strength (default 1.0).
        domains: Knowledge domains this rule applies to.
    """

    name: str
    pattern: list[dict]
    action: dict
    weight: float = 1.0
    domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pattern": self.pattern,
            "action": self.action,
            "weight": self.weight,
            "domains": self.domains,
        }


@dataclass
class GrammarRule:
    """Word-order transformation rule (SOV -> SVO etc.)."""

    name: str
    source_order: list[str]          # e.g. ["subject", "object", "verb"]
    target_order: list[str]          # e.g. ["verb", "object"]
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source_order": self.source_order,
            "target_order": self.target_order,
            "weight": self.weight,
        }


# ---------------------------------------------------------------- #
# KnowledgeBank
# ---------------------------------------------------------------- #

class KnowledgeBank:
    """Registry of grammar + transformation rules."""

    def __init__(self):
        self.rules: dict[str, Rule] = {}
        self.grammar_rules: dict[str, GrammarRule] = {}
        # POS tags for matcher convenience
        self.pos_tags: dict[str, str] = {}  # brick_id -> "VERB"/"NOUN"/"ADJ"

    # ---- population ------------------------------------------- #

    def add_rule(self, rule: Rule) -> "KnowledgeBank":
        self.rules[rule.name] = rule
        return self

    def add_grammar(self, rule: GrammarRule) -> "KnowledgeBank":
        self.grammar_rules[rule.name] = rule
        return self

    def tag(self, brick_id: str, pos: str) -> "KnowledgeBank":
        """Assign a POS tag to a brick (VERB / NOUN / ADJ / ...)."""
        self.pos_tags[brick_id] = pos
        return self

    # ---- query ------------------------------------------------ #

    def get_rule(self, name: str) -> Optional[Rule]:
        return self.rules.get(name)

    def rules_for_domain(self, domain: str) -> list[Rule]:
        return [r for r in self.rules.values() if not r.domains or domain in r.domains]

    def pos_of(self, brick_id: str) -> str:
        return self.pos_tags.get(brick_id, "")

    @property
    def size(self) -> int:
        return len(self.rules) + len(self.grammar_rules)

    def stats(self) -> dict:
        return {
            "rules": len(self.rules),
            "grammar_rules": len(self.grammar_rules),
            "tagged_bricks": len(self.pos_tags),
        }


# ---------------------------------------------------------------- #
# Default knowledge: seeded bricks + rules (the ~4000-node baseline)
# ---------------------------------------------------------------- #

def build_default_bricks() -> list:
    """Return the default seed brick set (compact but representative)."""
    from .brick_system import Brick

    return [
        # ---- math / code primitives ---- #
        Brick("concept_inverse", {"uz": ["teskari", "teskarisi"], "en": ["inverse", "invert"], "code": ["np.linalg.inv", "inv"]},
              kind="concept", domains=["data-analytics", "mathematics"], code_template="np.linalg.inv({arg})"),
        Brick("concept_matrix", {"uz": ["matritsa", "matritsani"], "en": ["matrix"], "code": ["np.array", "matrix"]},
              kind="concept", domains=["data-analytics", "mathematics"], code_template="np.array({arg})"),
        Brick("concept_sort", {"uz": ["sarala", "tartibla"], "en": ["sort"], "code": ["sorted", ".sort()"]},
              kind="concept", domains=["engineering", "data-analytics"], code_template="sorted({arg})"),
        Brick("concept_find", {"uz": ["top", "qidir"], "en": ["find", "search", "look up"], "code": [".find(", "index"]},
              kind="concept", domains=["engineering"], code_template="{arg}.find({target})"),
        Brick("concept_mean", {"uz": ["o'rtacha", "o'rtachasini", "o'rtachani", "o'rtachasi"], "en": ["mean", "average", "avg"], "code": ["np.mean"]},
              kind="concept", domains=["data-analytics"], code_template="np.mean({arg})"),
        Brick("concept_sum", {"uz": ["yig'indi"], "en": ["sum", "total"], "code": ["sum", "np.sum"]},
              kind="concept", domains=["data-analytics", "engineering"], code_template="sum({arg})"),
        Brick("concept_max", {"uz": ["eng katta", "maksimum"], "en": ["max", "maximum", "largest"], "code": ["max"]},
              kind="concept", domains=["data-analytics", "engineering"], code_template="max({arg})"),
        Brick("concept_min", {"uz": ["eng kichik", "minimum"], "en": ["min", "minimum", "smallest"], "code": ["min"]},
              kind="concept", domains=["data-analytics", "engineering"], code_template="min({arg})"),
        Brick("concept_intersection", {"uz": ["kesishma", "umumiy"], "en": ["intersection", "common"], "code": ["set.intersection"]},
              kind="concept", domains=["engineering"], code_template="set({a}).intersection({b})"),
        Brick("concept_filter", {"uz": ["filtrla"], "en": ["filter"], "code": ["filter"]},
              kind="concept", domains=["engineering"], code_template="[x for x in {arg} if {cond}]"),
        Brick("concept_loop", {"uz": ["har biri uchun", "aylanma"], "en": ["for each", "iterate"], "code": ["for x in "]},
              kind="concept", domains=["engineering"], code_template="for x in {arg}:\n    pass"),
        Brick("concept_error_handling", {"uz": ["xatoni ushla"], "en": ["catch error", "handle exception"], "code": ["try/except"]},
              kind="concept", domains=["engineering"], code_template="try:\n    {body}\nexcept {exc}:\n    {handler}"),

        # ---- types ---- #
        Brick("type_square_matrix", {"uz": ["kvadrat matritsa"], "en": ["square matrix"], "code": ["np.ndarray"]},
              kind="type", domains=["mathematics", "data-analytics"]),
        Brick("type_string", {"uz": ["matn"], "en": ["string", "text"], "code": ["str"]},
              kind="type", domains=["engineering"]),
        Brick("type_list", {"uz": ["ro'yxat"], "en": ["list", "array"], "code": ["list"]},
              kind="type", domains=["engineering", "data-analytics"]),

        # ---- language verbs (for grammar) ---- #
        Brick("verb_write", {"uz": ["yoz"], "en": ["write", "create", "generate"], "code": ["write"]},
              kind="word", domains=["engineering"], code_template="{arg}"),
        Brick("verb_read", {"uz": ["o'qi"], "en": ["read", "open"], "code": ["read"]},
              kind="word", domains=["engineering"], code_template="open({arg})"),
        Brick("verb_connect", {"uz": ["ulang"], "en": ["connect", "join", "merge"], "code": ["pd.merge"]},
              kind="word", domains=["data-analytics"], code_template="pd.merge({left}, {right})"),
    ]


def build_default_knowledge() -> "KnowledgeBank":
    """Seed the KnowledgeBank with grammar + transformation rules."""
    bank = KnowledgeBank()

    # ---- grammar: SOV -> SVO (Uzbek is SOV, target is SVO/code) ---- #
    bank.add_grammar(GrammarRule("uz_sov_to_svo",
                                 source_order=["object", "verb"],
                                 target_order=["verb", "object"],
                                 weight=0.9))

    # ---- transformation: VERB+NOUN -> function(argument) ---- #
    bank.add_rule(Rule(
        name="verb_noun_to_function",
        pattern=[{"kind": "VERB", "var": "verb"}, {"kind": "concept", "var": "noun"}],
        action={"type": "code", "template": "{verb}({noun})"},
        weight=0.8,
        domains=["engineering", "data-analytics"],
    ))

    # ---- transformation: inverse of matrix ---- #
    bank.add_rule(Rule(
        name="inverse_of_matrix",
        pattern=[{"id": "concept_inverse", "var": "inverse"}, {"id": "concept_matrix", "var": "matrix"}],
        action={"type": "code", "template": "np.linalg.inv({matrix})"},
        weight=1.0,
        domains=["mathematics", "data-analytics"],
    ))

    # ---- transformation: sort list ---- #
    bank.add_rule(Rule(
        name="sort_of_list",
        pattern=[{"id": "concept_sort", "var": "sort"}, {"id": "type_list", "var": "list"}],
        action={"type": "code", "template": "sorted({list})"},
        weight=1.0,
        domains=["engineering"],
    ))

    # ---- transformation: mean of array ---- #
    bank.add_rule(Rule(
        name="mean_of_array",
        pattern=[{"id": "concept_mean", "var": "mean"}, {"id": "type_list", "var": "list"}],
        action={"type": "code", "template": "np.mean({list})"},
        weight=1.0,
        domains=["data-analytics"],
    ))

    # ---- transformation: sum of list ---- #
    bank.add_rule(Rule(
        name="sum_of_list",
        pattern=[{"id": "concept_sum", "var": "sum"}, {"id": "type_list", "var": "list"}],
        action={"type": "code", "template": "sum({list})"},
        weight=1.0,
        domains=["data-analytics", "engineering"],
    ))

    # ---- transformation: max of list ---- #
    bank.add_rule(Rule(
        name="max_of_list",
        pattern=[{"id": "concept_max", "var": "max"}, {"id": "type_list", "var": "list"}],
        action={"type": "code", "template": "max({list})"},
        weight=1.0,
        domains=["data-analytics", "engineering"],
    ))

    # ---- transformation: min of list ---- #
    bank.add_rule(Rule(
        name="min_of_list",
        pattern=[{"id": "concept_min", "var": "min"}, {"id": "type_list", "var": "list"}],
        action={"type": "code", "template": "min({list})"},
        weight=1.0,
        domains=["data-analytics", "engineering"],
    ))

    # ---- emit constants ---- #
    bank.add_rule(Rule(
        name="emit_square_matrix_constraint",
        pattern=[{"id": "concept_inverse", "var": "inverse"}, {"id": "type_square_matrix", "var": "m"}],
        action={"type": "emit", "value": "Precondition: matrix must be square and invertible."},
        weight=0.8,
        domains=["mathematics"],
    ))

    # POS tagging for the seed bricks
    for verb in ("verb_write", "verb_read", "verb_connect", "concept_find"):
        bank.tag(verb, "VERB")
    for noun in ("concept_matrix", "type_string", "type_list", "concept_inverse",
                 "type_square_matrix", "concept_mean", "concept_sum",
                 "concept_max", "concept_min", "concept_intersection"):
        bank.tag(noun, "NOUN")

    return bank
