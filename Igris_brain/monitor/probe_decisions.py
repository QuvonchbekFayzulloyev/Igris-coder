"""
IGRIS DECISION-QUALITY PROBE (v2)
=================================
Emas: "tool bor-yo'q" — balki: agent tool'ni AQL bilan ishlata olyaptimi?

Har bir real task uchun to'liq qaror izi (decision trace) yoziladi:
  - plan (model rejasi)
  - har bir tool tanlovi: nima uchun, qanday args, natija ok/error
  - xato bo'lsa: qanday tuzatdi (retry/correction), yana xato bo'ldimi
  - yakuniy javob sifat eshigidan o'tdimi

Mezonlar (har task uchun 0..1):
  - tool_selection: to'g'ri tool tanlandimi (noto'g'ri/keraksiz chaqiruvlar soni)
  - args_correctness: argumentlar to'g'ri / ishlatiladigan bo'ldimi
  - reasoning: model reja tuzdimi, xatoni izohladi-izohlamadi, o'ylab harakat qildimi
  - recovery: xato kuzatilganda to'g'ri tuzatdimi
  - outcome: vazifa haqiqatan bajarildimi (fayl mavjud, content to'g'ri,
             oracle run OK, guard'lar buzilmagan)

v2 (S2 kengaytirish, 2026-09-18):
  - 4 → 21 task, 6 kategoriya: code / data / multi / web / draw / robustness
  - GUARD'lar: `keep_files` (existing fayl o'chirilmasligi kerak),
    `must_not_create_file` (javob faqat matnda bo'lishi kerak)
  - ORACLE: har task uchun ixtiyoriy bajaruv-tekshiruv — yozilgan Python
    run qilinadi, chiqat kutilgan qiymat bilan solishtiriladi (A1 yo'nalishi)
  - files: os.walk bilan TO'LIQ workspace skaneri (MCP/skill yozgan fayllar
    ham ko'rinadi — avvalgi faqat write_file args'dan edi)
  - kategoriya agregati + `category:code` filtri

Ishlatish:
  python probe_decisions.py --tasks all --model qwen3:8b
  python probe_decisions.py --tasks code,multi,draw
  python probe_decisions.py --tasks category:code
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.executor import AgentExecutor
from skills import DEFAULT_MANAGER
from tools.mcp_bridge import McpBridge

SCHEMA_VERSION = 2

CATEGORIES = ("code", "data", "multi", "web", "draw", "robustness")

# ---------------------------------------------------------------------- #
# Task-setup helper'lari (har task o'z workspace'ini o'zi tayyorlaydi)
# ---------------------------------------------------------------------- #

def _setup_buggy(ws: str) -> None:
    with open(os.path.join(ws, "buggy.py"), "w", encoding="utf-8") as fh:
        fh.write("def greet(name):\n    print('hi', name)\n\nprint(x)\n")


def _setup_keepme(ws: str) -> None:
    with open(os.path.join(ws, "config.json"), "w", encoding="utf-8") as fh:
        fh.write('{"env": "probe"}\n')


def _setup_csvs(ws: str) -> None:
    with open(os.path.join(ws, "data.csv"), "w", encoding="utf-8") as fh:
        fh.write("id,amount\ngood,100\ngood,200\nbad,999\ngood,300\n")


def _setup_multi_csv(ws: str) -> None:
    with open(os.path.join(ws, "sales.csv"), "w", encoding="utf-8") as fh:
        fh.write("order_id,product,qty,price\n1,apple,2,10\n2,pear,1,20\n3,apple,1,10\n")
    with open(os.path.join(ws, "prices.csv"), "w", encoding="utf-8") as fh:
        fh.write("product,cost\napple,5\npear,8\n")


# ---------------------------------------------------------------------- #
# Oracle helper'lar — har task uchun bajaruv-tekshiruv (A1 yo'nalishi)
# Qaytaradi: {"ok": bool, "detail": str}
# ---------------------------------------------------------------------- #

def _oracle_run_python_print(expect: str, name: str = "output.py",
                             argv: tuple = (), stdin_text: str = ""):
    """Yozilgan `name` faylni run qiladi; stdout'da `expect` bo'lishi kerak.

    argv: qo'shimcha CLI argumentlar (masalan ('Igris',) greet.py uchun)
    stdin_text: stdin'ga beriladigan matn (masalan '2\n3\n' — sum skriptlari)
    """
    def oracle(res: dict, ws: str) -> dict:
        path = os.path.join(ws, name)
        if not os.path.isfile(path):
            return {"ok": False, "detail": f"{name} not written"}
        try:
            proc = subprocess.run(
                [sys.executable, os.path.abspath(path), *argv], cwd=ws,
                capture_output=True, text=True, timeout=25,
                input=stdin_text if stdin_text else None)
        except subprocess.TimeoutExpired:
            return {"ok": False, "detail": f"{name} run timeout"}
        if proc.returncode != 0:
            return {"ok": False,
                    "detail": f"{name} exited {proc.returncode}: {proc.stderr.strip()[:200]}"}
        if expect in (proc.stdout or ""):
            return {"ok": True, "detail": f"stdout matched '{expect}'"}
        return {"ok": False,
                "detail": f"stdout missing '{expect}': {(proc.stdout or '').strip()[:200]}"}
    return oracle


def _oracle_json_c(res: dict, ws: str) -> dict:
    """items.json round-trip: massivda 3 obyekt, oxirgisi name='c' bo'lishi kerak."""
    path = os.path.join(ws, "items.json")
    if not os.path.isfile(path):
        return {"ok": False, "detail": "items.json not written"}
    try:
        data = json.loads(open(path, encoding="utf-8", errors="ignore").read())
    except Exception as exc:
        return {"ok": False, "detail": f"items.json invalid JSON: {exc}"}
    if isinstance(data, list) and len(data) == 3 and any(
            isinstance(o, dict) and o.get("name") == "c" for o in data):
        return {"ok": True, "detail": "items.json has 3 objects incl. name=c"}
    return {"ok": False, "detail": f"items.json wrong content: {str(data)[:150]}"}


