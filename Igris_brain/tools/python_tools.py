"""
IGRIS BRAIN — Python bajarish vositası
======================================
python_exec — berilgan Python kodni alohida subprocess'da bajaradi,
stdout/stderr ni qaytaradi.

Xavfsizlik:
  - alohida subprocess (agent jarayoni bilan aralashmaydi)
  - timeout (default 20s, max 60s)
  - cwd workspace root
  - chiqish cheklangan
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap

from .base import Tool

# Dp4 (qisman yaxshilandi): python_exec "sandbox" deya atalgan, lekin to'liq
# sandbox emas (faqat subprocess + cwd + timeout). Xavfli tizim chaqiruvlarini
# kod bajarilishdan OLDI bloklaymiz — agent snippet'i tashqariga chiqa olmaydi.
_DANGEROUS_CALLS = [
    # Protsess/yangi buyruq bajarish
    r"\b(subprocess|asyncio\.create_subprocess|multiprocessing)\b",
    r"\b(?:os|subprocess)\.(?:popen|system|kill|exec)\s*\(",
    # Tarmoq (tashqariga chiqish)
    r"\bsocket\.\w+",
    r"\brequests?\.(?:get|post|put|delete|request)\s*\(",
    r"\burllib\.(?:request|urlopen)",
    r"\b(?:urllib3|httpx)\.\w+",
    # Rekursiv/destruktiv fayl amallari + tizim boshqaruvi
    r"\b(?:shutil\.rmtree|shutil\.move|shutil\.copy)\b",
    r"\bos\.(?:remove|unlink|rmdir)\s*\(",
    # Faqat TO'PLAM darajasidagi exec/eval (re.compile() kabi zararsiz
    # chaqiruvlarni bloklamaydi — `compile` avval `re.`/`pathlib.` kabi prefiks
    # bilan kelishini istisno qilamiz).
    r"(?:^|[^\w.])(?:exec|eval)\s*\(",
    r"\bctypes\.",
    r"\b__import__\s*\(",
]
_DANGEROUS_RE = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS_CALLS]


def _blocked_by_sandbox(code: str) -> str:
    """Xavfli chaqiruv topilsa sabab matni qaytaradi, aks holda ""."""
    for pat in _DANGEROUS_RE:
        if pat.search(code):
            return f"code blocked by sandbox deny-list: {pat.pattern[:60]}"
    return ""

_CODE_TEMPLATE = """\
# IGRIS python_exec sandbox
import sys, io
_IGRIS_SOURCE = %r
try:
    exec(compile(_IGRIS_SOURCE, "<igris>", "exec"))
except SystemExit:
    pass
except Exception as e:
    print("ERROR: %%s: %%s" %% (type(e).__name__, e), file=sys.stderr)
    raise SystemExit(1)
"""


def _python_exec(ws, args: dict) -> dict:
    code = args.get("code", "")
    timeout = min(float(args.get("timeout", 20)), 60.0)
    max_output = int(args.get("max_output", 10_000))

    if not code or not isinstance(code, str):
        return {"ok": False, "error": "code is required"}

    # Dp4 (qisman): xavfli tizim/tarmoq chaqiruvlari bajarilishdan oldin bloklanadi
    blocked = _blocked_by_sandbox(code)
    if blocked:
        return {"ok": False, "error": blocked}

    source = textwrap.dedent(_CODE_TEMPLATE) % code

    try:
        proc = subprocess.run(
            [sys.executable, "-c", source],
            cwd=ws.root,
            capture_output=True,
            text=True,
            timeout=timeout,
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
        return {"ok": False, "error": f"python_exec timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"os error: {exc}"}


PYTHON_EXEC = Tool(
    name="python_exec",
    description=(
        "Execute Python code in a sandboxed subprocess and return its stdout/stderr. "
        "Use to run snippets, verify algorithms, or test small logic."
    ),
    parameters=[
        {"name": "code", "type": "string", "description": "Python code to execute"},
        {"name": "timeout", "type": "integer", "description": "Timeout in seconds (max 60)", "default": 20},
    ],
    fn=_python_exec,
)
