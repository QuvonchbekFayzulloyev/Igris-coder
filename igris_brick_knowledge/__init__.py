"""IGRIS Brick Knowledge System — Atomic semantic primitives for fast code resolution."""

__version__ = "1.0.0"

from .core.brick_system import Brick, BrickBank, BrickDomain
from .core.knowledge_system import KnowledgeBank
from .resolver.constraint_resolver import ConstraintResolver
from .chains.chain_system import ChainSystem
from .igris_agent import IgrisBrickAgent

__all__ = [
    "Brick", "BrickBank", "BrickDomain",
    "KnowledgeBank",
    "ConstraintResolver",
    "ChainSystem",
    "IgrisBrickAgent",
]
