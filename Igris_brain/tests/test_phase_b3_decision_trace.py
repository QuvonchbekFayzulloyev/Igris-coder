"""
Roadmap v2 — Phase B3 testlari: LLM DECISION TRACE (§16 qoldig'i)
==================================================================

Qamrov:
  - Native loop: har iteratsiya decision_trace'da (iteration/reasoning/
    tool_calls/content_preview), result["decision_trace"] mavjud
  - Planned loop: result["decision"] bloki (engine/reasoning/confidence/
    intent/plan_validated/steps_total)
  - Trace izchilligi: iteration raqamlari 1..N, reasoning max 500

Run: python test_phase_b3_decision_trace.py
"""

import json
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import AgentExecutor  # noqa: E402

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


WS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")


class _NativeLLM:
    """Native loop stub: 2 iteratsiya tool-call, so'ng final content.
    reasoning/thinking maydonlarini ham qaytaradi (qwen3 kabi)."""

    def __init__(self):
        self.calls = 0

    def chat_with_tools(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "reasoning": "Fayl yozish uchun write_file kerak",
                "tool_calls": [{"name": "write_file",
                                "arguments": {"path": "b3_trace.txt", "content": "salom"}}],
            }
        if self.calls == 2:
            return {
                "thinking": "Endi faylni o'qib tekshiraman",  # alternativ maydon nomi
                "tool_calls": [{"name": "list_files", "arguments": {"path": "", "depth": 1}}],
            }
        return {"content": "Barcha ishlar bajarildi: b3_trace.txt tayyor."}

    def complete(self, prompt, system=None):
        return None

    def chat(self, messages, system=None):
        return "barcha ishlar bajarildi"


class TestNativeDecisionTrace(unittest.TestCase):

    def test_trace_present_with_reasoning(self):
        ex = AgentExecutor(workspace_root=WS, llm=_NativeLLM(), memory=None,
                           mcp=None, human_provider=None, max_iter=6)
        res = ex.run_native("create b3_trace.txt file")
        self.assertIn(res["status"], ("ok", "partial"))
        trace = res.get("decision_trace")
        self.assertIsInstance(trace, list)
        self.assertGreaterEqual(len(trace), 3)  # 3 iteratsiya
        # 1-iteratsiya: reasoning maydoni
        self.assertEqual(trace[0]["iteration"], 1)
        self.assertIn("write_file", trace[0]["reasoning"])
        self.assertEqual(trace[0]["tool_calls"], ["write_file"])
        # 2-iteratsiya: alternativ 'thinking' maydoni ham olinadi
        self.assertIn("o'qib tekshiraman", trace[1]["reasoning"])
        self.assertEqual(trace[1]["tool_calls"], ["list_files"])
        check("native trace: reasoning maydoni olinadi", "write_file" in trace[0]["reasoning"])
        check("native trace: 'thinking' alternativi ham", "o'qib tekshiraman" in trace[1]["reasoning"])

    def test_trace_iterations_ordered(self):
        ex = AgentExecutor(workspace_root=WS, llm=_NativeLLM(), memory=None,
                           mcp=None, human_provider=None, max_iter=6)
        res = ex.run_native("create b3_trace.txt file")
        trace = res.get("decision_trace", [])
        iters = [t["iteration"] for t in trace]
        self.assertEqual(iters, sorted(iters))
        self.assertEqual(iters[0], 1)
        check("trace iteration tartibli", iters == sorted(iters))

    def test_trace_content_preview_on_final(self):
        ex = AgentExecutor(workspace_root=WS, llm=_NativeLLM(), memory=None,
                           mcp=None, human_provider=None, max_iter=6)
        res = ex.run_native("create b3_trace.txt file")
        trace = res.get("decision_trace", [])
        last = trace[-1]
        # oxirgi iteratsiya content qaytardi (final) — preview bo'sh bo'lmasligi kerak
        self.assertTrue(last.get("content_preview"))
        self.assertEqual(last.get("tool_calls"), [])
        check("final iteratsiyada content_preview bor", bool(last.get("content_preview")))


class TestPlannedDecisionBlock(unittest.TestCase):

    def test_decision_block_in_result(self):
        from test_phase_b1_verified_speech import _PlanLLM
        ex = AgentExecutor(workspace_root=WS, llm=_PlanLLM(), memory=None,
                           mcp=None, human_provider=None, max_iter=4)
        res = ex.run("create note file b1_note")
        d = res.get("decision")
        self.assertIsInstance(d, dict)
        self.assertIn("engine", d)
        self.assertIn("reasoning", d)
        self.assertIn("confidence", d)
        self.assertIn("intent", d)
        self.assertIn("plan_validated", d)
        self.assertIn("steps_total", d)
        self.assertEqual(d["plan_validated"], True)
        self.assertGreaterEqual(d["steps_total"], 1)
        check("planned decision bloki to'liq", d.get("plan_validated") is True)

    def test_fallback_decision_confidence(self):
        # llm=None → fallback reja → confidence 1.0 (Phase 5 kontrakti)
        ex = AgentExecutor(workspace_root=WS, llm=None, memory=None,
                           mcp=None, human_provider=None, max_iter=4)
        res = ex.run("show workspace files")
        d = res.get("decision", {})
        self.assertEqual(d.get("engine"), "fallback")
        self.assertEqual(d.get("confidence"), 1.0)
        check("fallback decision conf=1.0", d.get("confidence") == 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    ok = sum(1 for _, s in _RESULTS if s)
    print(f"\nCHECKS: {ok}/{len(_RESULTS)} " + ("PASS" if ok == len(_RESULTS) else "FAIL"))
    sys.exit(0 if ok == len(_RESULTS) else 1)