def _oracle_file_contains(name: str, needles: tuple) -> object:
    def oracle(res: dict, ws: str) -> dict:
        path = os.path.join(ws, name)
        if not os.path.isfile(path):
            return {"ok": False, "detail": f"{name} not written"}
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception as exc:
            return {"ok": False, "detail": f"{name} unreadable: {exc}"}
        missing = [n for n in needles if n not in text]
        if missing:
            return {"ok": False, "detail": f"{name} missing: {missing}"}
        return {"ok": True, "detail": f"{name} contains all expected markers"}
    return oracle


# ---------------------------------------------------------------------- #
# TASKS — 21 task, 6 kategoriya
# ---------------------------------------------------------------------- #

TASKS = [
    # ------------------------- CODE (6) ------------------------- #
    {
        "id": "code_csv",
        "category": "code",
        "task": (
            "Write a Python function that reads a CSV file, filters rows where "
            "age > 30, and returns the average of the salary column. Save it to "
            "analyze_csv.py"
        ),
        "expect": ["def ", "csv", "age", "salary"],
        "notes": "LLM multi-step code — planning + tool selection",
    },
    {
        "id": "multi_notes",
        "category": "multi",
        "task": (
            "Create a folder 'notes' and inside it two files: todo.txt with a "
            "list of 3 tasks, and done.txt saying 'all done'. Then list the files."
        ),
        "expect": ["todo.txt", "done.txt"],
        "notes": "multi-file workspace orchestration",
    },
    {
        "id": "draw_apple",
        "category": "draw",
        "task": (
            "Draw a blue apple and save it to blue_apple.png. Use the art MCP "
            "tools if available."
        ),
        "expect": ["blue_apple.png"],
        "notes": "capability-gap: image drawing needs skill/MCP, not write_file",
    },
    {
        "id": "fix_code",
        "category": "code",
        "task": (
            "The file buggy.py exists in the workspace and has a bug: it does "
            "print(x) but x is never defined. Read it, fix it, and run it."
        ),
        "expect": ["x = ", "ok"],
        "setup": _setup_buggy,
        "notes": "read -> understand -> fix -> verify loop",
    },
    # --- yangi code tasklari (oracle bilan) --- #
    {
        "id": "code_fib",
        "category": "code",
        "task": (
            "Write a Python script fib.py that prints the first 10 Fibonacci "
            "numbers as comma-separated values (0, 1, 1, 2, 3, 5, 8, 13, 21, 34)."
        ),
        "expect": ["fib.py"],
        "setup": None,
        "oracle": _oracle_run_python_print("0, 1, 1, 2, 3, 5, 8, 13, 21, 34", "fib.py"),
        "notes": "run-oracle: yozilgan skript HAQIQATAN to'g'ri chiqat berishi kerak",
    },
    {
        "id": "code_sort_fix",
        "category": "code",
        "task": (
            "The file sorter.py in the workspace sorts a list of numbers but "
            "prints them in the wrong order. Fix it so it prints them in "
            "ascending order, then run it to confirm."
        ),
        "expect": ["sorter.py"],
        "setup": lambda ws: open(os.path.join(ws, "sorter.py"), "w", encoding="utf-8").write(
            "nums = [5, 2, 9, 1, 7]\nnums.sort(reverse=True)\nprint(nums)\n"),
        "oracle": _oracle_run_python_print("[1, 2, 5, 7, 9]", "sorter.py"),
        "notes": "read -> locate wrong-order logic -> fix -> run-verify",
    },
    {
        "id": "code_json_roundtrip",
        "category": "code",
        "task": (
            "Write a Python script json_task.py that loads items.json (a JSON "
            "array of objects with a 'name' field), adds an object "
            "{\"name\": \"c\"} to the array, and saves it back to items.json."
        ),
        "expect": ["json_task.py"],
        "setup": lambda ws: open(os.path.join(ws, "items.json"), "w", encoding="utf-8").write(
            '[{"name": "a"}, {"name": "b"}]'),
        "oracle": _oracle_json_c,
        "notes": "data-file round-trip with structural verification",
    },
    {
        "id": "code_readonly_guard",
        "category": "robustness",
        "task": (
            "Read the file config.json in the workspace and tell me the value "
            "of the 'env' field. Do not modify or delete any files."
        ),
        "expect": ["probe"],
        "setup": _setup_keepme,
        "guards": {"keep_files": ["config.json"], "must_not_create_file": True},
        "notes": "answer-in-text task + destructive-action guard (o'chirish monitori)",
    },
    {
        "id": "code_cli_argparse",
        "category": "code",
        "task": (
            "Write a Python script greet.py that takes a name as a command-line "
            "argument (using argparse) and prints 'Hello, <name>!'. Running "
            "'python greet.py Igris' must print 'Hello, Igris!'."
        ),
        "expect": ["greet.py"],
        "oracle": _oracle_run_python_print("Hello, Igris!", "greet.py", argv=("Igris",)),
        "notes": "argparse + run-oracle (CLI kontrakti tekshiriladi)",
    },

    # ------------------------- DATA (3) ------------------------- #
    {
        "id": "data_filter_csv",
        "category": "data",
        "task": (
            "In the workspace there is data.csv with columns id,amount. Write a "
            "Python script clean.py that reads it, keeps only rows where id == "
            "'good', sums their amount, and prints the total. Expected total: 600."
        ),
        "expect": ["clean.py"],
        "setup": _setup_csvs,
        "oracle": _oracle_run_python_print("600", "clean.py"),
        "notes": "deterministik data-to'g'rilik oracle (sum == 600)",
    },
    {
        "id": "data_multi_join",
        "category": "data",
        "task": (
            "The workspace has sales.csv (order_id,product,qty,price) and "
            "prices.csv (product,cost). Write a Python script report.py that "
            "computes the total profit (sum of qty*(price-cost)) by joining on "
            "product, and prints the number."
        ),
        "expect": ["report.py"],
        "setup": _setup_multi_csv,
        "oracle": _oracle_run_python_print("27", "report.py"),
        "notes": "2-fayl join oracle: (2*(10-5))+(1*(10-5))+(1*(20-8)) = 27",
    },
    {
        "id": "data_stats_json",
        "category": "data",
        "task": (
            "Write a Python script stats.py that generates 100 random integers "
            "between 1 and 100, computes their mean, and prints it rounded to "
            "2 decimal places."
        ),
        "expect": ["stats.py"],
        "oracle": _oracle_run_python_print(".", "stats.py"),
        "notes": "yengil run-oracle: skript ishlaydi va o'ndalik chiqat beradi",
    },

    # ------------------------- MULTI (3) ------------------------- #
    {
        "id": "multi_restructure",
        "category": "multi",
        "task": (
            "The workspace has three files a.txt, b.txt, c.txt. Create folders "
            "letters and digits, move a.txt into letters, and c.txt into "
            "digits, leaving b.txt in place."
        ),
        "expect": ["letters", "digits"],
        "setup": lambda ws: [open(os.path.join(ws, n), "w", encoding="utf-8").write("x")
                             for n in ("a.txt", "b.txt", "c.txt")],
        "guards": {"keep_files": ["b.txt"]},
        "notes": "papka yaratish + ko'chirish + b.txt joyida qolishi kerak",
    },
    {
        "id": "multi_append_log",
        "category": "multi",
        "task": (
            "The file log.txt in the workspace contains some lines. Append a "
            "new line 'session end' to it WITHOUT deleting the existing "
            "content, then print the full file."
        ),
        "expect": ["session end"],
        "setup": lambda ws: open(os.path.join(ws, "log.txt"), "w", encoding="utf-8").write(
            "line one\nline two\n"),
        "guards": {"keep_files": ["log.txt"]},
        "oracle": _oracle_file_contains("log.txt", ("line one", "line two", "session end")),
        "notes": "append-semantika: eski kontent saqlanishi HAQIQATAN tekshiriladi",
    },
    {
        "id": "multi_nested_tree",
        "category": "multi",
        "task": (
            "Create a nested folder structure docs/2026/reports and inside the "
            "deepest folder write a file summary.md containing the word "
            "'quarterly'. Then print the full tree of the docs folder."
        ),
        "expect": ["summary.md", "quarterly"],
        "oracle": _oracle_file_contains(os.path.join("docs", "2026", "reports", "summary.md"),
                                        ("quarterly",)),
        "notes": "3-darajali papka + fayl + run-oracle to'liq yo'lda",
    },

    # ------------------------- WEB (2) ------------------------- #
    {
        "id": "web_fetch_sum",
        "category": "web",
        "task": (
            "Fetch the content of https://example.com and tell me what the "
            "page is about in one sentence."
        ),
        "expect": [],
        "notes": "web_fetch tool'i + javob faqat matnda (fayl yaratish kerak emas)",
    },
    {
        "id": "web_fetch_title",
        "category": "web",
        "task": (
            "Use web_fetch on https://example.com and report the exact page "
            "title in your reply."
        ),
        "expect": [],
        "guards": {"must_not_create_file": True},
        "notes": "aniq fakt olib kelish + fayl yaratish guard'i",
    },

    # ------------------------- DRAW (1) ------------------------- #
    {
        "id": "draw_shape",
        "category": "draw",
        "task": (
            "Draw a green triangle and save it to green_triangle.png using the "
            "art MCP tools or drawing skills."
        ),
        "expect": ["green_triangle.png"],
        "notes": "noma'lum subject (triangle) — capability-gap + skill yo'li",
    },

    # ------------------------- ROBUSTNESS (3) ------------------------- #
    {
        "id": "rb_missing_file",
        "category": "robustness",
        "task": (
            "Read the file does_not_exist.txt in the workspace and summarize "
            "its contents for me."
        ),
        "expect": [],
        "notes": "mavjud bo'lmagan fayl — agent xatoni ANIQLAB halol javob berishi kerak",
    },
    {
        "id": "rb_hitl_ambiguous",
        "category": "robustness",
        "task": (
            "Fix the bug."
        ),
        "expect": [],
        "notes": "HITL: vazifa ma'lumotsiz — clarify/request_human yoki aniq savol bo'lishi kerak",
    },
    {
        "id": "rb_overspecified",
        "category": "robustness",
        "task": (
            "Write a Python script calc.py that reads two numbers from stdin, "
            "prints their sum, and supports a --verbose flag that prints "
            "'computed' before the result. Then run: echo 2 3 | python calc.py"
        ),
        "expect": ["calc.py"],
        "oracle": _oracle_run_python_print("5", "calc.py", stdin_text="2\n3\n"),
        "notes": "ko'p qadamli talab: stdin + flag + run-oracle",
    },
]

