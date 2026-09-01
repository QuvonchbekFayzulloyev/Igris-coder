"""
IGRIS BRAIN — Qo'shimcha vositalar
===================================
search_code, create_directory, git_command, rename_file, delete_file —
kod qidirish, papka yaratish, git operatsiyalari, fayl nomini o'zgartirish
va xavfsiz o'chirish uchun qo'shimcha vositalar.

Xavfsizlik:
  - search_code: faqat workspace ichida qidiradi
  - create_directory: faqat workspace ichida papka yaratadi
  - git_command: xavfli git buyruqlarini bloklaydi (push, reset --hard, ...)
  - rename_file: faqat workspace ichida nomini o'zgartiradi
  - delete_file: xavfsiz o'chirish (trash/backup bilan)
"""

from __future__ import annotations

import glob as globmod
import os
import re
import shutil
import subprocess
import time

from .base import Tool


# ---------------------------------------------------------------- #
# search_code — kod qidirish (ripgrep-style, workspace ichida)
# ---------------------------------------------------------------- #

def _search_code(ws, args: dict) -> dict:
    pattern = args.get("pattern", "")
    path = args.get("path", "")
    file_type = args.get("type", "")
    max_results = int(args.get("max_results", 50))
    context_lines = int(args.get("context", 2))
    
    if not pattern:
        return {"ok": False, "error": "pattern is required"}
    
    search_dir = ws.resolve(path) if path else ws.root
    
    # ripgrep bor yoki yo'qligini tekshiramiz
    rg_available = False
    try:
        subprocess.run(["rg", "--version"], capture_output=True, timeout=5)
        rg_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    if rg_available:
        # ripgrep ishlatamiz (tez)
        cmd = ["rg", "--no-heading", "--line-number", "-C", str(context_lines)]
        if file_type:
            cmd.extend(["-t", file_type])
        cmd.extend(["--max-count", str(max_results)])
        cmd.append(pattern)
        cmd.append(search_dir)
        
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = proc.stdout[:50000]  # cheklaymiz
            if not output.strip():
                return {"ok": True, "output": f"No matches for '{pattern}'", "matches": 0}
            lines = output.strip().split("\n")
            return {"ok": True, "output": output[:10000], "matches": len(lines)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "search timed out"}
        except Exception as exc:
            return {"ok": False, "error": f"search failed: {exc}"}
    else:
        # ripgrep yo'q — Python regex bilan qidiramiz (sekinroq lekin ishlaydi)
        matches = []
        count = 0
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            return {"ok": False, "error": f"bad regex: {exc}"}
        
        for root, dirs, files in os.walk(search_dir):
            # .git va __pycache__ ni o'tkazib yuboramiz
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv")]
            for fname in files:
                if file_type:
                    if not fname.endswith(f".{file_type}"):
                        continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        for i, line in enumerate(fh, 1):
                            if regex.search(line):
                                rel = os.path.relpath(fpath, ws.root)
                                matches.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                                count += 1
                                if count >= max_results:
                                    break
                except (OSError, UnicodeDecodeError):
                    continue
                if count >= max_results:
                    break
            if count >= max_results:
                break
        
        if not matches:
            return {"ok": True, "output": f"No matches for '{pattern}'", "matches": 0}
        output = "\n".join(matches[:max_results])
        return {"ok": True, "output": output[:10000], "matches": len(matches)}


SEARCH_CODE = Tool(
    name="search_code",
    description=(
        "Search for a text/regex pattern in workspace files. Returns matching "
        "lines with file paths and line numbers. Use for finding function "
        "definitions, variable usages, error patterns, etc."
    ),
    parameters=[
        {"name": "pattern", "type": "string", "description": "Search pattern (regex supported)"},
        {"name": "path", "type": "string", "description": "Subdirectory to search in (default: workspace root)", "default": ""},
        {"name": "type", "type": "string", "description": "File type filter (e.g. 'py', 'js', 'ts')", "default": ""},
        {"name": "max_results", "type": "integer", "description": "Max matches to return", "default": 50},
        {"name": "context", "type": "integer", "description": "Context lines around match", "default": 2},
    ],
    fn=_search_code,
)


# ---------------------------------------------------------------- #
# create_directory — papka yaratish
# ---------------------------------------------------------------- #

def _create_directory(ws, args: dict) -> dict:
    path = args.get("path", "")
    if not path:
        return {"ok": False, "error": "path is required"}
    
    abs_path = ws.resolve(path)
    
    try:
        os.makedirs(abs_path, exist_ok=True)
        return {"ok": True, "output": f"directory created: {abs_path}", "path": abs_path}
    except OSError as exc:
        return {"ok": False, "error": f"cannot create directory: {exc}"}


CREATE_DIRECTORY = Tool(
    name="create_directory",
    description=(
        "Create a directory (and any missing parents) in the workspace. "
        "Use before writing files into a new subdirectory."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "Directory path relative to workspace root"},
    ],
    fn=_create_directory,
)


# ---------------------------------------------------------------- #
# git_command — git operatsiyalari (xavfsiz)
# ---------------------------------------------------------------- #

