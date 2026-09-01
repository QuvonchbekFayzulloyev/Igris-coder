"""
IGRIS BRAIN — Chain System
==========================
Modular capability chains (the "LoRA adapters" of the brick agent) plus a
chain healer that reconstructs missing chains from the most similar ones.

Reference (plan):
    If chain_math is missing:
      Available: chain_code (71% similar), chain_analysis (45% similar)
      Weights: [0.61, 0.39]
      Healed = 0.61 * chain_code + 0.39 * chain_analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from core.knowledge_system import KnowledgeBank, Rule


# ---------------------------------------------------------------- #
# Chain
# ---------------------------------------------------------------- #

@dataclass
class Chain:
    """A named capability: a bundle of rules + optional transform fn.

    Attributes:
        name: e.g. "chain_math", "chain_code", "chain_analysis", "chain_uz".
        rules: Rules belonging to this chain.
        vector: Optional 128-dim capability descriptor (for similarity).
        transform: Optional callable query -> output (LLM or custom).
        healing_source: Human-readable description of how this chain was healed.
    """

    name: str
    rules: list[Rule] = field(default_factory=list)
    vector: Optional[list] = None
    transform: Optional[Callable[[str], str]] = None
    healing_source: str = ""

    def matches(self, rule_name: str) -> bool:
        return any(r.name == rule_name for r in self.rules)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "rules": [r.name for r in self.rules],
            "has_transform": self.transform is not None,
        }


# ---------------------------------------------------------------- #
# ChainRegistry
# ---------------------------------------------------------------- #

class ChainRegistry:
    """Holds all chains and computes cross-chain similarities."""

    def __init__(self, knowledge: Optional[KnowledgeBank] = None):
        self.chains: dict[str, Chain] = {}
        # Reference rule set: full knowledge base (or union of registered chains)
        self.reference_rules: set[str] = (
            {r.name for r in knowledge.rules.values()} if knowledge else set()
        )

    def register(self, chain: Chain) -> "ChainRegistry":
        self.chains[chain.name] = chain
        return self

    def get(self, name: str) -> Optional[Chain]:
        return self.chains.get(name)

    def availability(self) -> dict[str, float]:
        """availability = fraction of known (reference) rules each chain covers."""
        if not self.reference_rules:
            self.reference_rules = {
                r.name for c in self.chains.values() for r in c.rules
            }
        out: dict[str, float] = {}
        for name, chain in self.chains.items():
            if not chain.rules:
                out[name] = 1.0 if chain.transform else 0.0
                continue
            covered = sum(1 for r in chain.rules if r.name in self.reference_rules)
            out[name] = covered / max(len(self.reference_rules), 1)
        return out

    def similarity_map(self) -> dict[str, dict[str, float]]:
        """chain -> {other_chain: similarity} using Jaccard on rule sets."""
        rule_sets = {name: {r.name for r in c.rules} for name, c in self.chains.items()}
        out: dict[str, dict[str, float]] = {}
        for a, ra in rule_sets.items():
            out[a] = {}
            for b, rb in rule_sets.items():
                if a == b:
                    continue
                union = ra | rb
                if not union:
                    out[a][b] = 0.0
                else:
                    out[a][b] = len(ra & rb) / len(union)
        return out

    @property
    def size(self) -> int:
        return len(self.chains)


# ---------------------------------------------------------------- #
# ChainHealer
# ---------------------------------------------------------------- #

class ChainHealer:
    """Reconstructs missing chains via weighted combination."""

    def __init__(self, registry: ChainRegistry):
        self.registry = registry

    def heal(
        self,
        missing_chain: str,
        min_similarity: float = 0.3,
    ) -> Chain:
        """Build a healed Chain for a missing capability name."""
        avail = self.registry.availability()
        sims = self.registry.similarity_map()

        weights: dict[str, float] = {}
        for name, sim in sims.get(missing_chain, {}).items():
            if avail.get(name, 0) > 0 and sim >= min_similarity:
                weights[name] = avail[name] * sim

        if not weights:
            return Chain(name=missing_chain)  # empty healed chain

        total = sum(weights.values())
        healed_rules: list[Rule] = []
        source: list[str] = []
        for name, w in sorted(weights.items(), key=lambda x: -x[1]):
            src = self.registry.get(name)
            if src:
                healed_rules.extend(src.rules)
                source.append(f"{name} ({w / total:.2f})")

        healed = Chain(
            name=f"{missing_chain} (healed)",
            rules=healed_rules,
            healing_source=", ".join(source),
        )
        return healed

    def heal_report(self, missing_chain: str) -> dict:
        """Human-readable healing report (plan example format)."""
        avail = self.registry.availability()
        sims = self.registry.similarity_map().get(missing_chain, {})
        candidates = sorted(
            ((n, s) for n, s in sims.items() if avail.get(n, 0) > 0),
            key=lambda x: -x[1],
        )
        if not candidates:
            return {"healed": False, "message": f"No healing candidates for {missing_chain}"}

        weights = []
        total = 0.0
        for name, sim in candidates:
            w = avail[name] * sim
            weights.append((name, sim, w))
            total += w

        parts = ", ".join(f"{n} ({s * 100:.0f}% similar)" for n, s, _ in weights)
        if total <= 0:
            return {"healed": False, "chain": missing_chain, "message": "No usable healing candidates"}
        weight_str = ", ".join(f"[{w / total:.2f}]" for _, _, w in weights)
        return {
            "healed": True,
            "chain": missing_chain,
            "candidates": parts,
            "weights": weight_str,
            "formula": f"Healed = {' + '.join(f'{w / total:.2f} x {n}' for n, _, w in weights)}",
        }


# ---------------------------------------------------------------- #
# Default chains
# ---------------------------------------------------------------- #

def build_default_chains(knowledge: KnowledgeBank) -> ChainRegistry:
    """Seed chains from the default knowledge rules."""
    reg = ChainRegistry(knowledge=knowledge)

    reg.register(Chain(
        name="chain_math",
        rules=[r for r in knowledge.rules.values() if "mathematics" in r.domains],
    ))
    reg.register(Chain(
        name="chain_code",
        rules=[r for r in knowledge.rules.values() if "engineering" in r.domains],
    ))
    reg.register(Chain(
        name="chain_analysis",
        rules=[r for r in knowledge.rules.values() if "data-analytics" in r.domains],
    ))
    reg.register(Chain(
        name="chain_uz",
        rules=[r for r in knowledge.rules.values() if "uzbek" in r.domains or "uz" in r.domains],
    ))
    return reg
