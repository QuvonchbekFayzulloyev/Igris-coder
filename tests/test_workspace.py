"""
Tests for igris.workspace -- the "one install, many projects" resolution
logic used by `igris new/use/projects` and the default run path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris import workspace as ws


@pytest.fixture
def fake_workspace(tmp_path, monkeypatch):
    """Redirect workspace_root() to an isolated tmp_path for every test."""
    monkeypatch.setattr(ws, "workspace_root", lambda: tmp_path)
    return tmp_path


def test_no_projects_raises(fake_workspace):
    with pytest.raises(ws.NoProjectSelected):
        ws.resolve_project_root()


def test_single_project_auto_selected(fake_workspace):
    ws.create_project("only-one")
    root = ws.resolve_project_root()
    assert root.name == "only-one"
    assert ws.get_active_project() == "only-one"


def test_multiple_projects_ambiguous_without_active(fake_workspace):
    ws.create_project("a")
    ws.create_project("b")
    with pytest.raises(ws.NoProjectSelected):
        ws.resolve_project_root()


def test_explicit_project_sets_active_and_persists(fake_workspace):
    ws.create_project("a")
    ws.create_project("b")

    root = ws.resolve_project_root("b")
    assert root.name == "b"
    assert ws.get_active_project() == "b"

    # subsequent call with no explicit project uses the now-active one
    root2 = ws.resolve_project_root()
    assert root2.name == "b"


def test_use_nonexistent_project_raises(fake_workspace):
    with pytest.raises(ws.NoProjectSelected):
        ws.resolve_project_root("missing")


def test_active_project_deleted_raises(fake_workspace):
    ws.create_project("a")
    ws.resolve_project_root("a")
    # simulate the project folder being deleted out from under igris
    (fake_workspace / "projects" / "a").rmdir()
    with pytest.raises(ws.NoProjectSelected):
        ws.resolve_project_root()


def test_list_projects_sorted(fake_workspace):
    ws.create_project("zebra")
    ws.create_project("alpha")
    assert ws.list_projects() == ["alpha", "zebra"]
