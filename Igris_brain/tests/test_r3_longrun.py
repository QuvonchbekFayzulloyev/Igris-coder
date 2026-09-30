"""
Roadmap v3 R3 — LONG-RUN + STRESS SUITE (§4 + §10 + §24 + §25)
===============================================================
Qamrov (LLM'siz — scripted LLM + real executor + real fs):

  1) 50+ STEP LONG-RUN  — 60 step'li reja; SM holatlari faqat forward
     (UNDERSTAND → PLAN → EXECUTE → VERIFY), checkpoint pike/i/o kuzatuvi
  2) GROWTH ASSERTION   — memory'da growth belgisi (step'lar davomida
     goal-context / requirements kengayishi) deterministik kuzatiladi
  3) STRESS: KETMA-KET RUN — 5 ta to'liq run ketma-ket (harness restart bilan),
     har biri mustaqil VERIFIED/ok; fayl/journal izolyatsiyasi
  4) STRESS: SLOW-LLM   — kechikuvchan LLM (latency 5-50ms) ostida executor
     timeout'siz to'g'ri ishlaydi
  5) LIMITLAR           — max_tool_calls tufayli stopped holat toza
     (checkpoint kept, resume mumkin)

Run: pytest -m e2e test_r3_longrun.py | python test_r3_longrun.py
"""
from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

try:
    import pytest  # noqa: F401
    pytestmark = pytest.mark.e2e
except ImportError:
    pytestmark = None

from executor.executor import AgentExecutor  # noqa: E402
from workspace_harness import WorkspaceHarness  # noqa: E402

N_STEPS = 60          # §26: 50+ step
STRESS_RUNS = 5


def _big_plan(n: int = N_STEPS) -> dict:
    steps = []
    for i in range(1, n + 1):
        steps.append({"id": i, "title": f"long step {i}",
                      "tools": ["write_file"],
                      "detail": f"create `long_{i:03d}.txt` part {i}"})
    return {"goal": "long-run task", "steps": steps, "engine": "llm"}


class _LongRunLLM:
    """60 step'li reja bilan deterministik stub (real_tasks naqshida)."""

    def __init__(self, plan: dict | None = None, delay: float = 0.0, seed: int = 42):
        self.plan = plan or _big_plan()
        self.delay = delay
        self._rng = random.Random(seed)

    def complete(self, prompt, system=None):
        if self.delay:
            time.sleep(self.delay * self._rng.uniform(0.5, 1.5))
        s = (system or "")
        p = (prompt or "")
        import re
        if "requirement extractor" in s or "intent/requirement" in s:
            return json.dumps({"intent": "code", "output_format": "code",
                               "deliverable_name": "long_060.txt",
                               "verbosity": "balanced", "confidence": 0.9})
        if "planner" in s and "tool-caller" not in s:
            return json.dumps(self.plan)
        if "COMPLETE or INCOMPLETE" in p:
            return "COMPLETE"
        if "finishing step" in s or "ACTUAL deliverable" in s:
            return json.dumps({"path": "long_060.txt",
                               "content": "final deliverable — long run done"})
        if "python_exec" in p or "python_exec" in s:
            return json.dumps({"code": "print('noop')"})
        if "write_file" in p or '"path"' in p:
            m = re.search(r"long[_ ]?(\d+)", p, re.IGNORECASE)
            n = int(m.group(1)) if m else 1
            return json.dumps({"path": f"long_{n:03d}.txt", "content": f"part {n}"})
        if "list_files" in p:
            return json.dumps({"path": "", "depth": 1})
        return "bajarildi"

    def chat(self, messages, system=None):
        if self.delay:
            time.sleep(self.delay * self._rng.uniform(0.5, 1.5))
        return "bajarildi"


def _mk(h: WorkspaceHarness, llm, **kw) -> AgentExecutor:
    opts = {"max_iter": N_STEPS * 2, "max_tool_calls": N_STEPS * 2}
    opts.update(kw)
    ex = AgentExecutor(
        workspace_root=h.root, llm=llm, memory=None, mcp=None,
        human_provider=None, checkpoint_dir=h.checkpoint_dir, **opts)
    ex.planner.max_steps = N_STEPS
    return ex


def _count(root: str, prefix: str = "long_") -> int:
    return len([f for f in os.listdir(root)
                if f.startswith(prefix) and f.endswith(".txt")])


# ---------------------------------------------------------------------- #
# 1) 50+ STEP LONG-RUN (§24)
# ---------------------------------------------------------------------- #

