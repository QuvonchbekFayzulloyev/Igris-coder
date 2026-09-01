"""
IGRIS BRAIN — Tool Registry
===========================
Birlashtiruvchi vosita ro'yxati. Har bir tool:
  - `name`: qisqa nom (read_file, run_command, ...)
  - `description`: LLM'ga ko'rsatiladigan tavsif
  - `parameters`: JSON-schema (name, type, description, required)
  - `fn`: (workspace, args) -> dict {ok, output/error}

Workspace barcha fayl operatsiyalari uchun xavfsiz sandbox beradi.
"""

from __future__ import annotations

from typing import Optional

from .base import Tool
from .workspace import Workspace
from . import fs_tools, shell_tools, python_tools, web_tools, extra_tools


class ToolRegistry:
    """Barcha mavjud vositalar ro'yxati."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(fs_tools.READ_FILE)
        self.register(fs_tools.WRITE_FILE)
        self.register(fs_tools.APPLY_PATCH)
        self.register(fs_tools.LIST_FILES)
        self.register(shell_tools.RUN_COMMAND)
        self.register(python_tools.PYTHON_EXEC)
        # Tez deterministik web vositalar (brauzersiz): web_fetch + rasm qidiruv
        self.register(web_tools.WEB_FETCH)
        self.register(web_tools.WEB_SEARCH_IMAGE)
        # Qo'shimcha vositalar: kod qidirish, papka yaratish, git, fayl boshqaruvi
        self.register(extra_tools.SEARCH_CODE)
        self.register(extra_tools.CREATE_DIRECTORY)
        self.register(extra_tools.GIT_COMMAND)
        self.register(extra_tools.RENAME_FILE)
        self.register(extra_tools.DELETE_FILE)

    def register(self, tool: Tool) -> "ToolRegistry":
        self.tools[tool.name] = tool
        return self

    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def names(self) -> list[str]:
        return list(self.tools.keys())

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools.values()]

    def ollama_schemas(self) -> list[dict]:
        """Ollama tools API formatidagi schema-lar (chat_with_tools uchun)."""
        return [t.ollama_schema() for t in self.tools.values()]

    def execute(self, workspace: Workspace, name: str, args: dict) -> dict:
        tool = self.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            return tool.execute(workspace, args or {})
        except Exception as exc:
            return {"ok": False, "error": f"{tool.name} raised: {exc}"}


# Singleton — server va agent foydalanadi
DEFAULT_REGISTRY = ToolRegistry()

__all__ = ["Tool", "ToolRegistry", "Workspace", "DEFAULT_REGISTRY"]
