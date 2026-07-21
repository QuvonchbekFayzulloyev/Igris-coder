"""Direct MCP tool tests for reusable Coder Knowledge Memory."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import igris.mcp_servers.memory_server as ms
from igris.config import Config
from igris.core.coder_memory import CoderMemoryStore


@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    store = CoderMemoryStore(Config.load(project_root=tmp_path))
    monkeypatch.setattr(ms, "_STORE", store)
    monkeypatch.setattr(ms, "_CONFIG", Config.load(project_root=tmp_path))
    return store


def test_memory_ingest_search_and_get_roundtrip(isolated_memory):
    created = ms.memory_ingest(
        title="Safe file deletion", category="security", content="Require explicit confirmation.",
        tags="filesystem,safety", source="project", quality_score=0.9,
    )
    assert created.startswith("OK:")

    found = ms.memory_search("filesystem safety confirmation")
    assert "Safe file deletion" in found
    artifact_id = isolated_memory.list()[0].id
    fetched = ms.memory_get(artifact_id, include_content=True)
    assert "Require explicit confirmation" in fetched


def test_memory_rejects_invalid_category_without_writing(isolated_memory):
    result = ms.memory_ingest(title="bad", category="unknown", content="x")
    assert result.startswith("ERROR:")
    assert isolated_memory.list() == []


def test_memory_record_lesson_requires_complete_verified_shape(isolated_memory):
    assert ms.memory_record_lesson("", "cause", "fix").startswith("ERROR:")
    result = ms.memory_record_lesson("Test hung", "missing timeout", "bound MCP calls", tags="mcp,reliability")
    assert result.startswith("OK:")
    lesson = isolated_memory.list()[0]
    assert lesson.category == "lesson"
    assert lesson.details["cause"] == "missing timeout"
