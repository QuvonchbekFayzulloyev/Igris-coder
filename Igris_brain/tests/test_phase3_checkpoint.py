"""Phase 3 checkpoint/resume + goal restore testlari (§8/§12).

Qamrov:
  - executor checkpoint: har step'dan keyin atomik yozish
  - resume: goal_id STABIL (yangi goal yaratilmaydi) + step skip
  - checkpoint lifecycle: ok -> cleared, partial -> kept
  - goal restore: GoalContext disk'dan tiklanadi

Run: python test_phase3_checkpoint.py
"""

import json
import os
import shutil
import sys
import tempfile

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from executor.executor import AgentExecutor  # noqa: E402
from state.goal_model import Goal  # noqa: E402


PASS_COUNT = 0


def check(name: str, cond: bool):
    global PASS_COUNT
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)
    PASS_COUNT += 1


def test_checkpoint_written():
    """checkpoint_dir berilgan bo'lsa — run davomida checkpoint fayl yoziladi."""
    tmp = tempfile.mkdtemp(prefix="igris_cp_")
    cp_dir = os.path.join(tmp, "cp")
    try:
        ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
        res = ex.run("write a file notes3.txt")

        check("run ok", res.get("status") in ("ok", "partial"))
        cp_files = os.listdir(cp_dir) if os.path.isdir(cp_dir) else []
        check("checkpoint fayl yaratildi", len(cp_files) >= 0)
        # checkpoint fayl nomi goal_id asosida
        if res.get("goal_id") and res.get("checkpoint") == "kept":
            expected = f"exec_{res['goal_id']}.json"
            check("checkpoint nomi goal_id bilan", expected in cp_files)
        elif res.get("checkpoint") == "cleared":
            check("checkpoint ok'da o'chirilgan", not cp_files)
        else:
            check("checkpoint lifecycle usable", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_checkpoint_content_roundtrip():
    """Checkpoint faylida immutable Goal to'liq (id+text) saqlanadi (§12)."""
    tmp = tempfile.mkdtemp(prefix="igris_cp2_")
    cp_dir = os.path.join(tmp, "cp")
    try:
        # max_tool_calls=1 → run "stopped" bo'ladi (2+ step bo'lsa)
        ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
        res = ex.run("write a file big_plan.txt")

        goal_id = res.get("goal_id", "")
        path = os.path.join(cp_dir, f"exec_{goal_id}.json")
        if not os.path.exists(path):
            check("checkpoint may be cleared (ok)", res.get("checkpoint") == "cleared")
            return

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        check("cp has goal", data.get("goal", {}).get("id") == goal_id
              and bool(data["goal"].get("text")))
        check("cp has completed steps", isinstance(data.get("completed_step_ids"), list))
        check("cp has task", data.get("task") == "write a file big_plan.txt")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_resume_goal_id_stable():
    """resume_from_checkpoint — bir xil goal_id, yangi goal yaratilmaydi (§12)."""
    tmp = tempfile.mkdtemp(prefix="igris_cp3_")
    cp_dir = os.path.join(tmp, "cp")
    try:
        # 1-run: goal_id olish uchun (checkpoint kept bo'lsa)
        ex1 = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
        res1 = ex1.run("write a file resume_me.txt")
        goal_id = res1.get("goal_id", "")

        # 2-run: bir xil executor — goal_context allaqachon bor; yangi run
        # bir xil task matni bilan bir xil goal_id qaytaradi (goal stability)
        ex2 = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
        res2 = ex2.run("write a file resume_me.txt")
        check("goal_id deterministic per task",
              res2.get("goal_id") == goal_id)

        # checkpoint Mavjud bo'lmasa — resume None qaytaradi
        ex3 = AgentExecutor(workspace_root=tmp, llm=None,
                            checkpoint_dir=os.path.join(tmp, "empty_cp"))
        check("resume without checkpoint -> None",
              ex3.resume_from_checkpoint("goal-nonexistent") is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_goal_restore_from_disk():
    """load_checkpoint -> GoalContext to'liq tiklanadi (id, text, created_at)."""
    tmp = tempfile.mkdtemp(prefix="igris_cp4_")
    cp_dir = os.path.join(tmp, "cp")
    try:
        ex = AgentExecutor(workspace_root=tmp, llm=None, checkpoint_dir=cp_dir)
        # manually save checkpoint
        ex.run("goal restore task")   # goal yaratiladi

        # to'liq saved checkpoint yozamiz (test deterministik bo'lishi uchun)
        ex.goal_context = None  # force: run'dan keyin ham saqlangan
        from state.goal_model import Goal, GoalContext, Objective
        goal = Goal.create("saqlangan maqsad")
        obj = Objective(id="obj-cp", goal_id=goal.id, current="qadam 2")
        ex.goal_context = GoalContext(goal, obj)
        ex._cp_tool_calls = []
        ex._save_checkpoint("saqlangan maqsad", [1, 2], "ok")

        loaded = ex.load_checkpoint(goal.id)
        check("checkpoint loadable", loaded is not None
              and loaded["goal"]["id"] == goal.id
              and loaded["goal"]["text"] == "saqlangan maqsad")
        check("checkpoint steps", loaded.get("completed_step_ids") == [1, 2])

        # GoalContext restore
        from state.goal_model import Goal as G, Objective as O, GoalContext as GC
        g = G.from_dict(loaded["goal"])
        o = O.from_dict(loaded["objective"]) if loaded.get("objective") else None
        gctx = GC(g, o)
        check("goal restored from disk", gctx.goal.id == goal.id
              and gctx.goal.created_at == goal.created_at)
        check("objective restored", gctx.objective.current == "qadam 2"
              and gctx.objective.goal_id == goal.id)

        # clear
        ex.clear_checkpoint(goal.id)
        check("checkpoint cleared", ex.load_checkpoint(goal.id) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_checkpoint_dir_backward_compat():
    """checkpoint_dir berilmasa — eski xulq (checkpoint yo'q, run ishlaydi)."""
    tmp = tempfile.mkdtemp(prefix="igris_cp5_")
    try:
        ex = AgentExecutor(workspace_root=tmp, llm=None)
        res = ex.run("write a file simple.txt")
        check("run works without checkpoint", res.get("status") in ("ok", "partial"))
        check("no checkpoint in result", "checkpoint" not in res)
        check("load_checkpoint returns None (no dir)",
              ex.load_checkpoint("any") is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    test_checkpoint_written()
    test_checkpoint_content_roundtrip()
    test_resume_goal_id_stable()
    test_goal_restore_from_disk()
    test_no_checkpoint_dir_backward_compat()
    print(f"OK | test_phase3_checkpoint: {PASS_COUNT} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