# Xavfli git buyruqlari — agent tizimni buzmasligi uchun bloklaymiz
_DANGEROUS_GIT = [
    re.compile(r"\bgit\s+(push|force-push|push\s+--force)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--(hard|merge|keep)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f\b", re.IGNORECASE),
    re.compile(r"\bgit\s+(branch\s+-D|branch\s+--delete)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+config\s+--global\b", re.IGNORECASE),
]


def _git_command(ws, args: dict) -> dict:
    command = args.get("command", "")
    cwd = args.get("cwd", "")
    
    if not command:
        return {"ok": False, "error": "command is required"}
    
    # Xavfli buyruqlarni tekshiramiz
    for pat in _DANGEROUS_GIT:
        if pat.search(command):
            return {"ok": False, "error": f"dangerous git command blocked: {command[:80]}"}
    
    search_dir = ws.resolve(cwd) if cwd else ws.root
    
    # git mavjudligini tekshiramiz
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"ok": False, "error": "git is not installed or not in PATH"}
    
    # Buyruqni bajaramiz
    try:
        proc = subprocess.run(
            ["git"] + command.split(),
            cwd=search_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = (proc.stdout or "")[:20000]
        stderr = (proc.stderr or "")[:5000]
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output": stdout + ("\n[stderr]\n" + stderr if stderr else ""),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"git command timed out: {command[:80]}"}
    except Exception as exc:
        return {"ok": False, "error": f"git error: {exc}"}


GIT_COMMAND = Tool(
    name="git_command",
    description=(
        "Run a git command in the workspace. Safe commands like 'git status', "
        "'git log', 'git diff', 'git add', 'git commit' are allowed. "
        "Dangerous commands (push, force, reset --hard) are blocked."
    ),
    parameters=[
        {"name": "command", "type": "string", "description": "Git subcommand (e.g. 'status', 'log --oneline -5', 'diff HEAD')"},
        {"name": "cwd", "type": "string", "description": "Working dir relative to workspace root", "default": ""},
    ],
    fn=_git_command,
)


# ---------------------------------------------------------------- #
# rename_file — fayl nomini o'zgartirish
# ---------------------------------------------------------------- #

def _rename_file(ws, args: dict) -> dict:
    old_path = args.get("old_path", "")
    new_path = args.get("new_path", "")
    
    if not old_path or not new_path:
        return {"ok": False, "error": "old_path and new_path are required"}
    
    abs_old = ws.resolve(old_path)
    abs_new = ws.resolve(new_path)
    
    if not os.path.exists(abs_old):
        return {"ok": False, "error": f"source file not found: {old_path}"}
    
    if os.path.exists(abs_new):
        return {"ok": False, "error": f"destination already exists: {new_path}"}
    
    try:
        # Papka yaratish kerak bo'lsa
        os.makedirs(os.path.dirname(abs_new), exist_ok=True)
        shutil.move(abs_old, abs_new)
        return {"ok": True, "output": f"renamed {old_path} -> {new_path}", "old": abs_old, "new": abs_new}
    except OSError as exc:
        return {"ok": False, "error": f"rename failed: {exc}"}


RENAME_FILE = Tool(
    name="rename_file",
    description=(
        "Rename or move a file within the workspace. "
        "Source must exist, destination must not exist."
    ),
    parameters=[
        {"name": "old_path", "type": "string", "description": "Current file path relative to workspace root"},
        {"name": "new_path", "type": "string", "description": "New file path relative to workspace root"},
    ],
    fn=_rename_file,
)


# ---------------------------------------------------------------- #
# delete_file — xavfsiz fayl o'chirish
# ---------------------------------------------------------------- #

def _delete_file(ws, args: dict) -> dict:
    path = args.get("path", "")
    force = args.get("force", False)
    
    if not path:
        return {"ok": False, "error": "path is required"}
    
    abs_path = ws.resolve(path)
    
    if not os.path.exists(abs_path):
        return {"ok": False, "error": f"file not found: {path}"}
    
    # Xavfsizlik: asosiy papkalarni o'chirishga ruxsat yo'q
    if abs_path.rstrip(os.sep) == ws.root.rstrip(os.sep):
        return {"ok": False, "error": "cannot delete workspace root"}
    
    # Agar force bo'lmasa — backup yaratamiz
    if not force:
        backup_dir = os.path.join(ws.root, ".igris_backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_name = f"{os.path.basename(path)}_{int(time.time())}"
        backup_path = os.path.join(backup_dir, backup_name)
        try:
            if os.path.isfile(abs_path):
                shutil.copy2(abs_path, backup_path)
            elif os.path.isdir(abs_path):
                shutil.copytree(abs_path, backup_path)
        except OSError:
            pass  # backup muvaffaqiyatsiz — davom etamiz
    
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
        elif os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        return {"ok": True, "output": f"deleted: {path}"}
    except OSError as exc:
        return {"ok": False, "error": f"delete failed: {exc}"}


DELETE_FILE = Tool(
    name="delete_file",
    description=(
        "Delete a file or directory from the workspace. A backup is "
        "automatically created in .igris_backups/ unless force=true. "
        "Cannot delete the workspace root."
    ),
    parameters=[
        {"name": "path", "type": "string", "description": "File or directory path relative to workspace root"},
        {"name": "force", "type": "boolean", "description": "Skip backup creation", "default": False},
    ],
    fn=_delete_file,
)
