"""
Tests for the hierarchical knowledge base: project-level DB + per-module
DBs (not one flat DB), scoped search that includes ancestor scopes, and
keyword-based module routing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.knowledge_base import KnowledgeEntry, KnowledgeStore, _cosine
from igris.core import knowledge_router


def make_store(tmp_path):
    config = Config.load(project_root=tmp_path)
    return KnowledgeStore(config)


def test_cosine_similarity_basic():
    assert _cosine([1, 0], [1, 0]) == 1.0
    assert round(_cosine([1, 0], [0, 1]), 5) == 0.0
    assert _cosine([], [1, 2]) == -1.0
    assert _cosine([1, 2], [1, 2, 3]) == -1.0  # mismatched dims


def test_add_and_load_project_level_entry(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="p1", text="Windows-first, no WSL by default", module_path="", embedding=[1, 0]))

    entries = store.load_module("")
    assert len(entries) == 1
    assert entries[0].text == "Windows-first, no WSL by default"


def test_project_and_module_dbs_are_separate_files(tmp_path):
    """The core requirement: not one flat DB -- project and module entries live in different files."""
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="p1", text="project rule", module_path="", embedding=[1, 0]))
    store.add(KnowledgeEntry(id="b1", text="backend rule", module_path="backend", embedding=[1, 0]))

    project_file = store.root / "project.json"
    backend_file = store.root / "modules" / "backend.json"
    assert project_file.exists()
    assert backend_file.exists()
    assert project_file != backend_file


def test_submodule_gets_its_own_db_file(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="c1", text="reprompt loop rule", module_path="backend.core", embedding=[1, 0]))
    assert (store.root / "modules" / "backend.core.json").exists()
    # sibling submodule must NOT see this entry when loaded directly
    assert store.load_module("backend.mcp_servers") == []


def test_search_scoped_to_submodule_includes_ancestor_scopes(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="p1", text="project-wide rule", module_path="", embedding=[1, 0, 0]))
    store.add(KnowledgeEntry(id="b1", text="backend rule", module_path="backend", embedding=[1, 0, 0]))
    store.add(KnowledgeEntry(id="c1", text="core rule", module_path="backend.core", embedding=[1, 0, 0]))
    store.add(KnowledgeEntry(id="f1", text="unrelated frontend rule", module_path="frontend", embedding=[1, 0, 0]))

    results = store.search(query_embedding=[1, 0, 0], module_path="backend.core", top_k=10)
    texts = {e.text for _, e in results}

    assert "core rule" in texts
    assert "backend rule" in texts
    assert "project-wide rule" in texts
    assert "unrelated frontend rule" not in texts  # different branch, correctly excluded


def test_search_ranks_by_similarity_not_insertion_order(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="low", text="barely related", module_path="backend", embedding=[0.1, 0.99]))
    store.add(KnowledgeEntry(id="high", text="very related", module_path="backend", embedding=[1.0, 0.0]))

    results = store.search(query_embedding=[1.0, 0.01], module_path="backend", top_k=2)
    assert results[0][1].text == "very related"


def test_search_top_k_limits_results(tmp_path):
    store = make_store(tmp_path)
    for i in range(10):
        store.add(KnowledgeEntry(id=f"e{i}", text=f"entry {i}", module_path="backend", embedding=[1, 0]))

    results = store.search(query_embedding=[1, 0], module_path="backend", top_k=3)
    assert len(results) == 3


def test_entries_without_embedding_are_excluded_from_search(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="no_emb", text="not yet embedded", module_path="backend", embedding=[]))
    results = store.search(query_embedding=[1, 0], module_path="backend", top_k=5)
    assert results == []


def test_list_modules(tmp_path):
    store = make_store(tmp_path)
    store.add(KnowledgeEntry(id="a", text="x", module_path="backend", embedding=[1]))
    store.add(KnowledgeEntry(id="b", text="y", module_path="frontend.components", embedding=[1]))
    assert store.list_modules() == ["backend", "frontend.components"]


# --- routing ---------------------------------------------------------

def test_route_backend_core_query():
    assert knowledge_router.route("what's the reprompt loop stage sequence") == "backend.core"


def test_route_frontend_component_query():
    assert knowledge_router.route("how should this React component be structured") == "frontend.components"


def test_route_provider_query():
    assert knowledge_router.route("how do I add a new ollama provider") == "backend.providers"


def test_route_unmatched_query_returns_none():
    assert knowledge_router.route("what's the weather today") is None
