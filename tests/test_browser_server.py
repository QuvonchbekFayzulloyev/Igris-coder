"""Browser MCP validation tests; real Chromium execution is covered separately when installed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import igris.mcp_servers.browser_server as bs


@pytest.fixture
def browser_root(tmp_path, monkeypatch):
    page = tmp_path / "page.html"
    page.write_text("<button id='go'>Go</button>", encoding="utf-8")
    monkeypatch.setattr(bs, "ROOT", tmp_path)
    monkeypatch.setattr(bs, "OUTPUT_ROOT", tmp_path / ".igris" / "sandbox" / "browser")
    return page


def test_browser_rejects_non_local_url_by_default(browser_root):
    result = bs.browser_user_journey("https://example.com", "[]")
    assert result.startswith("ERROR:")


def test_browser_validates_actions_and_invokes_runner_for_local_file(browser_root, monkeypatch):
    captured = {}

    def fake_runner(arguments, timeout_seconds):
        captured["arguments"] = arguments
        captured["timeout"] = timeout_seconds
        return '{"ok":true,"steps":[{"action":"click","ok":true}]}'

    monkeypatch.setattr(bs, "_run_runner", fake_runner)
    result = bs.browser_user_journey(
        browser_root.as_uri(),
        '[{"action":"click","selector":"#go"}]',
        name="button test",
    )

    assert "\"ok\":true" in result
    assert "--url" in captured["arguments"]
    assert bs.browser_user_journey(browser_root.as_uri(), "{}", name="bad").startswith("ERROR:")
