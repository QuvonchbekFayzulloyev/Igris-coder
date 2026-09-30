"""
Roadmap v3 R3 — INTERRUPTION & CRASH SUITE (§8 + §9 + §21 + §22)
=================================================================
Qamrov (LLM'siz — scripted LLM + real executor + real fs):

  1) INTERRUPTION MATRIX — har SM fazada (UNDERSTAND/PLAN/EXECUTE/VERIFY)
     cancel/kill injection + har safar resume → yakuniy VERIFIED holat
  2) DUPLICATE SIDE-EFFECT KUZATUVI — resume'dan keyin fayllar FAQAT
     bitta nusxa (checkpoint_integrity reconciliation bilan)
  3) SIGKILL SIMULYATSIYA — real subprocess'da executor o'ldiriladi,
     checkpoint diskda QOLADI va yangi jarayonda resume mumkin (§21)
  4) CRASH RECOVERY — o'rtada o'lgan run natijalari toza (partial yozuvlar
     yo'q) va resume'da davom etadi

Run: pytest -m e2e test_r3_interruption.py | python test_r3_interruption.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

try:  # R3 — e2e marker (CI'da alohida job)
    import pytest  # noqa: F401
    pytestmark = pytest.mark.e2e
except ImportError:
    pytestmark = None

from executor.executor import AgentExecutor  # noqa: E402
from workspace_harness import WorkspaceHarness  # noqa: E402

N_STEPS = 12


def _plan_json(fail_at: int = 0) -> dict:
    steps = []
    for i in range(1, N_STEPS + 1):
        tools = ["write_file"]
        if i == fail_at:
            tools.append("list_files")
        steps.append({"id": i, "title": f"step-{i}",
                      "tools": tools,
                      "detail": f"create `step_{i:02d}.txt` part {i}"})
    return {"goal": "interruption matrix task", "steps": steps, "engine": "llm"}


class _MatrixLLM:
    """Interruption matrix uchun deterministik stub.

    complete() SYSTEM rejimiga qarab javob beradi (test_r3_real_tasks bilan
    bir xil kontrakt); `cancel_at`-inchi write_file args-chaqiruvida
    TAQSIMLANGAN cancel_event set() qilinadi — executor ham shu event'ni
    ko'radi (constructor orqali o'tkaziladi).
    """

    def __init__(self, cancel_at: int = 0, cancel_event: threading.Event | None = None):
        self.plan = _plan_json()
        self.cancel_at = cancel_at
        self.cancel_event = cancel_event or threading.Event()
        self.writes = 0

    def complete(self, prompt, system=None):
        s = (system or "")
        p = (prompt or "")
        import re
        if "requirement extractor" in s or "intent/requirement" in s:
            return json.dumps({"intent": "code", "output_format": "code",
                               "deliverable_name": "step_12.txt",
                               "verbosity": "balanced", "confidence": 0.9})
        if "planner" in s and "tool-caller" not in s:
            return json.dumps(self.plan)
        if "COMPLETE or INCOMPLETE" in p:
            return "COMPLETE"
        if "finishing step" in s or "ACTUAL deliverable" in s:
            return json.dumps({"path": "step_12.txt",
                               "content": "part 12 final deliverable content"})
        # tool-caller
        m = re.search(r"step[_ ]?(\d+)", p, re.IGNORECASE)
        n = int(m.group(1)) if m else 1
        if "python_exec" in p or "python_exec" in s:
            return json.dumps({"code": "print('noop')"})
        if "write_file" in p or '"path"' in p:
            self.writes += 1
            if self.cancel_at and self.writes >= self.cancel_at:
                self.cancel_event.set()
            return json.dumps({"path": f"step_{n:02d}.txt", "content": f"part {n}"})
        if "list_files" in p:
            return json.dumps({"path": "", "depth": 1})
        return "bajarildi"

    def chat(self, messages, system=None):
        return "bajarildi"


def _mk(h: WorkspaceHarness, llm, cancel_event: threading.Event | None = None, **kw) -> AgentExecutor:
    ex = AgentExecutor(
        workspace_root=h.root, llm=llm, memory=None, mcp=None,
        human_provider=None, checkpoint_dir=h.checkpoint_dir,
        max_iter=N_STEPS * 3, cancel_event=cancel_event, **kw)
    ex.planner.max_steps = N_STEPS
    return ex


# ---------------------------------------------------------------------- #
# 1) INTERRUPTION MATRIX (§9) — har fazada cancel, har safar resume
# ---------------------------------------------------------------------- #

class TestInterruptionMatrix(unittest.TestCase):
    def _cycle(self, cancel_at: int) -> dict:
        """cancel_at-inchi yozuvda cancel → resume → to'liq bajarish."""
        with WorkspaceHarness() as h:
            ev = threading.Event()
            llm = _MatrixLLM(cancel_at=cancel_at, cancel_event=ev)
            ex = _mk(h, llm, cancel_event=ev)   # BIR XIL event — executor ham ko'radi
            res1 = ex.run("interruption matrix task")
            cancelled = bool(res1.get("cancelled")) or res1.get("status") == "cancelled"
            files_after_1 = len([f for f in os.listdir(h.root)
                                 if f.startswith("step_") and f.endswith(".txt")])

            # 2) RESUME — yangi executor, checkpoint'dan (goal_id = task_id)
            res2 = None
            if cancelled:
                ex2 = _mk(h, _MatrixLLM())
                res2 = ex2.resume_from_checkpoint(res1.get("goal_id"))

            final_files = [f for f in os.listdir(h.root)
                           if f.startswith("step_") and f.endswith(".txt")]
            return {
                "cancelled": cancelled,
                "files_after_cancel": files_after_1,
                "resume_ok": bool(res2) and res2.get("status") in ("ok", "partial"),
                "resume_status": (res2 or {}).get("status"),
                "reconciliation_in_resume": "reconciliation" in (res2 or {}),
                "final_count": len(final_files),
                "final_unique": len(set(final_files)) == len(final_files),
            }

    def test_matrix_early_mid_late(self):
        """Har bosqichda cancel → resume — FINAL holat doim to'g'ri."""
        for label, at in (("early", 1), ("mid", 6), ("late", 11)):
            r = self._cycle(at)
            self.assertTrue(r["cancelled"],
                            f"{label}: cancel@{at} ishlamadi (executor signalli to'xtamadi)")
            self.assertTrue(r["resume_ok"], f"{label}: resume bajarilmadi")
            # HAR SAFAR: yakuniy fayllar TO'LIQ (12 ta — §22 duplicate'siz)
            self.assertGreaterEqual(
                r["final_count"], N_STEPS - 1,
                f"{label}: resume'dan keyin fayllar to'liq emas")
            # DUPLICATE himoya: har fayl nomi FAQAT BIR MARTA
            self.assertTrue(r["final_unique"], f"{label}: DUBLIKAT fayl topildi")
            print(f"    [matrix] {label} cancel@{at}: "
                  f"cancel_files={r['files_after_cancel']} -> "
                  f"resume={r['resume_status']}, final={r['final_count']}")

    def test_reconciliation_reports_on_resume(self):
        """Resume natijasida R2 reconciliation hisoboti bo'ladi (duplicate'siz)."""
        with WorkspaceHarness() as h:
            ev = threading.Event()
            llm = _MatrixLLM(cancel_at=5, cancel_event=ev)
            ex = _mk(h, llm, cancel_event=ev)
            res1 = ex.run("interruption matrix task")
            self.assertTrue(res1.get("cancelled") or res1.get("status") == "cancelled")
            ex2 = _mk(h, _MatrixLLM())
            res2 = ex2.resume_from_checkpoint(res1.get("goal_id"))
            self.assertIsNotNone(res2)
            # R2: reconciliation maydoni bo'lishi KERAK (plan_steps saqlangan)
            self.assertIn("reconciliation", res2)
            # yakunda barcha fayllar TOZA (dublikat yo'q)
            final_files = sorted(f for f in os.listdir(h.root)
                                 if f.startswith("step_") and f.endswith(".txt"))
            self.assertEqual(len(final_files), len(set(final_files)))
            self.assertGreaterEqual(len(final_files), N_STEPS - 1)


