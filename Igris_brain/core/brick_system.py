"""
IGRIS BRAIN — Brick System
==========================
Semantic primitives (words, concepts, functions, types).

A "brick" is an atomic meaning unit. It knows its surface form in every
language (uz / en / code). It does NOT "think" — it just is.

Reference: plan's `igris_brick_knowledge` section
   "teskari" = Brick(canonical_id="concept_inverse",
                     surface_forms={"uz": ["teskari"], "en": ["inverse"],
                                    "code": ["np.linalg.inv"]},
                     semantic_vector=[0.8, 0.9, 0.2, ...])  # 128-dim
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------- #
# Constants
# ---------------------------------------------------------------- #

VECTOR_DIM = 128
BRICK_KINDS = ("word", "concept", "function", "type", "api")


def _hash_vector(token: str, dim: int = VECTOR_DIM, seed: int = 42) -> np.ndarray:
    """Deterministic pseudo-semantic vector from a token string.

    Pure Python implementation (no model needed): hashlib seeding yields a
    stable vector across runs/processes (unlike builtin `hash`, which is
    salted per-process for strings).
    """
    digest = hashlib.sha256(f"{seed}:{token}".encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], "big") & 0xFFFFFFFF  # 32-bit mask
    rng = np.random.RandomState(seed_int)
    vec = rng.randn(dim).astype(np.float32)
    norm = float(np.linalg.norm(vec)) or 1.0
    return vec / norm


# ---------------------------------------------------------------- #
# Brick
# ---------------------------------------------------------------- #

@dataclass
class Brick:
    """Atomic meaning unit — a word, concept, function or type.

    Attributes:
        canonical_id: Stable unique id, e.g. "concept_inverse".
        surface_forms: Map of language -> list of spellings.
            Languages: "uz", "en", "code".
        kind: One of BRICK_KINDS.
        semantic_vector: 128-dim unit vector (deterministic by default).
        domains: Knowledge domains this brick belongs to
            (engineering, data-analytics, windows-os, linux-os,
             examples-usage, problem-classification).
        code_template: Optional code snippet template with `{args}`.
    """

    canonical_id: str
    surface_forms: dict[str, list[str]] = field(default_factory=dict)
    kind: str = "word"
    semantic_vector: Optional[np.ndarray] = None
    domains: list[str] = field(default_factory=list)
    code_template: Optional[str] = None

    def __post_init__(self):
        if self.semantic_vector is None:
            self.semantic_vector = _hash_vector(self.canonical_id)

    # ---- lookup helpers ---------------------------------------- #

    def matches_surface(self, token: str, lang: Optional[str] = None) -> bool:
        """True if `token` equals one of this brick's surface forms."""
        token = token.strip().lower()
        langs = [lang] if lang else list(self.surface_forms.keys())
        for l in langs:
            if token in {f.lower() for f in self.surface_forms.get(l, [])}:
                return True
        return False

    def surface(self, lang: str) -> Optional[str]:
        forms = self.surface_forms.get(lang) or []
        return forms[0] if forms else None

    def similarity(self, other: "Brick") -> float:
        """Cosine similarity of semantic vectors."""
        a = self.semantic_vector
        b = other.semantic_vector
        if a is None or b is None:
            return 0.0
        dot = float(np.dot(a, b))
        return max(0.0, min(1.0, dot))

    def to_dict(self) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "kind": self.kind,
            "surface_forms": self.surface_forms,
            "domains": self.domains,
            "code_template": self.code_template,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Brick {self.canonical_id} ({self.kind})>"


# ---------------------------------------------------------------- #
# BrickBank
# ---------------------------------------------------------------- #

class BrickBank:
    """Registry of all bricks + fast lookup indexes."""

    def __init__(self):
        self.bricks: dict[str, Brick] = {}
        self._by_surface: dict[str, str] = {}  # (lang, token) -> canonical_id

    # ---- population ------------------------------------------- #

    def add(self, brick: Brick) -> "BrickBank":
        self.bricks[brick.canonical_id] = brick
        for lang, forms in brick.surface_forms.items():
            for f in forms:
                self._by_surface[(lang, f.lower())] = brick.canonical_id
        return self

    def add_many(self, bricks: list[Brick]) -> "BrickBank":
        for b in bricks:
            self.add(b)
        return self

    # ---- lookup ------------------------------------------------ #

    def get(self, canonical_id: str) -> Optional[Brick]:
        return self.bricks.get(canonical_id)

    def lookup(self, token: str, lang: str = "en") -> Optional[Brick]:
        """Exact surface-form lookup in one language."""
        cid = self._by_surface.get((lang, token.strip().lower()))
        return self.bricks.get(cid) if cid else None

    def lookup_any(self, token: str) -> Optional[Brick]:
        """Lookup across all languages."""
        token = token.strip().lower()
        for (lang, t), cid in self._by_surface.items():
            if t == token:
                return self.bricks.get(cid)
        return None

    def find_by_domain(self, domain: str) -> list[Brick]:
        return [b for b in self.bricks.values() if domain in b.domains]

    def find_by_kind(self, kind: str) -> list[Brick]:
        return [b for b in self.bricks.values() if b.kind == kind]

    def similar(self, brick: Brick, top_k: int = 5) -> list[tuple[Brick, float]]:
        """Top-k most similar bricks by cosine similarity (excluding self)."""
        scored = sorted(
            ((b, brick.similarity(b)) for b in self.bricks.values() if b is not brick),
            key=lambda x: x[1],
            reverse=True,
        )
        return scored[:top_k]

    def fuzzy_lookup(self, token: str, threshold: float = 0.60) -> Optional[Brick]:
        """Best-effort match: surface forms first, then vector similarity."""
        exact = self.lookup_any(token)
        if exact:
            return exact
        probe = Brick(canonical_id=f"__probe__{token}", kind="word")
        best, best_score = None, threshold
        for b in self.bricks.values():
            s = probe.similarity(b)
            # bias toward surface-form substring overlap
            if token[:3] in b.canonical_id:
                s += 0.15
            if s > best_score:
                best, best_score = b, s
        return best

    @property
    def size(self) -> int:
        return len(self.bricks)

    def stats(self) -> dict:
        by_kind: dict[str, int] = {}
        for b in self.bricks.values():
            by_kind[b.kind] = by_kind.get(b.kind, 0) + 1
        return {"total": self.size, "by_kind": by_kind}
