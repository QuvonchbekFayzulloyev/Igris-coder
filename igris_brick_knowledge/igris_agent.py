"""IGRIS Brick Knowledge Agent — Main Orchestrator.

No monologue thinking. Just: match pattern -> apply rule -> done.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

from .core.brick_system import BrickBank
from .core.knowledge_system import KnowledgeBank
from .resolver.constraint_resolver import ConstraintResolver, ResolutionResult
from .chains.chain_system import ChainSystem


class IgrisBrickAgent:
    """Lightweight agent using brick+knowledge+chains for fast resolution."""

    def __init__(self):
        self.bricks = BrickBank()
        self.knowledge = KnowledgeBank(self.bricks)
        self.resolver = ConstraintResolver(self.bricks, self.knowledge)
        self.chains = ChainSystem(self.bricks, self.knowledge)

    def query(self, text: str, lang: str = "uz") -> ResolutionResult:
        """Resolve a user query to code using brick+knowledge system."""
        # First try direct resolution
        result = self.resolver.resolve(text, lang)
        if result.code and result.confidence >= 0.7:
            return result

        # Try chain-based resolution
        chain_code, chain_conf, chain_id = self.chains.resolve_with_chain(text, lang, "code")
        if chain_code and chain_conf > result.confidence:
            result.code = chain_code
            result.confidence = chain_conf
            result.chains_used = [chain_id]
            result.steps.append(f"chain resolved: {chain_id}")

        # Try healing if still weak
        if result.confidence < 0.5:
            available = [c.chain_id for c in self.chains.all_chains()]
            for domain in ["math", "code", "data"]:
                healed = self.chains.heal(domain, available)
                if healed:
                    h_code, h_conf, h_chain = self.chains.resolve_with_chain(text, lang, domain)
                    if h_code and h_conf > result.confidence:
                        result.code = h_code
                        result.confidence = h_conf
                        result.chains_used = [h_chain]
                        result.healed = True
                        result.steps.append(f"healed via {domain}")
                        break

        return result

    def interactive(self):
        """Interactive CLI mode."""
        print("IGRIS Brick Knowledge Agent v1.0")
        print("Type 'quit' to exit, 'stats' for statistics\n")

        while True:
            try:
                user_input = input("Query> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Bye!")
                break
            if user_input.lower() == "stats":
                self._print_stats()
                continue

            # Auto-detect language
            lang = "uz" if any(c in user_input for c in "o'g'usq") else "en"

            start = time.time()
            result = self.query(user_input, lang)
            elapsed = (time.time() - start) * 1000

            print(f"Status: {'✓' if result.code else '✗'}")
            print(f"Confidence: {result.confidence:.3f}")
            print(f"Chains: {result.chains_used}")
            print(f"Time: {elapsed:.1f}ms")
            if result.healed:
                print("(healed)")
            print(f"Output:")
            print(result.code or "  (no result)")
            print()

    def _print_stats(self):
        print(f"\n=== Statistics ===")
        print(f"Bricks: {self.bricks.size}")
        print(f"Chains: {self.chains.chain_count}")
        for chain in self.chains.all_chains():
            print(f"  {chain.chain_id}: {chain.domain} ({len(chain.bricks_used)} bricks, {chain.hit_count} hits)")


def main():
    agent = IgrisBrickAgent()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = agent.query(query)
        print(json.dumps({
            "status": "ok" if result.code else "no_result",
            "confidence": result.confidence,
            "code": result.code,
            "chains": result.chains_used,
            "healed": result.healed,
            "time_ms": result.resolution_time_ms,
            "steps": result.steps,
        }, indent=2, ensure_ascii=False))
    else:
        agent.interactive()


if __name__ == "__main__":
    main()
