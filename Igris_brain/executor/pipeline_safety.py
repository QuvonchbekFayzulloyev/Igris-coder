"""
Roadmap v4 Phase A3 — PIPELINE SAFETY (§8 qoldig'i)
====================================================
v1 §8: input/output types, interruption, cancellation, rollback.

Komponentlar:
  1. TypedDict type-annotations — pipeline bosqichlari (§8 "input/output types")
  2. InterruptiblePipeline — checkpoint nuqtalari bilan bosqichlar ketma-ketligi;
     har bosqich boshida CANCEL tekshiriladi; checkpoint SAQLANADI (resume)
  3. WorkspaceBackup — `.igris_backups/` dan restore (qisman rollback)

Falsafa: deterministik, fail-safe, executor'siz testlanadigan.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from typing import Any, Callable, Optional, TypedDict

__all__ = [
    "StageInput", "StageOutput", "InterruptiblePipeline",
    "WorkspaceBackup",
]


# ---------------------------------------------------------------------- #
# 1) TYPES (§8 "input/output types")
# ---------------------------------------------------------------------- #

class StageInput(TypedDict, total=False):
    """Pipeline bosqichiga kirish (har bosqich uchun umumiy shakl)."""
    task: str            # asl vazifa matni
    stage: str           # bosqich nomi (understand/plan/execute/verify)
    payload: dict        # bosqich-specific ma'lumot
    previous: dict       # oldingi bosqich output'i (zanjir)
    goal_id: str         # run identifikatori


class StageOutput(TypedDict, total=False):
    """Pipeline bosqichidan chiqish."""
    stage: str
    ok: bool
    result: dict         # bosqich natijasi
    error: str           # ok=False bo'lsa sabab
    ts: float            # yakunlanish vaqti
    duration_ms: float


# ---------------------------------------------------------------------- #
# 2) INTERRUPTIBLE PIPELINE
# ---------------------------------------------------------------------- #

class InterruptiblePipeline:
    """Bosqichlar ketma-ketligi: har bosqich boshida cancel tekshiruvi +
    checkpoint (diskka JSON). Cancel bo'lsa — checkpoint SAQLANADI va
    resume() bosqichdan davom etadi.

    stages: [(name, fn), ...] — fn(input: StageInput) -> StageOutput
    checkpoint_path: JSON fayl (bo'sh bo'lsa checkpoint ishlamaydi)
    """

    def __init__(self, stages: list, cancel_event: Optional[threading.Event] = None,
                 checkpoint_path: str = ""):
        self.stages = list(stages or [])
        self.cancel_event = cancel_event or threading.Event()
        self.checkpoint_path = checkpoint_path

    # --- checkpoint (disk) --- #
    def _save_checkpoint(self, goal_id: str, stage_idx: int,
                         last_output: Optional[dict]) -> None:
        if not self.checkpoint_path:
            return
        try:
            os.makedirs(os.path.dirname(self.checkpoint_path)
                        or ".", exist_ok=True)
            data = {
                "goal_id": goal_id,
                "next_stage": stage_idx,
                "last_output": last_output,
                "ts": time.time(),
            }
            tmp = self.checkpoint_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, self.checkpoint_path)   # atomik
        except Exception:
            pass  # fail-safe: checkpoint yozilmasa run davom etadi

    def load_checkpoint(self, goal_id: str) -> Optional[dict]:
        if not self.checkpoint_path or not os.path.isfile(self.checkpoint_path):
            return None
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("goal_id") != goal_id:
                return None
            return data
        except Exception:
            return None

    def clear_checkpoint(self) -> None:
        try:
            if self.checkpoint_path and os.path.isfile(self.checkpoint_path):
                os.remove(self.checkpoint_path)
        except Exception:
            pass

    # --- asosiy run --- #
    def run(self, task: str, goal_id: str = "goal",
            payload: Optional[dict] = None) -> dict:
        """Bosqichlarni bajaradi; cancel → checkpoint + {'status': 'cancelled'}."""
        # RESUME: checkpoint bo'lsa — o'sha bosqichdan davom
        cp = self.load_checkpoint(goal_id)
        start_idx = 0
        previous: dict = {}
        if cp is not None:
            start_idx = min(int(cp.get("next_stage") or 0), len(self.stages))
            previous = dict(cp.get("last_output") or {})

        t0 = time.perf_counter()
        stage_results: list = []
        for i in range(start_idx, len(self.stages)):
            # Cancellation: har bosqich BOSHiDA tekshiriladi (§15)
            if self.cancel_event.is_set():
                self._save_checkpoint(goal_id, i, previous)
                return {
                    "status": "cancelled", "goal_id": goal_id,
                    "completed_stages": [r.get("stage") for r in stage_results],
                    "next_stage": self.stages[i][0],
                    "checkpoint": "kept",
                }
            name, fn = self.stages[i]
            s_in: StageInput = {
                "task": task, "stage": name,
                "payload": dict(payload or {}),
                "previous": previous, "goal_id": goal_id,
            }
            cs = time.perf_counter()
            try:
                s_out: StageOutput = fn(s_in) or {}
            except Exception as exc:
                s_out = {"stage": name, "ok": False, "result": {},
                         "error": f"{type(exc).__name__}: {exc}",
                         "duration_ms": round((time.perf_counter() - cs) * 1000, 1)}
            s_out.setdefault("stage", name)
            s_out.setdefault("ok", True)
            s_out["duration_ms"] = s_out.get("duration_ms") or round(
                (time.perf_counter() - cs) * 1000, 1)
            stage_results.append(s_out)
            if not s_out.get("ok"):
                # bosqich xatosi → checkpoint (shu bosqichdan qayta) + stopped
                self._save_checkpoint(goal_id, i, previous)
                return {
                    "status": "stopped", "goal_id": goal_id,
                    "error_stage": name, "error": s_out.get("error", ""),
                    "completed_stages": [r.get("stage")
                                         for r in stage_results[:-1]],
                    "checkpoint": "kept",
                }
            previous = {**previous, **(s_out.get("result") or {})}

        self.clear_checkpoint()
        return {
            "status": "ok", "goal_id": goal_id,
            "stages": [r.get("stage") for r in stage_results],
            "results": stage_results,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    def resume(self, task: str, goal_id: str = "goal") -> Optional[dict]:
        """Checkpoint'dan davom (cancel_event tozalangach)."""
        if self.load_checkpoint(goal_id) is None:
            return None
        return self.run(task, goal_id=goal_id)


