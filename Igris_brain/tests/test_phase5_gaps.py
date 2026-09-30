"""
Phase 5 bo'shliq yopish testlari (audit tavsiyalari ①②③)
=========================================================

Qamrov:
  - ① Step N of M progress: planned loop'da "step i/M: title" formati
  - ② Plan reasoning/confidence: LLM plan JSON ixtiyoriy maydonlar +
    fallback confidence=1.0 + invalid qiymatlar filtrlanadi
  - ③ Memory conflict: MemoryBridge.detect_conflicts — deterministik
    conflict signali + score yaqinligi flagi + disabled guard

Run: python test_phase5_gaps.py
"""

import json
import os
import re
import sys
import threading
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from planning.planner import TaskPlanner  # noqa: E402
from agent.memory_bridge import MemoryBridge  # noqa: E402
from executor.executor import AgentExecutor  # noqa: E402

_RESULTS: list[tuple[str, bool]] = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


# ============================================================
# ② Plan reasoning/confidence
# ============================================================

class TestPlanDecisionFields(unittest.TestCase):

    def test_llm_plan_keeps_reasoning_and_confidence(self):
        p = TaskPlanner(llm=None)
        parsed = {
            "goal": "x",
            "reasoning": "files first, then write, then verify",
            "confidence": 0.8,
            "steps": [{"id": 1, "title": "read", "tools": ["read_file"], "detail": ""}],
        }
        plan = p._normalize("x", parsed)
        self.assertEqual(plan.get("reasoning"), "files first, then write, then verify")
        self.assertEqual(plan.get("confidence"), 0.8)
        check("llm plan: reasoning saqlanadi", plan.get("reasoning") == "files first, then write, then verify")
        check("llm plan: confidence saqlanadi", plan.get("confidence") == 0.8)

    def test_llm_plan_without_fields_backward_compatible(self):
        p = TaskPlanner(llm=None)
        plan = p._normalize("x", {"steps": [{"id": 1, "title": "s", "tools": [], "detail": ""}]})
        self.assertNotIn("reasoning", plan)
        self.assertNotIn("confidence", plan)
        check("maydonsiz plan backward-compatible", "reasoning" not in plan and "confidence" not in plan)

    def test_invalid_confidence_filtered(self):
        p = TaskPlanner(llm=None)
        plan = p._normalize("x", {"confidence": "high", "reasoning": "", "steps": []})
        self.assertNotIn("confidence", plan)
        self.assertNotIn("reasoning", plan)
        check("invalid confidence filtrlanadi", "confidence" not in plan)

    def test_confidence_out_of_range_filtered(self):
        p = TaskPlanner(llm=None)
        plan = p._normalize("x", {"confidence": 1.7, "steps": []})
        self.assertNotIn("confidence", plan)
        check("1.7 confidence rad etiladi", "confidence" not in plan)

    def test_reasoning_truncated_to_500(self):
        p = TaskPlanner(llm=None)
        plan = p._normalize("x", {"reasoning": "r" * 900, "steps": []})
        self.assertLessEqual(len(plan.get("reasoning", "")), 500)
        check("reasoning 500 belgiga cheklangan", len(plan.get("reasoning", "")) <= 500)

    def test_fallback_has_full_confidence(self):
        p = TaskPlanner(llm=None)
        plan = p.plan("create notes.txt with hello")  # llm=None -> fallback
        self.assertEqual(plan.get("confidence"), 1.0)
        self.assertEqual(plan.get("engine"), "fallback")
        check("fallback confidence=1.0", plan.get("confidence") == 1.0)

    def test_plan_system_prompt_mentions_fields(self):
        from planning.planner import DEFAULT_PLAN_SYSTEM
        self.assertIn("reasoning", DEFAULT_PLAN_SYSTEM)
        self.assertIn("confidence", DEFAULT_PLAN_SYSTEM)
        check("prompt schema yangilangan", "reasoning" in DEFAULT_PLAN_SYSTEM and "confidence" in DEFAULT_PLAN_SYSTEM)


# ============================================================
# ③ Memory conflict detection
# ============================================================

class _FakeHybrid:
    def add_document(self, *a, **k):
        pass


class _FakeRetrieval:
    def __init__(self):
        self.hybrid = _FakeHybrid()

    def load_documents(self, d):
        pass


class _FakeManager:
    def __init__(self, results):
        self._results = results
        self.retrieval = _FakeRetrieval()

    def search(self, query, top_k=5):
        return {"results": list(self._results)[:top_k]}


class _FakeBridge:
    """MemoryBridge metodlarini __init__'siz yaratilgan nusxa ustida ishga tushiradi
    (test_phase3_context'dagi konventsiya bilan bir xil)."""

    def __init__(self, results):
        self.b = MemoryBridge.__new__(MemoryBridge)
        self.b.enabled = True
        self.b.manager = _FakeManager(results)
        self.b._error = ""
        self.b._latency = {}
        self.b._load_done = threading.Event()
        self.b._load_done.set()

    def detect_conflicts(self, query, top_k=3, min_score=0.0):
        return MemoryBridge.detect_conflicts(self.b, query, top_k=top_k, min_score=min_score)


