"""
Roadmap v4 Phase B3 — VERIFICATION COMPARISON (§10)
====================================================
v1 §10 qoldiqlari:
  - Expected result mapping — requirement/task → kutilgan natija (formal, LLM'siz)
  - Expected vs Actual comparison — VerificationComparison{match, diff, score}
  - Comparison methods: EXACT (fayl), SEMANTIC (matn), NUMERIC (son)

Falsafa: deterministik; "expected" task matnidAN yoki requirement'dan
chiqariladi; "actual" REAL fs / real tool natijasidan.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
from dataclasses import dataclass, field

__all__ = [
    "ExpectedResult", "VerificationComparison",
    "map_expected_from_task", "compare_expected_actual",
    "COMPARISON_EXACT", "COMPARISON_SEMANTIC", "COMPARISON_NUMERIC",
]

COMPARISON_EXACT = "exact"
COMPARISON_SEMANTIC = "semantic"
COMPARISON_NUMERIC = "numeric"


@dataclass
class ExpectedResult:
    """§10: bir requirement'ning kutilgan natijasi (formal shakl)."""
    kind: str                     # file_exists | file_contains | stdout_equals | stdout_contains | numeric_equals
    target: str = ""              # fayl yo'li yoki bo'sh (stdout uchun)
    value: str = ""               # kutilgan matn/son (str ko'rinishda)
    method: str = COMPARISON_EXACT   # exact | semantic | numeric

    def to_dict(self) -> dict:
        return {"kind": self.kind, "target": self.target,
                "value": self.value, "method": self.method}


@dataclass
class VerificationComparison:
    """§10: expected vs actual — bitta to'liq isbot."""
    match: bool
    score: float                  # 0.0..1.0 (qanchalik yaqin)
    method: str
    diff: str = ""                # farq (qisqa) — ok=False bo'lsa tushuntiradi
    expected: dict = field(default_factory=dict)
    actual: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"match": self.match, "score": round(self.score, 3),
                "method": self.method, "diff": self.diff[:300],
                "expected": self.expected, "actual": self.actual}


# ---------------------------------------------------------------------- #
# EXPECTED MAPPING (task matnidan — deterministik)
# ---------------------------------------------------------------------- #

_NUM_WORDS = {"bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "besh": 5,
              "olti": 6, "yetti": 7, "sakkiz": 8, "to'qqiz": 9, "o'n": 10}


def map_expected_from_task(task: str) -> list:
    """Task matnidAN kutilgan natijalarni chiqaradi (LLM'siz).

    Aniqlanadigan pattern'lar:
      - "create `X`" / "create X file"  → file_exists X (exact)
      - "`X` must contain 'TEXT'" yoki "containing TEXT" → file_contains
      - "print(s) NUMBER" / "prints NUMBER" / "outputs NUMBER" → stdout_equals (numeric)
      - "sum of A and B" → numeric A+B (stdout_equals)
    Qaytadi: [ExpectedResult, ...] (bo'sh — aniq expected chiqarilmadi).
    """
    text = str(task or "")
    low = text.lower()
    expected: list = []

    # 1) fayl yaratish talablari
    for m in re.finditer(r"`([\w\-./]+\.[\w]+)`", text):
        path = m.group(1)
        expected.append(ExpectedResult(kind="file_exists", target=path,
                                       value="", method=COMPARISON_EXACT))

    # 2) "print(s)/output(s) N" — raqamli natija
    m = re.search(r"\b(?:prints?|outputs?|writes?)\s+(-?\d+(?:\.\d+)?)\b", low)
    if m:
        expected.append(ExpectedResult(kind="stdout_equals", target="",
                                       value=m.group(1),
                                       method=COMPARISON_NUMERIC))

    # 3) "sum of A and B" → A+B
    m = re.search(r"\bsum\s+of\s+(-?\d+)\s+and\s+(-?\d+)\b", low)
    if m:
        total = int(m.group(1)) + int(m.group(2))
        expected.append(ExpectedResult(kind="stdout_equals", target="",
                                       value=str(total),
                                       method=COMPARISON_NUMERIC))

    # 4) "containing 'X'" / "contains `X`" — matn bo'lagi
    m = re.search(r"(?:containing|contains?)\s+['\"`]([^'\"`]+)['\"`]", low)
    if m:
        # qaysi faylga tegishli — oxirgi tilga olingan fayl (bor bo'lsa)
        target = expected[-1].target if expected else ""
        expected.append(ExpectedResult(kind="file_contains", target=target,
                                       value=m.group(1),
                                       method=COMPARISON_SEMANTIC))
    return expected


