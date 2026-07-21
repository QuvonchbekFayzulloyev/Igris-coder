r"""
Diagnostic script: verifies the MCP layer works end-to-end (spawns the
real filesystem/terminal/git servers over stdio, lists their tools, and
calls each one) without needing Ollama running. Resolves the active
project the same way `igris` itself does -- run it from anywhere once
you have at least one project (`igris new <name>`).

Usage:
    python path\to\igris-cli\tests\smoke_mcp.py      (PowerShell)
    python /path/to/igris-cli/tests/smoke_mcp.py     (bash)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from igris import workspace
from igris.config import Config
from igris.core.mcp_manager import MCPManager


async def main():
    try:
        project_root = workspace.resolve_project_root()
    except workspace.NoProjectSelected as e:
        print(f"{e}")
        return

    print(f"Running against project: {project_root}\n")
    config = Config.load(project_root=project_root)
    if not config.igris_dir.exists():
        config.ensure_project_scaffold()

    async with MCPManager(config) as mcp:
        print("=== tool schemas (Ollama format) ===")
        for t in mcp.tool_schemas():
            print(" -", t["function"]["name"])

        print("\n=== describe_tools() (for system prompt) ===")
        print(mcp.describe_tools())

        print("\n=== call filesystem__write_file + read back ===")
        print(await mcp.call("filesystem__write_file", {"path": ".igris/_smoke_test.txt", "content": "written by igris"}))
        print(await mcp.call("filesystem__read_file", {"path": ".igris/_smoke_test.txt"}))

        print("=== call filesystem__list_dir ===")
        print(await mcp.call("filesystem__list_dir", {"path": "."}))

        print("=== call git__git_status (harmless if not a git repo) ===")
        print(await mcp.call("git__git_status", {}))

        print("=== call terminal__env_info ===")
        print(await mcp.call("terminal__env_info", {}))

        print("=== call terminal__run_command (shell='auto' -- Windows-first policy) ===")
        print(await mcp.call("terminal__run_command", {"command": "echo hi from mcp terminal", "shell": "auto"}))

        print("=== safety gate: delete without confirm ===")
        print(await mcp.call("filesystem__delete_path", {"path": ".igris/_smoke_test.txt"}))

        print("=== cleanup: delete with confirm=true ===")
        print(await mcp.call("filesystem__delete_path", {"path": ".igris/_smoke_test.txt", "confirm": True}))

        print("=== path escape guard ===")
        print(await mcp.call("filesystem__read_file", {"path": "../../etc/passwd"}))


asyncio.run(main())
