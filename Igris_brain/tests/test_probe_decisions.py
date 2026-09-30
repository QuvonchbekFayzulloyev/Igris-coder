"""
IGRIS — probe_decisions v2 birlik testlari (S2 kengaytirish)
============================================================
LLM/Ollama YO'Q — faqat deterministik qismlar:
  - select_tasks (all / id-list / category:X / xato holatlari)
  - score_task (outcome kredit, oracle ustuvorligi, guard jarimalari)
  - oracle'lar (run-oracle to'g'ri/yolg'on yechimni ajratadi)
  - _scan_workspace (os.walk — nested/MCP fayllar ko'rinadi)
  - hisobot kontrakti (schema_version, categories, UI backend.ts bilan mos)
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from monitor import probe_decisions as pd


def _base_trace(**over) -> dict:
    trace = {
        "tool_calls": [],
        "plan_steps": [],
        "final_text": "",
        "files_joined": "",
        "retries": 0,
        "status": "ok",
        "files_present": [],
        "files_created": [],
        "workspace": "",
    }
    trace.update(over)
    return trace


def _task(tid: str) -> dict:
    return next(t for t in pd.TASKS if t["id"] == tid)


class TestTaskCatalog(unittest.TestCase):
    def test_21_tasks_six_categories(self):
        self.assertEqual(len(pd.TASKS), 21)
        self.assertEqual(len({t["id"] for t in pd.TASKS}), 21, "duplicate ids")
        cats = {t["category"] for t in pd.TASKS}
        self.assertEqual(cats, set(pd.CATEGORIES))
        for t in pd.TASKS:
            self.assertIn(t["category"], pd.CATEGORIES)
            self.assertTrue(t.get("task"), t["id"])
            self.assertTrue(t.get("notes"), t["id"])

    def test_category_counts(self):
        by_cat = {}
        for t in pd.TASKS:
            by_cat.setdefault(t["category"], []).append(t["id"])
        self.assertEqual(len(by_cat["code"]), 6)
        self.assertEqual(len(by_cat["data"]), 3)
        self.assertEqual(len(by_cat["multi"]), 4)
        self.assertEqual(len(by_cat["web"]), 2)
        self.assertEqual(len(by_cat["draw"]), 2)
        self.assertEqual(len(by_cat["robustness"]), 4)

    def test_legacy_ids_preserved(self):
        """Eski 4 task id'lari saqlangan — server/UI/eski hisobotlar mos."""
        for tid in ("code_csv", "multi_notes", "draw_apple", "fix_code"):
            self.assertIn(tid, {t["id"] for t in pd.TASKS})

    def test_fix_code_keeps_buggy_setup(self):
        t = _task("fix_code")
        ws = tempfile.mkdtemp()
        t["setup"](ws)
        text = open(os.path.join(ws, "buggy.py"), encoding="utf-8").read()
        self.assertIn("print(x)", text)


class TestSelectTasks(unittest.TestCase):
    def test_all(self):
        self.assertEqual(len(pd.select_tasks("all")), 21)

    def test_id_list(self):
        sel = pd.select_tasks("fix_code,code_fib")
        self.assertEqual([t["id"] for t in sel], ["fix_code", "code_fib"])

    def test_category_filter(self):
        self.assertEqual(len(pd.select_tasks("category:code")), 6)
        self.assertEqual(len(pd.select_tasks("category:draw")), 2)
        self.assertEqual(
            {t["category"] for t in pd.select_tasks("category:data")}, {"data"})

    def test_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            pd.select_tasks("nope")

    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError):
            pd.select_tasks("category:zzz")


