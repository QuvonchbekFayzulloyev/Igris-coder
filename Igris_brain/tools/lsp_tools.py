"""LSP Tools — code intelligence vositalari.

definition, references, hover, completion, diagnostics.
"""
from __future__ import annotations

import os
from typing import Optional

from .base import Tool


def _lsp_definition(ws, args: dict) -> dict:
    """Definition ga o'tish."""
    path = args.get("path", "")
    line = int(args.get("line", 0))
    column = int(args.get("column", 0))

    if not path:
        return {"ok": False, "error": "path is required"}

    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        defs = manager.goto_definition(path, line, column)
        return {
            "ok": True,
            "definitions": [d.to_dict() for d in defs],
            "count": len(defs),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lsp_references(ws, args: dict) -> dict:
    """Referencelarni topish."""
    path = args.get("path", "")
    line = int(args.get("line", 0))
    column = int(args.get("column", 0))

    if not path:
        return {"ok": False, "error": "path is required"}

    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        refs = manager.find_references(path, line, column)
        return {
            "ok": True,
            "references": [r.to_dict() for r in refs],
            "count": len(refs),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lsp_hover(ws, args: dict) -> dict:
    """Hover ma'lumotini olish."""
    path = args.get("path", "")
    line = int(args.get("line", 0))
    column = int(args.get("column", 0))

    if not path:
        return {"ok": False, "error": "path is required"}

    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        hover = manager.hover(path, line, column)
        if hover:
            return {"ok": True, "hover": hover.to_dict()}
        return {"ok": True, "hover": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lsp_completion(ws, args: dict) -> dict:
    """Completion takliflarini olish."""
    path = args.get("path", "")
    line = int(args.get("line", 0))
    column = int(args.get("column", 0))

    if not path:
        return {"ok": False, "error": "path is required"}

    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        completions = manager.completion(path, line, column)
        return {
            "ok": True,
            "completions": [c.to_dict() for c in completions[:20]],
            "count": len(completions),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lsp_diagnostics(ws, args: dict) -> dict:
    """Fayl diagnostikasini olish."""
    path = args.get("path", "")

    if not path:
        return {"ok": False, "error": "path is required"}

    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        diags = manager.diagnostics(path)
        return {
            "ok": True,
            "diagnostics": [d.to_dict() for d in diags],
            "count": len(diags),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _lsp_status(ws, args: dict) -> dict:
    """LSP serverlar holatini olish."""
    try:
        from lsp.manager import LSPManager
        manager = LSPManager(ws.root)
        return {
            "ok": True,
            "servers": manager.get_status(),
            "languages": manager.get_available_languages(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Tool ta'riflari

LSP_DEFINITION = Tool(
    name="lsp_definition",
    description=(
        "Go to definition of a symbol at the given position. "
        "Returns the file path, line, and column of the definition."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "line", "type": "integer", "description": "Line number (0-indexed)"},
        {"name": "column", "type": "integer", "description": "Column number (0-indexed)"},
    ],
    fn=_lsp_definition,
)

LSP_REFERENCES = Tool(
    name="lsp_references",
    description=(
        "Find all references to a symbol at the given position. "
        "Returns file paths, lines, and context for each reference."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "line", "type": "integer", "description": "Line number (0-indexed)"},
        {"name": "column", "type": "integer", "description": "Column number (0-indexed)"},
    ],
    fn=_lsp_references,
)

LSP_HOVER = Tool(
    name="lsp_hover",
    description=(
        "Get hover information (type, documentation) for a symbol at the given position."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "line", "type": "integer", "description": "Line number (0-indexed)"},
        {"name": "column", "type": "integer", "description": "Column number (0-indexed)"},
    ],
    fn=_lsp_hover,
)

LSP_COMPLETION = Tool(
    name="lsp_completion",
    description=(
        "Get code completion suggestions at the given position."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "line", "type": "integer", "description": "Line number (0-indexed)"},
        {"name": "column", "type": "integer", "description": "Column number (0-indexed)"},
    ],
    fn=_lsp_completion,
)

LSP_DIAGNOSTICS = Tool(
    name="lsp_diagnostics",
    description=(
        "Get diagnostics (errors, warnings) for a file."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
    ],
    fn=_lsp_diagnostics,
)

LSP_STATUS = Tool(
    name="lsp_status",
    description=(
        "Get status of all LSP servers and available languages."
    ),
    parameters=[],
    fn=_lsp_status,
)
