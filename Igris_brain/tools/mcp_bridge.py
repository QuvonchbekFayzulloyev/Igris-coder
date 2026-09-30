"""
IGRIS BRAIN — MCP Bridge
========================
Model Context Protocol klient: mcp_servers.json'da ro'yxatlangan stdio
server'lari bilan ulanydi va ularning tool'larini agentga beradi.

Qobiliyat:
    - server'larni ishga tushiradi (subprocess stdio)
    - list_tools()  -> [{name, description, parameters}]
    - call_tool(server, name, args) -> natija matni

AgentExecutor `mcp_call` tool'i orqali ishlatadi — model MCP vositalarini
chaqirishi mumkin (masalan rasm chizish).

Texnik qayd: MCP session'lar yashovchan (persistent) bo'lishi kerak, shuning
uchun alohida asyncio event loop fon thread'ida doimiy ishlaydi va barcha
chaqiruvlar `run_coroutine_threadsafe` orqali o'sha loop'ga yuboriladi.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from safety.safety import has_suspicious, sanitize  # noqa: E402 (N3: MCP chiqishini tozalash)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_servers.json")


class McpBridge:
    """Bir nechta MCP stdio server bilan ishlaydigan bridge."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, base_dir: str = ""):
        self.config_path = config_path
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.sessions: dict[str, ClientSession] = {}
        self.tool_index: dict[str, dict] = {}   # "server__tool" -> {server, name, schema}
        self._streams: dict[str, tuple] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None

    # ------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------ #

    def start(self) -> int:
        """Fon thread'ida asyncio loop'ni boshlaydi va server'larni ulaydi."""
        if self._loop is None or not self._loop.is_running():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="mcp-loop")
            self._thread.start()
        connected = 0
        for name, cfg in (self.load_config()).items():
            if not cfg.get("enabled", True):
                continue
            if self._submit(self._connect(name, cfg)):
                connected += 1
        return connected

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro) -> object:
        """Korutinani fon loop'iga yuboradi va natijani kutadi (bloklovchi)."""
        if self._loop is None:
            return None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=45)

    async def _connect(self, name: str, cfg: dict) -> bool:
        import traceback

        command = cfg.get("command", "python")
        args = cfg.get("args", [])
        # AUDIT FIX: konfiguratsiyadagi nisbiy `cwd` jarayon cwd'iga EMAS,
        # konfiguratsiya fayli joyiga nisbatan hal qilinadi — aks holda
        # pytest/server qaysi papkadan ishga tushishiga qarab stdio server
        # (masalan art_server.py) topilmay qolardi (Errno 2).
        raw_cwd = str(cfg.get("cwd") or "").strip()
        if not raw_cwd:
            cwd = self.base_dir
        elif os.path.isabs(raw_cwd):
            cwd = raw_cwd
        else:
            cwd = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(self.config_path)), raw_cwd))
        # Konfiguratsiyadagi env — asosiy muhit ustiga yoziladi (PATH va boshqa
        # muhim o'zgaruvchilar meros qilib olinadi, child har doim ishga tushadi).
        env = {**os.environ, **(cfg.get("env") or {})}
        try:
            params = StdioServerParameters(command=command, args=args, cwd=cwd, env=env)
            client = stdio_client(params)
            read, write = await client.__aenter__()
            try:
                session = await ClientSession(read, write).__aenter__()
                await asyncio.wait_for(session.initialize(), timeout=30)
            except Exception:
                await client.__aexit__(None, None, None)
                raise
            self._streams[name] = (client, read, write)
            self.sessions[name] = session
            resp = await session.list_tools()
            for t in resp.tools:
                key = f"{name}__{t.name}"
                self.tool_index[key] = {
                    "server": name,
                    "name": t.name,
                    "schema": {
                        "name": f"{name}__{t.name}",
                        "description": t.description or "",
                        "parameters": getattr(t, "inputSchema", {}) or {"type": "object", "properties": {}},
                    },
                }
            return True
        except Exception as exc:
            self.error = f"{name}: {exc}"
            traceback.print_exc()
            print(f"[igris][mcp] {name} connect failed: {exc}")
            # S3: silent-degradation registry — ulanmagan MCP server endi
            # /api/system/services'da ko'rinadi (UI + watchdog telemetry).
            try:
                from monitor.degradation import mark
                mark(f"mcp.{name}", str(exc)[:300], fallback="no-tools")
            except Exception:
                pass
            return False

    async def _close_sessions(self) -> None:
        """Close MCP sessions and stdio transports on their owning loop."""
        sessions = list(self.sessions.values())
        streams = list(self._streams.values())
        self.sessions.clear()
        self._streams.clear()
        self.tool_index.clear()

        for session in sessions:
            try:
                await session.__aexit__(None, None, None)
            except Exception as exc:
                self.error = f"MCP session close failed: {exc}"
        for client, _read, _write in streams:
            try:
                await client.__aexit__(None, None, None)
            except Exception as exc:
                self.error = f"MCP transport close failed: {exc}"

    def close(self):
        """Gracefully close MCP resources before stopping the event loop."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._close_sessions(), loop)
            future.result(timeout=15)
        except Exception as exc:
            self.error = f"MCP bridge close failed: {exc}"
        finally:
            loop.call_soon_threadsafe(loop.stop)
            if self._thread is not None and self._thread is not threading.current_thread():
                self._thread.join(timeout=5)
            self._loop = None
            self._thread = None

    # ------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------ #

    def list_tools(self) -> list[dict]:
        return [v["schema"] for v in self.tool_index.values()]

    def names(self) -> list[str]:
        return list(self.tool_index.keys())

    def describe_all(self) -> str:
        if not self.tool_index:
            return "(no MCP servers connected)"
        lines = ["MCP tools available via mcp_call (server__tool):"]
        for key, info in sorted(self.tool_index.items()):
            lines.append(f"- {key} — {info['schema']['description'][:180]}")
        return "\n".join(lines)

    def call_tool(self, server_tool: str, args: dict) -> dict:
        info = self.tool_index.get(server_tool)
        if info is None:
            return {"ok": False, "error": f"unknown MCP tool: {server_tool}. Available: {self.names()}"}
        session = self.sessions.get(info["server"])
        if session is None:
            return {"ok": False, "error": f"MCP server '{info['server']}' not connected"}

        async def _call():
            result = await session.call_tool(info["name"], args or {})
            texts = []
            images = []
            for c in getattr(result, "content", []) or []:
                ctype = getattr(c, "type", "")
                if ctype == "text":
                    texts.append(getattr(c, "text", ""))
                elif ctype == "image":
                    images.append({
                        "data": getattr(c, "data", ""),
                        "mimeType": getattr(c, "mimeType", "image/png"),
                    })
            if not texts:
                texts.append(str(getattr(result, "content", "")))
            text = "\n".join(texts)
            extra = {"image": images[0]} if images else {}
            return text, extra

        try:
            text, extra = self._submit(_call())
        except Exception as exc:
            return {"ok": False, "error": f"MCP call failed: {exc}"}
        # N3 (defense-in-depth): BARCHA MCP tool chiqishi (browser_get_text,
        # web_ai_get_conversation, ask_web_ai va h.k.) agentga yetib borishdan
        # oldin injection naqshlaridan tozalanadi — server tomoni ham tozalaydi,
        # lekin bu qatlam hech qanday tool'ni unutmaydi.
        if has_suspicious(text):
            text = sanitize(text)
        return {"ok": True, "output": text, "content": text, **extra}

    # ------------------------------------------------------------ #

    def status(self) -> dict:
        return {
            "servers": list(self.sessions.keys()),
            "tools": len(self.tool_index),
            "error": self.error,
        }

    def load_config(self) -> dict:
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("servers", {}) or {}
        except Exception as exc:
            self.error = f"mcp config load failed: {exc}"
            try:
                from monitor.degradation import mark
                mark("mcp.config", str(exc)[:300], fallback="no-mcp")
            except Exception:
                pass
            return {}


DEFAULT_BRIDGE = McpBridge()

__all__ = ["McpBridge", "DEFAULT_BRIDGE"]
