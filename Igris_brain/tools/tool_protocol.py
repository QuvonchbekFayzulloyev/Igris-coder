"""
Roadmap v4 Phase B1 — TOOL PROTOCOL QOLDIQLARI (§7)
====================================================
Mavjud poydevor (Phase 1'da qilingan): ToolMeta (side_effect/timeout/
precondition/postcondition), ToolError {error, code, recoverable}.

Bu modul QOLGAN qoldiqlarni yopadi:
  1. RETRY POLICY — tool turi bo'yicha max retry (read:1, write:2, exec:2,
     web:1) — deterministik jadval; executor `_call_with_retry` bilan mos
  2. OUTPUT SCHEMA — har tool uchun kutilgan natija kalitlari/teskari tekshiruv
     (ok/error/... majburiy; write tool'larda `path` bo'lishi kerak va h.k.)
  3. WRITE POST-VERIFY — write tool'dan keyin diskda HAQIQATAN yozilganini
     tekshirish (§7 "verification": tool ok=true'ga ishonib bo'lmaydi — §29)

Hammasi deterministik (LLM yo'q) va fail-safe.
"""
from __future__ import annotations

import os
from typing import Optional

__all__ = [
    "retry_policy", "max_retries_for", "output_schema_for",
    "validate_output", "verify_write_on_disk",
]

# ---------------------------------------------------------------------- #
# 1) RETRY POLICY (§7 "retry rules")
# ---------------------------------------------------------------------- #

# side_effect -> max retry soni (v4 reja jadvalidan)
_POLICY: dict[str, int] = {
    "read_only": 1,
    "write": 2,
    "unsafe": 2,
    "destructive": 0,   # destructive hech qachon avtomatik qayta bajarilmaydi
}

# Tool nomi bo'yicha aniq qoidalar (jadvaldan ustun)
_TOOL_OVERRIDES: dict[str, int] = {
    "web_fetch": 1,
    "web_search_image": 1,
    "read_file": 1,
    "list_files": 1,
    "search_code": 1,
    "grep": 1,
    "glob": 1,
    "search_in_file": 1,
    "todowrite": 1,
    "question": 1,
    "lsp_definition": 1,
    "lsp_references": 1,
    "lsp_hover": 1,
    "lsp_completion": 1,
    "lsp_diagnostics": 1,
    "lsp_status": 1,
    "write_file": 2,
    "apply_patch": 2,
    "edit_file": 2,
    "rename_file": 2,
    "create_directory": 2,
    "run_command": 2,
    "python_exec": 2,
    "git_command": 2,
    "delete_file": 0,
}

# Qaysi xato kodlari qayta urinishga loyiq (deterministik)
RETRYABLE_CODES = {4, 5}          # timeout, internal
NON_RETRYABLE_CODES = {1, 2, 3}   # unknown_tool, invalid_args, denied


def retry_policy(tool_name: str = "", side_effect: str = "") -> dict:
    """Tool uchun retry siyosati: {max_retries, retryable_codes}."""
    if tool_name in _TOOL_OVERRIDES:
        mr = _TOOL_OVERRIDES[tool_name]
    else:
        mr = _POLICY.get(side_effect, 1)
    return {"max_retries": mr, "retryable_codes": set(RETRYABLE_CODES)}


def max_retries_for(tool_name: str = "", side_effect: str = "") -> int:
    return retry_policy(tool_name, side_effect)["max_retries"]


def is_retryable(result: dict) -> bool:
    """Tool natijasi qayta urinishga loyiqmi (xato kodiga qarab)."""
    if result.get("ok"):
        return False
    return result.get("code") in RETRYABLE_CODES


# ---------------------------------------------------------------------- #
# 2) OUTPUT SCHEMA (§7 "output schema")
# ---------------------------------------------------------------------- #

# Har tool uchun kutilgan output maydonlari (majburiy + ixtiyoriy)
_OUTPUT_SCHEMAS: dict[str, dict] = {
    "read_file": {"required": ["ok"], "on_ok": ["content"]},
    "write_file": {"required": ["ok"], "on_ok": ["path"]},
    "apply_patch": {"required": ["ok"], "on_ok": ["path"]},
    "list_files": {"required": ["ok"], "on_ok": ["items"]},
    "search_code": {"required": ["ok"], "on_ok": ["matches"]},
    "run_command": {"required": ["ok"], "on_ok": ["output"]},
    "python_exec": {"required": ["ok"], "on_ok": ["output"]},
    "git_command": {"required": ["ok"], "on_ok": []},
    "web_fetch": {"required": ["ok"], "on_ok": ["content"]},
    "web_search_image": {"required": ["ok"], "on_ok": ["path"]},
    "create_directory": {"required": ["ok"], "on_ok": ["path"]},
    "rename_file": {"required": ["ok"], "on_ok": []},
    "delete_file": {"required": ["ok"], "on_ok": []},
}