def select_tasks(tasks: str = "all") -> list:
    """`all` | `id1,id2` | `category:code` bo'yicha tasklarni tanlaydi."""
    tasks = (tasks or "all").strip().lower()
    if tasks == "all":
        return list(TASKS)
    if tasks.startswith("category:"):
        cat = tasks.split(":", 1)[1].strip()
        sel = [t for t in TASKS if t.get("category") == cat]
        if not sel:
            raise ValueError(f"unknown category '{cat}'. Known: {list(CATEGORIES)}")
        return sel
    wanted = [s.strip() for s in tasks.split(",") if s.strip()]
    by_id = {t["id"]: t for t in TASKS}
    missing = [w for w in wanted if w not in by_id]
    if missing:
        raise ValueError(f"unknown task id(s): {missing}. Known: {list(by_id)}")
    return [by_id[w] for w in wanted]


def score_task(t, trace: dict) -> dict:
    """Subjective-but-reproducible scoring on the recorded trace."""
    calls = trace.get("tool_calls", [])
    names = [c.get("tool", "") for c in calls]
    failures = [c for c in calls if not c.get("ok", True)]
    retries = trace.get("retries", 0)
    guards = t.get("guards") or {}

    # --- tool selection ---
    # penalize: repeated identical calls, obviously wrong tool for the task
    repeats = len(names) - len(set(names))
    unknown_calls = sum(1 for c in calls
                        if str(c.get("error") or "").startswith("Unknown tool"))
    sel = max(0.0, 1.0 - 0.25 * repeats - 0.1 * len(failures) - 0.15 * unknown_calls)

    # --- args correctness ---
    empty_args = sum(1 for c in calls if not c.get("args"))
    args_score = max(0.0, 1.0 - 0.2 * empty_args - 0.1 * len(failures))

    # --- reasoning: was there a plan / did the model explain failures ---
    plan = trace.get("plan_steps", [])
    reason = 0.0
    if plan:
        reason += 0.5
    if trace.get("final_text") and len(trace["final_text"]) > 80:
        reason += 0.3
    if trace.get("explained_failure"):
        reason += 0.2

    # --- recovery: failures that got retried and succeeded ---
    rec = 0.0
    if failures:
        rec = 0.7 if trace.get("recovered") else 0.3
    elif not failures:
        rec = 1.0  # no errors to recover from

    # --- outcome: did the expected markers show up in final/files? ---
    # A3 tuzatildi: markerlar aniq topilmasa ham, vazifa HAQIQATAN bajarilgan
    # (status=ok + fayl yozilgan + natija bor) bo'lsa — outcome 0.0 emas, asosiy
    # kredit beriladi. Marker hit'lar faqat bonus sifatida qo'shiladi.
    final = (trace.get("final_text") or "") + "\n" + trace.get("files_joined", "")
    hits = sum(1 for m in t.get("expect", []) if m in final)
    marker_ratio = hits / len(t["expect"]) if t.get("expect") else 1.0

    # Vazifa bajarilgan deb hisoblash: run ok/partial + fayl yozilgan + yakuniy
    # matn bor. A3'dagi asosiy holat fix_code status=partial edi — agent faylni
    # yozib qo'ygan, lekin status "partial" belgilangan. Bunday run ham haqiqiy
    # natija keltirgan — 0.0 bo'lmasligi kerak (partial kichik jarima bilan).
    status_ok = trace.get("status") in ("ok", "done", "complete")
    status_partial = trace.get("status") == "partial"
    has_files = bool(trace.get("files_joined", "").strip())
    has_final = len((trace.get("final_text") or "").strip()) > 0
    if status_partial:
        # Partial: fayl + yakuniy matn bo'lsa — bajarilgan deb hisobla (0.8 koeff)
        run_completed = bool(has_files or has_final)
        completed_credit = 0.8 * (1.0 if run_completed else 0.0)
    else:
        run_completed = status_ok and (has_files or has_final)
        completed_credit = 1.0 if run_completed else 0.0

    # --- ORACLE (A1 yo'nalishi): bajaruv-tekshiruv ustuvor ---
    # Oracle bor bo'lsa outcome'ning 60%'i oracle natijasidan keladi —
    # marker/kesh-gate'ga emas, HAQIQIY ishlashga tayanadi.
    oracle = t.get("oracle")
    oracle_ratio = None
    oracle_detail = ""
    if oracle is not None:
        try:
            verdict = oracle({"final": trace.get("final_text", "")}, trace.get("workspace", ""))
        except Exception as exc:
            verdict = {"ok": False, "detail": f"oracle crashed: {exc}"}
        oracle_ratio = 1.0 if verdict.get("ok") else 0.0
        oracle_detail = str(verdict.get("detail") or "")
        trace["oracle"] = {"ok": bool(verdict.get("ok")), "detail": oracle_detail}

    # --- GUARD'lar: buzilgan constraint outcome'ni keskin pasaytiradi ---
    guard_violations = []
    for keep in guards.get("keep_files", []):
        if keep not in trace.get("files_present", []):
            guard_violations.append(f"keep_file missing: {keep}")
    if guards.get("must_not_create_file") and trace.get("files_created"):
        guard_violations.append(
            "created files in answer-only task: " + ", ".join(trace["files_created"][:5]))

    if run_completed and marker_ratio == 0.0 and oracle_ratio is None:
        out = 0.6 * completed_credit
    elif oracle_ratio is not None:
        out = 0.4 * completed_credit + 0.6 * oracle_ratio
    else:
        out = 0.4 * completed_credit + 0.6 * marker_ratio

    # Guard buzilishlari: har biri 50% jarima (guard bu HARD constraint)
    out *= max(0.0, 1.0 - 0.5 * len(guard_violations))
    if guard_violations:
        trace["guard_violations"] = guard_violations

    return {
        "tool_selection": round(sel, 2),
        "args_correctness": round(args_score, 2),
        "reasoning": round(min(1.0, reason), 2),
        "recovery": round(rec, 2),
        "outcome": round(out, 2),
    }


