"""
Git MCP server (Layer 1 - Core).

Thin wrapper around the git CLI. Requires git to be on PATH (Git for
Windows works fine here -- no WSL needed).

Run standalone for debugging:
    python -m igris.mcp_servers.git_server
"""
from __future__ import annotations

import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("git")
GIT_TIMEOUT_SECONDS = 10


def _git(*args: str, cwd: str = ".") -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except FileNotFoundError:
        return "ERROR: git not found on PATH"
    except subprocess.TimeoutExpired:
        return f"ERROR: git command timed out after {GIT_TIMEOUT_SECONDS}s"
    if result.returncode != 0 and not result.stdout:
        return f"ERROR: {result.stderr.strip()}"
    return result.stdout.strip() or result.stderr.strip() or "(no output)"


@mcp.tool()
def git_status() -> str:
    """Show working tree status (short form)."""
    return _git("status", "--short", "--branch")


@mcp.tool()
def git_diff(staged: bool = False, path: str = "") -> str:
    """Show diff of unstaged (or staged) changes, optionally scoped to a path."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if path:
        args.append("--")
        args.append(path)
    return _git(*args)


@mcp.tool()
def git_log(max_count: int = 10) -> str:
    """Show recent commit history, one line per commit."""
    return _git("log", f"-{max_count}", "--oneline", "--decorate")


@mcp.tool()
def git_commit(message: str, add_all: bool = True) -> str:
    """Stage and commit changes with the given message."""
    if add_all:
        add_result = _git("add", "-A")
        if add_result.startswith("ERROR"):
            return add_result
    return _git("commit", "-m", message)


@mcp.tool()
def git_current_branch() -> str:
    """Return the name of the currently checked-out branch."""
    return _git("rev-parse", "--abbrev-ref", "HEAD")


if __name__ == "__main__":
    mcp.run()
