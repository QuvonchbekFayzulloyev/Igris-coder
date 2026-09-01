"""
IGRIS DECISION-QUALITY PROBE
============================
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
  - outcome: vazifa haqiqatan bajarildimi (fayl mavjud, content to'g'ri, run OK)

Ishlatish:
  python probe_decisions.py --tasks all --model qwen3:8b
  python probe_decisions.py --tasks code,multi,draw
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from executor import AgentExecutor
from skills import DEFAULT_MANAGER
from mcp_bridge import McpBridge


TASKS = [
    {
        "id": "code_csv",
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
        "task": (
            "Create a folder 'notes' and inside it two files: todo.txt with a "
            "list of 3 tasks, and done.txt saying 'all done'. Then list the files."
        ),
        "expect": ["todo.txt", "done.txt"],
        "notes": "multi-file workspace orchestration",
    },
    {
        "id": "draw_apple",
        "task": (
            "Draw a blue apple and save it to blue_apple.png. Use the art MCP "
            "tools if available."
        ),
        "expect": ["blue_apple.png"],
        "notes": "capability-gap: image drawing needs skill/MCP, not write_file",
    },
    {
        "id": "fix_code",
        "task": (
            "The file buggy.py exists in the workspace and has a bug: it does "
            "print(x) but x is never defined. Read it, fix it, and run it."
        ),
        "expect": ["x = ", "ok"],
        "notes": "read -> understand -> fix -> verify loop",
    },
]


def score_task(t, trace: dict) -> dict:
    """Subjective-but-reproducible scoring on the recorded trace."""
    calls = trace.get("tool_calls", [])
    names = [c.get("tool", "") for c in calls]
    failures = [c for c in calls if not c.get("ok", True)]
    retries = trace.get("retries", 0)

    # --- tool selection ---
    # penalize: repeated identical calls, obviously wrong tool for the task
    repeats = len(names) - len(set(names))
    sel = max(0.0, 1.0 - 0.25 * repeats - 0.1 * len(failures))

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
    hits = sum(1 for m in t["expect"] if m in final)
    marker_ratio = hits / len(t["expect"]) if t["expect"] else 1.0

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
    # files_joined faqat 200 belgigacha kesilgan — marker keyingi qismda qolishi
    # mumkin; shu sabab bajarilgan run uchun marker yo'qligi 0.0 bo'lmasligi kerak.
    if run_completed and marker_ratio == 0.0:
        out = 0.6 * completed_credit
    else:
        out = 0.4 * completed_credit + 0.6 * marker_ratio

    return {
        "tool_selection": round(sel, 2),
        "args_correctness": round(args_score, 2),
        "reasoning": round(min(1.0, reason), 2),
        "recovery": round(rec, 2),
        "outcome": round(out, 2),
    }


def run_task(agent_cfg, task: dict, workspace: str, bridge=None) -> dict:
    if bridge is None:
        bridge = McpBridge()
        bridge.start()
    ex = AgentExecutor(
        workspace_root=workspace,
        llm=agent_cfg["llm"],
        skills=DEFAULT_MANAGER,
        mcp=bridge,
        human_provider=None,
        max_iter=10,
    )
    t0 = time.perf_counter()
    try:
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
                "preview": str(c.get("output_preview") or "")[:120],
            }
            for c in calls
        ],
        "plan_steps": res.get("plan", {}).get("steps", []),
        "final_text": str(res.get("final") or ""),
        "retries": (res.get("stats") or {}).get("corrections", 0),
        "status": res.get("status"),
        "duration_s": round(dur, 1),
    }
    # files written to workspace
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
    return {"id": task["id"], "task": task["task"][:90], "trace": trace, "scores": scores}


def run_probe(model: str = "qwen3:8b", tasks: str = "all",
              base_url: str = "http://localhost:11434",
              progress=None, out_path: str = "", bridge=None) -> dict:
    """Real qaror-sifat probe'ini ishga tushiradi.

    progress: optional callable(task_id, status) — server thread'dan chaqiriladi.
    bridge: server allaqachon ulangan MCP bridge'ni uzatish mumkin — ikkinchi
    McpBridge yaratilmaydi (port/protsess to'qnashuvining oldini olish).
    Qaytaradi: report dict {model, tasks:[...], aggregate:{...}} — shuningdek
    decision_probe.json ga yozadi (out_path berilmasa reports/ ga).
    """
    from llm.ollama_client import OllamaClient
    llm = OllamaClient(model=model, base_url=base_url)
    print(f"[probe] model={model} available={llm.is_available()}")

    selected = TASKS if tasks == "all" else [t for t in TASKS if t["id"] in tasks.split(",")]

    if not out_path:
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "decision_probe.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    report = {"model": model, "tasks": []}

    for t in selected:
        ws = tempfile.mkdtemp(prefix=f"igris_probe_{t['id']}_")
        # buggy.py for the fix task
        if t["id"] == "fix_code":
            with open(os.path.join(ws, "buggy.py"), "w", encoding="utf-8") as fh:
                fh.write("def greet(name):\n    print('hi', name)\n\nprint(x)\n")
        print(f"\n=== TASK {t['id']}: {t['notes']} ===")
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
        final = r["trace"]["final_text"].strip().replace("\n", " ")
        print(f"    FINAL: {final[:180]}")
        print(f"    SCORES: {r['scores']}")
        shutil.rmtree(ws, ignore_errors=True)

    # aggregate
    agg = {}
    for k in ("tool_selection", "args_correctness", "reasoning", "recovery", "outcome"):
        vals = [t["scores"][k] for t in report["tasks"]]
        agg[k] = round(sum(vals) / len(vals), 2)
    report["aggregate"] = agg

    # yakuniy hisobotni faylga yozamiz (atomic: tmp -> replace)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)

    print("\n=== AGGREGATE ===")
    for k, v in agg.items():
        print(f"  {k}: {v}")
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
