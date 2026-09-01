"""Verification for the agent execution layer (tools / planner / executor).

Run: python test_executor.py
Exits non-zero if any assertion fails.
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import Workspace, DEFAULT_REGISTRY  # noqa: E402
from planner import TaskPlanner  # noqa: E402
from executor import AgentExecutor  # noqa: E402


def check(name: str, cond: bool):
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="igris_ws_")
    try:
        ws = Workspace(tmp)

        # ---- 1. workspace write/read ---------------------------- #
        r = ws.write("hello.txt", "Hello Igris")
        check("workspace write ok", r.get("ok"))
        r = ws.read("hello.txt")
        check("workspace read content", r.get("content") == "Hello Igris")

        # ---- 2. path traversal protection ----------------------- #
        blocked = False
        try:
            ws.read("../../etc/passwd")
        except ValueError:
            blocked = True
        check("path traversal blocked", blocked)

        # ---- 3. registry tools available ------------------------ #
        names = set(DEFAULT_REGISTRY.names())
        check("6 default tools",
              {"read_file", "write_file", "apply_patch", "list_files",
               "run_command", "python_exec"}.issubset(names))

        # ---- 4. python_exec runs code --------------------------- #
        r = DEFAULT_REGISTRY.execute(ws, "python_exec", {"code": "print(2 + 3)"})
        check("python_exec output 5", r.get("ok") and "5" in r.get("stdout", ""))

        # ---- 5. python_exec SOURCE collision edge case ---------- #
        r = DEFAULT_REGISTRY.execute(ws, "python_exec",
                                     {"code": "x = 1\nprint('SOURCE', x + 1)"})
        check("python_exec SOURCE token safe", r.get("ok") and "SOURCE 2" in r.get("stdout", ""))

        # ---- 6. apply_patch with and without space marker ------- #
        ws.write("p.txt", "line1\nline2\nline3\n")
        r = DEFAULT_REGISTRY.execute(ws, "apply_patch",
                                     {"path": "p.txt", "patch": "- line2\n+ line2 edited"})
        check("apply_patch space marker", r.get("ok") and "line2 edited" in ws.read("p.txt")["content"])

        ws.write("p2.txt", "aaa\nbbb\n")
        r = DEFAULT_REGISTRY.execute(ws, "apply_patch",
                                     {"path": "p2.txt", "patch": "-bbb\n+BBB"})
        check("apply_patch no-space marker", r.get("ok") and "BBB" in ws.read("p2.txt")["content"])

        # ---- 7. planner fallback (no LLM) ----------------------- #
        planner = TaskPlanner(llm=None)
        plan = planner.plan("fix the bug and run tests")
        check("fallback plan has steps", len(plan.get("steps", [])) >= 2)
        check("fallback plan engine", plan.get("engine") == "fallback")

        # ---- 8. planner JSON extraction ------------------------- #
        extracted = TaskPlanner._extract_json(
            'Here you go:\n```json\n{"goal": "g", "steps": [{"id": 1, "title": "s"}]}\n```'
        )
        check("planner extracts fenced JSON", extracted is not None and extracted.get("goal") == "g")

        # ---- 9. executor end-to-end (no LLM) -------------------- #
        ex = AgentExecutor(workspace_root=tmp, llm=None)
        res = ex.run("write a file notes.txt")
        check("executor run returns result", res.get("status") in ("ok", "partial", "stopped"))
        check("executor wrote file", os.path.exists(os.path.join(tmp, "notes.txt")))

        # ---- 10. executor tool limit ---------------------------- #
        ex2 = AgentExecutor(workspace_root=tmp, llm=None, max_tool_calls=2)
        res2 = ex2.run("create three files a.py b.py c.py")
        check("executor tool limit respected", res2["stats"]["tool_calls"] <= 2)

        print()
        print("ALL EXECUTOR TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
