"""
Terminal MCP server (Layer 1 - Core).

Windows-first: defaults to PowerShell (pwsh if present, else powershell.exe),
never shells out to WSL/bash unless the caller explicitly asks for it or the
host OS isn't Windows. This mirrors the project's stated
"Windows-first, never WSL by default" convention.

Run standalone for debugging:
    python -m igris.mcp_servers.terminal_server
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("terminal")

DEFAULT_TIMEOUT = 60


def _resolve_shell(requested: str | None) -> tuple[list[str], str]:
    """Return (command_prefix, shell_name) honoring Windows-first policy."""
    system = platform.system()

    if requested == "wsl":
        # Only ever used if explicitly requested -- never the default.
        return (["wsl.exe", "bash", "-lc"], "wsl-bash")

    if system == "Windows" or requested in ("powershell", "pwsh", "cmd", None):
        if system != "Windows" and requested in ("powershell", "pwsh", "cmd"):
            # Explicit Windows shell requested on a non-Windows host: fall through to bash.
            pass
        elif system == "Windows":
            if requested == "cmd":
                return (["cmd.exe", "/c"], "cmd")
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            shell_name = "pwsh" if (pwsh and pwsh.lower().endswith("pwsh.exe")) else "powershell"
            return ([pwsh or "powershell.exe", "-NoProfile", "-NonInteractive", "-Command"], shell_name)

    # Non-Windows host, or explicit bash-family request.
    return (["bash", "-lc"], "bash")


@mcp.tool()
def run_command(command: str, shell: str = "auto", timeout_seconds: int = DEFAULT_TIMEOUT, cwd: str = ".") -> str:
    """
    Execute a shell command and return combined stdout/stderr + exit code.

    shell: "auto" (Windows-first default), "powershell", "pwsh", "cmd", "bash", or "wsl"
           (wsl is never chosen automatically -- only if you pass it explicitly).
    """
    requested = None if shell == "auto" else shell
    prefix, shell_name = _resolve_shell(requested)

    try:
        result = subprocess.run(
            prefix + [command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return f"ERROR: shell '{shell_name}' not found on this system"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout_seconds}s (shell={shell_name})"

    out = f"[shell={shell_name} exit={result.returncode}]\n"
    if result.stdout:
        out += f"--- stdout ---\n{result.stdout}\n"
    if result.stderr:
        out += f"--- stderr ---\n{result.stderr}\n"
    return out


@mcp.tool()
def which(program: str) -> str:
    """Locate an executable on PATH, Windows-first (checks .exe/.cmd/.ps1 too)."""
    found = shutil.which(program)
    return found or f"'{program}' not found on PATH"


@mcp.tool()
def env_info() -> str:
    """Report host OS, shell preference, and cwd -- useful before choosing a shell."""
    return (
        f"os={platform.system()} release={platform.release()}\n"
        f"cwd={os.getcwd()}\n"
        f"default_shell_policy=windows-first (pwsh/powershell), wsl only if explicitly requested"
    )


if __name__ == "__main__":
    mcp.run()
