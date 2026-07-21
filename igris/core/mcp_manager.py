"""
igris.core.mcp_manager
-----------------------
Spawns each server listed in .igris/mcp.json as a real MCP stdio server
(using the official `mcp` SDK) and exposes a single aggregated tool
surface to the rest of igris. Tool names are namespaced as
"<server>.<tool>" so multiple servers can coexist without collisions.

This is the thing that turns Ollama's tool-calling into an actual agent
loop that can touch the filesystem, run commands, and use git -- the
same role Claude Code's built-in tools play, just sourced from MCP.
"""
from __future__ import annotations

import json
import shlex
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class ToolHandle:
    server_name: str
    tool_name: str
    description: str
    input_schema: dict

    @property
    def qualified_name(self) -> str:
        return f"{self.server_name}.{self.tool_name}"

    def to_ollama_schema(self) -> dict:
        """Ollama's /api/chat tools format is OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.qualified_name.replace(".", "__"),  # some models choke on dots
                "description": self.description or f"{self.tool_name} ({self.server_name} MCP server)",
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


class MCPManager:
    """
    Async context manager. Usage:

        async with MCPManager(config) as mgr:
            tools = mgr.tool_schemas()
            result = await mgr.call("filesystem__read_file", {"path": "README.md"})
    """

    def __init__(self, config):
        self.config = config
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, ToolHandle] = {}  # keyed by qualified name with __ separator

    async def __aenter__(self) -> "MCPManager":
        mcp_cfg_path = self.config.path_for("mcp.config_file")
        servers = {}
        if mcp_cfg_path.exists():
            servers = json.loads(mcp_cfg_path.read_text(encoding="utf-8")).get("servers", {})

        for name, spec in servers.items():
            await self._connect(name, spec)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._stack.aclose()

    async def _connect(self, name: str, spec: dict) -> None:
        params = StdioServerParameters(
            command=spec["command"],
            args=spec.get("args", []),
            env=spec.get("env"),
            cwd=str(self.config.project_root),  # pin the tool subprocess to the active project
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[name] = session

        listing = await session.list_tools()
        for tool in listing.tools:
            handle = ToolHandle(
                server_name=name,
                tool_name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
            )
            key = handle.qualified_name.replace(".", "__")
            self._tools[key] = handle

    def tool_schemas(self) -> list[dict]:
        return [h.to_ollama_schema() for h in self._tools.values()]

    def describe_tools(self) -> str:
        """Human-readable tool list, used when building system prompts."""
        lines = []
        for h in self._tools.values():
            lines.append(f"- {h.qualified_name}: {h.description}")
        return "\n".join(lines)

    async def call(self, qualified_name_underscored: str, arguments: dict) -> str:
        handle = self._tools.get(qualified_name_underscored)
        if handle is None:
            return f"ERROR: unknown tool '{qualified_name_underscored}'"
        session = self._sessions[handle.server_name]
        try:
            # Do not cancel an MCP request here with asyncio.wait_for:
            # cancelling a live stdio request can corrupt the session's
            # transport task group. Every bundled server owns a bounded,
            # exception-safe timeout at the operation it performs instead.
            result = await session.call_tool(handle.tool_name, arguments or {})
        except Exception as e:
            return f"ERROR: tool '{handle.tool_name}' failed: {e}"
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else "(no output)"