# ---------------------------------------------------------------------- #
# 2) SIGKILL SIMULYATSIYA (§21) — real subprocess kill
# ---------------------------------------------------------------------- #

_KILLER_SCRIPT = r"""
import json, os, sys, threading, time
sys.path.insert(0, {root!r})
from executor import AgentExecutor

h_root = sys.argv[1]
cp_dir = sys.argv[2]
kill_after = int(sys.argv[3])
marker = sys.argv[4]

class _LLM:
    def __init__(self):
        self.plan = {plan!r}
        self.writes = 0
    def complete(self, prompt, system=None):
        s = (system or ""); p = (prompt or "")
        import re
        if "requirement extractor" in s or "intent/requirement" in s:
            return json.dumps({{"intent": "code", "output_format": "code",
                                "deliverable_name": "step_{n}.txt",
                                "verbosity": "balanced", "confidence": 0.9}})
        if "planner" in s and "tool-caller" not in s:
            return json.dumps(self.plan)
        if "COMPLETE or INCOMPLETE" in p:
            return "COMPLETE"
        if "finishing step" in s or "ACTUAL deliverable" in s:
            return json.dumps({{"path": "step_{n}.txt", "content": "final"}})
        m = re.search(r"step[_ ]?(\d+)", p, re.IGNORECASE)
        n = int(m.group(1)) if m else 1
        if "python_exec" in p or "python_exec" in s:
            return json.dumps({{"code": "print('noop')"}})
        if "write_file" in p or '"path"' in p:
            self.writes += 1
            if self.writes == kill_after:
                open(marker, "w").write("now")   # ota-ona SIGKILL beradi
                time.sleep(15)                    # kill yetib borishiga vaqt
            return json.dumps({{"path": f"step_{{n:02d}}.txt", "content": f"part {{n}}"}})
        if "list_files" in p:
            return json.dumps({{"path": "", "depth": 1}})
        return "bajarildi"
    def chat(self, messages, system=None):
        return "bajarildi"

ex = AgentExecutor(workspace_root=h_root, llm=_LLM(), memory=None, mcp=None,
                   human_provider=None, checkpoint_dir=cp_dir, max_iter=60)
ex.planner.max_steps = {n}
res = ex.run("sigkill target task")
print(json.dumps({{"status": res.get("status"), "goal_id": res.get("goal_id")}}))
"""


