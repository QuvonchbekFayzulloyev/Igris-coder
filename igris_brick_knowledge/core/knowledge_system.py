"""IGRIS Knowledge System — Grammar & Transformation Rules.

Knowledge = how Bricks connect, not what they mean.
Rules map brick combinations to code patterns or NL outputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .brick_system import Brick, BrickBank, BrickDomain


class RuleType(Enum):
    GRAMMAR = "grammar"      # SOV -> SVO, case marking, etc.
    CODE = "code"            # Brick组合 -> code pattern
    TRANSFORM = "transform"  # Input format -> output format
    TYPE_CONSTRAINT = "type" # Type checking / casting


@dataclass
class Rule:
    """A transformation rule that maps brick patterns to outputs."""

    rule_id: str
    rule_type: RuleType
    input_pattern: List[str]       # brick canonical_ids or POS tags
    output_template: str           # code template or NL template
    priority: int = 0              # higher = tried first
    conditions: List[str] = field(default_factory=list)  # pre-conditions
    description: str = ""

    def matches(self, brick_ids: List[str]) -> bool:
        if len(self.input_pattern) != len(brick_ids):
            return False
        for pattern, bid in zip(self.input_pattern, brick_ids):
            if pattern.startswith("TAG:"):
                continue  # POS tag wildcard
            if pattern != bid:
                return False
        return True


class KnowledgeBank:
    """Registry of transformation rules."""

    def __init__(self, brick_bank: BrickBank):
        self.brick_bank = brick_bank
        self._rules: List[Rule] = []
        self._build_default_rules()

    def add_rule(self, rule: Rule):
        self._rules.append(rule)

    def find_rules(self, brick_ids: List[str]) -> List[Rule]:
        matching = [r for r in self._rules if r.matches(brick_ids)]
        matching.sort(key=lambda r: -r.priority)
        return matching

    def apply_rule(self, rule: Rule, args: Dict[str, str]) -> Optional[str]:
        result = rule.output_template
        for key, value in args.items():
            result = result.replace(f"{{{key}}}", value)
        return result if "{" not in result else None

    def _build_default_rules(self):
        # Grammar rules
        self.add_rule(Rule(
            "grammar_svo", RuleType.GRAMMAR,
            ["TAG:VERB", "TAG:NOUN", "TAG:NOUN"],
            "{v}({n1}, {n2})",
            priority=10,
            description="SOV -> SVO transformation"
        ))

        # Code rules: math operations
        math_rules = [
            ("code_inverse", ["concept_inverse", "TAG:NOUN"], "np.linalg.inv({n1})"),
            ("code_sort", ["concept_sort", "TAG:NOUN"], "sorted({n1})"),
            ("code_sum", ["concept_sum", "TAG:NOUN"], "sum({n1})"),
            ("code_max", ["concept_max", "TAG:NOUN"], "max({n1})"),
            ("code_min", ["concept_min", "TAG:NOUN"], "min({n1})"),
            ("code_mean", ["concept_mean", "TAG:NOUN"], "np.mean({n1})"),
            ("code_sqrt", ["concept_sqrt", "TAG:NOUN"], "np.sqrt({n1})"),
            ("code_log", ["concept_log", "TAG:NOUN"], "np.log({n1})"),
            ("code_abs", ["math_abs", "TAG:NOUN"], "abs({n1})"),
            ("code_round", ["math_round", "TAG:NOUN"], "round({n1})"),
            ("code_determinant", ["math_determinant", "TAG:NOUN"], "np.linalg.det({n1})"),
            ("code_transpose", ["math_transpose", "TAG:NOUN"], "{n1}.T"),
            ("code_eigenvalues", ["math_eigenvalues", "TAG:NOUN"], "np.linalg.eigvals({n1})"),
        ]
        for rid, pattern, template in math_rules:
            self.add_rule(Rule(rid, RuleType.CODE, pattern, template, priority=20))

        # Code rules: data operations
        data_rules = [
            ("code_read_csv", ["data_read_csv", "TAG:NOUN"], "pd.read_csv({n1})"),
            ("code_groupby", ["data_groupby", "TAG:NOUN"], "{n1}.groupby({col})"),
            ("code_merge", ["data_merge", "TAG:NOUN", "TAG:NOUN"], "pd.merge({n1}, {n2})"),
            ("code_plot", ["data_plot", "TAG:NOUN"], "{n1}.plot()"),
            ("code_json_parse", ["data_json_parse", "TAG:NOUN"], "json.loads({n1})"),
            ("code_json_dump", ["data_json_dump", "TAG:NOUN"], "json.dumps({n1})"),
            ("code_len", ["data_len", "TAG:NOUN"], "len({n1})"),
            ("code_zip", ["data_zip", "TAG:NOUN", "TAG:NOUN"], "list(zip({n1}, {n2}))"),
            ("code_enumerate", ["data_enumerate", "TAG:NOUN"], "enumerate({n1})"),
        ]
        for rid, pattern, template in data_rules:
            self.add_rule(Rule(rid, RuleType.CODE, pattern, template, priority=20))

        # Code rules: system operations
        sys_rules = [
            ("code_file_exists", ["sys_file_exists", "TAG:NOUN"], "os.path.exists({n1})"),
            ("code_mkdir", ["sys_mkdir", "TAG:NOUN"], "os.makedirs({n1}, exist_ok=True)"),
            ("code_http_get", ["sys_http_get", "TAG:NOUN"], "requests.get({n1})"),
            ("code_read", ["concept_read", "TAG:NOUN"], "open({n1})"),
            ("code_write", ["concept_write", "TAG:NOUN"], "open({n1}, 'w')"),
            ("code_print", ["verb_print", "TAG:NOUN"], "print({n1})"),
        ]
        for rid, pattern, template in sys_rules:
            self.add_rule(Rule(rid, RuleType.CODE, pattern, template, priority=20))

        # Type constraint rules
        self.add_rule(Rule(
            "type_square_matrix", RuleType.TYPE_CONSTRAINT,
            ["TAG:NOUN"],
            "assert np.array({n1}).shape[0] == np.array({n1}).shape[1]",
            priority=5,
            conditions=["square_matrix"],
            description="Assert matrix is square"
        ))

        # Transform rules: language specific
        self.add_rule(Rule(
            "transform_sov_to_svo", RuleType.TRANSFORM,
            ["TAG:VERB", "TAG:OBJ", "TAG:OBJ"],
            "{v} {o1} {o2}",
            priority=15,
            description="Uzbek SOV -> English SVO"
        ))

    def pos_tag(self, text: str, lang: str = "uz") -> List[Tuple[str, str]]:
        """Simple POS tagger — maps words to brick domains."""
        words = text.lower().split()
        tagged = []
        for word in words:
            results = self.brick_bank.search(word, lang, top_k=1)
            if results:
                brick, score = results[0]
                if score > 0.3:
                    if brick.domain == BrickDomain.VERB:
                        tagged.append((word, "VERB"))
                    elif brick.domain in (BrickDomain.NOUN, BrickDomain.MATH, BrickDomain.DATA, BrickDomain.CONCEPT):
                        tagged.append((word, "NOUN"))
                    elif brick.domain == BrickDomain.TYPE:
                        tagged.append((word, "TYPE"))
                    else:
                        tagged.append((word, "NOUN"))
                else:
                    tagged.append((word, "NOUN"))
            else:
                tagged.append((word, "NOUN"))
        return tagged
