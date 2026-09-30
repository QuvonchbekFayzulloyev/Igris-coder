# -*- coding: utf-8 -*-
"""
Roadmap v3 R1 — REQUIREMENT MATRIX + COMPLETION CONTRACT (§2/§17/§28)
=====================================================================

FINAL RULE (TODO §29): VERIFIED SUCCESS = REALITY + REQUIREMENTS + EVIDENCE.

Bu modul har task uchun:
  1. Task matndan deterministik requirement'lar ajratadi (mandatory/optional)
     — LLM bo'lmasa ham ishlaydi (LLM faqat kengaytma).
  2. Run boshida immutable snapshot yaratadi (JSON) — o'zgartirib bo'lmaydi.
  3. Run oxirida har requirement uchun deterministik tekshiruv (fs/python)
     o'tkazadi: PASS/FAIL/UNKNOWN + REAL evidence (fs holati).
  4. Formal completion status qaytaradi:
       all mandatory PASS  -> complete
       FAIL bo'lsa        -> partial (bor) / failed (hech narsa yo'q)
       UNKNOWN bo'lsa     -> blocked
  5. `complete` faqat evidence bilan qaytadi (§28 Completion Contract).

Determinizm: fs tekshiruvlari va status hisobi 100% deterministik —
LLM decision'iga ishonch talab qilinmaydi (§29 Golden Rule).
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

# ------------------------------------------------------------------ #
# Konstantalar
# ------------------------------------------------------------------ #

# Task matnda qidiriladigan fayl kengaytmalari (executor._requested_files bilan mos)
FILE_EXT_RE = re.compile(
    r"[\w./\\\-]+\.(?:py|txt|md|json|png|jpg|jpeg|svg|html|css|js|csv|log|webm)\b",
    re.IGNORECASE,
)

# Check holatlari (§17): har requirement PASS/FAIL/UNKNOWN
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"

# Completion contract statuslari (§28)
CONTRACT_COMPLETE = "complete"
CONTRACT_PARTIAL = "partial"
CONTRACT_FAILED = "failed"
CONTRACT_BLOCKED = "blocked"

# Check turlari
CHECK_FILE_EXISTS = "file_exists"
CHECK_FILE_CONTAINS = "file_contains"
CHECK_FILE_ABSENT = "file_absent"
CHECK_FOLDER_EXISTS = "folder_exists"
CHECK_FILE_NOT_EMPTY = "file_not_empty"

# Bu fe'llar/lar requirement mavjudligini ko'rsatadi (uz/en) — mandatory
_MANDATORY_HINTS = (
    "yarat", "yaratish", "yoz", "yozish", "almashtir", "o'chir", "ochir",
    "joylashtir", "ko'chir", "kochir", "saqla", "saqlash", "tuzat",
    "create", "write", "replace", "delete", "remove", "move", "save", "fix",
    "hisobla", "hisoblash", "ishga tushir", "run",
)
# Bu iboralar ixtiyoriylikni ko'rsatadi — optional
_OPTIONAL_HINTS = (
    "agar kerak", "imkon bo'lsa", "ixtiyoriy", "bo'lsa yaxshi",
    "optionally", "if needed", "if possible", "nice to have", "mumkin bo'lsa",
)


# ------------------------------------------------------------------ #
# ReqItem — bitta requirement (§2/§17)
# ------------------------------------------------------------------ #

@dataclass
class ReqItem:
    """Bitta user requirement: nima kerak + qanday tekshiriladi.

    kind: mandatory (bajarilishi SHART) | optional (bajarilsa yaxshi)
    check: deterministik tekshiruv turi
    target: fayl path / papka / matn pattern
    evidence: tekshiruvdan keyin to'ldiriladigan REAL fs dalil
    """
    id: str
    text: str
    kind: str = "mandatory"           # mandatory | optional
    check: str = CHECK_FILE_EXISTS
    target: str = ""                  # fayl path yoki contains-pattern
    # --- runtime (snapshot'ga KIRMAYDI) ---
    status: str = STATUS_UNKNOWN
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "kind": self.kind,
            "check": self.check, "target": self.target,
        }

    @classmethod
    def from_dict(cls, obj: dict) -> "ReqItem":
        return cls(
            id=str(obj.get("id") or ""),
            text=str(obj.get("text") or ""),
            kind=str(obj.get("kind") or "mandatory"),
            check=str(obj.get("check") or CHECK_FILE_EXISTS),
            target=str(obj.get("target") or ""),
        )

    def result_dict(self) -> dict:
        """§17 matrix qatori: requirement + expected + actual + status."""
        return {
            "id": self.id, "text": self.text, "kind": self.kind,
            "check": self.check, "target": self.target,
            "status": self.status, "evidence": dict(self.evidence),
        }


# ------------------------------------------------------------------ #
# Extraction — task matndan requirement'lar (deterministik)
# ------------------------------------------------------------------ #

def extract_requirements(task: str) -> list[ReqItem]:
    """Task matndan deterministik requirement'lar ajratadi.

    Strategiya (LLM'siz, §2 explicit requirements):
      1. Taskdagi fayl nomlari topiladi (kengaytma bo'yicha).
      2. Fayl nomi atrofidagi matnda mandatory-hint fe'l bo'lsa —
         mandatory file_exists requirement.
      3. Optional-hint iborasi bo'lsa — optional.
      4. Fayl nomi yo'q, lekin mandatory-hint bor — "deliverable" umumiy
         requirement (file_not_empty check'ga tayyor, target yo'q → UNKNOWN).
    """
    task = task or ""
    items: list[ReqItem] = []
    seen_names: set[str] = set()
    low = task.lower()

    for i, m in enumerate(FILE_EXT_RE.finditer(task)):
        name = m.group(0).strip(".,;:()'\"`").replace("\\", "/")
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        # Hint konteksti: optional-hint FAQAT fayl nomidan OLDIN qidiriladi
        # ("agar kerak bo'lsa log.txt") — aks holda oldingi faylning oynasi
        # keyingisiga yetib qoladi. Action fe'l esa IKKALA tomonda.
        before = low[max(0, m.start() - 40): m.start()]
        around = low[max(0, m.start() - 60): m.end() + 30]
        is_optional = any(h in before for h in _OPTIONAL_HINTS)
        has_action = any(h in around for h in _MANDATORY_HINTS)
        kind = "optional" if is_optional else ("mandatory" if has_action else "mandatory")
        items.append(ReqItem(
            id=f"R{i + 1}",
            text=f"file '{name}' ({kind})",
            kind=kind,
            check=CHECK_FILE_EXISTS,
            target=name,
        ))

    # Fayl nomi yo'q lekin yaratish fe'li bor — umumiy deliverable req
    if not items and any(h in low for h in _MANDATORY_HINTS):
        items.append(ReqItem(
            id="R1",
            text="task deliverable (fayl/natija) yaratilishi kerak",
            kind="mandatory",
            check=CHECK_FILE_NOT_EMPTY,
            target="",
        ))
    return items


# ------------------------------------------------------------------ #
# RequirementSnapshot — immutable (§2)
# ------------------------------------------------------------------ #

class RequirementSnapshot:
    """Run boshida yaratiladigan O'ZGARMAS requirement ro'yxati.

    §2 kafolati: run davomida requirement qo'shib/olib tashlab bo'lmaydi —
    `items` faqat o'qish uchun; tekshiruv natijalari alohida saqlanadi.
    """

    def __init__(self, task: str, items: list[ReqItem]):
        self.task = task
        self.items: tuple[ReqItem, ...] = tuple(items)
        self.created_at = time.time()

    # ---- immutable snapshot (§10 checkpoint'ga yoziladigan shakl) ----
    def to_json(self) -> dict:
        return {
            "task": self.task,
            "created_at": self.created_at,
            "items": [it.to_dict() for it in self.items],
        }

    @classmethod
    def from_json(cls, obj: dict) -> "RequirementSnapshot":
        items = [ReqItem.from_dict(d) for d in (obj.get("items") or [])]
        snap = cls(str(obj.get("task") or ""), items)
        snap.created_at = float(obj.get("created_at") or 0.0)
        return snap

    def mandatory(self) -> list[ReqItem]:
        return [it for it in self.items if it.kind == "mandatory"]


# ------------------------------------------------------------------ #
# Matrix runner — deterministik fs/python checks (§17)
# ------------------------------------------------------------------ #

def _fs_evidence(root: str, path: str) -> dict:
    """Fayl haqida REAL dalil (§13 manifest qismi): exists/size/ba'zi content."""
    full = os.path.join(root, path) if not os.path.isabs(path) else path
    ev: dict = {"path": path}
    if os.path.isfile(full):
        try:
            size = os.path.getsize(full)
            with open(full, "rb") as fh:
                head = fh.read(200)
            ev.update(exists=True, size=size,
                      content_head=head.decode("utf-8", errors="replace")[:120])
        except Exception as exc:
            ev.update(exists=True, read_error=str(exc)[:80])
    elif os.path.isdir(full):
        ev.update(exists=True, is_dir=True)
    else:
        ev.update(exists=False)
    return ev


def check_item(root: str, item: ReqItem) -> tuple[str, dict]:
    """Bitta requirement'ni deterministik tekshiradi.

    Qaytadi: (status, evidence). Fs bilan bevosita ishlaydi —
    LLM javobiga, tool `ok=true`'ga ishonmaydi (§12/§29).
    """
    target = (item.target or "").strip()
    ev = _fs_evidence(root, target) if target else {"path": None}

    if item.check == CHECK_FILE_EXISTS:
        if target:
            ok = bool(ev.get("exists")) and not ev.get("is_dir")
            return (STATUS_PASS if ok else STATUS_FAIL), ev
        return STATUS_UNKNOWN, ev

    if item.check == CHECK_FILE_NOT_EMPTY:
        # Target yo'q bo'lsa — workspace'dagi YARATILGAN fayllar tekshiriladi
        # (target bo'sh: umumiy deliverable). Evidence: eng yangi fayl.
        if target:
            ok = bool(ev.get("exists")) and int(ev.get("size") or 0) > 0
            return (STATUS_PASS if ok else STATUS_FAIL), ev
        try:
            entries = sorted(
                ((f, os.path.getsize(os.path.join(root, f)))
                 for f in os.listdir(root)
                 if os.path.isfile(os.path.join(root, f))),
                key=lambda t: os.path.getmtime(os.path.join(root, t[0])),
            )
        except Exception:
            entries = []
        if entries:
            name, size = entries[-1]
            ev = {"path": name, "size": size, "exists": True}
            return (STATUS_PASS if size > 0 else STATUS_FAIL), ev
        return STATUS_FAIL, {"path": None, "exists": False}

    if item.check == CHECK_FILE_CONTAINS:
        if not target:
            return STATUS_UNKNOWN, ev
        if not ev.get("exists"):
            return STATUS_FAIL, ev
        pattern = getattr(item, "contains", None) or item.text
        try:
            with open(os.path.join(root, target), encoding="utf-8",
                      errors="replace") as fh:
                content = fh.read()
            ok = str(pattern).lower() in content.lower()
            return (STATUS_PASS if ok else STATUS_FAIL), {
                **ev, "pattern": str(pattern)[:80],
                "pattern_found": ok,
            }
        except Exception as exc:
            return STATUS_UNKNOWN, {**ev, "read_error": str(exc)[:80]}

    if item.check == CHECK_FILE_ABSENT:
        ok = not ev.get("exists")
        return (STATUS_PASS if ok else STATUS_FAIL), ev

    if item.check == CHECK_FOLDER_EXISTS:
        ok = bool(ev.get("is_dir"))
        return (STATUS_PASS if ok else STATUS_FAIL), ev

    return STATUS_UNKNOWN, ev


def run_matrix(snapshot: RequirementSnapshot, workspace_root: str) -> dict:
    """Barcha requirement'larni tekshiradi + §17 matrix qaytaradi.

    Snapshot.items O'ZGARMAYDI (immutable kafolat) — natijalar alohida
    `matrix` ro'yxatida qaytadi (status + evidence).
    """
    matrix: list[dict] = []
    for it in snapshot.items:
        status, ev = check_item(workspace_root, it)
        matrix.append({**it.result_dict(), "status": status, "evidence": ev})
    return {
        "workspace_root": workspace_root,
        "checked_at": time.time(),
        "matrix": matrix,
    }


# ------------------------------------------------------------------ #
# Completion contract — formal status (§28)
# ------------------------------------------------------------------ #

def completion_status(matrix: list[dict]) -> str:
    """Matrix natijasidan formal completion status.

    §28 qoidalari:
      barcha mandatory PASS                     -> complete
      mandatory FAIL (lekin ba'zilari PASS)     -> partial
      barcha mandatory FAIL                     -> failed
      mandatory UNKNOWN bor (FAIL yo'q)         -> blocked
      mandatory umuman yo'q                     -> complete (tekshiruv talabi yo'q)
    Optional'lar statusga ta'sir qilmaydi (lekin matrix'da ko'rinadi).
    """
    mand = [r for r in (matrix or []) if r.get("kind") == "mandatory"]
    if not mand:
        return CONTRACT_COMPLETE
    statuses = [str(r.get("status") or STATUS_UNKNOWN) for r in mand]
    if any(s == STATUS_FAIL for s in statuses):
        return CONTRACT_FAILED if all(s == STATUS_FAIL for s in statuses) \
            else CONTRACT_PARTIAL
    if any(s == STATUS_UNKNOWN for s in statuses):
        return CONTRACT_BLOCKED
    return CONTRACT_COMPLETE
