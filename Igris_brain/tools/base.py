"""
IGRIS BRAIN — Tool asosiy klassi
================================
Har bir vosita: name, description, parameters, fn(workspace, args).

Phase 1 (§7 Tool Protocol v2): har bir tool endi TOOL META bilan:
  - side_effect : read_only | write | unsafe | destructive
  - timeout_s   : standart timeout (default 30s)
  - permission  : auto | confirm | deny
  - precondition / postcondition validatorlar
Har bir xato TOOL ERROR formatida: {error, code, recoverable}.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

# Side-effect kategoriyalari (audit §7.1 jadvali)
SIDE_EFFECT_READ_ONLY = "read_only"
SIDE_EFFECT_WRITE = "write"
SIDE_EFFECT_UNSAFE = "unsafe"
SIDE_EFFECT_DESTRUCTIVE = "destructive"
SIDE_EFFECTS = {SIDE_EFFECT_READ_ONLY, SIDE_EFFECT_WRITE, SIDE_EFFECT_UNSAFE,
                SIDE_EFFECT_DESTRUCTIVE}

# Permission darajalari
PERMISSION_AUTO = "auto"        # avtomatik bajarish
PERMISSION_CONFIRM = "confirm"  # user tasdig'i kerak (destructive)
PERMISSION_DENY = "deny"        # umuman chaqirilmaydi


@dataclass
class ToolError(Exception):
    """Standart tool xato formati (audit §7.3): {error, code, recoverable}.

    Kodlar:
      1 = unknown_tool, 2 = invalid_args, 3 = denied,
      4 = timeout, 5 = internal
    """
    error: str
    code: int = 5
    recoverable: bool = True

    def __str__(self) -> str:
        return f"[{self.code}] {self.error} (recoverable={self.recoverable})"

    def to_dict(self) -> dict:
        return {"error": self.error, "code": self.code,
                "recoverable": self.recoverable}


# Phase 4 (§11): ErrorType enum — executor darajasida xato TASniflash
# (recovery strategiya tanlash uchun deterministik kalit).
class ErrorType:
    """Executor darajasidagi xato turlari (§11 qadam 1: Error types enum).

    ToolError.code -> ErrorType mapping:
      1 unknown_tool -> UNKNOWN_TOOL, 2 invalid_args -> INVALID_ARGS,
      3 denied -> DENIED, 4 timeout -> TIMEOUT, 5 internal -> INTERNAL.
    LLM transport xatolari LLM_ERROR; bekor qilingan run CANCELLED.
    """
    TOOL_ERROR = "tool_error"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGS = "invalid_args"
    DENIED = "denied"
    TIMEOUT = "timeout"
    INTERNAL = "internal"
    LLM_ERROR = "llm_error"
    CANCELLED = "cancelled"

    @classmethod
    def from_result(cls, out: dict) -> str:
        """Tool result dict -> ErrorType (ok=True bo'lsa "")."""
        if out.get("ok"):
            return ""
        code = out.get("code")
        mapping = {1: cls.UNKNOWN_TOOL, 2: cls.INVALID_ARGS, 3: cls.DENIED,
                   4: cls.TIMEOUT, 5: cls.INTERNAL}
        return mapping.get(code, cls.TOOL_ERROR if code is not None else cls.INTERNAL)


def tool_error_result(exc: Exception) -> dict:
    """Exception -> standart result dict (registry.execute formatiga mos)."""
    if isinstance(exc, ToolError):
        return {"ok": False, "error": exc.error, "code": exc.code,
                "recoverable": exc.recoverable}
    return {"ok": False, "error": str(exc), "code": 5, "recoverable": True}


@dataclass
class ToolMeta:
    """Tool shartnomasi (contract) — deterministic kontrol (§17).

    precondition : (args) -> (ok, reason) — bajarilishdan OLDIN
    postcondition: (args, result) -> (ok, reason) — bajarilgandan KEYIN
    """
    side_effect: str = SIDE_EFFECT_READ_ONLY
    timeout_s: float = 30.0
    permission: str = PERMISSION_AUTO
    precondition: Optional[Callable[[dict], tuple[bool, str]]] = None
    postcondition: Optional[Callable[[dict, dict], tuple[bool, str]]] = None


def _validate_args(parameters: list[dict], args: dict) -> tuple[bool, str]:
    """Argument tiplarini JSON-schema'dan deterministik tekshiradi."""
    for p in parameters:
        name = p.get("name")
        if name not in args:
            continue
        val = args[name]
        ptype = (p.get("type") or "string").lower()
        checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
        }
        check = checks.get(ptype)
        if check is not None and not check(val):
            return False, f"arg '{name}' must be {ptype}, got {type(val).__name__}"
    return True, ""