class TestOracleHelpers(unittest.TestCase):
    def test_run_python_print_ok_and_fail(self):
        oracle = pd._oracle_run_python_print("42", "answer.py")
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "answer.py"), "w", encoding="utf-8") as fh:
            fh.write("print(42)\n")
        self.assertTrue(oracle({}, ws)["ok"])
        with open(os.path.join(ws, "answer.py"), "w", encoding="utf-8") as fh:
            fh.write("print(41)\n")
        v = oracle({}, ws)
        self.assertFalse(v["ok"])
        self.assertIn("41", v["detail"])

    def test_run_python_missing_file(self):
        oracle = pd._oracle_run_python_print("x", "nope.py")
        v = oracle({}, tempfile.mkdtemp())
        self.assertFalse(v["ok"])
        self.assertIn("not written", v["detail"])

    def test_run_python_crash_reported(self):
        oracle = pd._oracle_run_python_print("x", "boom.py")
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "boom.py"), "w", encoding="utf-8") as fh:
            fh.write("raise ValueError('kaboom')\n")
        v = oracle({}, ws)
        self.assertFalse(v["ok"])
        self.assertIn("exited", v["detail"])

    def test_run_python_argv_and_stdin(self):
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "g.py"), "w", encoding="utf-8") as fh:
            fh.write("import sys\nprint('Hello, ' + sys.argv[1] + '!')\n")
        v = pd._oracle_run_python_print("Hello, Igris!", "g.py", argv=("Igris",))({}, ws)
        self.assertTrue(v["ok"])
        with open(os.path.join(ws, "s.py"), "w", encoding="utf-8") as fh:
            fh.write("import sys\nparts = sys.stdin.read().split()\nprint(int(parts[0]) + int(parts[1]))\n")
        v = pd._oracle_run_python_print("5", "s.py", stdin_text="2\n3\n")({}, ws)
        self.assertTrue(v["ok"])

    def test_file_contains_oracle(self):
        oracle = pd._oracle_file_contains("out.txt", ("a", "b"))
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "out.txt"), "w", encoding="utf-8") as fh:
            fh.write("a\nb\n")
        self.assertTrue(oracle({}, ws)["ok"])
        with open(os.path.join(ws, "out.txt"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        v = oracle({}, ws)
        self.assertFalse(v["ok"])
        self.assertIn("b", v["detail"])

    def test_json_oracle(self):
        ws = tempfile.mkdtemp()
        with open(os.path.join(ws, "items.json"), "w", encoding="utf-8") as fh:
            fh.write('[{"name": "a"}, {"name": "b"}, {"name": "c"}]')
        self.assertTrue(pd._oracle_json_c({}, ws)["ok"])
        with open(os.path.join(ws, "items.json"), "w", encoding="utf-8") as fh:
            fh.write('[{"name": "a"}]')
        self.assertFalse(pd._oracle_json_c({}, ws)["ok"])
        with open(os.path.join(ws, "items.json"), "w", encoding="utf-8") as fh:
            fh.write("not json{")
        self.assertFalse(pd._oracle_json_c({}, ws)["ok"])

    def test_data_join_expected_value_27(self):
        """Kanonik yechim oracle'dan O'TADI — kutilgan qiymat (27) to'g'ri."""
        t = _task("data_multi_join")
        ws = tempfile.mkdtemp()
        t["setup"](ws)
        with open(os.path.join(ws, "report.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "import csv\n"
                "sales = list(csv.DictReader(open('sales.csv')))\n"
                "prices = {r['product']: int(r['cost']) for r in csv.DictReader(open('prices.csv'))}\n"
                "print(sum(int(r['qty']) * (int(r['price']) - prices[r['product']]) for r in sales))\n"
            )
        v = t["oracle"]({}, ws)
        self.assertTrue(v["ok"], v)


class TestScoreTask(unittest.TestCase):
    def test_outcome_full_run_with_markers(self):
        s = pd.score_task(_task("multi_notes"), _base_trace(
            status="ok", final_text="done", files_joined="todo.txt::x\ndone.txt::y"))
        self.assertEqual(s["outcome"], 1.0)

    def test_outcome_partial_run_capped(self):
        """Partial + markerlar to'liq: 0.4*0.8(credit) + 0.6*1.0(markers) = 0.92."""
        s = pd.score_task(_task("multi_notes"), _base_trace(
            status="partial", final_text="done", files_joined="todo.txt::x\ndone.txt::y"))
        self.assertEqual(s["outcome"], 0.92)

    def test_outcome_no_markers_bonus(self):
        """Bajarilgan run + marker topilmasa (oracle yo'q) — A3 branch: 0.6*credit."""
        s = pd.score_task(_task("multi_notes"), _base_trace(
            status="ok", final_text="done", files_joined="other.txt::z"))
        self.assertEqual(s["outcome"], 0.6)

    def test_oracle_overrides_marker_logic(self):
        """Oracle bor bo'lsa: outcome = 0.4*credit + 0.6*oracle (stub bilan)."""
        t = dict(_task("code_fib"))
        t["oracle"] = lambda res, ws: {"ok": True, "detail": "stub ok"}
        s = pd.score_task(t, _base_trace(status="ok", final_text="written",
                                         files_joined="fib.py::..."))
        self.assertEqual(s["outcome"], 1.0)  # 0.4*1.0 + 0.6*1.0
        # oracle fail, lekin run bajargan: 0.4*1.0 + 0.6*0.0
        t2 = dict(_task("code_fib"))
        t2["oracle"] = lambda res, ws: {"ok": False, "detail": "nope"}
        s2 = pd.score_task(t2, _base_trace(status="ok", final_text="written",
                                           files_joined="fib.py::..."))
        self.assertEqual(s2["outcome"], 0.4)

    def test_oracle_fail_with_partial_run(self):
        """Oracle fail + partial run: 0.4*0.8 + 0.6*0.0 = 0.32."""
        t = dict(_task("code_fib"))
        t["oracle"] = lambda res, ws: {"ok": False, "detail": "x"}
        s = pd.score_task(t, _base_trace(status="partial", final_text="tried",
                                         files_joined="fib.py::..."))
        self.assertEqual(s["outcome"], 0.32)

    def test_guard_keep_file_violation(self):
        t = _task("code_readonly_guard")
        s = pd.score_task(t, _base_trace(
            status="ok", final_text="env is probe",
            files_present=["other.txt"], files_created=[]))
        # marker 1/1 + credit 1.0 = 1.0, guard jarimasi x2 (keep_files +
        # must_not_create_file yo'q — faqat keep buzildi): 1.0*(1-0.5) = 0.5
        self.assertEqual(s["outcome"], 0.5)

    def test_guard_must_not_create_file(self):
        """Javob-to'liq (marker 1.0) + fayl yaratgan: 1.0 * (1-0.5) = 0.5."""
        t = _task("web_fetch_title")
        s = pd.score_task(t, _base_trace(
            status="ok", final_text="title is Example Domain",
            files_present=["saved_page.html"], files_created=["saved_page.html"]))
        self.assertEqual(s["outcome"], 0.5)

    def test_guard_ok_no_violation(self):
        t = _task("code_readonly_guard")
        s = pd.score_task(t, _base_trace(
            status="ok", final_text="env is probe",
            files_present=["config.json"], files_created=[]))
        self.assertEqual(s["outcome"], 1.0)

    def test_unknown_tool_penalized(self):
        calls = [{"tool": "frobnicate", "ok": False, "error": "Unknown tool: frobnicate"}]
        s = pd.score_task(_task("multi_notes"), _base_trace(tool_calls=calls))
        # 1 - 0.1(failure) - 0.15(unknown) = 0.75
        self.assertEqual(s["tool_selection"], 0.75)

    def test_bounds_and_determinism(self):
        t = _task("code_csv")
        tr = _base_trace(tool_calls=[{"tool": "write_file", "ok": True, "args": {"path": "a.py"}}],
                         plan_steps=[{"id": 1}], final_text="x" * 100, retries=1)
        s1 = pd.score_task(t, tr)
        s2 = pd.score_task(t, tr)
        self.assertEqual(s1, s2)
        for v in s1.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)


class TestScanWorkspace(unittest.TestCase):
    def test_walk_finds_nested_and_mcp_files(self):
        ws = tempfile.mkdtemp()
        os.makedirs(os.path.join(ws, "docs", "2026"))
        open(os.path.join(ws, "top.txt"), "w").close()
        open(os.path.join(ws, "docs", "2026", "deep.md"), "w").close()
        open(os.path.join(ws, "mcp_written.png"), "w").close()
        found = pd._scan_workspace(ws)
        self.assertIn("top.txt", found)
        self.assertIn("docs/2026/deep.md", found)
        self.assertIn("mcp_written.png", found)


class TestRunTaskTrace(unittest.TestCase):
    def test_trace_records_files_created_and_signals(self):
        """run_task executor crashida ham toza trace qaytaradi (fail-safe)."""
        t = dict(_task("code_fib"))
        t["setup"] = lambda ws: None

        class _Boom:
            def __init__(self, **kw):
                raise RuntimeError("executor unavailable")

        import executor.executor as ex_mod
        orig = ex_mod.AgentExecutor
        ex_mod.AgentExecutor = _Boom
        try:
            r = pd.run_task({"llm": None}, t, tempfile.mkdtemp(), bridge=object())
        finally:
            ex_mod.AgentExecutor = orig
        self.assertEqual(r["trace"]["status"], "error")
        self.assertIn("CRASH", r["trace"]["final_text"])
        self.assertIn("id", r)
        self.assertIn("category", r)

    def test_score_attached_to_result(self):
        t = dict(_task("code_fib"))
        t["setup"] = lambda ws: None

        class _Boom:
            def __init__(self, **kw):
                raise RuntimeError("x")

        import executor.executor as ex_mod
        orig = ex_mod.AgentExecutor
        ex_mod.AgentExecutor = _Boom
        try:
            r = pd.run_task({"llm": None}, t, tempfile.mkdtemp(), bridge=object())
        finally:
            ex_mod.AgentExecutor = orig
        self.assertIn("scores", r)
        self.assertEqual(r["category"], "code")


class TestReportContract(unittest.TestCase):
    def test_select_and_aggregate_shape(self):
        """UI (backend.ts ProbeReport) bilan mos: tasks[].scores + aggregate."""
        sel = pd.select_tasks("all")
        agg = {}
        for k in ("tool_selection", "args_correctness", "reasoning", "recovery", "outcome"):
            vals = [pd.score_task(t, _base_trace(status="ok", final_text="x"))[k] for t in sel]
            agg[k] = round(sum(vals) / len(vals), 2)
        report = {"schema_version": pd.SCHEMA_VERSION, "model": "test",
                  "tasks": [{"id": t["id"], "category": t["category"],
                             "task": t["task"][:90], "trace": {}, "scores":
                             pd.score_task(t, _base_trace(status="ok", final_text="x"))}
                            for t in sel],
                  "aggregate": agg}
        # UI ProbeScores maydonlari
        for t in report["tasks"]:
            self.assertEqual(set(t["scores"].keys()),
                             {"tool_selection", "args_correctness", "reasoning",
                              "recovery", "outcome"})
        # kategoriya agregati
        cats = {}
        for cat in pd.CATEGORIES:
            ct = [x for x in report["tasks"] if x["category"] == cat]
            cats[cat] = {"n": len(ct),
                         "outcome": round(sum(x["scores"]["outcome"] for x in ct) / len(ct), 2)}
        self.assertEqual(sum(c["n"] for c in cats.values()), 21)

    def test_report_json_round_trip(self):
        """Trace'dagi oracle/guard maydonlari JSON-serializatsiya bo'lishi kerak.

        run_task real workspace'da score_task orqali trace['oracle']'ni yozadi;
        shu yerda biz shu yakuniy holatni simulyatsiya qilib JSON'ga solamiz.
        """
        t = _task("multi_notes")  # oracle yo'q — trace'dagi kalit o'zgarmaydi
        trace = _base_trace(status="ok", final_text="ok", files_present=["todo.txt"])
        trace["oracle"] = {"ok": True, "detail": "matched"}
        trace["guard_violations"] = []
        r = {"id": t["id"], "category": t["category"], "trace": trace,
             "scores": pd.score_task(t, trace)}
        blob = json.dumps(r, ensure_ascii=False)
        back = json.loads(blob)
        self.assertEqual(back["trace"]["oracle"]["ok"], True)
        self.assertIn("outcome", back["scores"])

    def test_trace_without_oracle_key_stays_clean(self):
        """Oracle yo'q taskda trace'ga oracle kaliti yozilmaydi (UI mos)."""
        t = _task("multi_notes")
        trace = _base_trace(status="ok", final_text="done")
        pd.score_task(t, trace)
        self.assertNotIn("oracle", trace)
        self.assertNotIn("guard_violations", trace)


if __name__ == "__main__":
    unittest.main()