def _scan_workspace(ws: str) -> tuple:
    """Workspace'dagi BARCHA fayllarni (papka daraxti bilan) to'playdi.

    Qaytaradi: (files_list) — nisbiy yo'llar. Bu MCP/skill tomonidan
    yozilgan fayllarni ham ko'radi (avvalgi faqat write_file args'dan edi).
    """
    found = []
    for root, _dirs, files in os.walk(ws):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), ws)
            found.append(rel.replace(os.sep, "/"))
        if len(found) > 200:
            break
    return sorted(found)


def run_task(agent_cfg, task: dict, workspace: str, bridge=None) -> dict:
    if bridge is None:
        bridge = McpBridge()
        bridge.start()
    t0 = time.perf_counter()
    setup = task.get("setup")
    if setup is not None:
        setup(workspace)
    files_before = set(_scan_workspace(workspace))
    try:
        # Executor KONSTRUKSIYASI ham guard ichida — workspace/mcp xatosi
        # butun probe'ni emas, faqat shu taskni "error" holatiga tushiradi.
        ex = AgentExecutor(
            workspace_root=workspace,
            llm=agent_cfg["llm"],
            skills=DEFAULT_MANAGER,
            mcp=bridge,
            human_provider=None,
            max_iter=int(task.get("max_iter") or 14),
        )
        res = ex.run_native(task["task"])
    except Exception as exc:
        res = {"status": "error", "final": f"CRASH: {exc}", "tool_calls": [],
               "stats": {"steps": 0, "tool_calls": 0, "corrections": 0}}
    dur = time.perf_counter() - t0

    calls = res.get("tool_calls", []) or []
    trace = {
        "tool_calls": [
            {
                "tool": c.get("tool"),
                "args": c.get("args"),
                "ok": bool((c.get("result") or {}).get("ok", True)),
                "error": str((c.get("result") or {}).get("error") or ""),
                "preview": str(c.get("output_preview") or "")[:120],
            }
            for c in calls
        ],
        "plan_steps": res.get("plan", {}).get("steps", []),
        "final_text": str(res.get("final") or ""),
        "retries": (res.get("stats") or {}).get("corrections", 0),
        "status": res.get("status"),
        "duration_s": round(dur, 1),
        "workspace": workspace,
    }
    # files: write_file/apply_patch args'lari (aniq yo'l bilishi foydali)
    files = []
    for c in calls:
        a = c.get("args") or {}
        if c.get("tool") in ("write_file", "apply_patch") and a.get("path"):
            p = os.path.join(workspace, str(a["path"]))
            if os.path.isfile(p):
                try:
                    files.append(f"{a['path']}::" + open(p, encoding="utf-8", errors="ignore").read()[:200])
                except Exception:
                    files.append(str(a["path"]))
    trace["files_joined"] = "\n".join(files)

    # files_after: os.walk — BARCHA fayllar (MCP/skill yozganlar ham)
    files_after = set(_scan_workspace(workspace))
    trace["files_present"] = sorted(files_after)
    trace["files_created"] = sorted(files_after - files_before)

    # skill/human signal'lari (qobiliyat-yetishmasligi va HITL o'lchanadi)
    trace["used_skill"] = any(c.get("tool") == "use_skill" and c.get("ok") for c in trace["tool_calls"])
    trace["asked_human"] = any(c.get("tool") == "request_human" and c.get("ok") for c in trace["tool_calls"])

    # explained failure: did any tool message contain the error text (self-awareness)
    trace["explained_failure"] = bool(
        any("failed" in (c.get("preview") or "").lower() or "error" in (c.get("preview") or "").lower()
            for c in trace["tool_calls"])
    ) or bool(
        re.search(r"(error|fail|tuzat|fixed|correct)", (trace.get("final_text") or ""), re.IGNORECASE)
    )
    # Haqiqiy recovery: xatodan KEYIN kamida bitta muvaffaqiyatli chaqiruv
    # ("xato bo'ldi, lekin tuzatdi" — shunchaki retries soni emas).
    recovered = False
    failed_seen = False
    for c in trace["tool_calls"]:
        if not c.get("ok", True):
            failed_seen = True
        elif failed_seen:
            recovered = True
            break
    trace["recovered"] = recovered or (trace["retries"] > 0 and not any(
        not c.get("ok", True) for c in trace["tool_calls"]
    ))
    scores = score_task(task, trace)
    return {"id": task["id"], "category": task.get("category", "code"),
            "task": task["task"][:90], "trace": trace, "scores": scores}