# ---------------------------------------------------------------------- #
# COMPARISON (expected vs actual)
# ---------------------------------------------------------------------- #

def _semantic_similarity(a: str, b: str) -> float:
    """Matn o'xshashligi 0..1 (SequenceMatcher — deterministik)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(),
                                   b.lower().strip()).ratio()


def _short_diff(expected: str, actual: str) -> str:
    """Qisqa unified diff (birinchi 5 qator)."""
    if expected == actual:
        return ""
    d = difflib.unified_diff(expected.splitlines()[:10],
                             actual.splitlines()[:10],
                             fromfile="expected", tofile="actual", lineterm="")
    lines = list(d)[:7]
    return "\n".join(lines)


def compare_expected_actual(expected: ExpectedResult, actual: dict) -> VerificationComparison:
    """Expected natijani real actual bilan solishtiradi.

    actual: {"stdout": str?, "files": {path: content}?, "root": str?}
      - stdout_equals/numeric → actual["stdout"]
      - file_exists/file_contains → actual["files"] yoki actual["root"] dan o'qish
    """
    kind = expected.kind
    method = expected.method

    # --- stdout asosli --- #
    if kind in ("stdout_equals", "stdout_contains"):
        stdout = str((actual or {}).get("stdout") or "")
        if kind == "stdout_contains" or method == COMPARISON_SEMANTIC:
            ok = expected.value.lower() in stdout.lower()
            score = 1.0 if ok else _semantic_similarity(expected.value, stdout)
            return VerificationComparison(
                match=ok, score=score, method=method,
                diff="" if ok else f"expected {expected.value!r} in stdout",
                expected=expected.to_dict(), actual={"stdout": stdout[:200]})
        # exact / numeric
        actual_val = stdout.strip()
        if method == COMPARISON_NUMERIC:
            try:
                ok = abs(float(actual_val) - float(expected.value)) < 1e-9
            except ValueError:
                ok = False
                score = 0.0
            else:
                score = 1.0 if ok else 0.0
            return VerificationComparison(
                match=ok, score=score, method=method,
                diff="" if ok else f"expected {expected.value!r}, got {actual_val!r}",
                expected=expected.to_dict(), actual={"stdout": actual_val[:200]})
        ok = actual_val == expected.value
        score = 1.0 if ok else _semantic_similarity(expected.value, actual_val)
        return VerificationComparison(
            match=ok, score=score, method=method,
            diff=_short_diff(expected.value, actual_val),
            expected=expected.to_dict(), actual={"stdout": actual_val[:200]})

    # --- fayl asosli --- #
    if kind in ("file_exists", "file_contains"):
        files = dict((actual or {}).get("files") or {})
        root = str((actual or {}).get("root") or "")
        content = files.get(expected.target)
        if content is None and root:
            full = os.path.join(root, expected.target.lstrip("/\\"))
            if os.path.isfile(full):
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    content = None
        if kind == "file_exists":
            ok = content is not None and len(content) > 0
            return VerificationComparison(
                match=ok, score=1.0 if ok else 0.0, method=method,
                diff="" if ok else f"file missing or empty: {expected.target}",
                expected=expected.to_dict(),
                actual={"target": expected.target,
                        "exists": content is not None})
        # file_contains
        if content is None:
            return VerificationComparison(
                match=False, score=0.0, method=method,
                diff=f"file missing: {expected.target}",
                expected=expected.to_dict(),
                actual={"target": expected.target, "exists": False})
        ok = str(expected.value).lower() in content.lower()
        score = 1.0 if ok else _semantic_similarity(expected.value, content[:400])
        return VerificationComparison(
            match=ok, score=score, method=method,
            diff="" if ok else f"{expected.value!r} not found in {expected.target}",
            expected=expected.to_dict(),
            actual={"target": expected.target, "bytes": len(content)})

    # noma'lum kind — neytral muvaffaqiyatsizlik (tekshirilmadi deb hisoblanmaydi)
    return VerificationComparison(
        match=False, score=0.0, method=method,
        diff=f"unknown expected kind: {kind}",
        expected=expected.to_dict(), actual={})


def compare_all(expected_list: list, actual: dict) -> dict:
    """Barcha expected'larni solishtiradi → {all_match, score, comparisons}."""
    comps = [compare_expected_actual(e, actual) for e in (expected_list or [])]
    if not comps:
        return {"all_match": True, "score": 1.0, "comparisons": []}
    all_match = all(c.match for c in comps)
    score = sum(c.score for c in comps) / len(comps)
    return {"all_match": all_match, "score": round(score, 3),
            "comparisons": [c.to_dict() for c in comps]}
