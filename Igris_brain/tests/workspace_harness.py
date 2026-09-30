"""
IGRIS BRAIN — Workspace Harness (Roadmap v3 R3, §1)
====================================================
Real task testlari uchun deterministik test muhiti:

  - WorkspaceSnapshot: berilgan papkani to'liq suratga oladi
    (har fayl: relative path + size + mtime + sha256 content hash)
  - diff(): ikki snapshot orasidagi o'zgarishlar
    (created / deleted / modified / unchanged) — §1 "before/after fayl hisobi"
  - WorkspaceHarness: temp workspace + checkpoint_dir yaratadi, test oxirida
    tozalaydi; har snapshot'ni nom bilan saqlaydi (before/after/resume...)

Faqat stdlib. Barcha funksiyalar deterministik — LLM'siz.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except Exception:
        return "unreadable"
    return h.hexdigest()


@dataclass
class FileRecord:
    """Bitta fayl haqida REAL dalil (§13 manifest qismi)."""
    path: str          # relative, '/' separator
    size: int
    mtime: float
    sha256: str

    def to_dict(self) -> dict:
        return {"path": self.path, "size": self.size,
                "mtime": self.mtime, "sha256": self.sha256}


@dataclass
class WorkspaceSnapshot:
    """Workspace'dagi BARCHA fayllar (rekursiv) — moment tasviri."""
    root: str
    files: dict = field(default_factory=dict)   # relpath -> FileRecord
    taken_at: float = 0.0

    def paths(self) -> set:
        return set(self.files.keys())

    def get(self, relpath: str) -> FileRecord:
        return self.files.get(relpath.replace(os.sep, "/"))


def take_snapshot(root: str, max_files: int = 5000,
                  ignore_dirs: tuple = ("_cp", "__pycache__", ".pytest_cache")) -> WorkspaceSnapshot:
    """root ichidagi barcha fayllarni suratga oladi (rekursiv, limit bilan).

    ignore_dirs — test infratuzilmasi (checkpoint saqlash kabi) workspace
    ARTIFACT emas: reality diff'dan chiqariladi.
    """
    import time
    snap = WorkspaceSnapshot(root=root, taken_at=time.time())
    ignored = set(ignore_dirs)
    count = 0
    for dirpath, dirs, filenames in os.walk(root):
        # ignore papkalarni daraxtdan olib tashlash (rekursiv skip)
        dirs[:] = [d for d in dirs if d not in ignored]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                st = os.stat(full)
                rec = FileRecord(path=rel, size=st.st_size,
                                 mtime=st.st_mtime, sha256=_file_hash(full))
            except Exception:
                rec = FileRecord(path=rel, size=-1, mtime=0.0,
                                 sha256="stat_error")
            snap.files[rel] = rec
            count += 1
            if count >= max_files:
                return snap
    return snap


def diff(before: WorkspaceSnapshot, after: WorkspaceSnapshot) -> dict:
    """Iki snapshot orasidagi REAL o'zgarishlar (§1 before/after).

    Qaytaradi:
      created:  [relpath...]  — yangi paydo bo'lganlar
      deleted:  [relpath...]  — yo'qolganlar
      modified: [relpath...]  — sha256 o'zgarganlar (content REAL farq)
      unchanged:[relpath...]  — hash bir xil
      summary:  ixcham sonlar
    """
    b_paths, a_paths = before.paths(), after.paths()
    created = sorted(a_paths - b_paths)
    deleted = sorted(b_paths - a_paths)
    modified, unchanged = [], []
    for p in sorted(b_paths & a_paths):
        if before.files[p].sha256 != after.files[p].sha256:
            modified.append(p)
        else:
            unchanged.append(p)
    return {
        "created": created,
        "deleted": deleted,
        "modified": modified,
        "unchanged": unchanged,
        "summary": {
            "created": len(created), "deleted": len(deleted),
            "modified": len(modified), "unchanged": len(unchanged),
        },
    }


class WorkspaceHarness:
    """R3 testlari uchun izolyatsiyalangan workspace kontekst-menejeri.

    Usage:
        with WorkspaceHarness() as h:
            h.seed({"in/a.txt": "hello"})          # boshlang'ich holat
            before = h.snapshot("before")
            ... run agent ...
            after = h.snapshot("after")
            d = h.diff("before", "after")
    """

    def __init__(self, prefix: str = "igris_r3_"):
        self.prefix = prefix
        self.root = tempfile.mkdtemp(prefix=prefix)
        self.checkpoint_dir = os.path.join(self.root, "_cp")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self._snapshots: dict = {}

    # -- context manager ------------------------------------------------
    def __enter__(self) -> "WorkspaceHarness":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()

    # -- asosiy API -------------------------------------------------------
    def seed(self, files: dict) -> None:
        """Boshlang'ich fayllar yozadi: {relpath: content}.

        content str → UTF-8 matn; bytes → ikkilik rejimda (R4: docx/binary).
        """
        for rel, content in (files or {}).items():
            full = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
            if isinstance(content, (bytes, bytearray)):
                with open(full, "wb") as fh:
                    fh.write(content)
            else:
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(content)

    def path(self, rel: str = "") -> str:
        return os.path.join(self.root, rel) if rel else self.root

    def read(self, rel: str) -> str:
        with open(self.path(rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def exists(self, rel: str) -> bool:
        return os.path.isfile(self.path(rel))

    def snapshot(self, name: str) -> WorkspaceSnapshot:
        snap = take_snapshot(self.root)
        self._snapshots[name] = snap
        return snap

    def get_snapshot(self, name: str) -> WorkspaceSnapshot:
        return self._snapshots.get(name)

    def diff(self, before_name: str, after_name: str) -> dict:
        b = self._snapshots.get(before_name)
        a = self._snapshots.get(after_name)
        if b is None or a is None:
            raise KeyError(f"snapshot '{before_name}' or '{after_name}' not taken")
        return diff(b, a)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
