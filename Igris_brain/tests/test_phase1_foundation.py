"""Phase 1 Foundation implementatsiya testlari.

Qamrov: state_machine.py, goal_model.py, tools/base.py (ToolMeta/ToolError),
git_command deny-list bypass tuzatishi, registry standart error formati.

Run: python test_phase1_foundation.py   (yoki pytest Igris_brain/test_phase1_foundation.py)
"""

import os
import shutil
import sys
import tempfile

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from state.state_machine import (  # noqa: E402
    AgentState, StateMachine, StateTransitionError, TaskStatus,
    VerificationStatus, validate_plan_tools,
)
from state.goal_model import (  # noqa: E402
    Action, Goal, GoalContext, Objective, Task,
)
from tools import Workspace, DEFAULT_REGISTRY  # noqa: E402
from tools.base import Tool, ToolError, ToolMeta  # noqa: E402


PASS_COUNT = 0


def check(name: str, cond: bool):
    global PASS_COUNT
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)
    PASS_COUNT += 1


# ------------------------------------------------------------------ #
# 1. State machine
# ------------------------------------------------------------------ #

def test_state_machine():
    sm = StateMachine(task_id="t1")
    check("sm initial INPUT", sm.state == AgentState.INPUT)

    happy = {
        "input_validated": True,
        "requirements_ready": True,
        "plan_steps": [{"id": 1, "tools": ["read_file"]}],
        "allowed_tools": ["read_file"],
        "tool_result": {"ok": True},
        "observation_flags": ["confirmed"],
        "verify_status": "VERIFIED",
        "remaining_steps": 0,
    }
    for st in ["UNDERSTAND", "PLAN", "EXECUTE", "OBSERVE", "VERIFY",
               "UPDATE_STATE", "COMPLETE"]:
        sm.transition(st, happy, trigger="test")
    check("sm happy path -> COMPLETE", sm.state == AgentState.COMPLETE)
    check("sm history yozildi", len(sm.history()) >= 8)

    # COMPLETE faqat VERIFIED bilan
    sm2 = StateMachine(task_id="t2")
    bad = dict(happy, verify_status="UNKNOWN")
    for st in ["UNDERSTAND", "PLAN", "EXECUTE", "OBSERVE", "VERIFY", "UPDATE_STATE"]:
        sm2.transition(st, bad)
    try:
        sm2.transition("COMPLETE", bad)
        check("COMPLETE blocks UNKNOWN", False)
    except StateTransitionError:
        check("COMPLETE blocks UNKNOWN", True)

    # no-transition yo'l bloklanadi
    sm3 = StateMachine(task_id="t3")
    try:
        sm3.transition("EXECUTE", happy)
        check("INPUT->EXECUTE blocked", False)
    except StateTransitionError:
        check("INPUT->EXECUTE blocked", True)

    # missing context bloklanadi
    sm4 = StateMachine(task_id="t4")
    try:
        sm4.transition("UNDERSTAND", {})
        check("missing ctx blocked", False)
    except StateTransitionError:
        check("missing ctx blocked", True)

    # repair: VERIFY -> EXECUTE (FAILED + retry limit)
    sm5 = StateMachine(task_id="t5", max_retries=1)
    fail_ctx = dict(happy, verify_status="FAILED")
    for st in ["UNDERSTAND", "PLAN", "EXECUTE", "OBSERVE", "VERIFY"]:
        sm5.transition(st, fail_ctx)
    sm5.transition("EXECUTE", fail_ctx)          # repair pass 1
    check("repair pass ruhsat", sm5.state == AgentState.EXECUTE)
    # repair'dan keyin OBSERVE -> VERIFY -> yana EXECUTE urinamiz: limit 1
    sm5.transition("OBSERVE", fail_ctx)
    sm5.transition("VERIFY", fail_ctx)
    try:
        sm5.transition("EXECUTE", fail_ctx)
        check("retry limit blocks", False)
    except StateTransitionError:
        check("retry limit blocks", True)

    # iteration limit: CONTINUE guard
    sm6 = StateMachine(task_id="t6", max_iter=2)
    cont_ctx = {"remaining_steps": 3}
    sm6.transition("UNDERSTAND", happy)
    sm6.transition("PLAN", happy)
    sm6.transition("EXECUTE", happy)
    sm6.transition("OBSERVE", happy)
    sm6.transition("VERIFY", happy)
    sm6.transition("UPDATE_STATE", dict(happy, remaining_steps=3))
    sm6.transition("CONTINUE", cont_ctx)          # iteration 0 -> 1
    sm6.transition("PLAN", happy)
    sm6.transition("EXECUTE", happy)
    sm6.transition("OBSERVE", happy)
    sm6.transition("VERIFY", happy)
    sm6.transition("UPDATE_STATE", dict(happy, remaining_steps=3))
    sm6.transition("CONTINUE", cont_ctx)          # iteration 1 -> 2
    check("iteration counter", sm6.iteration == 2)
    # endi max_iter=2 to'ldi — CONTINUE bloklanadi
    try:
        sm6.transition("PLAN", happy)             # CONTINUE -> PLAN ok
        # yangi iteratsiya uchun yana to'liq zanjir
        sm6.transition("EXECUTE", happy)
        sm6.transition("OBSERVE", happy)
        sm6.transition("VERIFY", happy)
        sm6.transition("UPDATE_STATE", dict(happy, remaining_steps=3))
        try:
            sm6.transition("CONTINUE", cont_ctx)
            check("iteration limit blocks CONTINUE", False)
        except StateTransitionError:
            check("iteration limit blocks CONTINUE", True)
    except StateTransitionError:
        check("iteration limit blocks CONTINUE", True)

    # history dump
    tmp = tempfile.mkdtemp(prefix="igris_sm_")
    try:
        path = os.path.join(tmp, "hist.jsonl")
        sm6.dump_history(path)
        import json
        with open(path, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        check("dump_history JSONL", len(lines) > 10 and "ts" in lines[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_validate_plan_tools():
    ok, msg = validate_plan_tools([{"tools": ["read_file"]}], ["read_file"])
    check("validate_plan_tools ok", ok)
    ok, msg = validate_plan_tools([{"tools": ["hack_tool"]}], ["read_file"])
    check("validate_plan_tools unknown blocked", not ok and "hack_tool" in msg)
    ok, msg = validate_plan_tools([], ["read_file"])
    check("validate_plan_tools empty blocked", not ok)


# ------------------------------------------------------------------ #
# 2. Goal model
# ------------------------------------------------------------------ #

def test_goal_model():
    goal = Goal.create("  Mini ilon o'yinini yasab ber  ")
    check("goal text stripped", goal.text == "Mini ilon o'yinini yasab ber")
    check("goal id prefixed", goal.id.startswith("goal-"))

    obj = Objective(id="obj-1", goal_id=goal.id, current="kod yozish")
    gctx = GoalContext(goal, obj)

    t1 = obj.add_task("snake klass", detail="grid logic", priority=2)
    t2 = obj.add_task("game loop", dependencies=[t1.id])
    sub = obj.add_task("sub-step", parent_task_id=t1.id)
    check("task tree", sub.parent_task_id == t1.id and t1.subtasks == [sub])
    check("sub inherits goal", sub.goal_id == goal.id)

    # invalid parent
    try:
        obj.add_task("x", parent_task_id="nope")
        check("bad parent blocked", False)
    except ValueError:
        check("bad parent blocked", True)

    # status transitions
    t1.set_status(TaskStatus.RUNNING)
    t1.set_status(TaskStatus.NEEDS_MORE_STEPS)
    t1.set_status(TaskStatus.RUNNING)
    t1.set_status(TaskStatus.COMPLETED)
    check("task completed", t1.is_terminal() and t1.finished_at is not None)
    try:
        t1.set_status(TaskStatus.RUNNING)        # COMPLETED terminal
        check("terminal blocked", False)
    except ValueError:
        check("terminal blocked", True)

    try:
        t2.set_status(TaskStatus.COMPLETED)      # PENDING -> COMPLETED
        check("PENDING->COMPLETED blocked", False)
    except ValueError:
        check("PENDING->COMPLETED blocked", True)

    # replan: goal saqlanadi
    wrong = Task(id="task-w", title="wrong goal", objective_id=obj.id,
                 goal_id="totally-wrong")
    obj.replan("yangi yondashuv", [wrong])
    check("replan keeps goal_id", obj.goal_id == goal.id)
    check("replan syncs task goal", obj.tasks[0].goal_id == goal.id)

    # frozen goal
    try:
        goal.text = "hacked"
        check("goal frozen", False)
    except Exception:
        check("goal frozen", True)

    # prompt pin
    pin = gctx.prompt_pin()
    check("pin has original goal", pin.startswith("[ORIGINAL GOAL]")
          and "Mini ilon" in pin)
    pin2 = gctx.prompt_pin("performance optimizatsiya")
    check("pin has current objective", "[CURRENT OBJECTIVE]" in pin2)

    # mismatch bind
    other = Objective(id="obj-2", goal_id="goal-OTHER", current="x")
    try:
        gctx.bind(other)
        check("bind mismatch blocked", False)
    except ValueError:
        check("bind mismatch blocked", True)

    # round-trip + resume
    d = gctx.to_dict()
    g2 = GoalContext.from_dict(d)
    check("round-trip goal", g2.goal.text == goal.text and g2.goal.id == goal.id)
    check("round-trip objective", g2.objective.current == obj.current
          and g2.objective.tasks[0].id == "task-w"
          and g2.objective.tasks[0].goal_id == goal.id)

    tmp = tempfile.mkdtemp(prefix="igris_goal_")
    try:
        from state.goal_model import save_goal_context, load_goal_context
        path = os.path.join(tmp, "goal_ctx.json")
        save_goal_context(gctx, path)
        g3 = load_goal_context(path)
        check("save/load resume", g3.goal.text == goal.text
              and g3.objective.goal_id == goal.id)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # empty goal rejected
    try:
        Goal.create("   ")
        check("empty goal rejected", False)
    except ValueError:
        check("empty goal rejected", True)

    # action round-trip
    a = Action(id="a1", tool="read_file", args={"path": "x.py"})
    a2 = Action.from_dict(a.to_dict())
    check("action round-trip", a2.tool == "read_file" and a2.args == {"path": "x.py"})


# ------------------------------------------------------------------ #
# 3. ToolMeta / ToolError / pre-post checks
# ------------------------------------------------------------------ #

def test_tool_meta():
    # default meta from overrides
    t = DEFAULT_REGISTRY.get("delete_file")
    check("delete_file destructive", t.meta.side_effect == "destructive"
          and t.meta.permission == "confirm")
    t = DEFAULT_REGISTRY.get("git_command")
    check("git_command unsafe", t.meta.side_effect == "unsafe")
    t = DEFAULT_REGISTRY.get("read_file")
    check("read_file read_only 10s", t.meta.side_effect == "read_only"
          and t.meta.timeout_s == 10.0)

    # registry schemas still work (backwards-compat)
    schemas = DEFAULT_REGISTRY.schemas()
    check("registry schemas intact", len(schemas) >= 13
          and all("name" in s for s in schemas))

    # explicit meta + precondition + postcondition
    def pre(args):
        if args.get("path", "").startswith("secret/"):
            return False, "precondition failed: secret path"
        return True, ""

    def post(args, result):
        if not result.get("ok"):
            return True, ""
        if len(result.get("content", "")) > 100:
            return False, "content too large"
        return True, ""

    meta = ToolMeta(side_effect="read_only", timeout_s=5.0,
                    precondition=pre, postcondition=post)
    tool = Tool(name="read_file", description="t", parameters=[
        {"name": "path", "type": "string"}], fn=lambda ws, a: {
            "ok": True, "content": "x" * 10}, meta=meta)

    r = tool.execute(None, {"path": "ok.txt"})
    check("precondition pass + postcondition pass", r.get("ok") is True
          and "postcondition_failed" not in r)
    r = tool.execute(None, {"path": "secret/k.txt"})
    check("precondition blocks", r.get("ok") is False and r.get("code") == 3)
    r = tool.execute(None, {})
    check("missing required args code=2", r.get("ok") is False
          and r.get("code") == 2)
    r = tool.execute(None, {"path": 123})
    check("wrong type code=2", r.get("ok") is False and r.get("code") == 2)

    # postcondition fail flags result
    tool2 = Tool(name="read_file", description="t", parameters=[
        {"name": "path", "type": "string"}], fn=lambda ws, a: {
            "ok": True, "content": "y" * 200}, meta=meta)
    r = tool2.execute(None, {"path": "ok.txt"})
    check("postcondition flags result", r.get("ok") is True
          and "postcondition_failed" in r)

    # ToolError -> standard result
    def boom(ws, a):
        raise ToolError(error="disk full", code=4, recoverable=False)
    tool3 = Tool(name="x", description="t", parameters=[], fn=boom)
    r = tool3.execute(None, {})
    check("ToolError standard format", r == {"ok": False, "error": "disk full",
                                             "code": 4, "recoverable": False})

    # generic exception -> code 5
    def bad(ws, a):
        raise RuntimeError("oops")
    tool4 = Tool(name="x", description="t", parameters=[], fn=bad)
    r = tool4.execute(None, {})
    check("generic exception code=5", r.get("ok") is False and r.get("code") == 5
          and r.get("recoverable") is True)


# ------------------------------------------------------------------ #
# 4. git_command deny-list (bypass fix)
# ------------------------------------------------------------------ #

def test_git_deny():
    tmp = tempfile.mkdtemp(prefix="igris_git_")
    try:
        ws = Workspace(tmp)
        blocked = [
            "push origin main",           # avval BYPASS edi (git prefikssiz)
            "git push origin main",
            "push --force origin main",
            "git push -f",
            "reset --hard HEAD~1",        # avval BYPASS edi
            "git reset --hard",
            "rebase main",                # yangi: tarix qayta yozish
            "git rebase -i HEAD~3",
            "branch -D feature",          # avval BYPASS edi
            "clean -fd",
            "git clean -f",
            "config --global user.name x",
            "git config --global user.email x@y.z",
            "reflog delete HEAD@{1}",
            "remote add evil https://evil.example",
        ]
        for cmd in blocked:
            r = DEFAULT_REGISTRY.execute(ws, "git_command", {"command": cmd})
            if r.get("ok") is not False or "blocked" not in str(r.get("error", "")):
                check(f"git deny: {cmd}", False)
                return
        check(f"git deny-list ({len(blocked)} ta bypass varianti)", True)

        # ruxsat etilgan buyruq — git yo'q bo'lsa ham blok EMAS
        r = DEFAULT_REGISTRY.execute(ws, "git_command", {"command": "status"})
        check("git allow: status", "blocked" not in str(r.get("error", "")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ #
# 5. Registry standart error formati
# ------------------------------------------------------------------ #

def test_registry_errors():
    tmp = tempfile.mkdtemp(prefix="igris_reg_")
    try:
        ws = Workspace(tmp)
        r = DEFAULT_REGISTRY.execute(ws, "no_such_tool", {})
        check("unknown tool code=1", r.get("code") == 1 and r.get("ok") is False)
        r = DEFAULT_REGISTRY.execute(ws, "git_command", {"command": "push origin"})
        check("denied code=3", r.get("code") == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ #

def main() -> int:
    test_state_machine()
    test_validate_plan_tools()
    test_goal_model()
    test_tool_meta()
    test_git_deny()
    test_registry_errors()
    print(f"OK | test_phase1_foundation: {PASS_COUNT} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
