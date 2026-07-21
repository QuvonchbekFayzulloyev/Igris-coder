"""Safety and isolation tests for the allow-listed sandbox MCP."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import igris.mcp_servers.sandbox_server as ss


@pytest.fixture
def isolated_sandbox(tmp_path, monkeypatch):
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    sandbox_root = tmp_path / ".igris" / "sandbox"
    monkeypatch.setattr(ss, "ROOT", tmp_path)
    monkeypatch.setattr(ss, "SANDBOX_ROOT", sandbox_root)
    monkeypatch.setattr(ss, "RUNS_ROOT", sandbox_root / "runs")
    return tmp_path


def test_sandbox_copies_workspace_runs_allowlisted_profile_and_discards(isolated_sandbox):
    created = ss.sandbox_create("compile")
    assert created.startswith("OK:")
    run_id = re.search(r"'([^']+)'", created).group(1)
    run_dir = ss.RUNS_ROOT / run_id
    copied_file = run_dir / "workspace" / "sample.py"
    assert copied_file.read_text(encoding="utf-8") == "value = 1\n"

    result = asyncio.run(ss.sandbox_run_profile(run_id, "python_compile"))
    assert "exit=0" in result
    assert "passed" in ss.sandbox_report(run_id)
    assert ss.sandbox_discard(run_id).startswith("REFUSED:")
    assert ss.sandbox_discard(run_id, confirm=True).startswith("OK:")
    assert not run_dir.exists()


def test_sandbox_rejects_path_like_ids(isolated_sandbox):
    result = ss.sandbox_report("../../outside")
    assert result.startswith("ERROR:")
