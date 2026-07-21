"""Workspace-isolated test runner MCP.

Each run copies project source into `.igris/sandbox/runs/<id>/workspace` and
only exposes named test profiles. It is intentionally not described as a VM
or a security boundary for hostile code; it protects the working tree from
normal test writes, generated files, and agent mistakes.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from igris.core.coder_memory import discard_sandbox_path


mcp = FastMCP("sandbox")
ROOT = Path.cwd().resolve()
SANDBOX_ROOT = ROOT / ".igris" / "sandbox"
RUNS_ROOT = SANDBOX_ROOT / "runs"
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".igris", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", "target", ".next", ".turbo",
)


def _safe_run_id(run_id: str) -> str:
    cleaned = run_id.strip().lower()
    if not _RUN_ID_RE.fullmatch(cleaned):
        raise ValueError("run_id must contain only lowercase letters, numbers, _ or -")
    return cleaned


def _run_dir(run_id: str) -> Path:
    safe_id = _safe_run_id(run_id)
    candidate = (RUNS_ROOT / safe_id).resolve()
    if RUNS_ROOT.resolve() not in candidate.parents:
        raise ValueError("run_id escaped the sandbox root")
    return candidate


def _write_manifest(run_dir: Path, data: dict) -> None:
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _profile_command(workspace: Path, profile: str) -> tuple[list[str], Path]:
    profiles: dict[str, tuple[list[str], Path]] = {
        # Reuse the interpreter that launched this MCP server. Resolving a
        # bare `python` from a copied workspace can hit a Windows launcher or
        # a project shim and make an otherwise simple verification hang.
        "python_compile": ([sys.executable, "-m", "compileall", "-q", "."], workspace),
        "python_pytest": ([sys.executable, "-m", "pytest", "tests", "-v"], workspace),
        "desktop_types": (["npx", "tsc", "-b"], workspace / "desktop"),
        "desktop_vitest": (["npx", "vitest", "run"], workspace / "desktop"),
        "desktop_build": (["npx", "vite", "build"], workspace / "desktop"),
        "desktop_bundle": (["npm", "run", "verify:bundle"], workspace / "desktop"),
    }
    if profile not in profiles:
        raise ValueError(f"unknown test profile '{profile}'")
    command, cwd = profiles[profile]
    if not cwd.exists():
        raise ValueError(f"test profile '{profile}' is not applicable: {cwd.relative_to(workspace)} does not exist")
    if profile.startswith("desktop_") and not (cwd / "node_modules").exists():
        raise ValueError(
            "desktop dependencies are intentionally not copied into a sandbox run. "
            "Run sandbox_install_dependencies first, then retry the profile."
        )
    if profile == "python_pytest" and not (workspace / "tests").exists():
        raise ValueError("test profile 'python_pytest' is not applicable: tests/ does not exist")
    return command, cwd


async def _run_process(command: list[str], cwd: Path, timeout_seconds: int) -> tuple[int, str]:
    """Run a sandbox profile without blocking FastMCP's event loop thread."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        # A child test process must never inherit the MCP protocol's stdin.
        # Some CLIs probe/read it during startup, which can deadlock the
        # stdio transport even though the command itself is non-interactive.
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise
    output = (stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")).strip()
    return process.returncode or 0, output


@mcp.tool()
def sandbox_create(label: str = "test") -> str:
    """Create an isolated source copy for a named test run.

    Dependency folders and `.igris` are deliberately excluded. The run is a
    workspace-isolation layer, not a VM for executing untrusted code.
    """
    try:
        slug = re.sub(r"[^a-z0-9_-]+", "-", label.strip().lower()).strip("-") or "test"
        run_id = f"{slug[:48]}-{uuid.uuid4().hex[:8]}"
        run_dir = _run_dir(run_id)
        workspace = run_dir / "workspace"
        RUNS_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT, workspace, ignore=_COPY_IGNORE)
        manifest = {
            "run_id": run_id,
            "created_at": time.time(),
            "source_root": str(ROOT),
            "workspace": str(workspace),
            "status": "created",
            "profiles": [],
        }
        _write_manifest(run_dir, manifest)
        return f"OK: sandbox run '{run_id}' created at {workspace}"
    except (OSError, ValueError, shutil.Error) as exc:
        return f"ERROR: could not create sandbox: {exc}"