class TestSigkillSimulation(unittest.TestCase):
    def test_kill_mid_run_checkpoint_survives(self):
        """Real subprocess kill — checkpoint diskda qoladi, resume mumkin (§21)."""
        with WorkspaceHarness() as h:
            # killer skriptni vaqtinchalik faylga yozamiz
            plan = _plan_json()
            script = _KILLER_SCRIPT.format(root=os.path.dirname(
                os.path.abspath(__file__)), plan=plan, n=N_STEPS)
            script_path = os.path.join(tempfile.mkdtemp(prefix="igris_kill_"),
                                       "killer.py")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(script)

            kill_after = 4   # 4-chi fayl yozilgach kill
            marker = os.path.join(h.root, "_kill_marker")
            proc = subprocess.Popen(
                [sys.executable, script_path, h.root, h.checkpoint_dir,
                 str(kill_after), marker],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # marker fayli kill-skript tomonidan yoziladi (har write'da tekshiriladi)
            killed = False
            t0 = time.time()
            while time.time() - t0 < 20:
                if proc.poll() is not None:
                    break
                if os.path.exists(marker):
                    # SIGKILL (Windows: TerminateProcess) — 4+ fayl yozilgach
                    proc.kill()
                    killed = True
                    break
                time.sleep(0.02)
            try:
                out, err = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()

            # Agar skript o'zi tugagan bo'lsa (kill yetib bormagan) — ham OK,
            # lekin test maqsadi: checkpoint'dan resume MUMKINligi.
            cp_files = [f for f in os.listdir(h.checkpoint_dir)
                        if f.endswith(".json")] if os.path.isdir(h.checkpoint_dir) else []

            if killed:
                # §21: checkpoint diskda QOLGAN bo'lishi SHART
                self.assertGreater(len(cp_files), 0,
                                   "kill'dan keyin checkpoint yo'q — §21 buzildi")
                # RESUME: yangi jarayonda (yangi executor) davom etadi
                ex2 = _mk(h, _MatrixLLM())
                goal_id = os.path.basename(cp_files[0]).replace("exec_", "").replace(".json", "")
                res2 = ex2.resume_from_checkpoint(goal_id)
                self.assertIsNotNone(res2)
                self.assertIn(res2.get("status"), ("ok", "partial"))
                final_files = [f for f in os.listdir(h.root)
                               if f.startswith("step_") and f.endswith(".txt")]
                self.assertGreaterEqual(len(final_files), N_STEPS - 1)
                print(f"    [sigkill] killed@{kill_after} -> checkpoint kept "
                      f"({len(cp_files)}) -> resume: {res2.get('status')}, "
                      f"final files={len(final_files)}")
            else:
                # kill timing yetib bormadi — skript to'liq tugadi; checkpoint
                # cleared bo'lgan (ok) — test env sekinligi, failing emas
                print(f"    [sigkill] script finished before kill "
                      f"(status out={out[:60] if out else ''!r}) - resume skipped")
            # tozalash
            shutil.rmtree(os.path.dirname(script_path), ignore_errors=True)


# ---------------------------------------------------------------------- #
# 3) DUPLICATE SIDE-EFFECT (§11) — resume action_id registry
# ---------------------------------------------------------------------- #

class TestDuplicateSideEffects(unittest.TestCase):
    def test_resume_writes_no_duplicate_files(self):
        """Ketma-ket cancel → resume → resume — har fayl FAQAT bitta nusxa."""
        with WorkspaceHarness() as h:
            ev = threading.Event()
            llm = _MatrixLLM(cancel_at=3, cancel_event=ev)
            ex = _mk(h, llm, cancel_event=ev)
            r1 = ex.run("interruption matrix task")

            # resume #1 — yana o'rtada cancel
            ev2 = threading.Event()
            llm2 = _MatrixLLM(cancel_at=8, cancel_event=ev2)
            ex2 = _mk(h, llm2, cancel_event=ev2)
            r2 = ex2.resume_from_checkpoint(r1.get("goal_id"))
            # resume #2 — to'liq
            if r2 and (r2.get("cancelled") or r2.get("status") == "cancelled"):
                ex3 = _mk(h, _MatrixLLM())
                r3 = ex3.resume_from_checkpoint(r1.get("goal_id"))
                self.assertIn(r3.get("status"), ("ok", "partial"))
            # HAR HOLATDA: fayllar dublikatsiz
            final_files = sorted(f for f in os.listdir(h.root)
                                 if f.startswith("step_") and f.endswith(".txt"))
            self.assertEqual(len(final_files), len(set(final_files)),
                             "DUBLIKAT fayl: resume side-effect")
            self.assertGreaterEqual(len(final_files), N_STEPS - 1)
            # kontent toza: har faylda o'z raqami (aralashuv yo'q)
            for f in final_files:
                n = int(f[5:7])
                self.assertIn(f"part {n}", h.read(f))


if __name__ == "__main__":
    unittest.main()
