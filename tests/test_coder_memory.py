"""Tests for durable, source-backed Coder Knowledge Memory."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.coder_memory import CoderMemoryStore, ProjectMemoryCollector


def make_store(tmp_path):
    return CoderMemoryStore(Config.load(project_root=tmp_path))


def test_ingest_persists_payload_standard_metadata_and_indexes(tmp_path):
    store = make_store(tmp_path)
    artifact, status = store.ingest(
        title="FastAPI route validation",
        category="code_pattern",
        content="def create_route(): pass",
        tags=["fastapi", "validation"],
        language="Python",
        framework="FastAPI",
        source="official",
        source_uri="https://example.test/routes",
        quality_score=0.9,
        reuse_score=0.8,
        details={"problem": "validate input", "tests": "pytest"},
    )

    assert status == "added"
    assert (store.root / artifact.content_path).read_text(encoding="utf-8") == "def create_route(): pass"
    manifest = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    assert manifest[0]["trust_score"] == 0.95
    assert manifest[0]["details"]["tests"] == "pytest"
    indexes = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert artifact.id in indexes["tag"]["fastapi"]
    assert artifact.id in indexes["framework"]["fastapi"]


def test_search_prefers_trusted_high_quality_source_over_equally_matching_guess(tmp_path):
    store = make_store(tmp_path)
    store.ingest(
        title="FastAPI validation pattern",
        category="api_pattern",
        content="Use dependency validation.",
        tags=["fastapi", "validation"],
        source="llm",
        quality_score=0.3,
        reuse_score=0.3,
    )
    official, _ = store.ingest(
        title="FastAPI validation pattern",
        category="api_pattern",
        content="Use a documented request model validation pattern.",
        tags=["fastapi", "validation"],
        source="official",
        quality_score=0.9,
        reuse_score=0.9,
    )

    hits = store.search("FastAPI validation", top_k=2)
    assert hits[0].artifact.id == official.id
    assert hits[0].artifact.source == "official"


def test_same_project_source_is_upserted_with_stable_id(tmp_path):
    store = make_store(tmp_path)
    first, status = store.ingest(
        title="Project overview", category="project", content="first", source="project", source_uri="project://README.md"
    )
    second, status = store.ingest(
        title="Project overview", category="project", content="second", source="project", source_uri="project://README.md"
    )

    assert status == "updated"
    assert first.id == second.id
    assert len(store.list()) == 1
    assert store.read_content(second) == "second"
    assert second.version.startswith("sha256:")


def test_project_collector_adds_docs_configs_adrs_and_tree_without_node_modules(tmp_path):
    (tmp_path / "README.md").write_text("# Example project", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='example'", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0001-storage.md").write_text("# Use JSON", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    config = Config.load(project_root=tmp_path)

    result = ProjectMemoryCollector(config).collect()
    entries = CoderMemoryStore(config).list()
    categories = {entry.category for entry in entries}
    tree = next(entry for entry in entries if entry.category == "folder_structure")

    assert result["added"] >= 4
    assert {"project", "config", "decision", "folder_structure"}.issubset(categories)
    assert "node_modules" not in CoderMemoryStore(config).read_content(tree)
