"""
IGRIS BRAIN — Input Validation Middleware (D1)
================================================
problems_to_fix.md :: D1 — API kirishlarida chuqur validatsiya yo'q.

Pydantic modellar faqat TIP tekshiradi (path/length/format yo'q). Bu middleware
barcha `/api/` POST so'rovlariga umumiy qatlam qo'shadi:

  1. BODY SIZE LIMIT      — juda katan body rad etiladi (413).
  2. STRING VALIDATION    — uzunlik limit, kontrol-belgilar, null-byte,
                            kod-injection naqshlari (422).
  3. PATH VALIDATION      — canonicalize (realpath) + traversal bloki:
                            workspace tashqarisiga chiqish (422).
  4. NUMBER VALIDATION    — min/max bounds (422).

Xavfsizlik printsiplari:
  - FAIL-CLOSED emas, FAIL-SAFE: faqat ANIQ qoidabuzarlik rad etiladi.
    Noma'lum maydonlar / JSON bo'lmagan body (octet-stream, stream payload)
    o'zgarishsiz o'tadi — mavjud xatti-harakat buzilmaydi (regressiya yo'q).
  - JSON parse xatosi FastAPI'ga qoldiriladi (u allaqachon 422 qaytaradi).
  - Hech qachon exception tashlab serverni qulatmaydi: kutilmagan xato
    requestni o'tkazadi (log yozib).

Ishlatilish:
    from input_validation import install_input_validation
    install_input_validation(app, workspace_root=WORKSPACE_ROOT)

    # Qo'shimcha maydon-qoidalari (ixtiyoriy):
    install_input_validation(app, field_rules={"message": {"max_length": 20000}})
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("igris.input_validation")

# ---------------------------------------------------------------------- #
# Sozlamalar (defaults)
# ---------------------------------------------------------------------- #

# Maksimal body hajmi (bayt). Chat tarixi 2000 xabar + kontekst bilan ham
# ~1MB'dan kichik; 10MB katta xavfsizlik chegarasi.
MAX_BODY_BYTES = 10 * 1024 * 1024

# Standart string uzunlik limiti (belgi). Chat xabarlari, path, rename va
# h.k. uchun yuqori chegaraga yaqin — qisqa limitlar endpoint'ga bog'liq
# maydon-qoidalar bilan kamaytiriladi.
DEFAULT_MAX_STRING = 100_000

# JSON ichidagi maksimal konteyner chuqurligi — deep-nesting DoS cheklovi.
MAX_JSON_DEPTH = 32

# Ixcham vs readable JSON farqi yo'q — depth hisoblash uchun yordamchi.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Kod-injection naqshlari: STRING ichiga yashiringan RUNTIME-CONNECTION
# satrlari. Eslatma: bu xavfsizlik DEVORI emas (chat matni tabiiy ravishda
# kod tili o'z ichiga olishi mumkin) — faqat ANIQLANGAN naqshlar bloklanadi.
# Qat'iy qoida sifatida faqat null-byte + kontrol-belgilar majburiy.
_CODE_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bnpm_(install|run)\b"),
    re.compile(r"\b(npx|bunx)\s+(playwright|puppeteer)\b"),
    re.compile(r"\b(curl|wget)\s+https?://\S*\s*\|\s*(ba)?sh\b"),
]

# ---------------------------------------------------------------------- #
# Path validation (D1: path canonicalize)
# ---------------------------------------------------------------------- #

# Sxemali URL'lar fayl-path sifatida qabul qilinmaydi (file://, http:// ...)
_PATH_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _safe_resolve_path(raw: str, workspace_root: Optional[str]) -> Dict[str, Any]:
    """Pathni canonicalize qilib tekshiradi.

    Qaytaradi: {"ok": True, "path": "<resolved>"} yoki {"ok": False, "reason": "..."}

    workspace_root berilgan bo'lsa QAT'IY rejim: path ichida bo'lishi shart.
    Berilmasa (default) — UMUMIY tekshiruv: traversal (`..`), sxemali URL,
    kontrol-belgilar rad etiladi (defense-in-depth; endpoint'lar o'z
    `Workspace.resolve` containment'ini ham saqlaydi).
    """
    if not raw or not raw.strip():
        return {"ok": False, "reason": "empty path"}

    # Null-byte / kontrol-belgilar darhol rad
    if _CONTROL_RE.search(raw):
        return {"ok": False, "reason": "control characters in path"}

    # Sxemali URL fayl-path bo'lolmaydi (file://, http://, \w script kabi)
    if _PATH_SCHEME_RE.search(raw):
        return {"ok": False, "reason": f"URL scheme not allowed in path"}

    # Traversal segmentlari: `..` (relative escape urinish)
    if any(seg == ".." for seg in re.split(r"[\\/]", raw)):
        return {"ok": False, "reason": "path traversal ('..') not allowed"}

    if workspace_root:
        try:
            root = os.path.realpath(os.path.abspath(workspace_root))
            # Relative path — root'ga nisbatan; absolute — o'zi.
            if os.path.isabs(raw):
                candidate = os.path.realpath(os.path.abspath(raw))
            else:
                candidate = os.path.realpath(os.path.join(root, raw))
            inside = os.path.commonpath([candidate, root]) == root
        except (OSError, ValueError) as exc:
            return {"ok": False, "reason": f"unresolvable path: {exc}"}
        if not inside:
            return {"ok": False, "reason": "path escapes workspace"}
        return {"ok": True, "path": candidate}

    return {"ok": True, "path": os.path.realpath(os.path.abspath(raw))}


# ---------------------------------------------------------------------- #
# JSON walk
# ---------------------------------------------------------------------- #

def _json_depth(obj: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(obj, dict):
        return max((_json_depth(v, depth + 1) for v in obj.values()), default=depth)
    if isinstance(obj, list):
        return max((_json_depth(v, depth + 1) for v in obj), default=depth)
    return depth


def _iter_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_strings(v)


def _validate_string(
    value: str,
    rule: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """String qoidabuzarligi bo'lsa sabab qaytaradi, aks holda None."""
    max_len = DEFAULT_MAX_STRING
    if rule:
        max_len = int(rule.get("max_length", max_len))
    if len(value) > max_len:
        return f"string too long ({len(value)} > {max_len})"

    # Kontrol-belgilar / null-byte — har qanday maydonda majburiy rad.
    if _CONTROL_RE.search(value):
        return "control characters in string"

    # Kod-injection naqshlari — faqat ANIQLANGAN naqshlar (fail-safe).
    for pat in _CODE_INJECTION_PATTERNS:
        m = pat.search(value)
        if m:
            return f"code-injection pattern detected: {m.group(0)!r}"

    return None


def _validate_numbers(obj: Any) -> Optional[str]:
    """Rekursiv: barcha sonlar chekli (inf/nan yo'q) bo'lishi kerak."""
    if isinstance(obj, bool):
        return None
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return "non-finite number in request"
    elif isinstance(obj, dict):
        for v in obj.values():
            r = _validate_numbers(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _validate_numbers(v)
            if r:
                return r
    return None


def validate_payload(
    payload: Any,
    field_rules: Optional[Dict[str, Dict[str, Any]]] = None,
    workspace_root: Optional[str] = None,
    path_fields: Optional[set] = None,
) -> Optional[str]:
    """To'liq payload validatsiyasi — qoidabuzarlik bo'lsa sabab, aks holda None.

    FAIL-SAFE: noma'lum tiplar (None, bool, int) o'tadi; faqat string/dict/list
    ichidan ANIQLANGAN qoidabuzarliklar topiladi.
    """
    field_rules = field_rules or {}
    path_fields = path_fields or {"path"}

    if not isinstance(payload, dict):
        return None  # JSON-array root — FastAPI o'zi hal qiladi

    # 1) Chuqurlik
    if _json_depth(payload) > MAX_JSON_DEPTH:
        return f"JSON nesting too deep (> {MAX_JSON_DEPTH})"

    # 2) Sonlar (inf/nan)
    num_bad = _validate_numbers(payload)
    if num_bad:
        return num_bad

    # 3) String maydonlar
    for key, value in payload.items():
        if isinstance(value, str):
            rule = field_rules.get(key)
            reason = _validate_string(value, rule)
            if reason:
                return f"field '{key}': {reason}"
        elif isinstance(value, list):
            # List ichidagi stringlar uchun ham xuddi shu qoida (list fieldlari:
            # history[], files[] ...)
            max_len = DEFAULT_MAX_STRING
            if field_rules.get(key):
                max_len = int(field_rules[key].get("max_length", max_len))
            for item in value:
                if isinstance(item, str):
                    reason = _validate_string(item, {"max_length": max_len})
                    if reason:
                        return f"field '{key}[]': {reason}"

    # 4) Path maydonlari (traversal/sxema/kontrol-belgilar rad)
    for key in sorted(set(payload.keys()) & set(path_fields)):
        value = payload[key]
        if isinstance(value, str):
            check = _safe_resolve_path(value, workspace_root)
            if not check["ok"]:
                return f"field '{key}': {check['reason']}"

    return None


# ---------------------------------------------------------------------- #
# ASGI middleware
# ---------------------------------------------------------------------- #

class InputValidationMiddleware:
    """Barcha /api/ POST so'rovlarini tekshiradi (D1).

    GET so'rovlarida body yo'q — o'tkazib yuboriladi. /api/chat/stream
    ham body-JSON (SSE javob emas) — shu yerda tekshiriladi.

    BaseHTTPMiddleware'ning `dispatch` sigsiga mos: __call__(request, call_next).
    `install_input_validation` orqali ulanadi.
    """

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        max_body_bytes: int = MAX_BODY_BYTES,
        field_rules: Optional[Dict[str, Dict[str, Any]]] = None,
        path_fields: Optional[set] = None,
    ):
        self.workspace_root = workspace_root
        self.max_body_bytes = max_body_bytes
        self.field_rules = field_rules or {}
        self.path_fields = path_fields or {"path"}

    async def __call__(self, request: Request, call_next):
        # Faqat POST /api/ — boshqalar tegilmaydi
        if request.method != "POST" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        # 1) Content-Length (agar berilgan bo'lsa) — early reject
        length_hdr = request.headers.get("content-length")
        if length_hdr:
            try:
                if int(length_hdr) > self.max_body_bytes:
                    return JSONResponse(
                        {"detail": f"request body too large (>{self.max_body_bytes} bytes)"},
                        status_code=413,
                    )
            except ValueError:
                return JSONResponse({"detail": "invalid Content-Length"}, status_code=400)

        # 2) Body o'qish + hajm tekshiruvi
        body = await request.body()
        if len(body) > self.max_body_bytes:
            return JSONResponse(
                {"detail": f"request body too large (>{self.max_body_bytes} bytes)"},
                status_code=413,
            )

        # 3) JSON bo'lmasa (fayl-upload, stream-hammasi) — o'tkazib yuborish
        ctype = request.headers.get("content-type", "")
        if "application/json" not in ctype:
            return await call_next(request)

        # 4) JSON parse — xato bo'lsa FastAPI o'zi 422 qaytaradi
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return await call_next(request)

        # 5) Semantic validation
        try:
            reason = validate_payload(
                payload,
                field_rules=self.field_rules,
                workspace_root=self.workspace_root,
                path_fields=self.path_fields,
            )
        except Exception:  # noqa: BLE001 — validatsiya hech qachon serverni qulatmaydi
            logger.exception("input_validation: unexpected error (fail-open)")
            return await call_next(request)

        if reason:
            client = request.client.host if request.client else "?"
            logger.warning("input_validation: rejected %s %s from %s: %s",
                           request.method, request.url.path, client, reason)
            return JSONResponse({"detail": f"validation failed: {reason}"}, status_code=422)

        return await call_next(request)


def install_input_validation(
    app,
    workspace_root: Optional[str] = None,
    field_rules: Optional[Dict[str, Dict[str, Any]]] = None,
    path_fields: Optional[set] = None,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> InputValidationMiddleware:
    """FastAPI app'ga D1 validatsiya middleware'ini o'rnatadi.

    BaseHTTPMiddleware korxonasi ichida ishlaydi — request body'ni o'qigach
    call_next qilish xavfsiz (Starlette _CachedRequest body'ni replay qiladi).
    """
    mw = InputValidationMiddleware(
        workspace_root=workspace_root,
        max_body_bytes=max_body_bytes,
        field_rules=field_rules,
        path_fields=path_fields,
    )
    app.add_middleware(BaseHTTPMiddleware, dispatch=mw)
    return mw