# ---------------------------------------------------------------------- #
# 3) WORKSPACE BACKUP / ROLLBACK (qisman)
# ---------------------------------------------------------------------- #

class WorkspaceBackup:
    """Workspace fayllarini `.igris_backups/` ga zaxiralaydi va tiklaydi.

    Rollback SEMANTIKASI (qisman, §8): run OLDIDAN snapshot olinadi;
    restore o'sha holatga qaytaradi (yangi fayllar o'chiriladi, o'zgargan/
    o'chirilgan fayllar zaxiradan tiklanadi).
    """

    BACKUP_DIR = ".igris_backups"

    def __init__(self, workspace_root: str, max_snapshots: int = 3):
        self.root = os.path.abspath(workspace_root)
        self.max_snapshots = max_snapshots

    @property
    def backup_root(self) -> str:
        return os.path.join(self.root, self.BACKUP_DIR)

    def snapshot(self, label: str = "") -> str:
        """Butun workspace'ni (backup papkasidan tashqari) zaxiralaydi.

        Qaytadi: snapshot ID (restore uchun).
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        snap_id = (label + "_" if label else "") + ts
        dst = os.path.join(self.backup_root, snap_id)
        os.makedirs(dst, exist_ok=True)
        ignore = shutil.ignore_patterns(self.BACKUP_DIR, ".git", "_cp")
        for item in os.listdir(self.root):
            if item == self.BACKUP_DIR:
                continue
            src = os.path.join(self.root, item)
            d = os.path.join(dst, item)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, d, ignore=ignore, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, d)
            except OSError:
                pass
        self._prune()
        return snap_id

    def restore(self, snap_id: str) -> dict:
        """Snapshot holatiga QAYTARISH (qisman rollback).

        - snapshot'da BOR fayl, workspace'da boshqacha/YO'Q → tiklanadi
        - workspace'da ORTIQCHA fayl (snapshot'da yo'q) → o'chiriladi
        Qaytadi: {restored, deleted, missing_snapshot}
        """
        src = os.path.join(self.backup_root, snap_id)
        if not os.path.isdir(src):
            return {"restored": 0, "deleted": 0, "missing_snapshot": True}

        def _rel_files(base: str) -> dict:
            out = {}
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames
                               if d not in (self.BACKUP_DIR, "_cp", ".git")]
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    out[os.path.relpath(full, base)] = full
            return out

        snap_files = _rel_files(src)
        ws_files = _rel_files(self.root)
        restored = deleted = 0
        # 1) tiklash / ustiga yozish
        for rel, full in snap_files.items():
            dst = os.path.join(self.root, rel)
            cur = ws_files.get(rel)
            try:
                if cur is None or not os.path.exists(cur):
                    os.makedirs(os.path.dirname(dst) or self.root,
                                exist_ok=True)
                    shutil.copy2(full, dst)
                    restored += 1
                elif open(cur, "rb").read() != open(full, "rb").read():
                    shutil.copy2(full, dst)
                    restored += 1
            except OSError:
                pass
        # 2) ortiqchalarni o'chirish
        snap_rels = set(snap_files.keys())
        for rel, full in ws_files.items():
            if rel not in snap_rels:
                try:
                    os.remove(full)
                    deleted += 1
                except OSError:
                    pass
        return {"restored": restored, "deleted": deleted,
                "missing_snapshot": False}

    def _prune(self) -> None:
        """Eski snapshot'larni o'chirish (max_snapshots)."""
        try:
            snaps = sorted(os.listdir(self.backup_root))
            extra = snaps[:-self.max_snapshots] if self.max_snapshots else []
            for name in extra:
                shutil.rmtree(os.path.join(self.backup_root, name),
                              ignore_errors=True)
        except OSError:
            pass

    def list_snapshots(self) -> list:
        try:
            return sorted(os.listdir(self.backup_root))
        except OSError:
            return []