def output_schema_for(tool_name: str) -> Optional[dict]:
    return _OUTPUT_SCHEMAS.get(tool_name)


def validate_output(tool_name: str, result: dict) -> tuple:
    """Tool natijasi output schema'ga mosmi?

    Qoidalar:
      - `ok` maydoni MAJBURIY (har natijada)
      - ok=True bo'lsa — on_ok maydonlari ham bo'lishi kerak
      - ok=False bo'lsa — `error` majburiy (§7 error format)
    Qaytadi: (ok, note) — ok: True/False (None ishlatilmaydi: schema yo'q = True).
    """
    schema = _OUTPUT_SCHEMAS.get(tool_name)
    if schema is None:
        return True, "no output schema (skipped)"
    res = dict(result or {})
    if "ok" not in res:
        return False, "output missing required field 'ok'"
    if res.get("ok"):
        missing = [k for k in schema.get("on_ok", []) if k not in res]
        if missing:
            return False, f"ok=True but missing fields: {missing}"
        return True, "output schema ok"
    if not res.get("error"):
        return False, "ok=False but no 'error' message"
    return True, "error output ok"


# ---------------------------------------------------------------------- #
# 3) WRITE POST-VERIFY (§7 "verification" + §29 golden rule)
# ---------------------------------------------------------------------- #

def verify_write_on_disk(workspace_root: str, tool_name: str,
                         args: dict, result: dict) -> tuple:
    """Write/patch tool'dan keyin diskda HAQIQATAN yozilganini tekshiradi.

    Qoidalar:
      - write_file: fayl mavjud + size > 0 + (agar content berilgan bo'lsa —
        diskdagi kontent kutilgan bilan bir xil (ixtiyoriy tekshiruv))
      - apply_patch: patch'dagi path mavjud
      - rename_file: yangi nom mavjud
      - create_directory: papka mavjud
      - boshqa tool'lar → None (tekshiruv yo'q, neytral)
    Qaytadi: (ok, note) — ok: True/False/None.
    """
    tool = (tool_name or "").lower()
    args = dict(args or {})
    res = dict(result or {})
    if tool in ("write_file", "apply_patch", "web_search_image"):
        if not res.get("ok"):
            return None, "tool failed — disk tekshiruviga ehtiyoj yo'q"
        path = str(args.get("path") or res.get("path") or "")
        if not path:
            return None, "no path to verify"
        full = os.path.join(workspace_root, path.lstrip("/\\"))
        if not os.path.isfile(full):
            return False, f"disk verify FAILED: {path} not written"
        if os.path.getsize(full) <= 0:
            return False, f"disk verify FAILED: {path} is empty"
        content = args.get("content")
        if tool == "write_file" and isinstance(content, str) and content:
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    disk = fh.read()
                if disk != content:
                    return False, f"disk verify FAILED: {path} content mismatch"
            except OSError as exc:
                return None, f"cannot read back: {exc}"
        return True, f"disk verify ok: {path}"
    if tool == "create_directory":
        if not res.get("ok"):
            return None, "tool failed"
        path = str(args.get("path") or res.get("path") or "")
        if not path:
            return None, "no path to verify"
        full = os.path.join(workspace_root, path.lstrip("/\\"))
        if not os.path.isdir(full):
            return False, f"disk verify FAILED: directory {path} missing"
        return True, f"disk verify ok: {path}/"
    if tool == "rename_file":
        if not res.get("ok"):
            return None, "tool failed"
        new_path = str(args.get("new_path") or args.get("to")
                       or res.get("new_path") or "")
        if not new_path:
            return None, "no target path to verify"
        full = os.path.join(workspace_root, new_path.lstrip("/\\"))
        if not os.path.isfile(full):
            return False, f"disk verify FAILED: {new_path} missing after rename"
        return True, f"disk verify ok: {new_path}"
    return None, "no disk verification for this tool"
