"""
Roadmap v4 A3 — PIPELINE SAFETY testlari (§8)
==============================================
Qamrov:
  - TypedDict stage input/output shartnomalari
  - InterruptiblePipeline: to'liq run, cancel (checkpoint kept), resume,
    stage xatosi → stopped, checkpoint goal_id mosligi
  - WorkspaceBackup: snapshot/restore (o'zgarish + ortiqcha fayl rollback),
    prune (max_snapshots)

Run: python test_a3_pipeline_safety.py | pytest test_a3_pipeline_safety.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.pipeline_safety import (  # noqa: E402
    StageInput, StageOutput, InterruptiblePipeline, WorkspaceBackup,
)


def _mk_stage(name: str, calls: list, fail: bool = False,
              cancel_event: threading.Event | None = None,
              cancel_on: bool = False):
    def fn(inp: StageInput) -> StageOutput:
        calls.append(name)
        if cancel_on and cancel_event is not None:
            cancel_event.set()
        if fail:
            raise RuntimeError(f"{name} exploded")
        return {"stage": name, "ok": True, "result": {name: True},
                "ts": 0.0, "duration_ms": 0.1}
    return fn


def _mk_pipeline(calls: list, cancel_event=None, fail_stage: str = "",
                 cancel_stage: str = "", tmp_dir: str = "") -> InterruptiblePipeline:
    stages = []
    for name in ("s1", "s2", "s3"):
        fn = _mk_stage(name, calls,
                       fail=(name == fail_stage),
                       cancel_event=cancel_event,
                       cancel_on=(name == cancel_stage))
        stages.append((name, fn))
    cp = os.path.join(tmp_dir, "cp.json") if tmp_dir else ""
    return InterruptiblePipeline(stages, cancel_event=cancel_event,
                                 checkpoint_path=cp)


class TestTypes(unittest.TestCase):
    def test_stage_contracts(self):
        ann = StageInput.__annotations__
        self.assertIn("task", ann)
        self.assertIn("stage", ann)
        self.assertIn("previous", ann)
        out_ann = StageOutput.__annotations__
        self.assertIn("ok", out_ann)
        self.assertIn("result", out_ann)
        self.assertIn("error", out_ann)


class TestInterruptiblePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="igris_a3_")

    def test_full_run_ok(self):
        calls: list = []
        p = _mk_pipeline(calls, tmp_dir=self.tmp)
        res = p.run("task", goal_id="g1")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["stages"], ["s1", "s2", "s3"])
        self.assertEqual(os.path.exists(p.checkpoint_path), False)

    def test_cancel_mid_run_checkpoint_kept(self):
        calls: list = []
        ev = threading.Event()
        p = _mk_pipeline(calls, cancel_event=ev, cancel_stage="s2",
                         tmp_dir=self.tmp)
        res = p.run("task", goal_id="g1")
        self.assertEqual(res["status"], "cancelled")
        self.assertEqual(res["next_stage"], "s3")
        self.assertEqual(res["checkpoint"], "kept")
        self.assertTrue(os.path.isfile(p.checkpoint_path))
        # s1, s2 bajarildi; s3 yo'q
        self.assertEqual(calls, ["s1", "s2"])

    def test_resume_continues_from_checkpoint(self):
        calls: list = []
        ev = threading.Event()
        p = _mk_pipeline(calls, cancel_event=ev, cancel_stage="s2",
                         tmp_dir=self.tmp)
        p.run("task", goal_id="g1")
        calls.clear()
        ev.clear()
        res2 = p.resume("task", goal_id="g1")
        self.assertEqual(res2["status"], "ok")
        self.assertEqual(res2["stages"], ["s3"])   # faqat qolgan bosqich
        self.assertEqual(calls, ["s3"])
        self.assertFalse(os.path.isfile(p.checkpoint_path))

    def test_resume_without_checkpoint_returns_none(self):
        calls: list = []
        p = _mk_pipeline(calls, tmp_dir=self.tmp)
        self.assertIsNone(p.resume("task", goal_id="g1"))

    def test_stage_failure_stops_with_checkpoint(self):
        calls: list = []
        p = _mk_pipeline(calls, fail_stage="s2", tmp_dir=self.tmp)
        res = p.run("task", goal_id="g1")
        self.assertEqual(res["status"], "stopped")
        self.assertEqual(res["error_stage"], "s2")
        self.assertIn("exploded", res["error"])
        self.assertEqual(res["checkpoint"], "kept")

    def test_checkpoint_goal_id_mismatch_ignored(self):
        calls: list = []
        p = _mk_pipeline(calls, tmp_dir=self.tmp)
        p._save_checkpoint("other-goal", 2, {})
        res = p.run("task", goal_id="g1")
        # boshqa goal_id — checkpoint E'TIBOR BERILMAYDI, to'liq run
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["stages"], ["s1", "s2", "s3"])


class TestWorkspaceBackup(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="igris_a3_ws_")

    def _write(self, rel: str, content: str) -> None:
        full = os.path.join(self.ws, rel)
        os.makedirs(os.path.dirname(full) or self.ws, exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    def _read(self, rel: str) -> str:
        with open(os.path.join(self.ws, rel), "r", encoding="utf-8") as fh:
            return fh.read()

    def test_rollback_modified_and_extra(self):
        self._write("a.txt", "original")
        wb = WorkspaceBackup(self.ws)
        snap = wb.snapshot("before")
        # run: o'zgartirish + yangi fayl
        self._write("a.txt", "MODIFIED")
        self._write("extra.txt", "new")
        r = wb.restore(snap)
        self.assertFalse(r["missing_snapshot"])
        self.assertEqual(r["restored"], 1)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(self._read("a.txt"), "original")
        self.assertFalse(os.path.exists(os.path.join(self.ws, "extra.txt")))

    def test_rollback_deleted_file_restored(self):
        self._write("b.txt", "keep me")
        wb = WorkspaceBackup(self.ws)
        snap = wb.snapshot()
        os.remove(os.path.join(self.ws, "b.txt"))
        r = wb.restore(snap)
        self.assertEqual(r["restored"], 1)
        self.assertEqual(self._read("b.txt"), "keep me")

    def test_missing_snapshot_flagged(self):
        wb = WorkspaceBackup(self.ws)
        r = wb.restore("no_such_snapshot")
        self.assertTrue(r["missing_snapshot"])

    def test_prune_keeps_max_snapshots(self):
        import time as _t
        self._write("f.txt", "x")
        wb = WorkspaceBackup(self.ws, max_snapshots=2)
        for i in range(4):
            wb.snapshot(f"s{i}")
            _t.sleep(0.02)   # timestamp farqi uchun
        self.assertEqual(len(wb.list_snapshots()), 2)

    def test_backup_dir_not_backed_up(self):
        self._write("data.txt", "d")
        wb = WorkspaceBackup(self.ws)
        snap1 = wb.snapshot("first")
        wb.snapshot("second")
        # backup papkasi o'zi zaxiraga tushmagan
        for name in wb.list_snapshots():
            self.assertFalse(
                os.path.exists(os.path.join(wb.backup_root, name,
                                            WorkspaceBackup.BACKUP_DIR)))
        self.assertTrue(snap1)


if __name__ == "__main__":
    unittest.main()
