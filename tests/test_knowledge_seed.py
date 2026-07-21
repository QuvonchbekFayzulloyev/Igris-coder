"""
Tests for igris.core.knowledge_seed.seed_all -- the full pipeline that
embeds and stores every SEED_ENTRIES item, plus a real route+search cycle
against the seeded data to confirm the hierarchical scoping actually
retrieves the right things.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core import knowledge_router
from igris.core.knowledge_base import KnowledgeStore
from igris.core.knowledge_seed import SEED_ENTRIES, seed_all


class _DeterministicFakeEmbedder:
    """Hash-based fake -- not semantically meaningful, but deterministic and dependency-free, enough to validate pipeline mechanics without live Ollama."""

    async def embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in digest[:16]]


def test_seed_all_embeds_and_stores_every_entry(tmp_path):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)
    embedder = _DeterministicFakeEmbedder()

    succeeded, failed = asyncio.run(seed_all(store, embedder))

    assert succeeded == len(SEED_ENTRIES)
    assert failed == 0


def test_seed_all_creates_expected_module_files(tmp_path):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)
    asyncio.run(seed_all(store, _DeterministicFakeEmbedder()))

    modules = set(store.list_modules())
    # every non-project-level module_path used in SEED_ENTRIES must have
    # produced its own file -- the hierarchical requirement, not one flat DB
    expected = {e.module_path for e in SEED_ENTRIES if e.module_path}
    assert expected.issubset(modules)


def test_seed_all_reports_progress_per_entry(tmp_path):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)
    calls = []

    asyncio.run(seed_all(
        store, _DeterministicFakeEmbedder(),
        on_progress=lambda i, total, seed, error: calls.append((i, total, error)),
    ))

    assert len(calls) == len(SEED_ENTRIES)
    assert all(error is None for _, _, error in calls)
    assert calls[0][0] == 1 and calls[-1][0] == len(SEED_ENTRIES)


def test_seed_all_continues_past_individual_failures(tmp_path):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)

    class _FlakyEmbedder:
        calls = 0

        async def embed_one(self, text):
            _FlakyEmbedder.calls += 1
            if _FlakyEmbedder.calls == 2:
                raise RuntimeError("simulated failure")
            return [0.1, 0.2]

    succeeded, failed = asyncio.run(seed_all(store, _FlakyEmbedder()))
    assert failed == 1
    assert succeeded == len(SEED_ENTRIES) - 1


def test_seeded_data_supports_a_real_route_and_search_cycle(tmp_path):
    config = Config.load(project_root=tmp_path)
    store = KnowledgeStore(config)
    embedder = _DeterministicFakeEmbedder()
    asyncio.run(seed_all(store, embedder))

    query = "how does the reprompt loop work"
    scope = knowledge_router.route(query)
    assert scope == "backend.core"

    query_vec = asyncio.run(embedder.embed_one(query))
    results = store.search(query_vec, module_path=scope, top_k=5)

    assert len(results) > 0
    scopes_returned = {entry.module_path for _, entry in results}
    # backend.core scope search must only surface backend.core/backend/project
    # entries, never an unrelated branch like frontend.*
    assert scopes_returned.issubset({"backend.core", "backend", ""})


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
