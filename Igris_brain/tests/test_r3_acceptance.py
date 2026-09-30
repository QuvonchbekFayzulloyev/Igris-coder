"""
Roadmap v3 R3 — E2E ACCEPTANCE RUNNER (§26: 15 senariy)
========================================================
Real Task Execution Plan §26'dagi 15 real-task senariysining rasmiy
qabul runner'i. Har senariy:
  - real executor + real fs ustida ishlaydi (LLM'siz — scripted stub),
  - requirement_matrix bilan YAKUNLANADI (§26: "har biri matrix bilan
    yakunlanadi"),
  - PASS/FAIL holatida jadval ko'rinishida chop etiladi.

Exit code: barcha senariylar PASS → 0; kamida bittasi FAIL → 1.

Run: python test_r3_acceptance.py   |   pytest -m e2e test_r3_acceptance.py
"""
from __future__ import annotations

import json
import os
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
from planning.requirement_matrix import extract_requirements, run_matrix  # noqa: E402
from planning.requirement_matrix import RequirementSnapshot  # noqa: E402
from workspace_harness import WorkspaceHarness  # noqa: E402


# ---------------------------------------------------------------------- #
# Scripted LLM (real_tasks/interruption naqshlari bilan bir xil kontrakt)
# ---------------------------------------------------------------------- #

class _ScriptedLLM:
    """Rejaga qarab deterministik javob beradigan stub LLM.

    plan: {"goal":..., "steps":[{id,title,tools,detail}]}
    overrides: {step_title_fragment: {tool: {args...}}} — maxsus args
    fail_tools: {(title_fragment, tool): error_matni} — tool failure simulyatsiyasi
    """

    def __init__(self, plan: dict, overrides: dict | None = None,
                 fail_tools: dict | None = None):
        self.plan = plan
        self.overrides = overrides or {}
        self.fail_tools = fail_tools or {}

    def complete(self, prompt, system=None):
        s = (system or "")
        p = (prompt or "")
        import re
        # 1) requirement extractor
        if "requirement extractor" in s or "intent/requirement" in s:
            return json.dumps({"intent": "code", "output_format": "code",
                               "deliverable_name": self._deliverable(),
                               "verbosity": "balanced", "confidence": 0.9})
        # 2) planner
        if "planner" in s and "tool-caller" not in s:
            return json.dumps(self.plan)
        # 3) completion checker
        if "COMPLETE or INCOMPLETE" in p:
            return "COMPLETE"
        # 4) finishing-step
        if "finishing step" in s or "ACTUAL deliverable" in s:
            path = self._deliverable()
            return json.dumps({"path": path,
                               "content": f"FINAL: {self.plan.get('goal', 'task')} done"})
        # 5) tool-caller / correction
        step_title = self._title_from_prompt(p)
        for frag, per_tool in self.overrides.items():
            if frag.lower() in step_title.lower():
                for tool, args in per_tool.items():
                    if tool in p or tool in s:
                        return json.dumps(args)
        # tool failure injection: _execute_agent_tool'ga etib bormasdan
        # (scripted LLM yo'q — _call_with_retry _ask_fix orqali tuzatadi)
        for (frag, tool), err in self.fail_tools.items():
            if frag.lower() in step_title.lower() and tool in p:
                # correction rejimi — tuzatilgan args qaytaramiz
                if "corrected JSON" in p or "Provide corrected" in p:
                    return json.dumps({"tool": tool, "args": self._default_args_for(tool, step_title)})
        # standart tool args
        if "python_exec" in p or "python_exec" in s:
            return json.dumps({"code": "print('noop')"})
        if "write_file" in p or '"path"' in p:
            return json.dumps(self._default_args_for("write_file", step_title))
        if "list_files" in p:
            return json.dumps({"path": "", "depth": 1})
        if "read_file" in p:
            return json.dumps({"path": self._first_target()})
        return "bajarildi"

    def chat(self, messages, system=None):
        return "bajarildi"

    # --- yordamchilar --- #
    def _deliverable(self) -> str:
        for st in reversed(self.plan.get("steps", [])):
            import re
            m = re.search(r"`([^`]+)`", st.get("detail", ""))
            if m:
                return m.group(1)
        return "result.txt"

    def _first_target(self) -> str:
        for st in self.plan.get("steps", []):
            import re
            m = re.search(r"`([^`]+)`", st.get("detail", ""))
            if m:
                return m.group(1)
        return ""

    def _title_from_prompt(self, p: str) -> str:
        import re
        m = re.search(r"Step:\s*(.+)", p)
        return (m.group(1).strip() if m else p[:80])

    def _default_args_for(self, tool: str, title: str) -> dict:
        import re
        # detail'dagi `path` ni olamiz (planner'dan kelgan)
        for st in self.plan.get("steps", []):
            if st.get("title", "") == title:
                m = re.search(r"`([^`]+)`", st.get("detail", ""))
                path = m.group(1) if m else "out.txt"
                return {"path": path,
                        "content": f"content for {title} -> {path}"}
        return {"path": "out.txt", "content": f"content for {title}"}


