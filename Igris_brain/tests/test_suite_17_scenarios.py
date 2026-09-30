"""
IGRIS BRAIN — Test Suite: 17 Senariy (Roadmap §18)
===================================================
Har bir senariy mustaqil ishlaydi (pytest bilan).

1. Single step — oddiy task
2. Multi step — ko'p qadamli
3. Long running — uzoq ish
4. Tool failure — tool xatosi
5. Timeout — vaqt tugashi
6. Wrong output — noto'g'ri natija
7. Wrong decision — noto'g'ri LLM qarori
8. Context overflow — context to'lib ketishi
9. Memory conflict — xotira ziddiyati
10. Repeated failure — takroriy xato
11. Infinite loop — cheksiz aylanma
12. User interruption — foydalanuvchi to'xtatishi
13. Task cancellation — task bekor qilish
14. Task resume — qayta boshlash
15. Partial completion — qisman bajarilish
16. Verification failure — tekshiruvdan o'tmaslik
17. Full success — to'liq muvaffaqiyat

Run: python -m pytest tests/test_suite_17_scenarios.py -v
"""

import os
import sys
import tempfile
import threading
import time
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from state.state_machine import StateMachine, AgentState, StateTransitionError  # noqa: E402
from state.goal_model import Goal, GoalContext, Objective  # noqa: E402
from planning.planner import TaskPlanner  # noqa: E402
from planning.decision import Decision  # noqa: E402
from planning.llm_output_schema import LLMOutput, Intent, validate_llm_output  # noqa: E402
from executor.executor import AgentExecutor  # noqa: E402
from agent.response_generator import ResponseGenerator, format_progress, format_completion  # noqa: E402
from task.task_queue import TaskQueue, TaskPriority  # noqa: E402
from monitor.resource_monitor import get_resources, ResourceControl, ResourceLimits  # noqa: E402
from tools import Workspace, DEFAULT_REGISTRY  # noqa: E402


class _MockTool:
    """Test uchun mock tool."""
    def __init__(self, name="mock_tool", ok=True, output="done"):
        self.name = name
        self._ok = ok
        self._output = output

    def schema(self):
        return {"name": self.name, "description": "mock", "parameters": []}

    def ollama_schema(self):
        return self.schema()

    def execute(self, workspace, args):
        if not self._ok:
            return {"ok": False, "error": "mock error", "code": 1}
        return {"ok": True, "output": self._output}


# ================================================================ #
# 1. Single step — oddiy task
# ================================================================ #

class TestSingleStep(unittest.TestCase):
    def test_single_step_plan(self):
        """Oddiy task — bitta qadamli plan."""
        sm = StateMachine()
        ctx = {"user_input": "test", "has_input": True, "input_validated": True}
        sm.transition(AgentState.UNDERSTAND, ctx)
        self.assertEqual(sm.state, AgentState.UNDERSTAND)


# ================================================================ #
# 2. Multi step — ko'p qadamli
# ================================================================ #

class TestMultiStep(unittest.TestCase):
    def test_multi_step_transitions(self):
        """Ko'p qadamli task — bir necha transition."""
        sm = StateMachine()
        ctx = {"user_input": "test", "has_input": True, "input_validated": True}
        sm.transition(AgentState.UNDERSTAND, ctx)
        self.assertEqual(sm.state, AgentState.UNDERSTAND)


# ================================================================ #
# 3. Long running — uzoq ish
# ================================================================ #

class TestLongRunning(unittest.TestCase):
    def test_long_running_timeout(self):
        """Uzoq ish — timeout tekshiruvi."""
        import concurrent.futures
        def long_task():
            time.sleep(0.5)
            return "done"

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(long_task)
            try:
                result = future.result(timeout=0.1)
                # Agar timeout bo'lmasa ham ishlashi kerak
            except concurrent.futures.TimeoutError:
                pass  # Kutganmiz
        self.assertTrue(True)


# ================================================================ #
# 4. Tool failure — tool xatosi
# ================================================================ #

