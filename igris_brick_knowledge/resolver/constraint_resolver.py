"""IGRIS Constraint Resolver — Graph Traversal + Healing Engine.

Resolves user intent by traversing brick connections, applying rules,
and healing missing chains via combinatorial reconstruction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.brick_system import Brick, BrickBank, BrickDomain
from ..core.knowledge_system import KnowledgeBank, Rule, RuleType
# BrickDomain is used for verb/noun classification


@dataclass
class ResolutionResult:
    """Output of the resolver."""
    code: Optional[str] = None
    confidence: float = 0.0
    chains_used: List[str] = field(default_factory=list)
    resolution_time_ms: float = 0.0
    healed: bool = False
    steps: List[str] = field(default_factory=list)


class ConstraintResolver:
    """Traverses brick graph + knowledge rules to resolve intent to code."""

    def __init__(self, brick_bank: BrickBank, knowledge_bank: KnowledgeBank):
        self.bricks = brick_bank
        self.knowledge = knowledge_bank
        self._min_confidence = 0.5

    def resolve(self, query: str, lang: str = "uz") -> ResolutionResult:
        start = time.time()
        result = ResolutionResult()

        # Step 1: Parse query into bricks
        tagged = self.knowledge.pos_tag(query, lang)
        result.steps.append(f"tagged: {tagged}")

        # Step 2: Search bricks for each word
        matched_bricks: List[Tuple[Brick, float]] = []
        for word, pos in tagged:
            matches = self.bricks.search(word, lang, top_k=3)
            if matches:
                matched_bricks.append(matches[0])

        if not matched_bricks:
            result.steps.append("no bricks matched")
            result.resolution_time_ms = (time.time() - start) * 1000
            return result

        result.steps.append(f"matched: {[b.canonical_id for b, _ in matched_bricks]}")

        # Step 3: Direct code generation from bricks
        verb_brick = None
        noun_bricks = []
        for brick, score in matched_bricks:
            if brick.domain == BrickDomain.VERB:
                verb_brick = brick
            elif brick.code_template:
                noun_bricks.append(brick)

        # Prefer the most specific code brick
        if noun_bricks:
            # Find the brick with the most specific code template
            best_brick = max(noun_bricks, key=lambda b: len(b.code_template))
            result.code = best_brick.code_template.replace("{arg}", "data")
            result.confidence = 0.85
            result.chains_used = [f"direct:{best_brick.canonical_id}"]
            result.steps.append(f"direct code: {best_brick.canonical_id}")
        elif verb_brick and verb_brick.code_template:
            result.code = verb_brick.code_template.replace("{arg}", "data")
            result.confidence = 0.7
            result.steps.append(f"verb code: {verb_brick.canonical_id}")

        # Step 4: Try rule-based approach if no direct code
        if not result.code:
            brick_ids = [b.canonical_id for b, _ in matched_bricks]
            rules = self.knowledge.find_rules(brick_ids)
            result.steps.append(f"rules found: {[r.rule_id for r in rules]}")

            for rule in rules:
                args = {}
                for i, bid in enumerate(brick_ids):
                    brick = self.bricks.get(bid)
                    if brick and brick.code_template:
                        args[f"n{i+1}"] = brick.code_template.replace("{arg}", "data")
                    else:
                        args[f"n{i+1}"] = f"/* {bid} */"

                output = self.knowledge.apply_rule(rule, args)
                if output:
                    result.code = output
                    result.confidence = 0.8
                    result.chains_used = [rule.rule_id]
                    result.steps.append(f"applied rule: {rule.rule_id}")
                    break

        # Step 5: If no rule matched, try healing
        if not result.code and len(matched_bricks) >= 2:
            healed = self._heal_chain(matched_bricks)
            if healed:
                result.code = healed
                result.confidence = 0.6
                result.healed = True
                result.steps.append("healed chain")

        # Step 6: Fallback — generate from brick templates
        if not result.code:
            result.code = self._fallback_generate(matched_bricks)
            result.confidence = 0.4
            result.steps.append("fallback generate")

        result.resolution_time_ms = (time.time() - start) * 1000
        return result

    def _heal_chain(self, bricks: List[Tuple[Brick, float]]) -> Optional[str]:
        """Reconstruct missing chain from available bricks."""
        if len(bricks) < 2:
            return None

        # Try to combine brick code templates
        parts = []
        for brick, score in bricks:
            if brick.code_template:
                parts.append(brick.code_template)
            elif brick.domain == BrickDomain.VERB:
                parts.append(f"# {brick.canonical_id}")
            else:
                parts.append(f"/* {brick.canonical_id} */")

        if parts:
            # Simple composition: first verb with remaining as args
            verb = None
            nouns = []
            for p, (b, _) in zip(parts, bricks):
                if b.domain == BrickDomain.VERB:
                    verb = p
                else:
                    nouns.append(p)

            if verb and nouns:
                arg_str = ", ".join(nouns[:3])
                return verb.replace("{arg}", arg_str)

        return None

    def _fallback_generate(self, bricks: List[Tuple[Brick, float]]) -> Optional[str]:
        """Generate code from brick templates as last resort."""
        if not bricks:
            return None

        primary_brick, primary_score = bricks[0]
        if primary_brick.code_template:
            if len(bricks) > 1:
                _, secondary_score = bricks[1]
                return primary_brick.code_template.replace("{arg}", "data")
            return primary_brick.code_template.replace("{arg}", "data")

        return None
