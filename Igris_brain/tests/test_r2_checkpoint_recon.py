"""
Roadmap v3 R2 — Checkpoint Integrity + Reconciliation testlari
===============================================================
Qamrov (§10 + §22 + §23 + §11):
  - checkpoint version maydoni + future-version rad etish
  - corruption detection: buzuk JSON -> .bak fallback
  - requirements snapshot + verifications + action_ids checkpoint'da
  - stale checkpoint: checkpoint'dan keyin tashqi o'zgarish aniqlanadi
  - reconciliation: fayl HAZIR -> skip, fayl YO'QOLGAN -> re-execute
  - merge_skip_with_reconciliation: redo step'lar skip'dan chiqariladi
  - resume_from_checkpoint integratsiya: result["reconciliation"]
  - duplicate protection: action_ids saqlanadi

Run: python test_r2_checkpoint_recon.py   (yoki pytest test_r2_checkpoint_recon.py)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import AgentExecutor  # noqa: E402
from executor import checkpoint_integrity as ci  # noqa: E402


def _mk(tmp: str, name: str, content: str = "x") -> None:
    with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
        fh.write(content)


class TestCheckpointVersioning(unittest.TestCase):
    def test_checkpoint_has_version(self):
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            ex.goal_context = None
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("version test")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = []
            ex._save_checkpoint("version test", [1], "done")
            data = json.load(open(os.path.join(cp_dir, f"exec_{goal.id}.json"),
                                  encoding="utf-8"))
            self.assertEqual(data.get("version"), ex.CHECKPOINT_VERSION)
            self.assertGreater(float(data.get("ts") or 0), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_future_version_rejected(self):
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("future test")
            # Future version bilan checkpoint yozamiz
            path = os.path.join(cp_dir, f"exec_{goal.id}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"version": ex.CHECKPOINT_VERSION + 10,
                           "task": "future test",
                           "goal": goal.to_dict(),
                           "completed_step_ids": [1], "ts": time.time()}, fh)
            self.assertIsNone(ex.load_checkpoint(goal.id))
            # Eski (v1, version maydoni yo'q) checkpoint o'qiladi — backward compat
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"task": "old", "goal": goal.to_dict(),
                           "completed_step_ids": [1], "ts": time.time()}, fh)
            loaded = ex.load_checkpoint(goal.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.get("completed_step_ids"), [1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCorruptionDetection(unittest.TestCase):
    def test_corrupt_json_falls_back_to_bak(self):
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("corruption test")
            path = os.path.join(cp_dir, f"exec_{goal.id}.json")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = []
            # 1) birinchi valid checkpoint (status=partial)
            ex._save_checkpoint("corruption test", [1], "partial")
            # 2) IKKINCHI save — avvalgisi endi .bak ga ko'chadi (R2 har atomik
            #    yozishda .bak yaratadi). Keyin asosiy fayl BUZILADI.
            ex._save_checkpoint("corruption test", [1, 2], "partial")
            self.assertTrue(os.path.exists(path + ".bak"), ".bak yaratilmagan")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"task": "corruption test", "goal": {"id": "goal-xx')
            loaded = ex.load_checkpoint(goal.id)
            self.assertIsNotNone(loaded, ".bak fallback ishlamadi")
            # .bak — birinchi checkpoint holati (har doim ham eng oxirgi emas,
            # lekin VALID — resume mumkin; bu kafolatning o'zi muhim)
            self.assertIn(loaded.get("completed_step_ids"), ([1], [1, 2]))
            self.assertEqual(loaded.get("goal", {}).get("id"), goal.id)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_corrupt_without_bak_returns_none(self):
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal
            goal = Goal.create("no bak test")
            path = os.path.join(cp_dir, f"exec_{goal.id}.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{buzuk")
            self.assertIsNone(ex.load_checkpoint(goal.id))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCheckpointR2Fields(unittest.TestCase):
    def test_requirements_verifications_action_ids_saved(self):
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("r2 fields test")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = [{"action_id": "act-aaa"}, {"action_id": "act-bbb"}]
            # requirement snapshot
            import planning.requirement_matrix as rmx
            ex._req_snapshot = rmx.RequirementSnapshot(
                "r2 fields test", rmx.extract_requirements("create notes_r2.txt"))
            ex._save_checkpoint("r2 fields test", [1], "partial",
                                plan_steps=[{"id": 1, "title": "write notes_r2.txt",
                                             "tools": ["write_file"]}])
            data = json.load(open(os.path.join(cp_dir, f"exec_{goal.id}.json"),
                                  encoding="utf-8"))
            # requirements snapshot saqlangan + round-trip
            self.assertIsInstance(data.get("requirements"), dict)
            snap = rmx.RequirementSnapshot.from_json(data["requirements"])
            self.assertEqual(snap.task, "r2 fields test")
            self.assertTrue(any("notes_r2" in it.target for it in snap.items))
            # plan_steps saqlangan
            self.assertEqual(data.get("plan_steps"),
                             [{"id": 1, "title": "write notes_r2.txt",
                               "tools": ["write_file"]}])
            # action_ids saqlangan
            self.assertEqual(data.get("action_ids"), ["act-aaa", "act-bbb"])
            # verifications ro'yxat (bo'sh ham bo'lsa maydon bor)
            self.assertIsInstance(data.get("verifications"), list)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestStaleness(unittest.TestCase):
    def test_stale_after_external_change(self):
        tmp = tempfile.mkdtemp()
        try:
            _mk(tmp, "a.txt", "old")
            cp = {"ts": time.time()}
            # tashqi o'zgarish checkpoint'dan KEYIN (grace 0.25s dan oshiq kutamiz)
            time.sleep(0.3)
            _mk(tmp, "a.txt", "CHANGED EXTERNALLY")
            self.assertTrue(ci.is_stale(cp, tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_not_stale_when_files_older(self):
        tmp = tempfile.mkdtemp()
        try:
            _mk(tmp, "a.txt", "content")
            old = time.time() - 60
            os.utime(os.path.join(tmp, "a.txt"), (old, old))
            self.assertFalse(ci.is_stale({"ts": time.time()}, tmp))
            # ts yo'q checkpoint — stalelik da'vo qilinmaydi
            self.assertFalse(ci.is_stale({}, tmp))
            self.assertFalse(ci.is_stale(None, tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestReconciliation(unittest.TestCase):
    def _steps(self):
        return [
            {"id": 1, "title": "write file notes.txt", "tools": ["write_file"],
             "tool_calls": [{"tool": "write_file", "args": {"path": "notes.txt"}}]},
            {"id": 2, "title": "read config", "tools": ["read_file"]},
            {"id": 3, "title": "create report.md", "tools": ["write_file"],
             "tool_calls": [{"tool": "write_file", "args": {"path": "report.md"}}]},
        ]

    def test_present_file_skipped_missing_file_redone(self):
        tmp = tempfile.mkdtemp()
        try:
            _mk(tmp, "notes.txt", "hello")
            # report.md YO'Q
            r = ci.reconcile_steps(self._steps(), [1, 2, 3], tmp,
                                   "write notes.txt and report.md")
            self.assertEqual(r["skip_ids"], [1, 2])
            self.assertEqual(r["redo_ids"], [3])
            self.assertEqual(r["missing_files"], {3: ["report.md"]})
            self.assertEqual(r["verified_files"], {1: ["notes.txt"]})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_all_present_all_skip(self):
        tmp = tempfile.mkdtemp()
        try:
            _mk(tmp, "notes.txt")
            _mk(tmp, "report.md")
            r = ci.reconcile_steps(self._steps(), [1, 2, 3], tmp, "")
            self.assertEqual(r["redo_ids"], [])
            self.assertEqual(r["skip_ids"], [1, 2, 3])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_body_file_treated_missing(self):
        """0-bayt fayl — yozilmagan deb hisoblanadi (reality check)."""
        tmp = tempfile.mkdtemp()
        try:
            _mk(tmp, "notes.txt", "")  # bo'sh
            r = ci.reconcile_steps([self._steps()[0]], [1], tmp, "")
            self.assertEqual(r["redo_ids"], [1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_merge_removes_redo_from_skip(self):
        recon = {"reconciled": True, "skip_ids": [1, 2], "redo_ids": [3]}
        skip, rep = ci.merge_skip_with_reconciliation([1, 2, 3], recon)
        self.assertEqual(skip, {1, 2})
        self.assertEqual(rep["checkpoint_skip_original"], [1, 2, 3])

    def test_merge_fail_safe_keeps_checkpoint_skip(self):
        skip, rep = ci.merge_skip_with_reconciliation([1, 2], None)
        self.assertEqual(skip, {1, 2})
        self.assertFalse(rep["reconciled"])


class TestResumeIntegration(unittest.TestCase):
    def test_resume_reports_reconciliation(self):
        """resume_from_checkpoint natijasida reconciliation hisoboti bo'ladi."""
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("write a file recon_notes.txt")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = []
            ex._save_checkpoint(
                "write a file recon_notes.txt", [1], "partial",
                plan_steps=[{"id": 1, "title": "write recon_notes.txt",
                             "tools": ["write_file"]}])
            # Fayl TASHQARIDAN yozilgan (tashqi o'zgarish — §23)
            time.sleep(0.3)  # grace (0.25s) dan oshiq — stale aniqlanadi
            _mk(tmp, "recon_notes.txt", "external content")
            ex2 = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            res = ex2.resume_from_checkpoint(goal.id)
            self.assertIsNotNone(res)
            self.assertIn("reconciliation", res)
            # fayl hazir -> step skip qilinadi (duplicate himoya, §22)
            if res["reconciliation"].get("reconciled"):
                self.assertIn(1, res["reconciliation"]["skip_ids"])
            # stale belgisi: fayl checkpoint'dan keyin yozilgan
            self.assertTrue(res.get("checkpoint_stale"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resume_redo_when_file_missing(self):
        """Fayl checkpoint'dan keyin O'CHIRILGAN — step QAYTA bajariladi."""
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            goal = Goal.create("write a file redo_target.txt")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = []
            # fayl checkpoint paytida HAZIR edi
            _mk(tmp, "redo_target.txt", "was here")
            ex._save_checkpoint(
                "write a file redo_target.txt", [1], "partial",
                plan_steps=[{"id": 1, "title": "write redo_target.txt",
                             "tools": ["write_file"]}])
            # fayl O'CHIRILADI (tashqi o'zgarish)
            os.remove(os.path.join(tmp, "redo_target.txt"))
            ex2 = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            res = ex2.resume_from_checkpoint(goal.id)
            self.assertIsNotNone(res)
            recon = res.get("reconciliation", {})
            if recon.get("reconciled"):
                self.assertIn(1, recon.get("redo_ids", []))
                self.assertEqual(recon.get("missing_files", {}).get(1),
                                 ["redo_target.txt"])
            # fayl QAYTA yozilgan bo'lishi kerak (executor step qayta bajaradi)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "redo_target.txt")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_requirements_restored_from_checkpoint(self):
        """Checkpoint'dagi requirement snapshot resume'da TIKLANADI (R1+R2)."""
        tmp = tempfile.mkdtemp()
        cp_dir = os.path.join(tmp, "cp")
        try:
            ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            from state.goal_model import Goal, GoalContext
            import planning.requirement_matrix as rmx
            goal = Goal.create("create req_snap.txt please")
            ex.goal_context = GoalContext(goal)
            ex._cp_tool_calls = []
            ex._req_snapshot = rmx.RequirementSnapshot(
                "create req_snap.txt please",
                rmx.extract_requirements("create req_snap.txt please"))
            ex._save_checkpoint("create req_snap.txt please", [1], "partial",
                                plan_steps=[{"id": 1, "title": "write req_snap.txt",
                                             "tools": ["write_file"]}])
            ex2 = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
            res = ex2.resume_from_checkpoint(goal.id)
            self.assertIsNotNone(res)
            snap = getattr(ex2, "_req_snapshot", None)
            self.assertIsNotNone(snap)
            self.assertTrue(any("req_snap" in it.target for it in snap.items))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