class TestMemoryConflict(unittest.TestCase):

    def test_conflict_detected_when_scores_close(self):
        # Bir xil savolga ikki xil javob: normal + teskari (score yaqin)
        normal = {"entry": {"content": "deploy command is npm run build", "id": "a"}, "score": 1.0}
        contra = {"entry": {"content": "deploy command is NOT npm run build anymore", "id": "b"}, "score": 0.9}
        fb = _FakeBridge([normal, contra])
        res = fb.detect_conflicts("deploy command")
        self.assertTrue(res["conflict"])
        check("conflict flag True (score yaqin)", res["conflict"] is True)

    def test_no_conflict_when_only_normal_entries(self):
        e1 = {"entry": {"content": "uses vite for build", "id": "a"}, "score": 1.0}
        e2 = {"entry": {"content": "uses esbuild for dev", "id": "b"}, "score": 0.8}
        fb = _FakeBridge([e1, e2])
        res = fb.detect_conflicts("build tool")
        self.assertFalse(res["conflict"])
        check("faqat normal yozuvlar -> conflict False", res["conflict"] is False)

    def test_no_conflict_when_score_gap_big(self):
        # Teskari yozuv ancha past score'da — dominant javob aniq, conflict emas
        normal = {"entry": {"content": "config path is config/app.json", "id": "a"}, "score": 2.0}
        contra = {"entry": {"content": "config path is not config/app.json", "id": "b"}, "score": 0.4}
        fb = _FakeBridge([normal, contra])
        res = fb.detect_conflicts("config path")
        self.assertFalse(res["conflict"])
        check("score farq katta -> conflict False", res["conflict"] is False)

    def test_conflicting_flag_per_entry(self):
        e1 = {"entry": {"content": "the port is 8080", "id": "a"}, "score": 1.0}
        e2 = {"entry": {"content": "port 8080 is outdated, use 9090", "id": "b"}, "score": 1.1}
        fb = _FakeBridge([e1, e2])
        res = fb.detect_conflicts("port")
        flags = {x["snippet"][:10]: x["conflicting"] for x in res["entries"]}
        self.assertFalse(list(flags.values())[0])
        self.assertTrue(list(flags.values())[1])
        check("har yozuvda conflicting flag", True)

    def test_disabled_bridge(self):
        fb = _FakeBridge([])
        fb.b.enabled = False
        res = fb.detect_conflicts("q")
        self.assertEqual(res["status"], "disabled")
        self.assertFalse(res["conflict"])
        check("disabled bridge guard", res["status"] == "disabled")

    def test_looks_conflicting_patterns(self):
        self.assertTrue(MemoryBridge._looks_conflicting("This no longer works"))
        self.assertTrue(MemoryBridge._looks_conflicting("renamed to utils.py"))
        self.assertFalse(MemoryBridge._looks_conflicting("deploy succeeds every time"))
        check("_looks_conflicting patternlari", True)


# ============================================================
# ① Step N of M progress
# ============================================================

class _StepLLM:
    """Planner'ga JSON reja, tool args so'ralganda oddiy args qaytaradi."""

    def __init__(self):
        self.planned = False

    def complete(self, prompt, system=None):
        if not self.planned:
            self.planned = True
            return json.dumps({
                "goal": "make a file",
                "steps": [
                    {"id": 1, "title": "write file", "tools": ["write_file"],
                     "detail": "create hello.txt"},
                    {"id": 2, "title": "verify", "tools": ["list_files"],
                     "detail": "check"},
                ],
            })
        return json.dumps({"path": "hello.txt", "content": "hello"})

    def chat(self, messages, system=None):
        return "done"


class TestStepProgress(unittest.TestCase):

    def test_step_n_of_m_in_progress(self):
        stages: list[str] = []
        ex = AgentExecutor(workspace_root=os.path.join(os.path.dirname(__file__), "agent_workspace"),
                           llm=_StepLLM(), memory=None, mcp=None, human_provider=None,
                           progress_cb=lambda s, d, r=None: stages.append(f"{s}: {d}"))
        res = ex.run("make a file")
        self.assertIn(res["status"], ("ok", "partial"))
        joined = " | ".join(stages)
        # §13(6): har step boshlanishida "step N/M" formati (planner nechta
        # qadam tuzsa ham — fallback yoki llm — format barqaror).
        step_marks = re.findall(r"step \d+/\d+:", joined)
        self.assertGreaterEqual(len(step_marks), 2)
        self.assertIn("step 1/", joined)
        check("step N/M formati progressda", len(step_marks) >= 2)


# ============================================================
# Yakuniy hisobot
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