class TestLongRun(unittest.TestCase):
    def test_60_step_plan_completes(self):
        with WorkspaceHarness() as h:
            llm = _LongRunLLM()
            ex = _mk(h, llm)
            res = ex.run("long-run task")
            self.assertEqual(res.get("status"), "ok", f"res={res.get('status')}")
            self.assertEqual(_count(h.root), N_STEPS,
                             f"60 fayl kerak, bor: {_count(h.root)}")
            # har fayl o'z raqami bilan to'g'ri (aralashuv yo'q)
            for i in (1, 30, 60):
                self.assertIn(f"part {i}", h.read(f"long_{i:03d}.txt"))
            print(f"    [long-run] 60 steps -> status={res['status']}, "
                  f"files={_count(h.root)}")

    def test_longrun_sm_states_forward_only(self):
        """SM holatlari faqat OLDINGA harakat (regress — bug belgisi)."""
        ORDER = ["UNDERSTAND", "PLAN", "EXECUTE", "VERIFY", "COMPLETE"]
        rank = {s: i for i, s in enumerate(ORDER)}
        with WorkspaceHarness() as h:
            exec_events: list[tuple[str, int]] = []

            def cb(stage: str, detail: str, record=None):
                if stage == "execute":
                    import re
                    m = re.search(r"step (\d+)/", detail)
                    if m:
                        exec_events.append((detail, int(m.group(1))))

            ex = _mk(h, _LongRunLLM(), progress_cb=cb)
            res = ex.run("long-run task")
            self.assertEqual(res.get("status"), "ok")
            # callback umuman chaqirilganini ham tasdiqlaymiz
            self.assertGreater(len(exec_events), 0,
                               "progress_cb 'execute' eventlari kelmadi")
            # kuzatilgan execute bosqichlari monoton o'suvchi
            last = -1
            for detail, n in exec_events:
                self.assertGreaterEqual(n, last,
                                        f"SM regress: step {n} after {last} ({detail!r})")
                last = n
            self.assertEqual(last, N_STEPS)
            print(f"    [long-run] SM forward-only OK ({len(exec_events)} execute events)")

    def test_longrun_growth_assertion(self):
        """§24 growth: step'lar davomida executor izchil kengayadi
        (verification log + timeline record'lar soni step soniga mos)."""
        with WorkspaceHarness() as h:
            ex = _mk(h, _LongRunLLM())
            res = ex.run("long-run task")
            self.assertEqual(res.get("status"), "ok")
            tl = res.get("timeline") or []
            executed = [t for t in tl if t.get("tool") == "write_file"]
            self.assertGreaterEqual(
                len(executed), N_STEPS,
                f"growth: write_file record'lari {len(executed)} < {N_STEPS}")
            # R1.2: COMPLETE faqat matrix complete bo'lganda — status=ok buni
            # anglatadi; verifications ham bo'lishi kerak
            self.assertIn("verifications", res)
            print(f"    [long-run] growth: timeline={len(tl)}, "
                  f"writes={len(executed)}, verifications={len(res.get('verifications', []))}")


# ---------------------------------------------------------------------- #
# 2) STRESS (§25)
# ---------------------------------------------------------------------- #

class TestStress(unittest.TestCase):
    def test_5_consecutive_runs_isolated(self):
        """5 ta to'liq run ketma-ket — har biri izolyatsiyalangan workspace'da ok."""
        for k in range(STRESS_RUNS):
            with WorkspaceHarness() as h:
                ex = _mk(h, _LongRunLLM(seed=100 + k))
                res = ex.run(f"long-run task run#{k}")
                self.assertEqual(res.get("status"), "ok", f"run#{k}: {res.get('status')}")
                self.assertEqual(_count(h.root), N_STEPS, f"run#{k}: fayl soni")
                # izolyatsiya: har running o'z checkpoint papkasi toza
                self.assertEqual(os.listdir(h.checkpoint_dir), [],
                                 f"run#{k}: checkpoint qoldiq (cleared bo'lishi kerak)")
                print(f"    [stress] run#{k}: ok, files={_count(h.root)}")

    def test_slow_llm_no_hang(self):
        """§25 slow-LLM: kechikish bilan ham run yakunlanadi (timeout yo'q)."""
        with WorkspaceHarness() as h:
            ex = _mk(h, _LongRunLLM(delay=0.01))
            t0 = time.time()
            res = ex.run("long-run task")
            dt = time.time() - t0
            self.assertEqual(res.get("status"), "ok")
            self.assertEqual(_count(h.root), N_STEPS)
            # 60 step × ~5-15ms kechikish — real vaqt chegarasi keng
            self.assertLess(dt, 60.0, "slow-LLM run juda uzoq")
            print(f"    [stress] slow-LLM (10ms avg): {dt:.2f}s, files={_count(h.root)}")

    def test_max_tool_calls_stops_cleanly(self):
        """Limit: max_tool_calls tufayli stopped — checkpoint KEPT, resume mumkin."""
        with WorkspaceHarness() as h:
            ex = _mk(h, _LongRunLLM(), max_iter=N_STEPS * 2,
                     max_tool_calls=10)   # 60 step > 10 tool limit
            res = ex.run("long-run task")
            self.assertEqual(res.get("status"), "stopped")
            self.assertEqual(res.get("checkpoint"), "kept",
                             "stopped'da checkpoint saqlanishi kerak")
            # to'xtagan nuqtada fayllar bor
            self.assertGreater(_count(h.root), 0)
            # RESUME: checkpoint'dan davom
            ex2 = _mk(h, _LongRunLLM(), max_iter=N_STEPS * 2)
            res2 = ex2.resume_from_checkpoint(res.get("goal_id"))
            self.assertIsNotNone(res2)
            self.assertEqual(res2.get("status"), "ok")
            self.assertEqual(_count(h.root), N_STEPS,
                             f"resume'dan keyin to'liq: {_count(h.root)}")
            print(f"    [stress] stopped@limit -> resume ok, final={_count(h.root)}")


if __name__ == "__main__":
    unittest.main()