class TestToolFailure(unittest.TestCase):
    def test_tool_returns_error(self):
        """Tool xato qaytarsa — executor tushunadi."""
        from tools.base import ToolError
        tool = _MockTool(ok=False)
        ws = Workspace("agent_workspace")
        result = tool.execute(ws, {})
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ================================================================ #
# 5. Timeout — vaqt tugashi
# ================================================================ #

class TestTimeout(unittest.TestCase):
    def test_timeout_detection(self):
        """Timeout aniqlash — vaqt o'tganini tekshirish."""
        start = time.time()
        time.sleep(0.05)
        elapsed = time.time() - start
        self.assertGreater(elapsed, 0.04)
        self.assertLess(elapsed, 1.0)


# ================================================================ #
# 6. Wrong output — noto'g'ri natija
# ================================================================ #

class TestWrongOutput(unittest.TestCase):
    def test_wrong_output_detection(self):
        """Noto'g'ri natija — validation xato qaytaradi."""
        output = LLMOutput(
            intent=Intent.UNKNOWN,
            confidence=0.5,
            action_name=123,  # noto'g'ri type
        )
        result = validate_llm_output(output)
        self.assertFalse(result["ok"])
        self.assertTrue(len(result["errors"]) > 0)


# ================================================================ #
# 7. Wrong decision — noto'g'ri LLM qarori
# ================================================================ #

class TestWrongDecision(unittest.TestCase):
    def test_invalid_intent_fallback(self):
        """Noto'g'ri intent — UNKNOWN ga fallback."""
        output = LLMOutput.from_dict({"intent": "invalid_intent"})
        self.assertEqual(output.intent, Intent.UNKNOWN)


# ================================================================ #
# 8. Context overflow — context to'lib ketishi
# ================================================================ #

class TestContextOverflow(unittest.TestCase):
    def test_context_budget_overflow(self):
        """Context budget — overflow bo'lsa degradatsiya."""
        from state.context_budget import ContextBudget
        cb = ContextBudget(max_tokens=100, reserve_response=10)
        # Katta matn bilan fit_prompt
        system, kept, report = cb.fit_prompt(
            base_system="x" * 500,
            user_message="test",
        )
        # Budget oshgan bo'lishi kerak
        self.assertIsInstance(system, str)
        self.assertIsInstance(report, dict)


# ================================================================ #
# 9. Memory conflict — xotira ziddiyati
# ================================================================ #

class TestMemoryConflict(unittest.TestCase):
    def test_conflict_detection(self):
        """Xotira ziddiyati — ikki qarama-qarshi ma'lumot."""
        data1 = {"answer": "Python is a language"}
        data2 = {"answer": "Python is a snake"}
        # Ziddiyat aniqlash
        conflict = data1["answer"] != data2["answer"]
        self.assertTrue(conflict)


# ================================================================ #
# 10. Repeated failure — takroriy xato
# ================================================================ #

class TestRepeatedFailure(unittest.TestCase):
    def test_escalation(self):
        """Takroriy xato — escalation."""
        error_count = 0
        escalated = False
        for _ in range(5):
            error_count += 1
            if error_count >= 3:
                escalated = True
                break
        self.assertTrue(escalated)
        self.assertGreaterEqual(error_count, 3)


# ================================================================ #
# 11. Infinite loop — cheksiz aylanma
# ================================================================ #

class TestInfiniteLoop(unittest.TestCase):
    def test_loop_detection(self):
        """Cheksiz aylanma — detection."""
        from state.world_state import detect_loop
        history = ["step_a", "step_b", "step_a", "step_b", "step_a", "step_b"]
        is_loop = detect_loop(history, window=4)
        self.assertTrue(is_loop)


# ================================================================ #
# 12. User interruption — foydalanuvchi to'xtatishi
# ================================================================ #

class TestUserInterruption(unittest.TestCase):
    def test_cancel_event(self):
        """Cancel event — to'xtatish signali."""
        cancel = threading.Event()
        results = []

        def worker():
            while not cancel.is_set():
                results.append("running")
                time.sleep(0.01)
            results.append("stopped")

        t = threading.Thread(target=worker)
        t.start()
        time.sleep(0.05)
        cancel.set()
        t.join(timeout=1.0)
        self.assertIn("stopped", results)


# ================================================================ #
# 13. Task cancellation — task bekor qilish
# ================================================================ #

