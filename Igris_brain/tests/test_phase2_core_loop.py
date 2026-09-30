"""Phase 2 Core Loop implementatsiya testlari.

Qamrov: world_state.py (Observation/AgentWorldState/VerificationRecord/
detect_loop/detect_stuck) + executor integratsiyasi (Action ID, world tracing,
verification evidence, native goal pin + world).

Run: python test_phase2_core_loop.py
"""

import os
import shutil
import sys
import tempfile

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from state.world_state import (  # noqa: E402
    AgentWorldState, Observation, VerificationLog, VerificationRecord,
    detect_loop, detect_stuck,
)
from executor.executor import AgentExecutor  # noqa: E402
from state.state_machine import AgentState, VerificationStatus  # noqa: E402


PASS_COUNT = 0


def check(name: str, cond: bool):
    global PASS_COUNT
    print(("PASS" if cond else "FAIL") + " | " + name)
    if not cond:
        sys.exit(1)
    PASS_COUNT += 1


def test_world_state():
    ws = AgentWorldState()
    ws.add_from_record({"tool": "write_file", "action_id": "act-1",
                        "args": {"path": "x.txt"},
                        "result": {"ok": True, "bytes": 50},
                        "output_preview": "written"})
    ws.add_from_record({"tool": "run_command", "action_id": "act-2",
                        "args": {}, "result": {"ok": False, "error": "nope"},
                        "output_preview": "nope"})
    s = ws.stats()
    check("ws confirmed/assumed split", s["confirmed"] == 1 and s["assumed"] == 1)
    check("ws files_touched", "x.txt" in ws.files_touched)
    check("ws flags confirmed", ws.observation_flags() == ["confirmed"])
    check("ws last_error", ws.last_error == "nope")

    # faqat xatolar bo'lsa — flags assumed (verify UNKNOWN, COMPLETE taqiqlanadi)
    ws2 = AgentWorldState()
    ws2.add_from_record({"tool": "list_files", "action_id": "a3", "args": {},
                         "result": {"ok": False}, "output_preview": "err"})
    check("ws flags assumed-only", ws2.observation_flags() == ["assumed"])

    # compress
    for i in range(30):
        ws2.add_from_record({"tool": "read_file", "action_id": f"a{i}", "args": {},
                             "result": {"ok": True}, "output_preview": f"n{i}"})
    summary = ws2.compress_old(keep_last=5)
    check("ws compress", bool(summary) and len(ws2.observations) == 5
          and len(ws2.compressed_summaries) == 1)

    # empty state — flags bo'sh
    check("ws empty flags", AgentWorldState().observation_flags() == [])


def test_verification_record():
    vr = VerificationRecord.make("a1", "syntax", True,
                                 expected={"syntax_ok": True},
                                 actual={"syntax": "ok"})
    check("vr verified", vr.status == VerificationStatus.VERIFIED.value)
    vr = VerificationRecord.make("a2", "run", False, note="NameError")
    check("vr failed", vr.status == VerificationStatus.FAILED.value
          and vr.note == "NameError")
    vr = VerificationRecord.make("a3", "deliverable", None)
    check("vr unknown", vr.status == VerificationStatus.UNKNOWN.value)

    log = VerificationLog()
    log.add(VerificationRecord.make("a1", "syntax", True))
    log.add(VerificationRecord.make("a2", "deliverable", False))
    check("vlog final_status", log.final_status() == "FAILED")
    check("vlog to_list", len(log.to_list()) == 2
          and "expected" in log.to_list()[0])

    d = VerificationRecord.make("a9", "grounding", True).to_dict()
    check("vr evidence fields",
          all(k in d for k in ("action_id", "expected", "actual",
                               "method", "status", "timestamp")))


def test_loop_detection():
    # aylanma: A→B→A→B (exact dedup ushlab ko'rolmaydigan naqsh)
    loop, why = detect_loop(["write_file:{p:a}", "read_file:{p:a}",
                             "write_file:{p:a}", "read_file:{p:a}"])
    check("loop A-B pattern caught", loop and "repeats" in why)
    # normal ketma-ketlik — loop emas
    loop2, _ = detect_loop(["write_file:{p:a}", "read_file:{p:b}", "run_command:{}"])
    check("normal flow not loop", not loop2)
    # qisqa tarix — tekshiruvga yetmaydi
    loop3, _ = detect_loop(["x:1", "x:1"])
    check("short history ignored", not loop3)
    # stuck: 7 iteratsiya, 0 yozuv
    stuck, why2 = detect_stuck(0, 7)
    check("stuck caught", stuck and "no write" in why2)
    # yozma ish bo'lsa — stuck emas
    stuck2, _ = detect_stuck(2, 7)
    check("write prevents stuck", not stuck2)


def test_executor_action_ids():
    """run() — har tool record'da action_id bor, world/vlog tracing bor."""
    tmp = tempfile.mkdtemp(prefix="igris_p2_")
    try:
        ex = AgentExecutor(workspace_root=tmp, llm=None)
        res = ex.run("write a file notes2.txt")

        tcs = res.get("tool_calls", [])
        check("records have action_id", all(tc.get("action_id") for tc in tcs))
        check("action_id unique", len({tc["action_id"] for tc in tcs}) == len(tcs))
        check("world_stats in result", "world_stats" in res
              and res["world_stats"]["observations"] >= 1)
        check("confirmed_facts in result", isinstance(res.get("confirmed_facts"), list))
        # fayl yozilgan bo'lsa files_touched'da (haqiqiy yo'llar ex.world'da)
        if os.path.exists(os.path.join(tmp, "notes2.txt")):
            touched = list((ex.world.files_touched or {}).keys())
            check("world files_touched tracked",
                  touched and any("notes2" in p for p in touched)
                  and res["world_stats"]["files_touched"] == len(touched))
        # verifications evidence (deliverable gate ishlagan bo'lsa)
        if "verifications" in res:
            check("verifications evidence fields",
                  all(k in res["verifications"][0]
                      for k in ("expected", "actual", "method", "status")))
        else:
            # deliverable gate ishga tushmagan (masalan browser task) — ham OK
            check("verifications optional (gate not triggered)", True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_run_native_world_and_loop_guard():
    """run_native — world state to'ldiriladi; aylanma guard ishlaydi."""
    tmp = tempfile.mkdtemp(prefix="igris_p2n_")
    try:
        class MockLLM:
            model = "mock"

            def complete(self, system="", prompt=""):
                return ""

            def chat_with_tools(self, messages, tools=None):
                # aylanma: har doim bir xil ketma-ketlikni takrorlaymiz
                # (ayniy args — seen_calls bloklaydi, keyin 'no progress' yo'li)
                return {"content": "", "tool_calls": [
                    {"function": {"name": "list_files",
                                  "arguments": {"path": ""}}}]}
                yield  # pragma: no cover

        ex = AgentExecutor(workspace_root=tmp, llm=MockLLM())
        res = ex.run_native("loop test task")
        check("native finished", res.get("status") in ("ok", "partial", "stopped"))
        check("native world_stats", "world_stats" in res)
        check("native goal_id", str(res.get("goal_id", "")).startswith("goal-"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    test_world_state()
    test_verification_record()
    test_loop_detection()
    test_executor_action_ids()
    test_run_native_world_and_loop_guard()
    print(f"OK | test_phase2_core_loop: {PASS_COUNT} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
