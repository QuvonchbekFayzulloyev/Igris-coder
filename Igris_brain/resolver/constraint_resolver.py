"""
IGRIS BRAIN — Constraint Resolver
=================================
Single graph traversal: input -> bricks -> rules -> output.

No monologue. Just: match pattern -> apply rule -> done.

Healing = combinatorial reconstruction. If a chain is missing, the resolver
calculates the missing piece from what it has (weighted combination of the
most similar available chains).

Reference (plan):
    Input: "matritsani teskari top"
      -> Bricks: [matrix(accusative), inverse, find]
      -> Rule (Grammar): SOV -> SVO
      -> Rule (Code): VERB+NOUN -> function(argument)
      -> Output: np.linalg.inv(matrix)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.brick_system import BrickBank
from core.knowledge_system import KnowledgeBank, Rule


# ---------------------------------------------------------------- #
# Resolution output
# ---------------------------------------------------------------- #

@dataclass
class Resolution:
    """Result of a single resolution pass."""

    query: str
    status: str = "ok"                 # ok | partial | failed
    confidence: float = 0.0
    matched_bricks: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)   # transparent rule trace
    output: str = ""
    healed: bool = False
    healing_source: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "matched_bricks": self.matched_bricks,
            "matched_rules": self.matched_rules,
            "trace": self.trace,
            "output": self.output,
            "healed": self.healed,
            "healing_source": self.healing_source,
        }


# ---------------------------------------------------------------- #
# Tokenizer + POS guesser
# ---------------------------------------------------------------- #

STOPWORDS_UZ = {"va", "uchun", "bilan", "bu", "shu", "bir", "da", "ni", "ning",
                "ga", "dan", "lar", "larni", "the", "a", "an", "to", "of", "in",
                "is", "are", "please", "men", "meni", "menga"}

# Uzbek case / plural suffixes to strip during lookup (longest first)
UZ_SUFFIXES = ("larni", "larning", "lardan", "larga", "larda", "ning",
               "lari", "lar", "dagi", "dan", "da", "ni", "ga",
               "mi", "man", "siz")


def tokenize_query(query: str) -> list[str]:
    """Lowercase, strip punctuation, drop stopwords."""
    tokens = re.findall(r"[a-zA-Z'`’\-]+", query.lower())
    return [t for t in tokens if t not in STOPWORDS_UZ and len(t) > 1]


def strip_uz_suffix(token: str) -> str:
    """Best-effort morphological reduction for Uzbek nouns."""
    for suffix in UZ_SUFFIXES:
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


# ---------------------------------------------------------------- #
# ConstraintResolver
# ---------------------------------------------------------------- #

class ConstraintResolver:
    """Graph traversal + healing engine for the coder agent."""

    def __init__(self, brick_bank: BrickBank, knowledge: KnowledgeBank):
        self.bricks = brick_bank
        self.knowledge = knowledge

    # ------------------------------------------------------------ #
    # Step 1: brick binding
    # ------------------------------------------------------------ #

    def bind_bricks(self, tokens: list[str]) -> list[tuple[str, str, float]]:
        """Map tokens -> (canonical_id, kind, confidence).

        Exact surface lookup first; falls back to suffix-stripped lookup,
        then fuzzy (vector) lookup.
        """
        bound: list[tuple[str, str, float]] = []
        for token in tokens:
            brick = (self.bricks.lookup_any(token)
                     or self.bricks.lookup_any(strip_uz_suffix(token))
                     or self.bricks.fuzzy_lookup(token))
            if brick:
                conf = 1.0 if brick.matches_surface(token) else 0.8
                bound.append((brick.canonical_id, brick.kind, conf))
        return bound

    # ------------------------------------------------------------ #
    # Step 2: rule matching (single graph traversal)
    # ------------------------------------------------------------ #

    def match_rule(self, rule: Rule, bound: list[tuple[str, str, float]]) -> Optional[dict]:
        """Try to match a rule pattern against the bound bricks.

        Unordered (bag) matching: each matcher must consume a distinct bound
        brick, in any order — this handles SOV -> SVO word-order variation
        without a separate reorder step.

        A matcher of {"kind": "X"} matches a bound brick of kind X.
        A matcher of {"id": "Y"} matches a bound brick with id Y.
        "VERB"/"NOUN" special kinds resolve via POS tags.
        Matchers may carry {"var": "name"} to bind into the action template.
        Returns {vars: {...}, score: float} or None.
        """
        pattern = rule.pattern
        if len(pattern) > len(bound):
            return None

        # Consume bound bricks greedily for each matcher
        used = [False] * len(bound)
        var_bindings: dict[str, str] = {}
        score = rule.weight
        consumed_ids: list[str] = []

        for matcher in pattern:
            found = False
            for i, (cid, kind, conf) in enumerate(bound):
                if used[i]:
                    continue
                ok, var = self._matcher_ok(matcher, cid, kind)
                if not ok:
                    continue
                used[i] = True
                found = True
                if var:
                    var_bindings[var] = cid
                score *= conf
                consumed_ids.append(cid)
                break
            if not found:
                return None

        var_bindings["_canonical_ids"] = consumed_ids
        var_bindings["_score"] = score
        return var_bindings

    def _matcher_ok(self, matcher: dict, cid: str, kind: str) -> tuple[bool, Optional[str]]:
        """Check a single matcher. Returns (ok, variable_name)."""
        var = matcher.get("var")
        if "id" in matcher:
            return (matcher["id"] == cid), var

        want = matcher.get("kind", "")
        if want in ("VERB", "NOUN", "ADJ"):
            pos = self.knowledge.pos_of(cid)
            return pos == want, var
        if want == kind:
            return True, var
        return False, None

    # ------------------------------------------------------------ #
    # Step 3: apply action
    # ------------------------------------------------------------ #

    def apply_action(self, rule: Rule, var_bindings: dict) -> str:
        """Apply a rule's action using the matched variable bindings."""
        action = rule.action
        atype = action.get("type")

        if atype == "emit":
            return str(action.get("value", ""))

        if atype == "code":
            template = action.get("template", "")
            # Fill {var} with the canonical surface (code form if available)
            result = template
            for var, cid in var_bindings.items():
                if var.startswith("_"):
                    continue
                brick = self.bricks.get(cid)
                code_form = brick.surface("code") if brick else cid
                result = result.replace("{" + var + "}", code_form or cid)
            return result

        if atype == "reorder":
            order = action.get("order", [])
            ids = var_bindings.get("_canonical_ids", [])
            return " ".join(str(ids[i]) for i in order if i < len(ids))

        return ""

    # ------------------------------------------------------------ #
    # Main entry
    # ------------------------------------------------------------ #

    def resolve(self, query: str) -> Resolution:
        """Resolve a natural-language query into code/output."""
        res = Resolution(query=query)
        tokens = tokenize_query(query)
        if not tokens:
            res.status = "failed"
            res.trace.append("No tokens after filtering")
            return res

        # 1. bind bricks
        bound = self.bind_bricks(tokens)
        res.matched_bricks = [cid for cid, _, _ in bound]
        res.trace.append(f"Bricks: {res.matched_bricks}")
        if not bound:
            res.status = "failed"
            res.trace.append("No bricks matched")
            return res

        # 2. find first matching rule
        best_rule: Optional[Rule] = None
        best_vars: Optional[dict] = None
        best_score = 0.0

        for rule in self.knowledge.rules.values():
            m = self.match_rule(rule, bound)
            if m and m["_score"] > best_score:
                best_rule, best_vars, best_score = rule, m, m["_score"]

        if not best_rule:
            res.status = "partial"
            res.confidence = min(0.5, 0.3 * len(bound))
            res.trace.append("No rule matched — partial resolution")
            res.output = " ".join(res.matched_bricks)
            return res

        # 3. apply action
        res.matched_rules.append(best_rule.name)
        res.trace.append(f"Rule: {best_rule.name} (score={best_score:.2f})")
        res.output = self.apply_action(best_rule, best_vars)

        # confidence = rule score blended with brick coverage
        coverage = len(res.matched_bricks) / max(len(tokens), 1)
        res.confidence = min(1.0, 0.6 * best_score + 0.4 * coverage)
        res.status = "ok" if res.confidence >= 0.5 else "partial"
        res.trace.append(f"Output: {res.output}")
        return res

    # ------------------------------------------------------------ #
    # Healing engine
    # ------------------------------------------------------------ #

    def heal(
        self,
        query: str,
        available_chains: dict[str, float],
        chain_similarities: Optional[dict[str, dict[str, float]]] = None,
    ) -> Resolution:
        """Reconstruct a resolution when a capability chain is missing.

        Args:
            query: The original query.
            available_chains: name -> availability score (0..1).
            chain_similarities: optional map chain_name -> {other: similarity}.
        """
        res = Resolution(query=query, status="partial", healed=True)
        res.trace.append("Healing: reconstructing from available chains")

        weights: dict[str, float] = {}
        for name, avail in available_chains.items():
            if avail <= 0:
                continue
            sims = (chain_similarities or {}).get(name, {})
            for other, sim in sims.items():
                if other not in available_chains and sim > 0.3:
                    weights[other] = weights.get(other, 0.0) + avail * sim

        if not weights:
            res.trace.append("No healing candidates")
            res.output = ""
            res.confidence = 0.0
            return res

        total = sum(weights.values())
        res.healing_source = ", ".join(
            f"{name} ({w / total:.2f})" for name, w in sorted(weights.items(), key=lambda x: -x[1])
        )
        res.confidence = min(0.7, max(weights.values()) / total)
        res.trace.append(f"Healed weights: {res.healing_source}")
        res.output = f"[healed from {res.healing_source}]"
        return res
