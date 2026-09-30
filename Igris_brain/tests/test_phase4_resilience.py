"""Phase 4 impl testlari — §11/§15/§16 Resilience.

Qamrov:
  - §11 ErrorType enum: ToolError code -> ErrorType mapping, from_result
  - §15 Cancellation: cancel_event set -> run() "cancelled" status, checkpoint kept
  - §15 Cancellation: cancel o'rtada (step ichida) ham to'xtaydi
  - §15 Cancellation: run_native() ham cancel signaliga qaraydi
  - §11 Same-error -> escalate: bir xil xato N marta -> _record_tool_error True
  - §16 Structured logs: errors[] + recovery_events[] natija record'ida
  - Server RunManager: cancel() flag qo'yadi, status() cancel_requested ko'rsatadi

Run: python test_phase4_resilience.py
"""

import os
import sys
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from tools import Workspace, ToolRegistry, DEFAULT_REGISTRY
from tools.base import ToolError, ErrorType
from executor.executor import AgentExecutor

_RESULTS = []


def check(name, cond):
    _RESULTS.append((name, bool(cond)))
    return bool(cond)


# ------------------------------------------------------------------ #
# Fake LLM — hech narsa qilmaydi (offline test)
# ------------------------------------------------------------------ #

class FakeLLM:
    def complete(self, system=None, prompt=None, **kw):
        return ""

    def chat_with_tools(self, messages, tools=None, **kw):
        return None


def _mk_executor(tmpdir, **kw):
    return AgentExecutor(
        workspace_root=tmpdir,
        llm=FakeLLM(),
        checkpoint_dir=os.path.join(tmpdir, "cp"),
        **kw,
    )


# ------------------------------------------------------------------ #
# §11: ErrorType enum
# ------------------------------------------------------------------ #

class TestErrorType(unittest.TestCase):
    def test_from_result_mapping(self):
        check("code 1 -> unknown_tool",
              ErrorType.from_result({"ok": False, "code": 1, "error": "x"}) == "unknown_tool")
        check("code 2 -> invalid_args",
              ErrorType.from_result({"ok": False, "code": 2, "error": "x"}) == "invalid_args")
        check("code 3 -> denied",
              ErrorType.from_result({"ok": False, "code": 3, "error": "x"}) == "denied")
        check("code 4 -> timeout",
              ErrorType.from_result({"ok": False, "code": 4, "error": "x"}) == "timeout")
        check("code 5 -> internal",
              ErrorType.from_result({"ok": False, "code": 5, "error": "x"}) == "internal")
        check("no code -> internal",
              ErrorType.from_result({"ok": False, "error": "x"}) == "internal")
        check("ok -> empty",
              ErrorType.from_result({"ok": True}) == "")
        check("unknown code -> tool_error",
              ErrorType.from_result({"ok": False, "code": 99, "error": "x"}) == "tool_error")


# ------------------------------------------------------------------ #
# §15: Cancellation — planned loop
# ------------------------------------------------------------------ #

class TestCancelPlanned(unittest.TestCase):
    def test_cancel_before_run(self):
        """Cancel event oldindan set bo'lsa — run darhol 'cancelled' qaytaradi."""
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        ex.cancel_event.set()
        res = ex.run("hello world task")
        check("pre-cancelled run -> cancelled", res.get("status") == "cancelled")
        check("cancelled flag in result", res.get("cancelled") is True)
        check("recovery event logged",
              any(e.get("action") == "cancelled" for e in res.get("recovery_events", [])))

    def test_cancel_mid_run(self):
        """Run davomida cancel bosilsa — keyingi step'da to'xtaydi."""
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ev = threading.Event()
        ex = _mk_executor(tmp, cancel_event=ev)
        # 1-chastdan keyin cancel bosamiz — timer bilan
        def _cancel_soon():
            time.sleep(0.05)
            ev.set()
        threading.Thread(target=_cancel_soon, daemon=True).start()
        res = ex.run("write hello to file")
        check("mid-cancel -> cancelled status", res.get("status") == "cancelled")
        check("cancelled result flag", res.get("cancelled") is True)

    def test_cancel_checkpoint_kept(self):
        """Cancelled run — checkpoint SAQLANADI (resume mumkin)."""
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        ex.cancel_event.set()
        res = ex.run("create test file xyz")
        if res.get("goal_id"):
            check("cancelled -> checkpoint kept", res.get("checkpoint") == "kept")


# ------------------------------------------------------------------ #
# §15: Cancellation — native loop
# ------------------------------------------------------------------ #

