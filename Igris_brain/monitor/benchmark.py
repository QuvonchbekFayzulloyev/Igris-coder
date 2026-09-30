"""
IGRIS BRAIN — Benchmark Harness
===============================
Runs simple (deterministic) and complex (LLM) tasks, measures quality and
speed, and writes a report.

Quality scoring per task:
  - each task declares a set of "expected" substrings / regex markers
  - quality = (matched markers) / (total markers)  per task
  - a task is a "pass" when quality >= task.pass_threshold

Speed metrics:
  - duration_ms (end-to-end), engine used, tokens/sec for LLM outputs

Usage:
    python benchmark.py                    # hybrid (LLM on) + all engines
    python benchmark.py --no-llm           # deterministic only
    python benchmark.py --model qwen3:8b
    python benchmark.py --tasks simple|complex|all --out reports/benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.igris_agent import IgrisAgent  # noqa: E402

# ---------------------------------------------------------------------- #
# Task suite
# ---------------------------------------------------------------------- #
# kind: 'simple' = deterministic-friendly, 'complex' = needs LLM reasoning

TASKS: list[dict] = [
    # ---------------- SIMPLE (uz + en) ---------------- #
    {
        "id": "s1", "kind": "simple", "lang": "uz",
        "query": "matritsani teskari top",
        "expected": ["np.linalg.inv"],
        "pass_threshold": 1.0,
        "note": "inverse of matrix (uz SOV)",
    },
    {
        "id": "s2", "kind": "simple", "lang": "uz",
        "query": "ro'yxatni sarala",
        "expected": ["sorted("],
        "pass_threshold": 1.0,
        "note": "sort list (uz suffix stripping)",
    },
    {
        "id": "s3", "kind": "simple", "lang": "en",
        "query": "sort the list",
        "expected": ["sorted("],
        "pass_threshold": 1.0,
        "note": "sort list (en)",
    },
    {
        "id": "s4", "kind": "simple", "lang": "en",
        "query": "mean of the list",
        "expected": ["np.mean"],
        "pass_threshold": 1.0,
        "note": "mean of list (en)",
    },
    {
        "id": "s5", "kind": "simple", "lang": "en",
        "query": "sum the list",
        "expected": ["sum(", "np.sum"],
        "pass_threshold": 0.5,
        "note": "sum of list (en)",
    },
    {
        "id": "s6", "kind": "simple", "lang": "uz",
        "query": "ro'yxatning o'rtachasini hisobla",
        "expected": ["np.mean", "mean"],
        "pass_threshold": 0.5,
        "note": "compute average of list (uz)",
    },
    # ---------------- COMPLEX (LLM reasoning) ---------------- #
    {
        "id": "c1", "kind": "complex", "lang": "en",
        "query": "Write a Python function that reads a CSV file, filters rows where age > 30, and returns the average of the salary column.",
        "expected": ["def ", "csv", "age", "salary"],
        "pass_threshold": 0.75,
        "note": "multi-step data task",
    },
    {
        "id": "c2", "kind": "complex", "lang": "en",
        "query": "Write a Python function using recursion to compute the nth Fibonacci number with memoization.",
        "expected": ["def ", "fib", "memo", "cache", "dict"],
        "pass_threshold": 0.6,
        "note": "recursion + memoization",
    },
    {
        "id": "c3", "kind": "complex", "lang": "en",
        "query": "Write a Python function that checks whether a string is a valid palindrome ignoring spaces and case.",
        "expected": ["def ", "palindrome", "lower", "replace", "reverse", "=="],
        "pass_threshold": 0.6,
        "note": "palindrome with normalization",
    },
    {
        "id": "c4", "kind": "complex", "lang": "en",
        "query": "Write a Python snippet using pandas to group a DataFrame by 'category' and compute the mean of 'value'.",
        "expected": ["pandas", "pd", "groupby", "mean"],
        "pass_threshold": 0.75,
        "note": "pandas groupby",
    },
    {
        "id": "c5", "kind": "complex", "lang": "en",
        "query": "Write a Python function that takes two lists and returns their intersection preserving order.",
        "expected": ["def ", "intersection", "list"],
        "pass_threshold": 0.66,
        "note": "list intersection",
    },
    {
        "id": "c6", "kind": "complex", "lang": "uz",
        "query": "Python funksiya yozing: foydalanuvchi kiritgan sonlar ro'yxatining eng katta va eng kichik elementlarini qaytarsin.",
        "expected": ["def ", "max", "min"],
        "pass_threshold": 0.6,
        "note": "uz: min/max of list",
    },
]


# ---------------------------------------------------------------------- #
# Quality scoring
# ---------------------------------------------------------------------- #

def score_task(task: dict, output: str) -> float:
    """Fraction of expected markers found in the output (case-insensitive)."""
    out = (output or "").lower()
    if not out:
        return 0.0
    hits = 0
    for marker in task["expected"]:
        if re.search(re.escape(marker.lower()), out):
            hits += 1
    return hits / len(task["expected"])


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


# ---------------------------------------------------------------------- #
# Runner
# ---------------------------------------------------------------------- #

def run_benchmark(agent: IgrisAgent, tasks: list[dict]) -> dict:
    results = []
    for task in tasks:
        t0 = time.perf_counter()
        try:
            res = agent.resolve(task["query"], allow_llm=True)
            status = res.get("status", "failed")
            output = res.get("output", "")
        except Exception as exc:
            res = {"status": "error", "output": ""}
            status = "error"
            output = ""
            print(f"  !! error {task['id']}: {exc}")

        dur_ms = (time.perf_counter() - t0) * 1000.0
        quality = score_task(task, output)
        tokens = estimate_tokens(output)
        tok_sec = (tokens / (dur_ms / 1000.0)) if dur_ms > 0 else 0.0

        results.append({
            "id": task["id"],
            "kind": task["kind"],
            "lang": task["lang"],
            "query": task["query"],
            "status": status,
            "engine": res.get("engine", "?"),
            "confidence": round(res.get("confidence", 0.0), 3),
            "duration_ms": round(dur_ms, 1),
            "tokens": tokens,
            "tokens_per_sec": round(tok_sec, 1),
            "quality": round(quality, 2),
            "pass": quality >= task["pass_threshold"],
            "output_preview": (output or "")[:120].replace("\n", " "),
        })

    # aggregate
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    simple = [r for r in results if r["kind"] == "simple"]
    complex_t = [r for r in results if r["kind"] == "complex"]

    def agg(rs: list[dict]) -> dict:
        if not rs:
            return {"count": 0, "avg_quality": 0.0, "avg_duration_ms": 0.0, "pass_rate": 0.0}
        return {
            "count": len(rs),
            "avg_quality": round(sum(r["quality"] for r in rs) / len(rs), 3),
            "avg_duration_ms": round(sum(r["duration_ms"] for r in rs) / len(rs), 1),
            "pass_rate": round(sum(1 for r in rs if r["pass"]) / len(rs), 3),
            "engines": sorted({r["engine"] for r in rs}),
        }

    summary = {
        "total_tasks": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "simple": agg(simple),
        "complex": agg(complex_t),
        "llm_available": agent.llm_available(),
        "model": agent.llm.model,
    }
    return {"summary": summary, "tasks": results}


def write_report(report: dict, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out_path


def print_table(report: dict) -> None:
    s = report["summary"]
    print("=" * 92)
    print(f"IGRIS BENCHMARK   model={s['model']}  llm_available={s['llm_available']}")
    print(f"pass_rate={s['pass_rate']:.0%} ({s['passed']}/{s['total_tasks']})")
    print(f"  simple : n={s['simple']['count']} quality={s['simple']['avg_quality']:.2f} "
          f"avg={s['simple']['avg_duration_ms']:.0f}ms pass={s['simple']['pass_rate']:.0%} engines={s['simple']['engines']}")
    print(f"  complex: n={s['complex']['count']} quality={s['complex']['avg_quality']:.2f} "
          f"avg={s['complex']['avg_duration_ms']:.0f}ms pass={s['complex']['pass_rate']:.0%} engines={s['complex']['engines']}")
    print("-" * 92)
    header = f"{'id':<4}{'kind':<8}{'engine':<13}{'conf':<6}{'ms':<8}{'t/s':<8}{'q':<6}{'pass':<6}preview"
    print(header)
    print("-" * 92)
    for r in report["tasks"]:
        print(f"{r['id']:<4}{r['kind']:<8}{r['engine']:<13}{r['confidence']:<6}"
              f"{r['duration_ms']:<8}{r['tokens_per_sec']:<8}{r['quality']:<6}"
              f"{'PASS' if r['pass'] else 'FAIL':<6}{r['output_preview']}")
    print("=" * 92)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description="IGRIS benchmark")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--tasks", default="all", choices=["all", "simple", "complex"])
    parser.add_argument("--out", default="reports/benchmark.json")
    parser.add_argument("--no-memory", action="store_true", help="disable memory (speed test)")
    args = parser.parse_args(argv)

    agent = IgrisAgent(
        use_llm=not args.no_llm,
        llm_model=args.model,
        memory_enabled=not args.no_memory,
        memory_session="benchmark",
    )
    tasks = [t for t in TASKS if args.tasks == "all" or t["kind"] == args.tasks]

    print(f"[igris] benchmark start: {len(tasks)} tasks, model={args.model}, "
          f"llm={'on' if agent.llm_available() else 'OFF'}, memory={agent.memory.enabled}")
    t0 = time.perf_counter()
    report = run_benchmark(agent, tasks)
    report["wall_seconds"] = round(time.perf_counter() - t0, 2)

    path = write_report(report, args.out)
    print_table(report)
    print(f"\nreport: {os.path.abspath(path)}")
    if agent.memory.enabled:
        agent.memory.end_session("benchmark done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
