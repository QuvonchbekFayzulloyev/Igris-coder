"""
Roadmap v4 Phase B2+B3 — AGENTIC LOOP + VERIFICATION COMPARISON testlari
=========================================================================
B2 (§9):
  - decision_trace'da har iteratsiyada UNIQUE iteration_id (UUID) bo'ladi
  - action_reason — har iteratsiya qarorining sababi natijada ko'rinadi
  - per-iteration timeout — sekin tool'lar kesiladi (config)
B3 (§10):
  - ExpectedResult mapping (task matnidan deterministik)
  - VerificationComparison{match, score, diff, method} — exact/semantic/numeric
  - compare_all agregat
  - Executor integratsiya: expected mapping + comparison natijada

Run: python test_b2_b3_loop_verification.py | pytest test_b2_b3_loop_verification.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, _test_dir)  # workspace_harness tests/ ichida
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from verification.verification_comparison import (  # noqa: E402
    ExpectedResult, map_expected_from_task, compare_expected_actual,
    compare_all, COMPARISON_EXACT, COMPARISON_SEMANTIC, COMPARISON_NUMERIC,
)
from tools.tool_protocol import (  # noqa: E402
    max_retries_for, is_retryable, validate_output, verify_write_on_disk,
    RETRYABLE_CODES, NON_RETRYABLE_CODES,
)
from workspace_harness import WorkspaceHarness  # noqa: E402


# ====================================================================== #
# B1 — TOOL PROTOCOL
# ====================================================================== #

class TestRetryPolicy(unittest.TestCase):
    def test_table_from_plan(self):
        self.assertEqual(max_retries_for("read_file"), 1)
        self.assertEqual(max_retries_for("write_file"), 2)
        self.assertEqual(max_retries_for("python_exec"), 2)
        self.assertEqual(max_retries_for("web_fetch"), 1)
        self.assertEqual(max_retries_for("delete_file"), 0)

    def test_side_effect_fallback(self):
        self.assertEqual(max_retries_for(side_effect="read_only"), 1)
        self.assertEqual(max_retries_for(side_effect="write"), 2)
        self.assertEqual(max_retries_for(side_effect="unsafe"), 2)

    def test_retryable_codes(self):
        self.assertTrue(is_retryable({"ok": False, "code": 4}))   # timeout
        self.assertTrue(is_retryable({"ok": False, "code": 5}))   # internal
        self.assertFalse(is_retryable({"ok": False, "code": 1}))  # unknown
        self.assertFalse(is_retryable({"ok": False, "code": 2}))  # invalid args
        self.assertFalse(is_retryable({"ok": False, "code": 3}))  # denied
        self.assertFalse(is_retryable({"ok": True}))


class TestOutputSchema(unittest.TestCase):
    def test_ok_result_with_fields(self):
        ok, note = validate_output("write_file", {"ok": True, "path": "a.txt"})
        self.assertTrue(ok, note)

    def test_missing_ok_field(self):
        ok, note = validate_output("write_file", {"path": "a.txt"})
        self.assertFalse(ok)
        self.assertIn("'ok'", note)

    def test_ok_without_required_fields(self):
        ok, note = validate_output("write_file", {"ok": True})
        self.assertFalse(ok)
        self.assertIn("missing fields", note)

    def test_error_without_message(self):
        ok, note = validate_output("write_file", {"ok": False, "code": 5})
        self.assertFalse(ok)
        self.assertIn("error", note)

    def test_unknown_tool_skipped(self):
        ok, note = validate_output("custom_mcp_tool", {"ok": True})
        self.assertTrue(ok)


class TestWritePostVerify(unittest.TestCase):
    def test_written_content_matches(self):
        with WorkspaceHarness() as h:
            # TOOL avval faylni yozgan bo'ladi — verify uni diskda tekshiradi
            h.seed({"a.txt": "hello world"})
            ok, note = verify_write_on_disk(
                h.root, "write_file",
                {"path": "a.txt", "content": "hello world"},
                {"ok": True})
            self.assertTrue(ok, note)

    def test_content_mismatch_detected(self):
        with WorkspaceHarness() as h:
            # fayl boshqa kontent bilan "yozildi" (lying tool simulyatsiyasi)
            h.seed({"a.txt": "DIFFERENT"})
            ok, note = verify_write_on_disk(
                h.root, "write_file",
                {"path": "a.txt", "content": "hello world"},
                {"ok": True})
            self.assertFalse(ok)
            self.assertIn("mismatch", note)

    def test_missing_file_detected(self):
        with WorkspaceHarness() as h:
            ok, note = verify_write_on_disk(
                h.root, "write_file",
                {"path": "ghost.txt", "content": "x"}, {"ok": True})
            self.assertFalse(ok)
            self.assertIn("not written", note)

    def test_empty_file_detected(self):
        with WorkspaceHarness() as h:
            with open(os.path.join(h.root, "e.txt"), "w") as fh:
                fh.write("")
            ok, note = verify_write_on_disk(
                h.root, "write_file", {"path": "e.txt"}, {"ok": True})
            self.assertFalse(ok)
            self.assertIn("empty", note)

    def test_read_tool_neutral(self):
        with WorkspaceHarness() as h:
            ok, note = verify_write_on_disk(
                h.root, "read_file", {"path": "a.txt"}, {"ok": True})
            self.assertIsNone(ok)


# ====================================================================== #
# B3 — VERIFICATION COMPARISON
# ====================================================================== #

class TestExpectedMapping(unittest.TestCase):
    def test_file_and_stdout(self):
        exp = map_expected_from_task("create `calc.py` that prints 5")
        kinds = [(e.kind, e.target, e.value) for e in exp]
        self.assertIn(("file_exists", "calc.py", ""), kinds)
        self.assertIn(("stdout_equals", "", "5"), kinds)
        # numeric method
        se = next(e for e in exp if e.kind == "stdout_equals")
        self.assertEqual(se.method, COMPARISON_NUMERIC)

    def test_sum_of_two(self):
        exp = map_expected_from_task("write sum of 2 and 3 to result.txt")
        se = next(e for e in exp if e.kind == "stdout_equals")
        self.assertEqual(se.value, "5")

    def test_contains_pattern(self):
        exp = map_expected_from_task("create `report.md` containing 'operational'")
        fc = next(e for e in exp if e.kind == "file_contains")
        self.assertEqual(fc.target, "report.md")
        self.assertIn("operational", fc.value)

    def test_no_expectations(self):
        self.assertEqual(map_expected_from_task("just think about it"), [])


class TestComparison(unittest.TestCase):
    def test_numeric_exact_match(self):
        c = compare_expected_actual(
            ExpectedResult(kind="stdout_equals", value="5",
                           method=COMPARISON_NUMERIC),
            {"stdout": "5\n"})
        self.assertTrue(c.match)
        self.assertEqual(c.score, 1.0)

    def test_numeric_mismatch_with_diff(self):
        c = compare_expected_actual(
            ExpectedResult(kind="stdout_equals", value="5",
                           method=COMPARISON_NUMERIC),
            {"stdout": "4\n"})
        self.assertFalse(c.match)
        self.assertIn("expected", c.diff)

    def test_semantic_similarity(self):
        c = compare_expected_actual(
            ExpectedResult(kind="stdout_equals", value="operation completed",
                           method=COMPARISON_SEMANTIC),
            {"stdout": "operation completed successfully"})
        # contains semantic: kutilgan matn stdout ICHIDA — True
        self.assertTrue(c.match)

    def test_semantic_miss(self):
        c = compare_expected_actual(
            ExpectedResult(kind="stdout_equals", value="operation failed",
                           method=COMPARISON_SEMANTIC),
            {"stdout": "everything is great"})
        self.assertFalse(c.match)
        self.assertLess(c.score, 1.0)

    def test_file_exists_via_root(self):
        with WorkspaceHarness() as h:
            h.seed({"out.txt": "data"})
            c = compare_expected_actual(
                ExpectedResult(kind="file_exists", target="out.txt"),
                {"root": h.root})
            self.assertTrue(c.match)

    def test_file_contains_case_insensitive(self):
        with WorkspaceHarness() as h:
            h.seed({"doc.md": "# TITLE\nBody"})
            c = compare_expected_actual(
                ExpectedResult(kind="file_contains", target="doc.md",
                               value="title", method=COMPARISON_SEMANTIC),
                {"root": h.root})
            self.assertTrue(c.match)

    def test_file_missing(self):
        with WorkspaceHarness() as h:
            c = compare_expected_actual(
                ExpectedResult(kind="file_exists", target="ghost.txt"),
                {"root": h.root})
            self.assertFalse(c.match)
            self.assertIn("missing", c.diff)

    def test_compare_all_aggregate(self):
        exps = [ExpectedResult(kind="file_exists", target="a.txt"),
                ExpectedResult(kind="stdout_equals", value="1",
                               method=COMPARISON_NUMERIC)]
        with WorkspaceHarness() as h:
            h.seed({"a.txt": "x"})
            res = compare_all(exps, {"root": h.root, "stdout": "1"})
            self.assertTrue(res["all_match"])
            self.assertEqual(res["score"], 1.0)
            res2 = compare_all(exps, {"root": h.root, "stdout": "2"})
            self.assertFalse(res2["all_match"])
            self.assertLess(res2["score"], 1.0)


# ====================================================================== #
# B2 — EXECUTOR INTEGRATSIYA (iteration UUID + action_reason)
# ====================================================================== #

PLAN = {"goal": "write file", "engine": "llm", "steps": [
    {"id": 1, "title": "write file", "tools": ["write_file"],
     "detail": "create `b2.txt` with hello"}]}


class _NativeLLM:
    """chat_with_tools orqali 2 iteratsiya: write_file → final javob."""

    def __init__(self):
        self.calls = 0

    def chat_with_tools(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return {"content": "",
                    "reasoning": "need to create the file first",
                    "tool_calls": [{"name": "write_file",
                                    "arguments": {"path": "b2.txt",
                                                  "content": "hello"}}]}
        self.final = True
        return {"content": "file created and verified", "tool_calls": []}

    def complete(self, prompt, system=None):
        return "file created"

    def chat(self, messages, system=None):
        return "file created"


class TestExecutorLoopB2(unittest.TestCase):
    def _run_native(self):
        from executor.executor import AgentExecutor
        with WorkspaceHarness() as h:
            ex = AgentExecutor(
                workspace_root=h.root, llm=_NativeLLM(), memory=None,
                mcp=None, human_provider=None,
                checkpoint_dir=h.checkpoint_dir, max_iter=4,
                max_tool_calls=10)
            res = ex.run_native("create b2.txt with hello")
            res["_harness"] = h
            return res

    def test_iteration_ids_unique_in_trace(self):
        res = self._run_native()
        trace = res.get("decision_trace") or []
        self.assertGreaterEqual(len(trace), 2)
        ids = [t.get("iteration_id") for t in trace]
        self.assertTrue(all(ids), "har iteratsiyada iteration_id bo'lishi kerak")
        self.assertEqual(len(set(ids)), len(ids), "UUID'lar TAKRORLANMAS bo'lishi kerak")

    def test_action_reason_present(self):
        res = self._run_native()
        trace = res.get("decision_trace") or []
        self.assertTrue(all("action_reason" in t for t in trace),
                        f"action_reason yo'q: {trace}")
        self.assertIn("file", str(trace[-1]["action_reason"]).lower()
                      + str(trace[0]["action_reason"]).lower())


class TestPerIterationTimeout(unittest.TestCase):
    """B2 (§9): sekin tool'siz iteratsiya kesiladi (default 120s — config)."""

    def test_timeout_without_tools_stops(self):
        from executor.executor import AgentExecutor

        class _StuckLLM:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools=None):
                self.calls += 1
                time.sleep(0.3)
                return {"content": "hmm, thinking...", "tool_calls": []}

            def complete(self, prompt, system=None):
                return "thinking"

            def chat(self, messages, system=None):
                return "thinking"

        with WorkspaceHarness() as h:
            ex = AgentExecutor(
                workspace_root=h.root, llm=_StuckLLM(), memory=None,
                mcp=None, human_provider=None,
                checkpoint_dir=h.checkpoint_dir, max_iter=5,
                max_tool_calls=10)
            ex.per_iteration_timeout_s = 0.2
            res = ex.run_native("do something")
            self.assertEqual(res.get("status"), "stopped")
            self.assertEqual(res.get("engine"), "tool-calling",
                             "timeout planned fallback'ga o'tmasligi kerak")
            actions = [r.get("action") for r in (res.get("recovery_events") or [])]
            self.assertIn("iteration_timeout", actions)
            self.assertIn("timeout", (res.get("final") or "").lower())

    def test_iteration_with_tool_not_killed(self):
        """Tool bajarilgan iteratsiya timeout'dan o'tsa ham kesilmaydi —
        keyingi iteratsiya yakunlanishi mumkin."""
        from executor.executor import AgentExecutor

        class _SlowToolLLM:
            def __init__(self):
                self.calls = 0

            def chat_with_tools(self, messages, tools=None):
                self.calls += 1
                time.sleep(0.3)
                if self.calls == 1:
                    return {"content": "", "reasoning": "writing",
                            "tool_calls": [{"name": "write_file",
                                            "arguments": {"path": "t.txt",
                                                          "content": "x"}}]}
                return {"content": "done", "tool_calls": []}

            def complete(self, prompt, system=None):
                return "done"

            def chat(self, messages, system=None):
                return "done"

        with WorkspaceHarness() as h:
            ex = AgentExecutor(
                workspace_root=h.root, llm=_SlowToolLLM(), memory=None,
                mcp=None, human_provider=None,
                checkpoint_dir=h.checkpoint_dir, max_iter=5,
                max_tool_calls=10)
            ex.per_iteration_timeout_s = 0.2
            res = ex.run_native("create t.txt")
            # 2-iteratsiya (final) timeout kesadi — lekin fayl YOZILGAN
            # bo'lishi kerak (1-iteratsiya tool'i bajarildi)
            self.assertTrue(os.path.exists(os.path.join(h.root, "t.txt")),
                            "tool bajarilgan iteratsiya kesilmasligi kerak edi")