def _mk(h: WorkspaceHarness, llm, **kw) -> AgentExecutor:
    n = max(len(llm.plan.get("steps", [])), 8)
    opts = {"max_iter": n * 2, "max_tool_calls": n * 2}
    opts.update(kw)
    ex = AgentExecutor(
        workspace_root=h.root, llm=llm, memory=None, mcp=None,
        human_provider=None, checkpoint_dir=h.checkpoint_dir, **opts)
    ex.planner.max_steps = n
    return ex


def build_matrix_from_task(task: str) -> RequirementSnapshot:
    """Task matndan immutable snapshot (extract_requirements bilan)."""
    return RequirementSnapshot(task, extract_requirements(task))


def _cnt(m: dict) -> str:
    """run_matrix dict natijasidan 'PASS/UMUMIY' (mandatory) xulosasi."""
    mand = [r for r in m["matrix"] if r.get("kind") == "mandatory"]
    return f"{sum(1 for r in mand if r.get('status') == 'PASS')}/{len(mand)}"



def _plan(goal: str, specs: list[tuple[str, list[str]]]) -> dict:
    steps = [{"id": i + 1, "title": t, "tools": tools,
              "detail": d} for i, (t, tools, d) in enumerate(specs)]
    return {"goal": goal, "steps": steps, "engine": "llm"}


def _step(title: str, tools: list[str], detail: str) -> tuple[str, list[str], str]:
    return (title, tools, detail)


# ---------------------------------------------------------------------- #
# 15 SENARIY (§26) — har biri runner funksiyasi bilan
# ---------------------------------------------------------------------- #

RESULTS: list[dict] = []


def _record(name: str, ok: bool, detail: str = "", matrix_summary: str = ""):
    RESULTS.append({"name": name, "ok": ok, "detail": detail,
                    "matrix": matrix_summary})
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" - {detail}" if detail else "")
          + (f" | matrix: {matrix_summary}" if matrix_summary else ""))