@mcp.tool()
async def sandbox_install_dependencies(run_id: str, target: str = "desktop", timeout_seconds: int = 180) -> str:
    """Install declared dependencies inside a sandbox copy (currently target=desktop only)."""
    if target != "desktop":
        return "ERROR: target must be 'desktop'"
    try:
        run_dir = _run_dir(run_id)
        workspace = run_dir / "workspace"
        cwd = workspace / target
        if not (cwd / "package-lock.json").exists():
            return "ERROR: sandbox desktop/package-lock.json is missing"
        exit_code, output = await _run_process(["npm", "ci"], cwd, max(30, min(timeout_seconds, 900)))
        return f"[exit={exit_code}]\n{output[-12_000:]}"
    except asyncio.TimeoutError:
        return f"ERROR: sandbox dependency installation timed out after {timeout_seconds}s"
    except (OSError, ValueError) as exc:
        return f"ERROR: could not install sandbox dependencies: {exc}"


@mcp.tool()
async def sandbox_run_profile(run_id: str, profile: str, timeout_seconds: int = 120) -> str:
    """Run one allow-listed verification profile inside an isolated source copy.

    Profiles: python_compile, python_pytest, desktop_types, desktop_vitest,
    desktop_build, desktop_bundle. No arbitrary shell command is accepted.
    """
    try:
        run_dir = _run_dir(run_id)
        workspace = run_dir / "workspace"
        if not workspace.exists():
            return f"ERROR: sandbox run '{run_id}' does not exist"
        command, cwd = _profile_command(workspace, profile)
        exit_code, output = await _run_process(command, cwd, max(5, min(timeout_seconds, 900)))
        log_path = run_dir / f"{profile}.log"
        log_path.write_text(output, encoding="utf-8")
        manifest = _load_manifest(run_dir)
        profiles = manifest.setdefault("profiles", [])
        profiles.append({"profile": profile, "exit_code": exit_code, "finished_at": time.time(), "log": log_path.name})
        manifest["status"] = "passed" if exit_code == 0 else "failed"
        _write_manifest(run_dir, manifest)
        return f"[profile={profile} exit={exit_code}]\n{output[-16_000:]}"
    except asyncio.TimeoutError:
        return f"ERROR: sandbox profile '{profile}' timed out after {timeout_seconds}s"
    except (OSError, ValueError) as exc:
        return f"ERROR: could not run sandbox profile: {exc}"


@mcp.tool()
def sandbox_report(run_id: str) -> str:
    """Return the isolated run manifest and names of its test logs."""
    try:
        run_dir = _run_dir(run_id)
        if not run_dir.exists():
            return f"ERROR: sandbox run '{run_id}' does not exist"
        manifest = _load_manifest(run_dir)
        manifest["logs"] = sorted(path.name for path in run_dir.glob("*.log"))
        return json.dumps(manifest, ensure_ascii=False, indent=2)
    except (OSError, ValueError) as exc:
        return f"ERROR: could not read sandbox report: {exc}"


@mcp.tool()
def sandbox_discard(run_id: str, confirm: bool = False) -> str:
    """Delete one isolated test run. Requires confirm=true."""
    if not confirm:
        return "REFUSED: pass confirm=true to delete a sandbox run."
    try:
        run_dir = _run_dir(run_id)
        if not run_dir.exists():
            return f"ERROR: sandbox run '{run_id}' does not exist"
        discard_sandbox_path(run_dir, RUNS_ROOT)
        return f"OK: discarded sandbox run '{run_id}'"
    except (OSError, ValueError) as exc:
        return f"ERROR: could not discard sandbox run: {exc}"


if __name__ == "__main__":
    mcp.run()
