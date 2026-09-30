"""IGRIS Chain System — Modular LoRA Adapters + Chain Healer.

Chains are composable knowledge pathways that combine bricks and rules
for specific domains (code, math, analysis, uzbek, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.brick_system import Brick, BrickBank, BrickDomain
from ..core.knowledge_system import KnowledgeBank


@dataclass
class Chain:
    """A knowledge pathway for a specific domain/task."""
    chain_id: str
    domain: str
    description: str
    bricks_used: List[str]  # canonical_ids
    rules_used: List[str]   # rule_ids
    weight: float = 1.0     # confidence weight
    hit_count: int = 0      # how many times used

    def similarity(self, other: "Chain") -> float:
        """Jaccard similarity of brick sets."""
        set_a = set(self.bricks_used)
        set_b = set(other.bricks_used)
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.0


class ChainSystem:
    """Manages domain-specific chains and heals missing ones."""

    def __init__(self, brick_bank: BrickBank, knowledge_bank: KnowledgeBank):
        self.bricks = brick_bank
        self.knowledge = knowledge_bank
        self._chains: Dict[str, Chain] = {}
        self._build_default_chains()

    def add_chain(self, chain: Chain):
        self._chains[chain.chain_id] = chain

    def get_chain(self, chain_id: str) -> Optional[Chain]:
        return self._chains.get(chain_id)

    def find_chain(self, domain: str) -> Optional[Chain]:
        for chain in self._chains.values():
            if chain.domain == domain:
                return chain
        return None

    def record_hit(self, chain_id: str):
        if chain_id in self._chains:
            self._chains[chain_id].hit_count += 1

    def heal(self, missing_domain: str, available_chains: List[str]) -> Optional[Chain]:
        """Reconstruct a missing chain from available chains."""
        candidates = []
        for chain_id in available_chains:
            chain = self._chains.get(chain_id)
            if chain:
                candidates.append(chain)

        if not candidates:
            return None

        # Weighted combination of available chains
        total_weight = sum(c.weight for c in candidates)
        if total_weight == 0:
            return None

        merged_bricks = []
        merged_rules = []
        for c in candidates:
            weight_ratio = c.weight / total_weight
            # Include bricks proportional to weight
            n_bricks = max(1, int(len(c.bricks_used) * weight_ratio + 0.5))
            merged_bricks.extend(c.bricks_used[:n_bricks])
            merged_rules.extend(c.rules_used[:max(1, int(len(c.rules_used) * weight_ratio + 0.5))])

        # Deduplicate
        merged_bricks = list(dict.fromkeys(merged_bricks))
        merged_rules = list(dict.fromkeys(merged_rules))

        healed_chain = Chain(
            chain_id=f"healed_{missing_domain}",
            domain=missing_domain,
            description=f"Healed chain for {missing_domain}",
            bricks_used=merged_bricks,
            rules_used=merged_rules,
            weight=0.6 * max(c.weight for c in candidates),
        )
        self.add_chain(healed_chain)
        return healed_chain

    def resolve_with_chain(self, query: str, lang: str = "uz", domain: str = "code") -> Tuple[Optional[str], float, str]:
        """Resolve using a specific chain."""
        chain = self.find_chain(domain)
        if not chain:
            return None, 0.0, ""

        self.record_hit(chain.chain_id)

        # Filter bricks to chain's domain
        tagged = self.knowledge.pos_tag(query, lang)
        matched = []
        for word, pos in tagged:
            matches = self.bricks.search(word, lang, top_k=2)
            if matches:
                brick, score = matches[0]
                if brick.canonical_id in chain.bricks_used:
                    matched.append((brick, score))

        if not matched:
            # Fallback: use any matching bricks
            for word, pos in tagged:
                matches = self.bricks.search(word, lang, top_k=1)
                if matches:
                    matched.append(matches[0])

        if not matched:
            return None, 0.0, chain.chain_id

        # Try rules
        brick_ids = [b.canonical_id for b, _ in matched]
        rules = self.knowledge.find_rules(brick_ids)

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
                confidence = chain.weight * (0.8 + 0.1 * min(len(matched), 3))
                return output, confidence, chain.chain_id

        # Fallback: use first brick's template
        if matched:
            brick, score = matched[0]
            if brick.code_template:
                return brick.code_template.replace("{arg}", "data"), 0.5, chain.chain_id

        return None, 0.0, chain.chain_id

    def _build_default_chains(self):
        self.add_chain(Chain(
            "chain_math", "math", "Mathematical operations",
            ["concept_inverse", "concept_sort", "concept_sum", "concept_max", "concept_min",
             "concept_mean", "math_matrix", "math_eigenvalues", "math_svd", "math_determinant",
             "math_transpose", "math_multiply", "math_sqrt", "math_log", "math_abs", "math_round"],
            ["code_inverse", "code_sort", "code_sum", "code_max", "code_min", "code_mean"],
            weight=1.0,
        ))
        self.add_chain(Chain(
            "chain_code", "code", "General coding patterns",
            ["concept_read", "concept_write", "concept_execute", "concept_find",
             "verb_print", "verb_loop", "verb_if", "verb_return",
             "type_list", "type_dict", "type_string", "type_number"],
            ["code_print", "code_read", "code_write"],
            weight=1.0,
        ))
        self.add_chain(Chain(
            "chain_data", "data", "Data analysis patterns",
            ["data_read_csv", "data_groupby", "data_merge", "data_plot",
             "data_json_parse", "data_json_dump", "data_len", "data_zip",
             "data_enumerate", "type_dataframe"],
            ["code_read_csv", "code_groupby", "code_merge", "code_plot"],
            weight=1.0,
        ))
        self.add_chain(Chain(
            "chain_uz", "uz", "Uzbek language patterns",
            ["concept_inverse", "concept_sort", "concept_sum", "concept_find",
             "concept_read", "concept_write", "verb_print"],
            ["transform_sov_to_svo"],
            weight=0.8,
        ))
        self.add_chain(Chain(
            "chain_sys", "system", "System operations",
            ["sys_file_exists", "sys_mkdir", "sys_http_get",
             "concept_read", "concept_write", "concept_execute"],
            ["code_file_exists", "code_mkdir", "code_http_get"],
            weight=0.9,
        ))

    @property
    def chain_count(self) -> int:
        return len(self._chains)

    def all_chains(self) -> List[Chain]:
        return list(self._chains.values())