# Tool nomi bo'yicha default meta — audit §7.1 jadvalidan (xavfsiz kategoriyalar)
_DEFAULT_META_OVERRIDES: dict[str, dict] = {
    # read_only
    "read_file":        {"side_effect": "read_only", "timeout_s": 10.0},
    "list_files":       {"side_effect": "read_only", "timeout_s": 10.0},
    "search_code":      {"side_effect": "read_only", "timeout_s": 30.0},
    "web_fetch":        {"side_effect": "read_only", "timeout_s": 15.0},
    # write
    "write_file":       {"side_effect": "write", "timeout_s": 10.0},
    "apply_patch":      {"side_effect": "write", "timeout_s": 10.0},
    "rename_file":      {"side_effect": "write", "timeout_s": 10.0},
    "create_directory": {"side_effect": "write", "timeout_s": 10.0},
    "web_search_image": {"side_effect": "write", "timeout_s": 15.0},
    # unsafe (exec)
    "run_command":      {"side_effect": "unsafe", "timeout_s": 30.0},
    "python_exec":      {"side_effect": "unsafe", "timeout_s": 30.0},
    "git_command":      {"side_effect": "unsafe", "timeout_s": 30.0},
    # destructive
    "delete_file":      {"side_effect": "destructive", "timeout_s": 10.0,
                         "permission": "confirm"},
}


class Tool:
    def __init__(self, name: str, description: str, parameters: list[dict],
                 fn: Callable, required: Optional[list[str]] = None,
                 meta: Optional[ToolMeta] = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        # `default` maydoni bor parametr — IXTIYORIY (Phase 1 tuzatish: avval
        # barcha parametrlar required deb e'lon qilingan edi, holbuki tool'lar
        # args.get(default) bilan ishlaydi. Bu Ollama schema'ni ham to'g'irlaydi).
        self.required = required or [p["name"] for p in parameters
                                     if "default" not in p]
        self.fn = fn
        # ToolMeta: kiritilmagan bo'lsa — nom bo'yicha xavfsiz default (§17)
        if meta is not None:
            m = meta
        elif name in _DEFAULT_META_OVERRIDES:
            m = ToolMeta(**_DEFAULT_META_OVERRIDES[name])
        else:
            m = ToolMeta()
        self.meta = m
        # eski kod uchun qulaylik atributlari
        self.side_effect = m.side_effect
        self.timeout_s = m.timeout_s
        self.permission = m.permission

    def schema(self) -> dict:
        """Flat JSON-schema (name, description, parameters)."""
        props = {p["name"]: {k: v for k, v in p.items() if k != "name"}
                 for p in self.parameters}
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": self.required,
            },
        }

    def ollama_schema(self) -> dict:
        """Ollama `/api/chat` tools API formatida wrapper.

        Ollama quyidagi tuzilmani kutadi:
            {"type": "function", "function": {name, description, parameters}}
        """
        return {"type": "function", "function": self.schema()}

    def _precheck(self, args: dict) -> tuple[bool, str]:
        """Required + tip + precondition validator — deterministic (§17)."""
        missing = [r for r in self.required if r not in (args or {})]
        if missing:
            return False, f"missing required args: {missing}"
        ok, msg = _validate_args(self.parameters, args or {})
        if not ok:
            return ok, msg
        if self.meta.precondition is not None:
            try:
                ok, msg = self.meta.precondition(args or {})
                if not ok:
                    return False, msg or "precondition failed"
            except Exception as exc:   # validator yiqilsa — rad etamiz (fail-safe)
                return False, f"precondition validator error: {exc}"
        return True, ""

    def _postcheck(self, args: dict, result: dict) -> tuple[bool, str]:
        ok, msg = True, ""
        if self.meta.postcondition is not None:
            try:
                ok, msg = self.meta.postcondition(args or {}, result or {})
            except Exception as exc:
                return False, f"postcondition validator error: {exc}"
        return ok, msg

    def execute(self, workspace, args: dict) -> dict:
        """Deterministik bajarish trubasi: precheck -> fn -> postcheck.

        precheck rad etsa: {ok: False, error, code: 2|3} — fn UMUMAN
        chaqirilmaydi (LLM argumetnlariga ishonch yo'q — §17).
        postcondition yiqilsa: result.postcondition_failed qo'shiladi
        (natija saqlanadi, lekin 'yozildi' da'vosi belgilanadi).
        """
        args = dict(args or {})
        ok, msg = self._precheck(args)
        if not ok:
            low = msg.lower()
            denied = "precondition failed" in low or "denied" in low
            return {"ok": False, "error": msg,
                    "code": 3 if denied else 2, "recoverable": True}
        try:
            result = dict(self.fn(workspace, args) or {})
        except ToolError as exc:
            return tool_error_result(exc)
        except Exception as exc:
            return tool_error_result(exc)
        post_ok, post_msg = self._postcheck(args, result)
        if not post_ok:
            result["postcondition_failed"] = post_msg
        return result
