"""Real MCP + Chromium smoke test for a user-like button/form journey."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.mcp_manager import MCPManager


def test_browser_mcp_clicks_fills_asserts_and_captures_screenshot(tmp_path):
    page = tmp_path / "journey.html"
    page.write_text(
        """<!doctype html><html><head><title>Journey</title></head><body>
        <label>Name <input id='name'></label><button id='save'>Save</button>
        <p id='result'></p>
        <script>document.querySelector('#save').addEventListener('click', () => {
          document.querySelector('#result').textContent = `Saved ${document.querySelector('#name').value}`;
        });</script></body></html>""",
        encoding="utf-8",
    )
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    (tmp_path / ".igris" / "mcp.json").write_text(
        json.dumps({
            "servers": {
                "browser": {
                    "command": "python",
                    "args": ["-m", "igris.mcp_servers.browser_server"],
                }
            }
        }),
        encoding="utf-8",
    )

    async def run() -> tuple[str, str]:
        async with MCPManager(config) as mcp:
            capability = await mcp.call("browser__browser_check", {})
            if '"ok":true' not in capability:
                pytest.skip(f"Playwright Chromium is not installed: {capability}")
            journey = await mcp.call(
                "browser__browser_user_journey",
                {
                    "url": page.as_uri(),
                    "actions_json": json.dumps([
                        {"action": "fill", "selector": "#name", "value": "Igris"},
                        {"action": "click", "selector": "#save"},
                        {"action": "expect_text", "text": "Saved Igris"},
                        {"action": "screenshot", "name": "saved-state"},
                    ]),
                    "name": "real-user-flow",
                },
            )
            return capability, journey

    capability, journey = asyncio.run(run())
    assert '"ok":true' in capability
    assert '"ok":true' in journey
    assert "final.png" in journey
