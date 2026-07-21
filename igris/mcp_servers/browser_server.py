"""Local Playwright MCP for user-like browser verification.

The server delegates browser control to the bundled Node runner so Python MCP
startup never depends on a browser. By default only localhost and project-local
file URLs are allowed; callers must explicitly opt into an external URL.
"""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("browser")
ROOT = Path.cwd().resolve()
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY_ROOT / "desktop" / "scripts" / "mcp_browser_runner.mjs"
OUTPUT_ROOT = ROOT / ".igris" / "sandbox" / "browser"
_RUN_NAME_RE = re.compile(r"[^a-z0-9_-]+")


def _is_safe_url(url: str, allow_external: bool) -> bool:
    parsed = urlparse(url)
    if allow_external:
        return parsed.scheme in {"http", "https", "file"}
    if parsed.scheme == "file":
        try:
            path_part = unquote(parsed.path)
            # file:///C:/... is the URI form emitted by pathlib on Windows;
            # the leading slash is not part of the drive-qualified path.
            if re.match(r"^/[A-Za-z]:/", path_part):
                path_part = path_part[1:]
            local_path = Path(path_part).resolve()
        except OSError:
            return False
        return ROOT == local_path or ROOT in local_path.parents
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def _run_runner(arguments: list[str], timeout_seconds: int) -> str:
    if not RUNNER.exists():
        return f"ERROR: Playwright runner is missing: {RUNNER}"
    try:
        result = subprocess.run(
            ["node", str(RUNNER), *arguments],
            capture_output=True,
            text=True,
            timeout=max(5, min(timeout_seconds, 180)),
        )
    except FileNotFoundError:
        return "ERROR: Node.js is not installed or not on PATH; install Node before using the browser MCP"
    except subprocess.TimeoutExpired:
        return f"ERROR: Playwright runner timed out after {timeout_seconds}s"
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0 and not output:
        return "ERROR: Playwright runner failed without diagnostic output"
    return output


@mcp.tool()
def browser_check(timeout_seconds: int = 30) -> str:
    """Check whether the bundled Playwright package and Chromium browser can launch."""
    return _run_runner(["--check"], timeout_seconds)


@mcp.tool()
def browser_user_journey(
    url: str,
    actions_json: str,
    name: str = "journey",
    timeout_seconds: int = 45,
    allow_external: bool = False,
) -> str:
    """Run user-like Playwright actions against a local app and save screenshots.

    actions_json is a JSON array. Supported actions: click, fill, press,
    expect_visible, expect_text, expect_url, wait_for, screenshot. Default
    targets are localhost or project-local file URLs; set allow_external only
    for a deliberate external test target.
    """
    try:
        if not _is_safe_url(url, allow_external):
            return "ERROR: URL is not a permitted local/project target; pass allow_external=true only for a deliberate external target"
        actions = json.loads(actions_json)
        if not isinstance(actions, list):
            return "ERROR: actions_json must decode to an array"
        if len(actions) > 50:
            return "ERROR: a browser journey may contain at most 50 actions"
        if not all(isinstance(action, dict) for action in actions):
            return "ERROR: every browser action must be an object"

        safe_name = _RUN_NAME_RE.sub("-", name.strip().lower()).strip("-") or "journey"
        output_dir = OUTPUT_ROOT / f"{safe_name[:48]}-{uuid.uuid4().hex[:8]}"
        output_dir.mkdir(parents=True, exist_ok=False)
        result = _run_runner(
            [
                "--url", url,
                "--actions", json.dumps(actions, ensure_ascii=False),
                "--out", str(output_dir),
                "--timeout", str(max(1, min(timeout_seconds, 120))),
            ],
            timeout_seconds + 15,
        )
        if result.startswith("ERROR:"):
            return result
        return f"output_dir={output_dir}\n{result}"
    except json.JSONDecodeError as exc:
        return f"ERROR: actions_json must be a JSON array: {exc.msg}"
    except (OSError, ValueError, TypeError) as exc:
        return f"ERROR: browser journey failed: {exc}"


if __name__ == "__main__":
    mcp.run()
