"""
Filesystem MCP server (Layer 1 - Core).

Exposes file operations as MCP tools over stdio. Paths are resolved
relative to the process's current working directory, which igris always
launches from the project root, so the model never needs an absolute path.

Run standalone for debugging:
    python -m igris.mcp_servers.filesystem_server
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")

ROOT = Path.cwd().resolve()
MAX_READ_BYTES = 400_000  # guard against dumping huge binaries into context


def _safe_path(rel_path: str) -> Path:
    """Resolve rel_path under ROOT, refusing to escape the project root."""
    candidate = (ROOT / rel_path).resolve()
    if ROOT not in candidate.parents and candidate != ROOT:
        raise ValueError(f"Path '{rel_path}' escapes project root, refused.")
    return candidate


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file relative to the project root and return its contents."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: {path} does not exist"
    if p.stat().st_size > MAX_READ_BYTES:
        return f"ERROR: {path} is too large ({p.stat().st_size} bytes) to read whole; use search_files instead"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: {path} is not valid UTF-8 text (binary file?)"


@mcp.tool()
def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """Write (overwrite) a UTF-8 text file relative to the project root."""
    p = _safe_path(path)
    if create_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"OK: wrote {len(content)} chars to {path}"


@mcp.tool()
def list_dir(path: str = ".", max_entries: int = 200) -> str:
    """List files and directories at the given relative path."""
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: {path} does not exist"
    if not p.is_dir():
        return f"ERROR: {path} is not a directory"
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    lines = []
    for e in entries[:max_entries]:
        kind = "dir " if e.is_dir() else "file"
        lines.append(f"{kind}  {e.relative_to(ROOT)}")
    if len(entries) > max_entries:
        lines.append(f"... ({len(entries) - max_entries} more entries truncated)")
    return "\n".join(lines) if lines else "(empty)"


@mcp.tool()
def search_files(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """Recursively glob for files matching a pattern (e.g. '*.py', '**/*.md')."""
    base = _safe_path(path)
    matches = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".igris")]
        for fname in files:
            if fnmatch.fnmatch(fname, pattern):
                rel = Path(root, fname).resolve().relative_to(ROOT)
                matches.append(str(rel))
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    return "\n".join(matches) if matches else "(no matches)"


@mcp.tool()
def rename_or_move(source: str, destination: str) -> str:
    """Rename or move a file/directory within the project root."""
    src = _safe_path(source)
    dst = _safe_path(destination)
    if not src.exists():
        return f"ERROR: {source} does not exist"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return f"OK: moved {source} -> {destination}"


@mcp.tool()
def delete_path(path: str, confirm: bool = False) -> str:
    """Delete a file (not a directory tree). Requires confirm=true as a safety gate."""
    if not confirm:
        return "REFUSED: pass confirm=true to actually delete. This is a safety gate."
    p = _safe_path(path)
    if not p.exists():
        return f"ERROR: {path} does not exist"
    if p.is_dir():
        return f"ERROR: {path} is a directory; delete_path only removes single files"
    p.unlink()
    return f"OK: deleted {path}"


if __name__ == "__main__":
    mcp.run()
