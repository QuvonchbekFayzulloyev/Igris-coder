"""
Roadmap v3 R3 — REAL TASK SUITE (§1 + §5 + §6 + §7)
====================================================
Qamrov (LLM'siz — scripted LLM + real executor + real fs):

  1) FILE CREATE      — task → fayl REAL yaratiladi (harness diff bilan)
  2) FILE MODIFY      — mavjud fayl tahriri (eski kontent -> yangi)
  3) FILE ORGANIZE    — fayllarni papkalarga joylashtirish (move semantikasi)
  4) CODE-GEN+RUN     — .py yoziladi, python_exec bilan ishga tushiriladi,
                        exit code + stdout evidence (§6)
  5) CSV→SUMMARY      — CSV o'qiladi, hisob natijasi summary faylga (§7)
  6) MULTI-FILE       — bir necha fayl/papka bir run'da

Har test REAL fs holatini workspace_harness bilan tekshiradi:
tool ok=true'ga emas, disk daliliga tayanadi (§29 golden rule).

Run: pytest test_r3_real_tasks.py   |   python test_r3_real_tasks.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import AgentExecutor  # noqa: E402
from workspace_harness import WorkspaceHarness  # noqa: E402


# ---------------------------------------------------------------------- #
# Scripted LLM — plan + args deterministik (real LLM yo'q)
# ---------------------------------------------------------------------- #

class _ScriptedPlanLLM:
    """Planned loop uchun deterministik stub.

    complete() SYSTEM promptiga qarab rejim tanlaydi:
      - 'intent/requirement extractor' -> extractor JSON (deliverable = 1-fayl)
      - 'planner'                      -> plan JSON
      - 'tool-caller'                  -> args JSON (detail'dagi fayl nomi)
      - 'finishing step' (CORRECTIVE)  -> yetkazib beriladigan natija JSON
      - 'COMPLETE or INCOMPLETE'       -> 'COMPLETE' (fayl real yozilgan)
      - boshqa                          -> 'bajarildi' matn
    Bu rejimlar real executor prompt kontraktlari bilan mos (§5/§6 testlari).
    """

    def __init__(self, steps: list[dict], content_map: dict | None = None):
        self.plan = {"goal": "scripted", "steps": steps, "engine": "llm"}
        self.content_map = content_map or {}

    def complete(self, prompt, system=None):
        s = (system or "")
        p = (prompt or "")
        import re
        # 1) requirement extractor rejimi — bitta deliverable fayl JSON'i
        if "requirement extractor" in s or "intent/requirement" in s:
            m = re.search(r"`([\w./-]+\.\w+)`", p) or re.search(
                r"([\w-]+\.(?:txt|md|json|csv|py|html|css|js))", p)
            name = m.group(1) if m else "result.txt"
            return json.dumps({"intent": "code", "output_format": "code",
                               "deliverable_name": name,
                               "verbosity": "balanced", "confidence": 0.9})
        # 2) planner rejimi
        if "planner" in s and "tool-caller" not in s:
            return json.dumps(self.plan)
        # 3) verify rejimi — COMPLETE/INCOMPLETE bahosi
        if "COMPLETE or INCOMPLETE" in p:
            return "COMPLETE"
        # 4) finishing/corrective rejimi — REAL deliverable JSON
        if "finishing step" in s or "ACTUAL deliverable" in s:
            m = re.search(r"`([\w./-]+\.\w+)`", p) or re.search(
                r"FILE '([\w./-]+\.\w+)'", p)
            name = m.group(1) if m else "result.txt"
            body = self.content_map.get(name, f"done content for {name}\n")
            return json.dumps({"path": name, "content": body})
        # 5) tool-caller rejimi — args JSON
        m = re.search(r"`([\w./-]+\.\w+)`", p)
        target = m.group(1) if m else "result.txt"
        if "python_exec" in p or "python_exec" in s:
            # python_exec `code` argumentini talab qiladi — yozilgan skriptni
            # runpy.run_path bilan ishga tushiramiz (real run, §6).
            # DIQQAT: sandbox deny-list exec(/eval(/os/subprocess'ni bloklaydi
            # (Dp4) — runpy esa ruxsat etilgan standart modul.
            if not m:
                return json.dumps({"code": "print('no target')"})
            code = f"import runpy\nrunpy.run_path({target!r}, run_name='__main__')\n"
            return json.dumps({"code": code})
        if "write_file" in p or '"path"' in p:
            body = self.content_map.get(target, f"content for {target}\n")
            return json.dumps({"path": target, "content": body})
        if "read_file" in p:
            return json.dumps({"path": target})
        if "list_files" in p:
            return json.dumps({"path": "", "depth": 2})
        return "bajarildi"

    def chat(self, messages, system=None):
        return "bajarildi"


def _mk_ex(h: WorkspaceHarness, llm, **kw) -> AgentExecutor:
    return AgentExecutor(
        workspace_root=h.root, llm=llm, memory=None, mcp=None,
        human_provider=None, checkpoint_dir=h.checkpoint_dir, **kw)


# ---------------------------------------------------------------------- #
# 1) FILE CREATE
# ---------------------------------------------------------------------- #

class TestFileCreate(unittest.TestCase):
    def test_task_creates_real_file(self):
        with WorkspaceHarness() as h:
            steps = [{"id": 1, "title": "Create notes.md", "tools": ["write_file"],
                      "detail": "Create `notes.md` with project notes."}]
            llm = _ScriptedPlanLLM(steps, {"notes.md": "# Project Notes\nreal content\n"})
            ex = _mk_ex(h, llm)
            before = h.snapshot("before")
            res = ex.run("Create notes.md with project notes")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            # §13/§29: REAL fs dalil — fayl diskda va kontent to'liq
            self.assertTrue(h.exists("notes.md"))
            self.assertIn("real content", h.read("notes.md"))
            d = h.diff("before", "after")
            self.assertIn("notes.md", d["created"])
            # size dalili
            rec = after.get("notes.md")
            self.assertGreater(rec.size, 0)
            self.assertNotEqual(rec.sha256, "")


# ---------------------------------------------------------------------- #
# 2) FILE MODIFY
# ---------------------------------------------------------------------- #

class TestFileModify(unittest.TestCase):
    def test_modify_changes_content_hash(self):
        with WorkspaceHarness() as h:
            h.seed({"config.json": '{"env": "dev"}'})
            before = h.snapshot("before")
            steps = [{"id": 1, "title": "Update config.json", "tools": ["write_file"],
                      "detail": "Rewrite `config.json` with production settings."}]
            llm = _ScriptedPlanLLM(steps, {"config.json": '{"env": "production"}'})
            ex = _mk_ex(h, llm)
            res = ex.run("Update config.json with production settings")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            self.assertEqual(h.read("config.json").strip(), '{"env": "production"}')
            d = h.diff("before", "after")
            # MODIFY: fayl yangi emas, KONTENTI o'zgargan (hash farq) — §1
            self.assertNotIn("config.json", d["created"])
            self.assertIn("config.json", d["modified"])
            self.assertEqual(d["summary"]["modified"], 1)


# ---------------------------------------------------------------------- #
# 3) FILE ORGANIZE (move semantikasi)
# ---------------------------------------------------------------------- #

class TestFileOrganize(unittest.TestCase):
    def test_organize_moves_files(self):
        with WorkspaceHarness() as h:
            h.seed({"a.txt": "alpha", "b.txt": "beta", "c.txt": "gamma"})
            before = h.snapshot("before")
            steps = [
                {"id": 1, "title": "Create letters folder file", "tools": ["write_file"],
                 "detail": "Create `letters/a.txt` with moved content."},
                {"id": 2, "title": "Create letters folder file b", "tools": ["write_file"],
                 "detail": "Create `letters/b.txt` with moved content."},
                {"id": 3, "title": "Create digits folder file c", "tools": ["write_file"],
                 "detail": "Create `digits/c.txt` with moved content."},
            ]
            llm = _ScriptedPlanLLM(steps, {
                "letters/a.txt": "alpha", "letters/b.txt": "beta",
                "digits/c.txt": "gamma"})
            ex = _mk_ex(h, llm, max_iter=8)
            res = ex.run("Organize files: a.txt,b.txt into letters/, c.txt into digits/")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            # Yangi joylashuvlar REAL
            self.assertTrue(h.exists("letters/a.txt"))
            self.assertTrue(h.exists("letters/b.txt"))
            self.assertTrue(h.exists("digits/c.txt"))
            d = h.diff("before", "after")
            self.assertIn("letters/a.txt", d["created"])
            self.assertIn("digits/c.txt", d["created"])
            # Kontent saqlangan (move = copy + delete, kontent hash bir xil)
            self.assertEqual(h.read("letters/a.txt"), "alpha")


# ---------------------------------------------------------------------- #
# 4) CODE-GEN + RUN + EXIT CODE (§6)
# ---------------------------------------------------------------------- #

class TestCodeGenRun(unittest.TestCase):
    def test_generated_script_runs_with_exit_zero(self):
        with WorkspaceHarness() as h:
            before = h.snapshot("before")
            steps = [
                {"id": 1, "title": "Write calc script", "tools": ["write_file"],
                 "detail": "Create `calc_r3.py` that prints the sum 2+3."},
                {"id": 2, "title": "Run calc script", "tools": ["python_exec"],
                 "detail": "Execute `calc_r3.py` and confirm it works."},
            ]
            llm = _ScriptedPlanLLM(steps, {
                "calc_r3.py": "print(2 + 3)\n"})
            ex = _mk_ex(h, llm, max_iter=8)
            res = ex.run("Write calc_r3.py that prints 2+3, then run it")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            self.assertTrue(h.exists("calc_r3.py"))
            # §6: run evidence — script TO'G'RI chiqat berishi kerak
            run_steps = [s for s in res.get("steps", []) if s["id"] == 2]
            self.assertTrue(run_steps)
            # python_exec natijasida 5 chiqati bor-yo'qligini tekshiramiz
            step_result = json.dumps(run_steps[0].get("result", {}))
            self.assertIn("5", step_result)
            # script o'zi ham diskda (codegen real)
            self.assertIn("print(2 + 3)", h.read("calc_r3.py"))
            d = h.diff("before", "after")
            self.assertIn("calc_r3.py", d["created"])

    def test_broken_script_surfaces_error_not_ok(self):
        """Xato skript — xato YASHIRILMAYDI: error step yoki errors[] (§29)."""
        with WorkspaceHarness() as h:
            steps = [
                {"id": 1, "title": "Write broken script", "tools": ["write_file"],
                 "detail": "Create `boom.py`."},
                {"id": 2, "title": "Run broken script", "tools": ["python_exec"],
                 "detail": "Execute `boom.py`."},
            ]
            llm = _ScriptedPlanLLM(steps, {"boom.py": "raise ValueError('kaboom')\n"})
            ex = _mk_ex(h, llm, max_iter=8)
            res = ex.run("Write boom.py and run it")
            # run crash QILMASLIGI kerak, lekin xato ko'rinadigan bo'lishi kerak
            self.assertIn(res["status"], ("ok", "partial", "error", "stopped"))
            err_steps = [s for s in res.get("steps", []) if s.get("status") == "error"]
            has_err = bool(res.get("errors")) or bool(err_steps) \
                or "kaboom" in json.dumps(res.get("steps", []))
            self.assertTrue(has_err, "xato yashirildi — §29 buzilishi")


# ---------------------------------------------------------------------- #
# 5) CSV → SUMMARY (§7)
# ---------------------------------------------------------------------- #

class TestCsvToSummary(unittest.TestCase):
    def test_csv_processed_summary_written(self):
        with WorkspaceHarness() as h:
            h.seed({"sales_r3.csv": "id,amount\n1,100\n2,200\n3,300\n"})
            before = h.snapshot("before")
            steps = [
                {"id": 1, "title": "Write summary script", "tools": ["write_file"],
                 "detail": "Create `summarize.py` that reads `sales_r3.csv` and writes `summary.md`."},
                {"id": 2, "title": "Run summary script", "tools": ["python_exec"],
                 "detail": "Execute `summarize.py`."},
            ]
            llm = _ScriptedPlanLLM(steps, {
                "summarize.py":
                    "import csv\n"
                    "rows = list(csv.DictReader(open('sales_r3.csv')))\n"
                    "total = sum(int(r['amount']) for r in rows)\n"
                    "with open('summary.md', 'w') as f:\n"
                    "    f.write(f'# Sales Summary\\n\\nTotal: {total}\\n')\n"
                    "print(f'total={total}')\n"})
            ex = _mk_ex(h, llm, max_iter=8)
            res = ex.run("Read sales_r3.csv and write a summary.md with the total")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            # §7: real data-processing — summary REAL va TO'G'RI
            if h.exists("summary.md"):
                text = h.read("summary.md")
                self.assertIn("600", text)  # 100+200+300
            # run evidence: stdout'da total=600
            all_text = json.dumps(res.get("steps", []))
            self.assertIn("600", all_text)
            d = h.diff("before", "after")
            self.assertIn("summarize.py", d["created"])


# ---------------------------------------------------------------------- #
# 6) MULTI-FILE bir run'da
# ---------------------------------------------------------------------- #

class TestMultiFile(unittest.TestCase):
    def test_multiple_files_created_in_one_run(self):
        with WorkspaceHarness() as h:
            before = h.snapshot("before")
            steps = [
                {"id": 1, "title": "Create index.html", "tools": ["write_file"],
                 "detail": "Create `index.html`."},
                {"id": 2, "title": "Create style.css", "tools": ["write_file"],
                 "detail": "Create `style.css`."},
                {"id": 3, "title": "Create app.js", "tools": ["write_file"],
                 "detail": "Create `app.js`."},
            ]
            llm = _ScriptedPlanLLM(steps, {
                "index.html": "<html>r3</html>", "style.css": "body{}", "app.js": "// app"})
            ex = _mk_ex(h, llm, max_iter=8)
            res = ex.run("Create index.html, style.css and app.js")
            after = h.snapshot("after")

            self.assertIn(res["status"], ("ok", "partial"))
            for f in ("index.html", "style.css", "app.js"):
                self.assertTrue(h.exists(f), f"{f} yozilmagan")
            d = h.diff("before", "after")
            for f in ("index.html", "style.css", "app.js"):
                self.assertIn(f, d["created"])
            self.assertEqual(d["summary"]["created"], 3)


# ---------------------------------------------------------------------- #
# §26 acceptance: requirement matrix bilan yakunlanadi (R1 integratsiya)
# ---------------------------------------------------------------------- #

class TestMatrixBackedAcceptance(unittest.TestCase):
    def test_completion_contract_on_real_task(self):
        """Real task + requirement matrix — completion status REAL fs'dan."""
        with WorkspaceHarness() as h:
            steps = [{"id": 1, "title": "Create deliverable_r3.txt", "tools": ["write_file"],
                      "detail": "Create `deliverable_r3.txt` with the report."}]
            llm = _ScriptedPlanLLM(steps, {"deliverable_r3.txt": "R3 report body\n"})
            ex = _mk_ex(h, llm)
            res = ex.run("Create deliverable_r3.txt with the report")
            # R1 kontrakt: matrix fs evidence bilan
            self.assertIn("completion", res)
            self.assertEqual(res.get("completion"), "complete")
            self.assertTrue(h.exists("deliverable_r3.txt"))


if __name__ == "__main__":
    unittest.main()