def run_probe(model: str = "qwen3:8b", tasks: str = "all",
              base_url: str = "http://localhost:11434",
              progress=None, out_path: str = "", bridge=None) -> dict:
    """Real qaror-sifat probe'ini ishga tushiradi.

    progress: optional callable(task_id, status) — server thread'dan chaqiriladi.
    bridge: server allaqachon ulangan MCP bridge'ni uzatish mumkin — ikkinchi
    McpBridge yaratilmaydi (port/protsess to'qnashuvining oldini olish).
    tasks: "all" | "id1,id2" | "category:code"
    Qaytaradi: report dict {schema_version, model, tasks:[...], aggregate,
    categories} — shuningdek decision_probe.json ga yozadi (out_path berilmasa
    reports/ ga).
    """
    from llm.ollama_client import OllamaClient
    llm = OllamaClient(model=model, base_url=base_url)
    print(f"[probe] model={model} available={llm.is_available()}")

    selected = select_tasks(tasks)

    if not out_path:
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "decision_probe.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    report = {"schema_version": SCHEMA_VERSION, "model": model, "tasks": []}

    for t in selected:
        ws = tempfile.mkdtemp(prefix=f"igris_probe_{t['id']}_")
        print(f"\n=== TASK {t['id']} [{t.get('category', 'code')}]: {t['notes']} ===")
        print(f"    {t['task'][:100]}")
        if progress:
            progress(t["id"], "running")
        r = run_task({"llm": llm}, t, ws, bridge=bridge)
        report["tasks"].append(r)
        if progress:
            progress(t["id"], "done")

        print(f"    status={r['trace']['status']}  dur={r['trace']['duration_s']}s  retries={r['trace']['retries']}")
        for c in r["trace"]["tool_calls"]:
            mark = "OK " if c["ok"] else "ERR"
            print(f"    [{mark}] {c['tool']}({json.dumps(c['args'], ensure_ascii=False)[:100]})")
            if c["preview"]:
                print(f"           ~ {c['preview'][:110]}")
        if r["trace"].get("oracle"):
            print(f"    ORACLE: {r['trace']['oracle']}")
        if r["trace"].get("guard_violations"):
            print(f"    GUARDS: {r['trace']['guard_violations']}")
        final = r["trace"]["final_text"].strip().replace("\n", " ")
        print(f"    FINAL: {final[:180]}")
        print(f"    SCORES: {r['scores']}")
        shutil.rmtree(ws, ignore_errors=True)

    # aggregate
    agg = {}
    for k in ("tool_selection", "args_correctness", "reasoning", "recovery", "outcome"):
        vals = [t["scores"][k] for t in report["tasks"]]
        agg[k] = round(sum(vals) / len(vals), 2) if vals else 0.0
    report["aggregate"] = agg

    # kategoriya agregati — qaysi domenda agent kuchsiz, darhol ko'rinadi
    categories = {}
    for cat in CATEGORIES:
        cat_tasks = [t for t in report["tasks"] if t.get("category") == cat]
        if cat_tasks:
            categories[cat] = {
                "n": len(cat_tasks),
                "outcome": round(sum(t["scores"]["outcome"] for t in cat_tasks) / len(cat_tasks), 2),
                "reasoning": round(sum(t["scores"]["reasoning"] for t in cat_tasks) / len(cat_tasks), 2),
            }
    report["categories"] = categories

    # yakuniy hisobotni faylga yozamiz (atomic: tmp -> replace)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)

    print("\n=== AGGREGATE ===")
    for k, v in agg.items():
        print(f"  {k}: {v}")
    if categories:
        print("--- categories ---")
        for cat, c in categories.items():
            print(f"  {cat} (n={c['n']}): outcome={c['outcome']} reasoning={c['reasoning']}")
    print(f"  report: {out_path}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="all")
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--base-url", default="http://localhost:11434")
    args = ap.parse_args()
    run_probe(model=args.model, tasks=args.tasks, base_url=args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
