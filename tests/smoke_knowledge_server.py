import asyncio
from pathlib import Path

from igris.config import Config
from igris.core.mcp_manager import MCPManager


async def main():
    config = Config.load(project_root=Path("/home/claude/igris-cli/projects/knowledge_smoke_test"))
    async with MCPManager(config) as mcp:
        print("=== tools registered ===")
        for t in mcp.tool_schemas():
            print(" -", t["function"]["name"])

        print("\n=== knowledge_list_modules (no embedding needed) ===")
        print(await mcp.call("knowledge__knowledge_list_modules", {}))

        print("\n=== knowledge_add (requires live Ollama -- expect a clear error, not a crash) ===")
        result = await mcp.call("knowledge__knowledge_add", {"text": "test rule", "module": "backend"})
        print(result)
        assert "ERROR" in result or "OK" in result, "tool must return a clear result either way, not raise"

        print("\n=== knowledge_search (same expectation) ===")
        result = await mcp.call("knowledge__knowledge_search", {"query": "test"})
        print(result)


asyncio.run(main())