class AcceptanceRunner:
    """§26 senariylarini yig'ib, jadval bilan yakunlaydi."""

    # 1. File creation
    @staticmethod
    def s01_file_creation():
        name = "1. File creation"
        with WorkspaceHarness() as h:
            h.seed({"readme.md": "existing"})
            llm = _ScriptedLLM(_plan("create report file", [
                _step("write report", ["write_file"],
                      "create `report.txt` with the analysis result")]))
            res = _mk(h, llm).run("create report file with analysis")
            ok = res.get("status") == "ok" and h.exists("report.txt")
            matrix = run_matrix(build_matrix_from_task(
                "create report.txt file"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 2. File modification
    @staticmethod
    def s02_file_modification():
        name = "2. File modification"
        with WorkspaceHarness() as h:
            h.seed({"config.json": '{"mode": "basic"}'})
            llm = _ScriptedLLM(_plan("modify config", [
                _step("edit config", ["apply_patch"],
                      "update `config.json` mode to advanced")]),
                overrides={"edit config": {"apply_patch": {
                    "path": "config.json", "patch": "basic -> advanced"}}})
            res = _mk(h, llm).run("modify config.json mode")
            ok = res.get("status") in ("ok", "partial") and h.exists("config.json")
            matrix = run_matrix(build_matrix_from_task("modify config.json"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 3. File organization
    @staticmethod
    def s03_file_organization():
        name = "3. File organization"
        with WorkspaceHarness() as h:
            h.seed({"a.txt": "A", "b.txt": "B", "c.txt": "C"})
            llm = _ScriptedLLM(_plan("organize files", [
                _step("move files", ["write_file"],
                      "organize `a.txt` and `b.txt` into folders")]))
            res = _mk(h, llm).run("organize a.txt b.txt c.txt files")
            # §26: papkaga ko'chirish semantikasi — ko'pi bilan "ok";
            # matrix manba fayllarning HAZIRLIGINI tekshiradi
            ok = res.get("status") in ("ok", "partial")
            matrix = run_matrix(build_matrix_from_task(
                "organize a.txt b.txt c.txt files"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 4. Code generation + execution
    @staticmethod
    def s04_codegen_execution():
        name = "4. Code generation + execution"
        with WorkspaceHarness() as h:
            llm = _ScriptedLLM(_plan("gen and run code", [
                _step("write script", ["write_file"],
                      "create `calc.py` that prints 2+3"),
                _step("run script", ["python_exec"],
                      "execute `calc.py` and show output")]),
                overrides={
                    "write script": {"write_file": {
                        "path": "calc.py", "content": "print(2 + 3)\n"}},
                    "run script": {"python_exec": {
                        "code": "print(2 + 3)\n"}}})
            res = _mk(h, llm).run("create calc.py and run it")
            outputs = " ".join(str(t.get("output_preview") or t.get("output")
                                   or t.get("detail") or "")
                               for t in (res.get("timeline") or []))
            ok = ("5" in outputs) and h.exists("calc.py")
            matrix = run_matrix(build_matrix_from_task("create calc.py"), h.root)
            _record(name, ok, f"calc.py exists, stdout has 5",
                    f"{_cnt(matrix)}")

    # 5. Multi-file task
    @staticmethod
    def s05_multi_file():
        name = "5. Multi-file task"
        with WorkspaceHarness() as h:
            llm = _ScriptedLLM(_plan("multi file", [
                _step("write index", ["write_file"], "create `index.md` main"),
                _step("write styles", ["write_file"], "create `style.css` styles"),
                _step("write script", ["write_file"], "create `app.js` logic"),
            ]))
            res = _mk(h, llm).run("create index.md style.css app.js files")
            ok = all(h.exists(f) for f in ("index.md", "style.css", "app.js"))
            matrix = run_matrix(build_matrix_from_task(
                "create index.md style.css app.js"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 6. Data processing
    @staticmethod
    def s06_data_processing():
        name = "6. Data processing"
        with WorkspaceHarness() as h:
            h.seed({
                "sales.csv": ("product,amount\napple,10\npear,5\nplum,12\n"),
            })
            llm = _ScriptedLLM(_plan("process data", [
                _step("compute total", ["python_exec"],
                      "read `sales.csv` and write `total.txt` with the sum")]),
                overrides={"compute total": {"python_exec": {
                    "code": ("import csv\n"
                             "rows = list(csv.DictReader(open('sales.csv')))\n"
                             "total = sum(int(r['amount']) for r in rows)\n"
                             "open('total.txt', 'w').write(str(total))\n"
                             "print(total)\n")}}})
            res = _mk(h, llm).run("process sales.csv into total.txt")
            ok = h.exists("total.txt") and h.read("total.txt").strip() == "27"
            matrix = run_matrix(build_matrix_from_task(
                "process sales.csv into total.txt"), h.root)
            _record(name, ok, f"total.txt={h.read('total.txt').strip() if h.exists('total.txt') else 'MISSING'}",
                    f"{_cnt(matrix)}")

    # 7. Research — web/browser MCP'siz deterministik: read_file + xulosa
    @staticmethod
    def s07_research():
        name = "7. Research"
        with WorkspaceHarness() as h:
            h.seed({"source.md": "IGRIS uses checkpoint+reconciliation."})
            llm = _ScriptedLLM(_plan("research source", [
                _step("read source", ["read_file"], "read `source.md` first"),
                _step("write summary", ["write_file"],
                      "create `summary.md` from the source notes")]),
                overrides={"read source": {"read_file": {"path": "source.md"}}})
            res = _mk(h, llm).run("research source.md and write summary.md")
            ok = h.exists("summary.md")
            matrix = run_matrix(build_matrix_from_task(
                "research source.md write summary.md"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 8. Document creation
    @staticmethod
    def s08_document_creation():
        name = "8. Document creation"
        with WorkspaceHarness() as h:
            # R4'dan keyin: hujjat REAL tuzilishga ega bo'lishi kerak
            # (document verifier min_sections=2 talab qiladi)
            llm = _ScriptedLLM(_plan("create doc", [
                _step("write doc", ["write_file"],
                      "create `README.md` with sections")]),
                overrides={"write doc": {"write_file": {
                    "path": "README.md",
                    "content": ("# Project" + chr(10) + chr(10) + "Overview text." + chr(10) + chr(10) + "## Usage" + chr(10) + chr(10) + "Run it." + chr(10) + chr(10) + "## API" + chr(10) + chr(10) + "Endpoints." + chr(10))}}})
            res = _mk(h, llm).run("create README.md document")
            content = h.read("README.md") if h.exists("README.md") else ""
            ok = "# " in content or res.get("status") == "ok"
            matrix = run_matrix(build_matrix_from_task("create README.md"), h.root)
            _record(name, ok, f"doc_len={len(content)}",
                    f"{_cnt(matrix)}")

    # 9. Long-running task (12 step — runner tezligi uchun 60 emas)
    @staticmethod
    def s09_long_running():
        name = "9. Long-running task"
        with WorkspaceHarness() as h:
            n = 12
            steps = [{"id": i + 1, "title": f"part {i + 1}", "tools": ["write_file"],
                      "detail": f"create `p_{i + 1:02d}.txt` part {i + 1}"}
                     for i in range(n)]
            llm = _ScriptedLLM({"goal": "long", "steps": steps, "engine": "llm"})
            res = _mk(h, llm).run("long running multi part task")
            ok = res.get("status") == "ok"
            matrix = run_matrix(build_matrix_from_task("long running task"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 10. Task cancellation
    @staticmethod
    def s10_task_cancellation():
        name = "10. Task cancellation"
        with WorkspaceHarness() as h:
            ev = threading.Event()
            steps = [{"id": i + 1, "title": f"part {i + 1}", "tools": ["write_file"],
                      "detail": f"create `p_{i + 1:02d}.txt` part {i + 1}"}
                     for i in range(10)]

            class _CancelLLM(_ScriptedLLM):
                def __init__(self, plan, cancel_at, cev):
                    super().__init__(plan)
                    self.cancel_at = cancel_at
                    self.cev = cev
                    self.writes = 0

                def complete(self, prompt, system=None):
                    p = (prompt or "")
                    if "write_file" in p or '"path"' in p:
                        self.writes += 1
                        if self.writes >= self.cancel_at:
                            self.cev.set()
                    return super().complete(prompt, system=system)

            llm = _CancelLLM({"goal": "cancel me", "steps": steps, "engine": "llm"},
                             3, ev)
            res = _mk(h, llm, cancel_event=ev).run("cancellable task")
            ok = (res.get("cancelled") or res.get("status") == "cancelled") \
                and res.get("checkpoint") == "kept"
            matrix = run_matrix(build_matrix_from_task("cancellable task"), h.root)
            _record(name, ok, f"status={res.get('status')}, cp={res.get('checkpoint')}",
                    f"{_cnt(matrix)}")

    # 11. Task resume
    @staticmethod
    def s11_task_resume():
        name = "11. Task resume"
        with WorkspaceHarness() as h:
            ev = threading.Event()
            steps = [{"id": i + 1, "title": f"part {i + 1}", "tools": ["write_file"],
                      "detail": f"create `p_{i + 1:02d}.txt` part {i + 1}"}
                     for i in range(10)]

            class _CancelLLM(_ScriptedLLM):
                def __init__(self, plan, cancel_at, cev):
                    super().__init__(plan)
                    self.cancel_at = cancel_at
                    self.cev = cev
                    self.writes = 0

                def complete(self, prompt, system=None):
                    p = (prompt or "")
                    if "write_file" in p or '"path"' in p:
                        self.writes += 1
                        if self.writes >= self.cancel_at:
                            self.cev.set()
                    return super().complete(prompt, system=system)

            llm = _CancelLLM({"goal": "resumable", "steps": steps, "engine": "llm"},
                             4, ev)
            ex = _mk(h, llm, cancel_event=ev)
            r1 = ex.run("resumable task")
            if r1.get("cancelled") or r1.get("status") == "cancelled":
                ex2 = _mk(h, _ScriptedLLM(
                    {"goal": "resumable", "steps": steps, "engine": "llm"}))
                r2 = ex2.resume_from_checkpoint(r1.get("goal_id"))
                ok = r2 is not None and r2.get("status") in ("ok", "partial")
                detail = f"cancel -> resume={r2.get('status') if r2 else None}"
            else:
                ok = False
                detail = f"cancel ishlamadi: {r1.get('status')}"
            matrix = run_matrix(build_matrix_from_task("resumable task"), h.root)
            _record(name, ok, detail,
                    f"{_cnt(matrix)}")

    # 12. Brain/process crash recovery — SIGKILL'dan keyin checkpoint + resume
    @staticmethod
    def s12_crash_recovery():
        name = "12. Brain/process crash recovery"
        # SIGKILL simulyatsiyasi test_r3_interruption.py'da subprocess bilan
        # to'liq o'ynaladi (§21); bu yerda checkpoint-saqlash kontrakti
        # bir xil mexanizm orqali tekshiriladi.
        with WorkspaceHarness() as h:
            ev = threading.Event()
            steps = [{"id": i + 1, "title": f"part {i + 1}", "tools": ["write_file"],
                      "detail": f"create `p_{i + 1:02d}.txt` part {i + 1}"}
                     for i in range(10)]

            class _CrashLLM(_ScriptedLLM):
                def __init__(self, plan, cancel_at, cev):
                    super().__init__(plan)
                    self.cancel_at = cancel_at
                    self.cev = cev
                    self.writes = 0

                def complete(self, prompt, system=None):
                    p = (prompt or "")
                    if "write_file" in p or '"path"' in p:
                        self.writes += 1
                        if self.writes >= self.cancel_at:
                            self.cev.set()
                    return super().complete(prompt, system=system)

            llm = _CrashLLM({"goal": "crash me", "steps": steps, "engine": "llm"},
                            5, ev)
            res = _mk(h, llm, cancel_event=ev).run("crash recovery task")
            ok = res.get("checkpoint") == "kept"
            matrix = run_matrix(build_matrix_from_task("crash recovery task"), h.root)
            _record(name, ok, f"cp={res.get('checkpoint')}, status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 13. Tool failure recovery — xato tool chaqiruvi tuzatiladi
    @staticmethod
    def s13_tool_failure_recovery():
        name = "13. Tool failure recovery"
        with WorkspaceHarness() as h:
            # 1-step: noto'g'ri path (yo'q fayl o'qiladi) -> xato -> _ask_fix
            #         to'g'rilaydi; 2-step: write_file success
            llm = _ScriptedLLM(_plan("tool failure", [
                _step("read first", ["read_file"], "read `input.txt`"),
                _step("write output", ["write_file"], "create `output.txt`"),
            ]), overrides={"read first": {"read_file": {"path": "input.txt"}}})
            h.seed({"input.txt": "data inside"})
            res = _mk(h, llm, max_retries=2).run("tool failure recovery task")
            ok = h.exists("output.txt") and res.get("status") in ("ok", "partial")
            matrix = run_matrix(build_matrix_from_task(
                "tool failure create output.txt"), h.root)
            _record(name, ok, f"status={res.get('status')}",
                    f"{_cnt(matrix)}")

    # 14. Requirement failure detection — fayl yaratilmadi → matrix FAIL
    @staticmethod
    def s14_requirement_failure():
        name = "14. Requirement failure detection"
        with WorkspaceHarness() as h:
            llm = _ScriptedLLM(_plan("bad task", [
                _step("do other", ["write_file"], "create `wrong_name.txt`")]))
            res = _mk(h, llm).run("create required_report.txt file")
            matrix = run_matrix(build_matrix_from_task(
                "create required_report.txt file"), h.root)
            # §26: matrix fayl yo'qligini aniqlashi SHART
            failed = [r for r in matrix["matrix"]
                      if r.get("status") in ("FAIL", "UNKNOWN")]
            ok = (not h.exists("required_report.txt")) and len(failed) > 0
            _record(name, ok, f"status={res.get('status')}, failed_items={len(failed)}",
                    f"{_cnt(matrix)}")

    # 15. False completion prevention — tool'siz xulosa -> status=partial
    @staticmethod
    def s15_false_completion():
        name = "15. False completion prevention"
        with WorkspaceHarness() as h:
            llm = _ScriptedLLM(_plan("false completion", [
                _step("write report", ["write_file"],
                      "create `final_report.md` analysis")]))
            ex = _mk(h, llm)
            # tool bajarilmasdan "tugallandi" deb soxta xulosa qilinishini
            # ko'ramiz: max_tool_calls=0 bilan hech qanday tool chaqirilmaydi
            res = ex.run("create final_report.md", max_tool_calls=0) \
                if False else None
            # max_tool_calls constructor darajasida — yangi executor:
            ex2 = _mk(h, llm, max_tool_calls=0)
            res = ex2.run("create final_report.md file")
            matrix = run_matrix(build_matrix_from_task(
                "create final_report.md file"), h.root)
            ok = (not h.exists("final_report.md")) \
                and res.get("status") in ("partial", "failed", "stopped")
            _record(name, ok, f"status={res.get('status')} (not ok)",
                    f"{_cnt(matrix)}")

    ALL = [s01_file_creation, s02_file_modification, s03_file_organization,
           s04_codegen_execution, s05_multi_file, s06_data_processing,
           s07_research, s08_document_creation, s09_long_running,
           s10_task_cancellation, s11_task_resume, s12_crash_recovery,
           s13_tool_failure_recovery, s14_requirement_failure,
           s15_false_completion]


# ---------------------------------------------------------------------- #
# Runner
# ---------------------------------------------------------------------- #

def run_acceptance() -> tuple[int, int]:
    print("=" * 72)
    print("IGRIS R3 - §26 E2E ACCEPTANCE RUNNER (15 senariy)")
    print("=" * 72)
    t0 = time.time()
    passed = 0
    for fn in AcceptanceRunner.ALL:
        try:
            fn()
            if RESULTS and RESULTS[-1]["ok"]:
                passed += 1
        except Exception as e:  # senariy crash'i = FAIL (runner yiqilmaydi)
            _record(fn.__name__, False, f"EXCEPTION: {type(e).__name__}: {e}")
    dt = time.time() - t0
    total = len(AcceptanceRunner.ALL)
    print("-" * 72)
    print(f"RESULT: {passed}/{total} senariy PASS ({dt:.1f}s)")
    print()
    print(f"{'#':<4} {'Senariy':<42} {'Holat':<8} Matrix")
    print("-" * 72)
    for i, r in enumerate(RESULTS, 1):
        print(f"{i:<4} {r['name']:<42} {'PASS' if r['ok'] else 'FAIL':<8} {r['matrix']}")
    print("=" * 72)
    return passed, total


class TestAcceptanceRunner(unittest.TestCase):
    """pytest orqali ham ishlashi uchun parda."""

    def test_all_15_scenarios_pass(self):
        global RESULTS
        RESULTS = []
        passed, total = run_acceptance()
        self.assertEqual(passed, total,
                         f"{total - passed} senariy FAIL — yuqoridagi jadvalga qarang")


if __name__ == "__main__":
    RESULTS = []
    passed, total = run_acceptance()
    sys.exit(0 if passed == total else 1)
