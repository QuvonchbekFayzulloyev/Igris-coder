"""
IGRIS BRAIN — Fayl vositalari
=============================
read_file, write_file, apply_patch, edit_file, list_files — hammasi Workspace orqali.
"""

from __future__ import annotations

import difflib
import os
import re

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


def _edit_file(ws, args: dict) -> dict:
    """Fayl ichidagi aniq qismni tahrirlash — exact string replacement.

    args: {path, old_string, new_string, replace_all}
    - old_string: o'zgartirilishi kerak bo'lgan matn (indentation muhim!)
    - new_string: yangi matn
    - replace_all: barcha takrorlanishlarni o'zgartirish (default: false)
    """
    path = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)

    if not old_string:
        return {"ok": False, "error": "old_string is required"}
    if old_string == new_string:
        return {"ok": False, "error": "old_string and new_string are identical"}

    # Faylni o'qish
    current = ws.read(path)
    if not current["ok"]:
        return current

    content = current["content"]

    # Tekshirish — old_string mavjudmi?
    count = content.count(old_string)
    if count == 0:
        # Ya'ni xatolik — foydalanuvchiga fayl tarkibini ko'rsatamiz
        lines = content.splitlines()
        preview = "\n".join(lines[:20])
        return {
            "ok": False,
            "error": f"old_string not found in {path}",
            "hint": f"File has {len(lines)} lines. First 20 lines:\n{preview}",
        }

    if count > 1 and not replace_all:
        return {
            "ok": False,
            "error": f"old_string found {count} times. Use replace_all=true or provide more context.",
        }

    # O'zgartirish
    if replace_all:
        new_content = content.replace(old_string, new_string)
    else:
        new_content = content.replace(old_string, new_string, 1)

    # Saqlash
    write_result = ws.write(path, new_content)
    if not write_result["ok"]:
        return write_result

    # Diff yaratish
    diff = list(difflib.unified_diff(
        content.splitlines(), new_content.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="",
    ))

    return {
        "ok": True,
        "path": path,
        "replacements": count if replace_all else 1,
        "diff": diff[:60],
        "changed": True,
    }


def _search_in_file(ws, args: dict) -> dict:
    """Fayl ichida matn qidirish — regex support bilan.

    args: {path, pattern, use_regex}
    """
    path = args.get("path", "")
    pattern = args.get("pattern", "")
    use_regex = args.get("use_regex", False)

    if not pattern:
        return {"ok": False, "error": "pattern is required"}

    current = ws.read(path)
    if not current["ok"]:
        return current

    content = current["content"]
    lines = content.splitlines()
    matches = []

    for i, line in enumerate(lines, 1):
        if use_regex:
            if re.search(pattern, line):
                matches.append({"line": i, "text": line.rstrip()})
        else:
            if pattern in line:
                matches.append({"line": i, "text": line.rstrip()})

    return {
        "ok": True,
        "path": path,
        "pattern": pattern,
        "matches": len(matches),
        "results": matches[:50],
    }


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

EDIT_FILE = Tool(
    name="edit_file",
    description=(
        "Edit a file by replacing an exact string with new content. "
        "Provides precise, targeted edits without rewriting the entire file. "
        "Preserves indentation. Use for small to medium edits."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "old_string", "type": "string", "description": "Exact string to replace (including indentation)"},
        {"name": "new_string", "type": "string", "description": "New string to insert"},
        {"name": "replace_all", "type": "boolean", "description": "Replace all occurrences (default: false)", "default": False},
    ],
    fn=_edit_file,
)

SEARCH_IN_FILE = Tool(
    name="search_in_file",
    description=(
        "Search for text patterns within a file. Supports exact match and regex. "
        "Returns matching lines with line numbers."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File path relative to workspace root"},
        {"name": "pattern", "type": "string", "description": "Search pattern (text or regex)"},
        {"name": "use_regex", "type": "boolean", "description": "Use regex matching (default: false)", "default": False},
    ],
    fn=_search_in_file,
)