class TestExecutorB3Integration(unittest.TestCase):
    """B3: planned run'da expected_comparison natijada bo'ladi."""

    def test_expected_comparison_in_result(self):
        import json as _json
        from executor.executor import AgentExecutor

        plan = {"goal": "create calc.py that prints 5", "engine": "llm",
                "steps": [{"id": 1, "title": "write script",
                           "tools": ["write_file"],
                           "detail": "create `calc.py` that prints 5"}]}

        class _LLM:
            def complete(self, prompt, system=None):
                s = (system or "")
                p = (prompt or "")
                if "requirement extractor" in s:
                    return _json.dumps({"intent": "code",
                                        "output_format": "code",
                                        "deliverable_name": "calc.py",
                                        "verbosity": "balanced",
                                        "confidence": 0.9})
                if "planner" in s and "tool-caller" not in s:
                    return _json.dumps(plan)
                if "COMPLETE or INCOMPLETE" in p:
                    return "COMPLETE"
                if "finishing step" in s:
                    return _json.dumps({"path": "calc.py", "content": "x"})
                if "write_file" in p or '"path"' in p:
                    return _json.dumps({"path": "calc.py",
                                        "content": "print(2 + 3)"})
                return "bajarildi"

            def chat(self, messages, system=None):
                return "bajarildi"

        with WorkspaceHarness() as h:
            ex = AgentExecutor(workspace_root=h.root, llm=_LLM(), memory=None,
                               mcp=None, human_provider=None,
                               checkpoint_dir=h.checkpoint_dir, max_iter=8,
                               max_tool_calls=10)
            res = ex.run("create calc.py that prints 5")
            cmp_res = res.get("expected_comparison")
            self.assertIsNotNone(cmp_res,
                                 "expected_comparison natijada bo'lishi kerak")
            self.assertIn("all_match", cmp_res)
            self.assertIn("comparisons", cmp_res)
            # calc.py 5 emas 5 chiqaradi (2+3) — all_match True bo'lishi kerak
            self.assertTrue(cmp_res["all_match"],
                            str(cmp_res["comparisons"])[:200])


if __name__ == "__main__":
    unittest.main()
