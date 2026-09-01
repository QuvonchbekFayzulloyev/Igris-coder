"""
IGRIS BRAIN — Tool asosiy klassi
================================
Har bir vosita: name, description, parameters, fn(workspace, args).
"""

from __future__ import annotations

from typing import Callable, Optional


class Tool:
    def __init__(self, name: str, description: str, parameters: list[dict],
                 fn: Callable, required: Optional[list[str]] = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required = required or [p["name"] for p in parameters]
        self.fn = fn

    def schema(self) -> dict:
        """Flat JSON-schema (name, description, parameters)."""
        props = {p["name"]: {k: v for k, v in p.items() if k != "name"}
                 for p in self.parameters}
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": self.required,
            },
        }

    def ollama_schema(self) -> dict:
        """Ollama `/api/chat` tools API formatida wrapper.

        Ollama quyidagi tuzilmani kutadi:
            {"type": "function", "function": {name, description, parameters}}
        """
        return {"type": "function", "function": self.schema()}

    def execute(self, workspace, args: dict) -> dict:
        return self.fn(workspace, args)