def _grep(ws, args: dict) -> dict:
    """Barcha fayllarda matn qidirish — grep kabi.

    args: {pattern, path, include, use_regex, max_results}
    """
    import subprocess
    pattern = args.get("pattern", "")
    search_path = args.get("path", ".")
    include = args.get("include", "")
    use_regex = args.get("use_regex", False)
    max_results = int(args.get("max_results", 50))

    if not pattern:
        return {"ok": False, "error": "pattern is required"}

    # ripgrep bo'lsa ishlatamiz
    cmd = ["rg", "--no-heading", "-n"]
    if not use_regex:
        cmd.append("-F")
    if include:
        cmd.extend(["-g", include])
    cmd.extend(["--max-count", "5", pattern, search_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        matches = []
        for line in lines[:max_results]:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "text": parts[2][:200],
                })
        return {
            "ok": True,
            "pattern": pattern,
            "matches": len(matches),
            "results": matches,
        }
    except FileNotFoundError:
        # ripgrep yo'q — os.walk bilan qidiramiz
        return _grep_fallback(ws, pattern, search_path, include, use_regex, max_results)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Search timed out"}


def _grep_fallback(ws, pattern: str, search_path: str, include: str,
                   use_regex: bool, max_results: int) -> dict:
    """Ripgrep yo'qsa fallback."""
    import re as _re
    root = ws.root
    matches = []
    for dirpath, _, filenames in os.walk(os.path.join(root, search_path)):
        for fname in filenames:
            if include and not fname.endswith(include.replace("*", "")):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if use_regex:
                            if _re.search(pattern, line):
                                matches.append({
                                    "file": os.path.relpath(fpath, root),
                                    "line": i,
                                    "text": line.rstrip()[:200],
                                })
                        else:
                            if pattern in line:
                                matches.append({
                                    "file": os.path.relpath(fpath, root),
                                    "line": i,
                                    "text": line.rstrip()[:200],
                                })
                        if len(matches) >= max_results:
                            break
            except Exception:
                continue
            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break
    return {
        "ok": True,
        "pattern": pattern,
        "matches": len(matches),
        "results": matches,
    }


def _glob(ws, args: dict) -> dict:
    """Fayl pattern matching — glob syntax.

    args: {pattern, path}
    """
    import glob as _glob
    pattern = args.get("pattern", "")
    search_path = args.get("path", ".")

    if not pattern:
        return {"ok": False, "error": "pattern is required"}

    root = ws.root
    full_pattern = os.path.join(root, search_path, pattern)
    files = _glob.glob(full_pattern, recursive=True)

    results = []
    for f in files[:100]:
        rel = os.path.relpath(f, root)
        results.append({
            "path": rel,
            "is_dir": os.path.isdir(f),
            "size": os.path.getsize(f) if os.path.isfile(f) else 0,
        })

    return {
        "ok": True,
        "pattern": pattern,
        "matches": len(results),
        "results": results,
    }


GREP = Tool(
    name="grep",
    description=(
        "Search for text patterns across all files in the workspace. "
        "Supports exact match and regex. Returns file, line number, and matching text."
    ),
    parameters=[
        {"name": "pattern", "type": "string", "description": "Search pattern"},
        {"name": "path", "type": "string", "description": "Directory to search (default: workspace root)", "default": "."},
        {"name": "include", "type": "string", "description": "File filter (e.g., '*.py', '*.js')", "default": ""},
        {"name": "use_regex", "type": "boolean", "description": "Use regex matching (default: false)", "default": False},
        {"name": "max_results", "type": "integer", "description": "Maximum results to return", "default": 50},
    ],
    fn=_grep,
)

GLOB = Tool(
    name="glob",
    description=(
        "Find files matching a glob pattern (e.g., '**/*.py', 'src/**/*.ts'). "
        "Returns file paths, sizes, and types."
    ),
    parameters=[
        {"name": "pattern", "type": "string", "description": "Glob pattern"},
        {"name": "path", "type": "string", "description": "Directory to search (default: workspace root)", "default": "."},
    ],
    fn=_glob,
)
