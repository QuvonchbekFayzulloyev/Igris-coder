"""
IGRIS BRAIN — Terminal vositası
===============================
run_command — subprocess orqali buyruq bajarish.

Xavfsizlik:
  - cwd har doim workspace root ichida
  - timeout (default 30s, max 120s)
  - chiqish hajmi cheklangan (max_output)
  - `shell=True` emas — buyruq array sifatida beriladi
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess

from .base import Tool

# Xavfli buyruq naqshlari — agentning `run_command` orqali tizimni buzishi /
# tashqariga chiqishi bloklanadi (Igris_Memory config'dagi deny-list bilan mos).
DENY_PATTERNS = [
    # Tizimni yo'q qilish / formatlash
    re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+/?\s*(/|\\|\*|~)", re.IGNORECASE),
    re.compile(r"\brm\s+-[a-zA-Z]*rf\b\s+(/|\\|\*)", re.IGNORECASE),
    re.compile(r"\b(rd|rmdir)\s+/?[sS]?\s*(/|\\|\*)", re.IGNORECASE),
    # "format" so'zi juda keng (git format-patch, --format json...) — faqat
    # DISK formatlash naqshlari bloklanadi (C:\\, /dev/, mkfs/fdisk/diskpart).
    re.compile(r"\b(format|mkfs)\s+[a-zA-Z]:\\?", re.IGNORECASE),
    re.compile(r"\bformat\s+/(sd[a-z]|hd[a-z]|nvme[0-9])", re.IGNORECASE),
    re.compile(r"\b(mkfs|fdisk|diskpart|format-volume|clear-disk)\b", re.IGNORECASE),
    re.compile(r"\b(del|erase|rm)\s+/?[a-zA-Z]:\\", re.IGNORECASE),  # C:\ kabi o'chirish
    # Root/imtiyoz ko'tarish + xavfli tizim boshqaruvi
    re.compile(r"\bsudo\s+(rm|shutdown|reboot|halt|poweroff|mkfs|dd|fdisk|kill|pkill)", re.IGNORECASE),
    re.compile(r"\b(shutdown|reboot|halt|poweroff|init\s+0)\b", re.IGNORECASE),
    # Disk bloklariga to'g'ridan-to'g'ri yozish
    re.compile(r"\bdd\s+if=.*\bof=/dev/", re.IGNORECASE),
    re.compile(r">\s*/dev/(sd[a-z]|hd[a-z]|nvme[0-9])", re.IGNORECASE),
    re.compile(r"\bmount\s+.*\s+/(mnt|media)", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\s+(/|\\|~|\$HOME)", re.IGNORECASE),
    # Xavfli PowerShell/Windows buyruqlari
    re.compile(r"\bremove-item\s+-?[a-zA-Z]*recurse[a-zA-Z]*\s+/?\s*[a-zA-Z]:\\", re.IGNORECASE),
    re.compile(r"\breg\s+(delete|add).*\\currentversion\\run", re.IGNORECASE),
]


def _check_deny(cmd: str):
    """Buyruq xavfli naqshga to'g'ri kelsa — matn qaytaradi, aks holda None."""
    for pat in DENY_PATTERNS:
        if pat.search(cmd):
            return f"command blocked by deny-pattern: {pat.pattern[:60]}"
    return None


def _run_command(ws, args: dict) -> dict:
    cmd = args.get("command", "")
    timeout = min(float(args.get("timeout", 30)), 120.0)
    max_output = int(args.get("max_output", 20_000))
    cwd = ws.resolve(args.get("cwd", "")) if args.get("cwd") else ws.root

    if not cmd or not isinstance(cmd, str):
        return {"ok": False, "error": "command is required"}

    # Xavfsizlik: xavfli buyruq naqshlari (rm -rf /, sudo rm, shutdown...)
    denied = _check_deny(cmd)
    if denied:
        return {"ok": False, "error": denied}

    # parse into argv (simple shlex; windows-compatible-ish)
    try:
        argv = shlex.split(cmd, posix=os.name != "nt")
    except ValueError as exc:
        return {"ok": False, "error": f"bad command: {exc}"}

    if not argv:
        return {"ok": False, "error": "empty command"}
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        stdout = (proc.stdout or "")[:max_output]
        stderr = (proc.stderr or "")[:max_output]
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": (stdout + ("\n[stderr]\n" + stderr if stderr else ""))[:max_output],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"command timed out after {timeout}s: {cmd}"}
    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {argv[0]}"}
    except OSError as exc:
        return {"ok": False, "error": f"os error: {exc}"}


RUN_COMMAND = Tool(
    name="run_command",
    description=(
        "Run a shell command in the workspace and return its output. "
        "Use for tests, builds, and any terminal work."
    ),
    parameters=[
        {"name": "command", "type": "string", "description": "Shell command to run"},
        {"name": "cwd", "type": "string", "description": "Working dir relative to workspace root", "default": ""},
        {"name": "timeout", "type": "integer", "description": "Timeout in seconds (max 120)", "default": 30},
    ],
    fn=_run_command,
)