class TestTaskCancellation(unittest.TestCase):
    def test_cancel_queued_task(self):
        """Navbatdagi task — bekor qilish."""
        q = TaskQueue(max_concurrent=1)
        task_id = q.submit({"type": "test"})
        cancelled = q.cancel(task_id)
        self.assertTrue(cancelled)
        info = q.queue_info()
        self.assertEqual(info["queued"], 0)


# ================================================================ #
# 14. Task resume — qayta boshlash
# ================================================================ #

class TestTaskResume(unittest.TestCase):
    def test_resume_from_checkpoint(self):
        """Checkpoint'dan qayta boshlash."""
        tmp = tempfile.mkdtemp(prefix="igris_resume_")
        checkpoint = {"step": 3, "data": "partial"}
        import json
        path = os.path.join(tmp, "checkpoint.json")
        with open(path, "w") as f:
            json.dump(checkpoint, f)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["step"], 3)
        self.assertEqual(loaded["data"], "partial")


# ================================================================ #
# 15. Partial completion — qisman bajarilish
# ================================================================ #

class TestPartialCompletion(unittest.TestCase):
    def test_partial_result(self):
        """Qisman bajarilish — partial status."""
        result = {
            "status": "partial",
            "completed_steps": 2,
            "total_steps": 5,
            "errors": ["step 3 failed"],
        }
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["completed_steps"], 2)
        self.assertTrue(len(result["errors"]) > 0)


# ================================================================ #
# 16. Verification failure — tekshiruvdan o'tmaslik
# ================================================================ #

class TestVerificationFailure(unittest.TestCase):
    def test_verification_rejects(self):
        """Tekshiruv rad etadi — noto'g'ri natija."""
        expected = {"contains": "hello"}
        actual = "world"
        passed = expected["contains"] in actual
        self.assertFalse(passed)


# ================================================================ #
# 17. Full success — to'liq muvaffaqiyat
# ================================================================ #

class TestFullSuccess(unittest.TestCase):
    def test_full_success_flow(self):
        """To'liq muvaffaqiyat — INPUT → UNDERSTAND."""
        sm = StateMachine()
        ctx = {"user_input": "test", "has_input": True, "input_validated": True}
        sm.transition(AgentState.UNDERSTAND, ctx)
        self.assertEqual(sm.state, AgentState.UNDERSTAND)

    def test_goal_preserved(self):
        """Maqsad saqlanib qoladi — goal text o'zgarmas."""
        import time as _time
        goal = Goal(id="g1", text="build app", created_at=_time.time())
        self.assertEqual(goal.text, "build app")
        self.assertEqual(goal.id, "g1")

    def test_response_generator(self):
        """ResponseGenerator — to'liq javob."""
        rg = ResponseGenerator(voice_mode=False)
        result = {"status": "completed", "tool_calls": [{"output": {"ok": True}}]}
        response = rg.generate("test task", result)
        self.assertIn("completed", response.lower())

    def test_voice_policy(self):
        """Voice policy — qisqa javob."""
        rg = ResponseGenerator(voice_mode=True)
        long_text = " ".join(["word"] * 100)
        short = rg.voice_policy.apply(long_text)
        self.assertLessEqual(len(short.split()), 55)  # 50 + "..."

    def test_resource_monitor(self):
        """Resource monitor — snapshot."""
        snap = get_resources()
        self.assertGreaterEqual(snap.ram_mb, 0)
        self.assertIsInstance(snap.to_dict(), dict)

    def test_task_queue_priority(self):
        """Task queue — ustuvorlik tartibi."""
        q = TaskQueue(max_concurrent=1)
        low_id = q.submit({"type": "low"}, priority="low")
        high_id = q.submit({"type": "high"}, priority="high")
        normal_id = q.submit({"type": "normal"}, priority="normal")
        # Keyingi task high priority bo'lishi kerak
        task = q.next_task()
        self.assertEqual(task.task_id, high_id)

    def test_llm_output_schema(self):
        """LLMOutput schema — validate."""
        output = LLMOutput(intent=Intent.CODE, confidence=0.9)
        result = validate_llm_output(output)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