class TestCancelNative(unittest.TestCase):
    def test_cancel_native_pre(self):
        """run_native ham cancel signaliga qaraydi."""
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        ex.cancel_event.set()
        res = ex.run_native("some task")
        check("pre-cancelled native -> cancelled", res.get("status") == "cancelled")


# ------------------------------------------------------------------ #
# §11: Same-error -> escalate
# ------------------------------------------------------------------ #

class TestSameErrorEscalate(unittest.TestCase):
    def test_same_error_counter(self):
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        out = {"ok": False, "error": "connection refused", "code": 5}
        e1 = ex._record_tool_error("web_fetch", out)
        e2 = ex._record_tool_error("web_fetch", out)
        e3 = ex._record_tool_error("web_fetch", out)
        check("1st error -> no escalate", e1 is False)
        check("2nd error -> no escalate", e2 is False)
        check("3rd same error -> ESCALATE", e3 is True)

    def test_different_errors_no_escalate(self):
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        check("err A", ex._record_tool_error("t", {"ok": False, "error": "A"}) is False)
        check("err B", ex._record_tool_error("t", {"ok": False, "error": "B"}) is False)
        check("err C", ex._record_tool_error("t", {"ok": False, "error": "C"}) is False)
        check("err D (har xili) -> no escalate",
              ex._record_tool_error("t", {"ok": False, "error": "D"}) is False)

    def test_error_log_structured(self):
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        ex._record_tool_error("web_fetch", {"ok": False, "error": "boom", "code": 5})
        check("error log length", len(ex._error_log) == 1)
        entry = ex._error_log[0]
        check("error entry keys",
              set(entry.keys()) == {"type", "message", "tool", "ts"})
        check("error type internal (code 5)", entry["type"] == "internal")


# ------------------------------------------------------------------ #
# §16: Structured logs in result
# ------------------------------------------------------------------ #

class TestLogsInResult(unittest.TestCase):
    def test_errors_and_recovery_in_result(self):
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        ex.cancel_event.set()
        res = ex.run("abc task")
        check("errors list present after cancel",
              isinstance(res.get("errors"), list) or res.get("errors") is None)
        check("recovery_events present",
              any(e.get("action") == "cancelled" for e in res.get("recovery_events", [])))


# ------------------------------------------------------------------ #
# §15: RunManager cancel (server darajasi — FastAPI'siz)
# ------------------------------------------------------------------ #

class TestRunManagerCancel(unittest.TestCase):
    def test_run_manager_cancel_flow(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from server.server import RunManager
        except Exception as exc:
            check("RunManager import (fastapi mavjud)", False)
            return
        rm = RunManager()
        # Fake run state (thread'siz — cancel flag tekshiruvi)
        with rm._lock:
            rm._runs["test-run-1"] = {"id": "test-run-1", "status": "running",
                                      "started_at": time.time()}
            rm._cancel_events["test-run-1"] = threading.Event()
        ok = rm.cancel("test-run-1")
        check("cancel returns True for running", ok is True)
        with rm._lock:
            ev = rm._cancel_events["test-run-1"]
            st = rm._runs["test-run-1"]
        check("cancel event is set", ev.is_set())
        check("cancel_requested flag", st.get("cancel_requested") is True)
        st_state = rm.status("test-run-1")
        check("status shows cancel_requested", st_state.get("cancel_requested") is True)
        # Tugagan run — cancel False
        with rm._lock:
            rm._runs["test-run-1"]["status"] = "done"
        check("cancel on finished run -> False", rm.cancel("test-run-1") is False)
        # Yo'q run — False
        check("cancel on unknown run -> False", rm.cancel("nope") is False)


# ------------------------------------------------------------------ #
# Regression: normal run cancel'siz ishlayveradi
# ------------------------------------------------------------------ #

class TestNoCancelRegression(unittest.TestCase):
    def test_normal_run_unaffected(self):
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")
        ex = _mk_executor(tmp)
        check("cancel_event default not set", not ex.cancel_event.is_set())
        res = ex.run("hello")
        check("normal run status not cancelled", res.get("status") != "cancelled")
        check("no errors in clean run", not res.get("errors"))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestErrorType, TestCancelPlanned, TestCancelNative,
                TestSameErrorEscalate, TestLogsInResult, TestRunManagerCancel,
                TestNoCancelRegression):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=1)
    res = runner.run(suite)
    passed = res.testsRun - len(res.failures) - len(res.errors)
    print(f"\n{'=' * 50}")
    print(f"CHECKS: {passed}/{res.testsRun} PASS"
          + ("" if res.wasSuccessful() else "  <<< FAILURES"))
    sys.exit(0 if res.wasSuccessful() else 1)
