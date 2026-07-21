"""Real stdio MCP smoke test for durable memory and isolated verification."""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.mcp_manager import MCPManager


def test_memory_and_sandbox_servers_work_over_real_mcp_stdio(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\nA reusable local project.", encoding="utf-8")
    (tmp_path / "module.py").write_text("value = 42\n", encoding="utf-8")
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    (tmp_path / ".igris" / "mcp.json").write_text(
        json.dumps({
            "servers": {
                "memory": {"command": "python", "args": ["-m", "igris.mcp_servers.memory_server"]},
                "sandbox": {"command": "python", "args": ["-m", "igris.mcp_servers.sandbox_server"]},
            }
        }),
        encoding="utf-8",
    )

    async def run() -> tuple[str, str, str, str]:
        async with MCPManager(config) as mcp:
            collected = await mcp.call("memory__memory_collect_project", {})
            searched = await mcp.call("memory__memory_search", {"query": "reusable local project"})
            created = await mcp.call("sandbox__sandbox_create", {"label": "real-mcp"})
            run_id = re.search(r"'([^']+)'", created).group(1)
            compiled = await mcp.call("sandbox__sandbox_run_profile", {"run_id": run_id, "profile": "python_compile"})
            discarded = await mcp.call("sandbox__sandbox_discard", {"run_id": run_id, "confirm": True})
            return collected, searched, compiled, discarded

    collected, searched, compiled, discarded = asyncio.run(run())
    assert collected.startswith("OK:")
    assert "Demo" in searched
    assert "exit=0" in compiled
    assert discarded.startswith("OK:")
