"""
IGRIS BRAIN — Fayl vositalari
=============================
read_file, write_file, apply_patch, list_files — hammasi Workspace orqali.
"""

from __future__ import annotations

import difflib
import os

from .base import Tool


def _read_file(ws, args: dict) -> dict:
    path = args.get("path", "")
    return ws.read(path)


def _write_file(ws, args: dict) -> dict:
    path = args.get("path", "")
    content = args.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    return ws.write(path, content)


def _apply_patch(ws, args: dict) -> dict:
    """Unified-diff yoki simple +-patch qo'llash.

    args: {path, patch}  — patch satrlar: '- old', '+ yangi', '  kontekst'
    """
    path = args.get("path", "")
    patch_text = args.get("patch", "")
    if not patch_text:
        return {"ok": False, "error": "patch is empty"}

    current = ws.read(path)
    if not current["ok"]:
        return current
    old_lines = current["content"].splitlines(keepends=True)
    old_text = current["content"]

    # simple +/- patch (newline tolerant)
    try:
        new_text = _apply_simple_patch(old_text, patch_text)
        if new_text == old_text:
            return {"ok": False, "error": "patch did not change the file (context mismatch?)"}
        ws.write(path, new_text)
        diff = list(difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines(),
            fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
        return {"ok": True, "path": path, "diff": diff[:60], "changed": True}
    except Exception as exc:
        return {"ok": False, "error": f"apply_patch failed: {exc}"}


def _apply_simple_patch(old_text: str, patch_text: str) -> str:
    """Minimal +/- satr patch. '-' olib tashlaydi, '+' qo'shadi."""
    lines = old_text.splitlines(keepends=True)
    removals: list[str] = []
    additions: list[tuple[int, str]] = []   # (anchor_index, line)

    # '- old' / '+ new' — marker'dan keyingi bitta bo'shliq separator deb hisoblanadi,
    # lekin ikkala shakl ham qabul qilinadi ('- old' yoki '-old')
    for pl in patch_text.splitlines(keepends=True):
        line = pl.rstrip("\r\n")
        if line.startswith("-"):
            removals.append(_strip_marker(line[1:]))
        elif line.startswith("+"):
            additions.append((None, _strip_marker(line[1:]) + "\n"))

    # apply removals (exact match, newline-agnostic)
    out = []
    for ln in lines:
        stripped = ln.rstrip("\r\n")
        if stripped in removals:
            removals.remove(stripped)
            continue
        out.append(ln)
    if removals:
        raise ValueError(f"removal lines not found in file: {removals[:3]}")

    # append additions at the end (simple heuristic)
    for _, add in additions:
        out.append(add)
    return "".join(out)


def _strip_marker(s: str) -> str:
    """Marker'dan keyingi bitta bo'shliqni olib tashlaydi (agar mavjud bo'lsa)."""
    return s[1:] if s.startswith(" ") else s


def _list_files(ws, args: dict) -> dict:
    path = args.get("path", "")
    depth = int(args.get("depth", 2))
    return ws.list(path, depth=depth)


# ---------------------------------------------------------------- #
# Tool ta'riflari
# ---------------------------------------------------------------- #

READ_FILE = Tool(
    name="read_file",
    description="Read a file from the workspace and return its content.",
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
    ],
    fn=_read_file,
)

WRITE_FILE = Tool(
    name="write_file",
    description="Create or overwrite a file in the workspace with the given content.",
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "content", "type": "string", "description": "Full file content to write"},
    ],
    fn=_write_file,
)

APPLY_PATCH = Tool(
    name="apply_patch",
    description=(
        "Apply a minimal patch to an existing file. Lines starting with '-' are "
        "removed, lines starting with '+' are appended. Use for small edits."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "patch", "type": "string",
         "description": "Patch text: '- old line' / '+ new line'"},
    ],
    fn=_apply_patch,
)

LIST_FILES = Tool(
    name="list_files",
    description="List files and directories in the workspace (tree, limited depth).",
    parameters=[
        {"name": "path", "type": "string", "description": "Directory to list (default root)", "default": ""},
        {"name": "depth", "type": "integer", "description": "Max recursion depth", "default": 2},
    ],
    fn=_list_files,
)
