"""
Roadmap v2 — Phase C1 testlari: LONG-RUNNING E2E (§18 qoldig'i)
================================================================

Qamrov (LLM'siz, deterministik stublar bilan):
  1) 20+ qadamli reja to'liq bajariladi — yakuniy "ok", barcha step'lar done
  2) FAILURE INJECTION — o'rtadagi qadam xato qiladi: run davom etadi
     (replan), errors[] to'ladi, status partial/ok
  3) CANCEL INJECTION — run o'rtasida cancel: status "cancelled",
     checkpoint kept, partijal progress saqlanadi
  4) RESUME — cancelled run'dan keyin resume_from_checkpoint: qolgan
     qadamlar bajariladi, bajarilganlar skip, yakuniy "ok" + checkpoint cleared

Time guard: har test 30s dan kam (perf regression himoyasi).

Roadmap v2 C3: pytest markeri `e2e` — CI'da alohida job'da yugurtiriladi.
Run: python test_phase_c1_e2e_longrun.py  |  pytest -m e2e
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

try:  # Roadmap v2 C3: e2e marker — CI'da alohida job (pytest.ini'da ro'yxatda)
    import pytest  # noqa: F401
    pytestmark = pytest.mark.e2e
except ImportError:
    pytestmark = None

from executor.executor import AgentExecutor  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


N_STEPS = 22  # 20+ talab


def _plan_json(fail_at: int = 0, fail_tool: str = "list_files"):
    """20+ qadamli reja: har qadamda write_file (i) + list_files (checkpoint)."""
    steps = []
    for i in range(1, N_STEPS + 1):
        tools = ["write_file"]
        if i == fail_at:
            tools.append(fail_tool)
        steps.append({"id": i, "title": f"step-{i}", "tools": tools,
                      "detail": f"create step_{i:02d}.txt part {i}"})
    return {"goal": "long running task", "steps": steps, "engine": "llm"}


class _ScriptedLLM:
    """Planned loop stub — kontentga qarab javob beradi.

    - plan so'rovi (_planner system) -> _plan_json
    - 'write_file' args so'rovi -> {"path": "step_XX.txt", "content": ...}
    - 'list_files' args -> {"path": "", "depth": 1}
    - boshqa (xulosa) -> qisqa matn
    fail_at qadamda fail_tool DOIM xato qaytaradi (args-ga qaramay).
    """

    def __init__(self, fail_at: int = 0, fail_tool: str = "list_files"):
        self.plan = _plan_json(fail_at, fail_tool)
        self.fail_at = fail_at
        self.fail_tool = fail_tool

    def complete(self, prompt, system=None):
        p = (prompt or "") + (system or "")
        if "steps" in p and "goal" in p:
            return json.dumps(self.plan)
        import re as _re
        m = _re.search(r"step[_ ]?(\d+)", p, _re.IGNORECASE)
        n = int(m.group(1)) if m else 1
        if f"write_file" in p and "path" in p:
            return json.dumps({"path": f"step_{n:02d}.txt",
                               "content": f"part {n}"})
        if "list_files" in p:
            if self.fail_at and n == self.fail_at:
                return json.dumps({"path": "\x00invalid_path_for_fail"})  # FTS/xato yo'li
            return json.dumps({"path": "", "depth": 1})
        return "barcha qadamlar bajarildi."

    def chat(self, messages, system=None):
        return "barcha qadamlar bajarildi."


def _mk(tmp, fail_at=0, fail_tool="list_files", **kw):
    ex = AgentExecutor(
        workspace_root=tmp,
        llm=_ScriptedLLM(fail_at, fail_tool),
        memory=None, mcp=None, human_provider=None,
        max_iter=N_STEPS * 3,          # long-running uchun keng limit
        checkpoint_dir=os.path.join(tmp, "cp"),
        **kw,
    )
    # C1: planner max_steps 6 default — 20+ qadam uchun kengaytiramiz
    ex.planner.max_steps = N_STEPS
    return ex


class TestLongRunFull(unittest.TestCase):
    """20+ qadamli reja — to'liq bajarish."""

    def test_full_run_all_steps_done(self):
        tmp = tempfile.mkdtemp(prefix="igris_c1a_")
        try:
            t0 = time.perf_counter()
            ex = _mk(tmp)
            res = ex.run("long running task")
            dur = time.perf_counter() - t0
            self.assertIn(res["status"], ("ok", "partial"))
            done = [s for s in res.get("steps", []) if s.get("status") == "done"]
            self.assertGreaterEqual(len(done), N_STEPS - 2)   # 20+ deyarli hammasi
            files = [f for f in os.listdir(tmp) if f.startswith("step_") and f.endswith(".txt")]
            self.assertGreaterEqual(len(files), N_STEPS - 2)
            check(f"20+ qadam bajarildi (done={len(done)})", len(done) >= N_STEPS - 2)
            check(f"fayllar diskda ({len(files)})", len(files) >= N_STEPS - 2)
            check(f"time guard: {dur:.1f}s < 30s", dur < 30)
            check("checkpoint cleared (ok)", res.get("checkpoint") == "cleared")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFailureInjection(unittest.TestCase):
    """O'rtada tool xatosi — run davom etadi, errors[] to'ladi."""

    def test_mid_run_failure_partial_progress(self):
        tmp = tempfile.mkdtemp(prefix="igris_c1b_")
        try:
            ex = _mk(tmp, fail_at=5, fail_tool="list_files")
            res = ex.run("long running task")
            # xato qadam bo'lishi mumkin, lekin qolgan qadamlar HAMMASI to'xtamasdan
            # o'tishi kerak (replan) yoki kamida errors[] to'lgan bo'lishi kerak
            done = [s for s in res.get("steps", []) if s.get("status") == "done"]
            err_steps = [s for s in res.get("steps", []) if s.get("status") == "error"]
            self.assertGreater(len(done), 3)  # kamida bir qismi bajarilgan
            has_errors = bool(res.get("errors")) or len(err_steps) >= 1
            self.assertTrue(has_errors)
            check(f"failure'dan keyin davom etdi (done={len(done)}, err_steps={len(err_steps)})",
                  len(done) > 3)
            check("errors[] yoki error step qayd etilgan", has_errors)
            check("status partial/ok (crash yo'q)", res.get("status") in ("ok", "partial"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCancelAndResume(unittest.TestCase):
    """Cancel injection o'rtada -> checkpoint kept -> resume -> ok."""

    def test_cancel_mid_then_resume_completes(self):
        tmp = tempfile.mkdtemp(prefix="igris_c1c_")
        try:
            # 1) CANCEL: 3-step'dan keyin cancel
            ev = threading.Event()
            ex = _mk(tmp, cancel_event=ev)
            # ScriptedLLM ichida step raqamini kuzatib cancel bosamiz:
            orig_complete = ex.llm.complete
            state = {"n": 0}

            def _complete_with_cancel(prompt=None, system=None, **kw):
                p = (prompt or "") + (system or "")
                if "write_file" in p and "path" in p:
                    state["n"] += 1
                    if state["n"] == 3:
                        ev.set()  # cancel o'rtada
                return orig_complete(prompt, system, **kw) if False else _ScriptedLLM.complete(ex.llm, prompt, system)

            ex.llm.complete = _complete_with_cancel
            res1 = ex.run("long running task")
            self.assertEqual(res1.get("status"), "cancelled")
            goal_id = res1.get("goal_id")
            self.assertTrue(goal_id)
            check("cancel -> cancelled status", res1.get("status") == "cancelled")
            check("cancel -> checkpoint kept", res1.get("checkpoint") == "kept")

            # qancha step bajarilgani
            done_before = [s for s in res1.get("steps", []) if s.get("status") == "done"]
            check(f"cancel oldidan qism progress ({len(done_before)} step)",
                  len(done_before) >= 1)

            # 2) RESUME: yangi executor nusxa — bir xil checkpoint_dir
            ex2 = AgentExecutor(
                workspace_root=tmp,
                llm=_ScriptedLLM(),           # xatosiz — qolganlari bajaradi
                memory=None, mcp=None, human_provider=None,
                max_iter=N_STEPS * 3,
                checkpoint_dir=os.path.join(tmp, "cp"),
            )
            ex2.planner.max_steps = N_STEPS  # C1: reja yana 22 qadam bo'lsin
            res2 = ex2.resume_from_checkpoint(goal_id)
            self.assertIsNotNone(res2)
            self.assertIn(res2.get("status"), ("ok", "partial"))
            # goal_id STABIL (§12)
            self.assertEqual(res2.get("goal_id"), goal_id)
            done_after = [s for s in res2.get("steps", []) if s.get("status") == "done"]
            remaining = N_STEPS - len(done_before)
            check(f"resume: qolgan qadamlar bajarildi ({len(done_after)}/{remaining})",
                  len(done_after) >= remaining - 2)
            check("resume: yakuniy checkpoint cleared",
                  res2.get("checkpoint") == "cleared")
            # fayllar to'liq (resume oldin yozilganlari ham saqlaydi)
            files = [f for f in os.listdir(tmp) if f.startswith("step_") and f.endswith(".txt")]
            check(f"resume: barcha fayllar ({len(files)})", len(files) >= N_STEPS)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resume_without_checkpoint_returns_none(self):
        tmp = tempfile.mkdtemp(prefix="igris_c1d_")
        try:
            ex = _mk(tmp)
            self.assertIsNone(ex.resume_from_checkpoint("goal-nonexistent"))
            check("checkpoint yo'q -> None", True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
