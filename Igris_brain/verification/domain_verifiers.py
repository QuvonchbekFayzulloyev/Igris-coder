"""
Roadmap v3 R4 — DOMAIN VERIFIERS (§13 + §14 + §15 + §16)
=========================================================
Deterministik (LLM'siz) domayn tekshiruvchilari — A1 run-oracle falsafasining
executor darajasidagi davomi: tool natijasiga emas, HAQIQIY artefaktni ko'radi.

  §14 code reality    — .py yozildi → IZOLYATSIYADA ishga tushiriladi,
                        stdout kutilgan qiymat/regex bilan solishtiriladi
  §15 research verify — manba fayl ko'rsatilgan → content SHA-256 hash +
                        min_length evidence; xulosa faylida manba havolasi
                        (path + qisqa hash) borligi tekshiriladi
  §16 document verify — .md → sarlavha tuzilishi (# soni, bo'lim nomlari,
                        min bo'limlar); .csv → tushunarlilik (ustunlar,
                        qatorlar); .json/.html — format tekshiruvi
  §13 file manifest   — kutilgan fayllar: exists + size>0 + encoding (UTF-8
                        bo'laklari) + unexpected katta fayllar haqida hisobot

Falsafa (§29 golden rule): har verifier (ok, note, evidence) qaytaradi.
ok=True → VERIFIED, False → FAILED, None → NEYTRAL (tekshirib bo'lmadi —
muhit/deny-list sabab). Executor status faqat ok=False'da pasayadi.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

__all__ = [
    "verify_code_output", "verify_source_evidence", "verify_document",
    "verify_file_manifest", "run_domain_verifiers",
]


# ---------------------------------------------------------------------- #
# §14 — CODE REALITY: expected output comparison
# ---------------------------------------------------------------------- #

def _run_python_isolated(code: str, timeout: float = 6.0) -> tuple:
    """Python kodini izolyatsiyada ishga tushiradi → (ok, stdout, stderr).

    ok: True (exit 0) | False (fatal) | None (neytral: deny-list/timeout).
    """
    src = str(code or "")
    if not src.strip():
        return None, "", "empty source"
    try:
        from tools.python_tools import _blocked_by_sandbox
        blocked = _blocked_by_sandbox(src)
        if blocked:
            return None, "", blocked
    except Exception:
        pass  # deny-list moduli yo'q — baribir izolyatsiyada ishga tushiramiz
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", src],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                 "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    except OSError:
        return None, "", "os error"
    if proc.returncode != 0:
        return False, proc.stdout or "", proc.stderr or ""
    return True, proc.stdout or "", proc.stderr or ""


def verify_code_output(code: str, expected: str | None = None,
                       pattern: str | None = None,
                       timeout: float = 6.0) -> tuple:
    """§14: kod ishga tushadi va stdout kutilgan natijaga mosmi?

    expected: aniq matn (strip qilib, to'liq stdout'ning bir qismi sifatida);
    pattern:  regex (stdout'da QIDIRILADI — search).
    Birortasi berilishi shart; ikkalasi bo'lsa IKKALASI ham mos kelishi kerak.
    Qaytadi: (ok, note) — ok: True/False/None.
    """
    if expected is None and pattern is None:
        return None, "no expected value or pattern given"
    run_ok, stdout, stderr = _run_python_isolated(code, timeout=timeout)
    if run_ok is None:
        return None, f"neutral ({stderr[:80] or 'cannot run'})"
    if run_ok is False:
        tail = (stderr or "").strip().splitlines()[-1][:120] if (stderr or "").strip() else "non-zero exit"
        return False, f"script crashed: {tail}"
    out = stdout or ""
    if expected is not None and str(expected).strip() not in out:
        return False, f"expected {str(expected).strip()!r} not in stdout (got {out.strip()[:80]!r})"
    if pattern is not None:
        try:
            if not re.search(pattern, out):
                return False, f"pattern /{pattern}/ not found in stdout"
        except re.error:
            return None, f"invalid pattern: {pattern}"
    note = ("expected output matched" if expected is not None
            else f"stdout matched pattern /{pattern}/")
    return True, note


# ---------------------------------------------------------------------- #
# §15 — RESEARCH VERIFY: source evidence (path + content hash)
# ---------------------------------------------------------------------- #

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_source_evidence(root: str, source_path: str,
                           summary_path: str | None = None,
                           min_length: int = 40) -> tuple:
    """§15: manba fayl HAQIQIY va xulosada havola qilinganmi?

    Tekshiruvlar (ketma-ket, birinchisi muvaffaqiyatsizligi → (False, ...)):
      1. manba mavjud + bo'sh emas → SHA-256 hash (evidence)
      2. summary_path berilgan bo'lsa: mavjud + manba nomi/havolasi ichida
      Qaytadi: (ok, note) — ok: True/False/None; note'da hash evidence.
    """
    src = str(source_path or "").strip()
    if not src:
        return None, "no source path given"
    full = os.path.join(root, src)
    if not os.path.isfile(full):
        return False, f"source file missing: {src}"
    try:
        size = os.path.getsize(full)
        if size <= 0:
            return False, f"source file empty: {src}"
        digest = _sha256(full)
    except OSError as exc:
        return None, f"cannot read source: {exc}"

    evidence = {"source": src, "bytes": size, "sha256": digest[:16] + "…"}
    if summary_path:
        sfull = os.path.join(root, str(summary_path))
        if not os.path.isfile(sfull):
            return False, f"summary file missing: {summary_path} (source: {evidence})"
        try:
            with open(sfull, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            return None, f"cannot read summary: {exc}"
        base = os.path.basename(src)
        if base not in content and src not in content:
            return False, f"summary does not reference source {base!r}"
        if len(content.strip()) < min_length:
            return False, f"summary too short ({len(content.strip())} < {min_length})"
        return True, f"source evidence verified: {evidence}"
    return True, f"source evidence collected: {evidence}"


# ---------------------------------------------------------------------- #
# §16 — DOCUMENT VERIFY: md/docx structure
# ---------------------------------------------------------------------- #

def verify_document(root: str, path: str, min_sections: int = 2,
                    required_sections: list | None = None) -> tuple:
    """§16: hujjat HAQIQIY tuzilishga egami?

    .md  — bo'lim sarlavhalari (ATX `#`): min_sections + required_sections
           (qismlar bo'yicha case-insensitive qidiruv);
    .csv — ustunlar + min qatorlar (csv moduli);
    .json — parse bo'ladimi;
    .html — asosiy teglar (<html/<body/<head);
    .docx — ZIP imzosi (PK) + word/document.xml mavjudligi.
    Qaytadi: (ok, note) — ok: True/False/None (noma'lum format → None).
    """
    full = os.path.join(root, str(path or ""))
    ext = os.path.splitext(path or "")[1].lower()
    if not os.path.isfile(full):
        return False, f"document missing: {path}"
    try:
        with open(full, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return None, f"cannot read: {exc}"
    if not raw:
        return False, f"document empty: {path}"

    if ext in (".md", ".markdown"):
        text = raw.decode("utf-8", errors="replace")
        heads = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
        if len(heads) < min_sections:
            return False, (f"only {len(heads)} section heading(s) "
                           f"(< {min_sections})")
        if required_sections:
            low = [h.lower() for h in heads]
            missing = [s for s in required_sections
                       if not any(str(s).lower() in h for h in low)]
            if missing:
                return False, f"missing sections: {', '.join(map(str, missing[:4]))}"
        return True, f"document structure ok ({len(heads)} sections)"

    if ext == ".csv":
        import csv
        import io
        try:
            rows = list(csv.reader(io.StringIO(raw.decode("utf-8", errors="replace"))))
        except csv.Error as exc:
            return False, f"csv parse error: {exc}"
        if len(rows) < 2:
            return False, "csv has fewer than 2 rows (header + data)"
        if not rows[0] or not rows[0][0].strip():
            return False, "csv header row empty"
        return True, f"csv ok ({len(rows) - 1} data rows, {len(rows[0])} columns)"

    if ext == ".json":
        try:
            json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            return False, f"invalid json: {str(exc)[:80]}"
        return True, "json parses"

    if ext in (".html", ".htm"):
        text = raw.decode("utf-8", errors="replace").lower()
        if "<html" not in text or "<body" not in text:
            return False, "html missing <html>/<body> tags"
        return True, "html structure ok"

    if ext == ".docx":
        if not raw.startswith(b"PK"):
            return False, "docx: not a ZIP container"
        import zipfile
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                if "word/document.xml" not in zf.namelist():
                    return False, "docx: word/document.xml missing"
        except zipfile.BadZipFile:
            return False, "docx: corrupt zip"
        return True, "docx container ok"

    return None, f"no verifier for extension {ext or '(none)'}"


# ---------------------------------------------------------------------- #
# §13 — FILE MANIFEST: extension/encoding/unexpected
# ---------------------------------------------------------------------- #

_TEXT_EXTS = {".py", ".md", ".txt", ".csv", ".json", ".html", ".htm",
              ".css", ".js", ".ts", ".yaml", ".yml", ".toml", ".ini",
              ".sh", ".bat", ".xml", ".svg"}


def verify_file_manifest(root: str, expected_files: list,
                         max_unexpected: int = 50) -> tuple:
    """§13: kutilgan fayllar manifesti — exists/size/encoding/unexpected.

    Tekshiruvlar:
      1. har kutilgan fayl: mavjud + size > 0
      2. matn fayllari: UTF-8 (yoki ASCII) valid encoding
      3. UNEXPECTED fayllar (kutilmagan, checkpoint `_cp/`'dan tashqari):
         xavfsizlik/ortiqcha-artefakt hisoboti (>= max_unexpected → False)
    Qaytadi: (ok, note) — ok: True/False; note'da manifest xulosasi.
    """
    exp = [str(f).strip().replace("\\", "/") for f in (expected_files or [])
           if str(f).strip()]
    missing, empty, bad_enc = [], [], []
    for rel in exp:
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            missing.append(rel)
            continue
        if os.path.getsize(full) <= 0:
            empty.append(rel)
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext in _TEXT_EXTS:
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    fh.read()
            except UnicodeDecodeError:
                bad_enc.append(rel)
            except OSError:
                pass
    if missing:
        return False, f"manifest missing files: {', '.join(missing[:5])}"
    if empty:
        return False, f"manifest empty files: {', '.join(empty[:5])}"
    if bad_enc:
        return False, f"non-UTF8 text files: {', '.join(bad_enc[:5])}"

    exp_set = {os.path.normpath(e) for e in exp}
    unexpected = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("_cp", ".git")]
        for name in filenames:
            rel = os.path.normpath(os.path.relpath(os.path.join(dirpath, name), root))
            if rel not in exp_set:
                unexpected.append(rel)
    if len(unexpected) >= max_unexpected:
        return False, (f"too many unexpected files: {len(unexpected)} "
                       f"(>= {max_unexpected}) — possible artifact leak")
    note = (f"manifest ok ({len(exp)} expected, {len(unexpected)} unexpected)"
            + (f": {unexpected[:5]}" if unexpected else ""))
    return True, note


# ---------------------------------------------------------------------- #
# Executor integratsiyasi: yozilgan artefaktlarga qarab avtomatik tekshiruv
# ---------------------------------------------------------------------- #

def run_domain_verifiers(root: str, task: str, written_paths: list) -> list:
    """Yozilgan fayllar vazifa matniga qarab domayn verifier'lardan o'tadi.

    Qaytadi: [{domain, method, target, ok, note}, ...] — executor buni
    VerificationLog'ga yozadi. Hech qachon exception otmaydi (fail-safe).
    """
    results: list = []
    low = (task or "").lower()
    for rel in (written_paths or []):
        rel = str(rel).replace("\\", "/")
        ext = os.path.splitext(rel)[1].lower()
        try:
            # §14: python fayllari — har doim run+syntax tekshiruvi
            if ext == ".py":
                try:
                    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
                        code = fh.read()
                except OSError:
                    code = ""
                ok, note = verify_code_output(code, pattern=r".")
                results.append({"domain": "code", "method": "run_output",
                                "target": rel, "ok": ok, "note": note})
            # §16: hujjat fayllari
            elif ext in (".md", ".markdown", ".csv", ".json", ".html", ".htm", ".docx"):
                ok, note = verify_document(root, rel)
                results.append({"domain": "document", "method": "structure",
                                "target": rel, "ok": ok, "note": note})
            # §15: research — taskda 'research/summary/source' bo'lsa
            elif ext == ".txt" and any(w in low for w in
                                       ("research", "summary", "source", "manba")):
                ok, note = verify_source_evidence(root, rel, summary_path=rel)
                results.append({"domain": "research", "method": "source_evidence",
                                "target": rel, "ok": ok, "note": note})
        except Exception as exc:  # fail-safe: verifier yiqilishi run'ni buzmaydi
            results.append({"domain": "unknown", "method": "error",
                            "target": rel, "ok": None,
                            "note": f"verifier error: {exc}"})
    return results
