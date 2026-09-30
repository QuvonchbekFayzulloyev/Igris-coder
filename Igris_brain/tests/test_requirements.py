"""
IGRIS — RequirementExtractor + adaptive planning tests (Part L)
===============================================================
- Deterministic fallback: til/intent/format/chuqurlik/deliverable to'g'ri.
- LLM path: JSON parse + CAG cache.
- planner.plan(requirements=...) — fallback reja talab modeliga mos.
- executor: placeholder args yo'q; _req_asks_output req asosida ishlaydi.
"""

import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from core.requirements import Requirement, RequirementExtractor  # noqa: E402
from planning.planner import TaskPlanner  # noqa: E402


class _FakeLLM:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, system="", prompt=""):
        self.calls.append((system, prompt))
        return self.text


class TestRequirementDeterministic(unittest.TestCase):
    def _ex(self, msg):
        return RequirementExtractor(llm=None).extract(msg)

    def test_code_intent_and_deliverable(self):
        r = self._ex("qisqa qilib React backend yoz, fayl: app.py")
        self.assertEqual(r.intent, "code")
        self.assertEqual(r.output_format, "code")
        self.assertEqual(r.deliverable_name, "app.py")
        self.assertTrue(r.needs_tools)
        self.assertEqual(r.language, "uz")

    def test_weather_intent(self):
        r = self._ex("bugun Toshkentda havo qanday")
        self.assertEqual(r.intent, "weather")

    def test_summarize_and_verbosity(self):
        r = self._ex("batafsil xulosa ber")
        self.assertEqual(r.intent, "summarize")
        self.assertEqual(r.verbosity, "detailed")

    def test_table_format(self):
        r = self._ex("jadval qilib ko'rsat")
        self.assertEqual(r.output_format, "table")

    def test_list_format_and_concise(self):
        r = self._ex("qisqa ro'yxat qilib ber")
        self.assertEqual(r.output_format, "list")
        self.assertEqual(r.verbosity, "concise")

    def test_english_default(self):
        r = self._ex("write a python script that sorts a list")
        self.assertEqual(r.language, "en")
        self.assertEqual(r.intent, "code")


class TestRequirementLLMPath(unittest.TestCase):
    def test_parse_and_cache(self):
        from agent.cag import CagCache
        llm = _FakeLLM('{"intent": "code", "language": "uz", "output_format": "code", '
                       '"verbosity": "detailed", "constraints": ["test qo\\u0161ish"], '
                       '"deliverable_name": "main.py", "domain": "", "needs_tools": true, '
                       '"confidence": 0.9}')
        cache = CagCache()
        ex = RequirementExtractor(llm=llm, cache=cache)
        r = ex.extract("app.py fayl yoz, test qo'shish bilan")
        self.assertEqual(r.intent, "code")
        self.assertEqual(r.output_format, "code")
        self.assertEqual(r.verbosity, "detailed")
        self.assertEqual(r.deliverable_name, "main.py")
        self.assertTrue(r.needs_tools)
        self.assertEqual(len(llm.calls), 1)
        # Ikkinchi chaqiruv — CAG hit, LLM qayta chaqirilmaydi
        r2 = ex.extract("app.py fayl yoz, test qo'shish bilan")
        self.assertEqual(r2.intent, "code")
        self.assertEqual(len(llm.calls), 1)

    def test_bad_json_falls_back_deterministic(self):
        llm = _FakeLLM("no json here")
        ex = RequirementExtractor(llm=llm)
        r = ex.extract("havo qanday")
        self.assertEqual(r.intent, "weather")  # deterministic fallback

    def test_to_block(self):
        r = Requirement(intent="code", language="uz", output_format="code",
                        verbosity="detailed", constraints=["test qo'shish"],
                        deliverable_name="main.py")
        block = r.to_block()
        self.assertIn("deliverable file: main.py", block)
        self.assertIn("constraints: test qo'shish", block)


class TestPlannerAdaptive(unittest.TestCase):
    def test_fallback_uses_requirements(self):
        p = TaskPlanner(llm=None)
        req = Requirement(intent="code", output_format="code",
                          deliverable_name="app.py", needs_tools=True)
        plan = p.plan("React backend yoz app.py", req)
        self.assertEqual(plan["engine"], "fallback")
        titles = " | ".join(s["title"] for s in plan["steps"])
        self.assertIn("app.py", titles)
        self.assertIn("Write app.py", titles)

    def test_fallback_without_requirements(self):
        p = TaskPlanner(llm=None)
        plan = p.plan("fix the bug and run tests")
        self.assertEqual(plan["engine"], "fallback")
        self.assertTrue(plan["steps"])

    def test_fallback_web_uses_requirement(self):
        p = TaskPlanner(llm=None, mcp_names=["web_ai_bridge__browser_navigate",
                                              "web_ai_bridge__browser_get_text"])
        req = Requirement(intent="web", output_format="steps", language="uz")
        plan = p.plan("saytni ochib tahlil qil", req)
        titles = " | ".join(s["title"] for s in plan["steps"])
        self.assertIn("browser", titles.lower())
        self.assertIn("steps", titles.lower())


class TestExecutorAdaptive(unittest.TestCase):
    def _executor(self, llm=None):
        from executor.executor import AgentExecutor
        tmp = tempfile.mkdtemp(prefix="igris_req_test_")
        return AgentExecutor(workspace_root=tmp, llm=llm)

    def test_req_asks_output(self):
        ex = self._executor()
        r = Requirement(intent="file", output_format="file", deliverable_name="hisobot.md")
        self.assertTrue(ex._req_asks_output("x", r))
        r2 = Requirement(intent="answer", output_format="text")
        self.assertFalse(ex._req_asks_output("x", r2))

    def test_default_args_no_placeholder(self):
        ex = self._executor(llm=None)
        args = ex._default_args("write_file", {"title": "x", "detail": ""}, "task yoz")
        # Offline'da ham placeholder "# generated by Igris" yo'q
        self.assertNotIn("generated by Igris", str(args.get("content", "")))
        args2 = ex._default_args("python_exec", {"title": "x", "detail": ""}, "task yoz")
        self.assertNotEqual(args2.get("code"), "print('ok')")

    def test_default_args_llm_fails_no_fake(self):
        ex = self._executor(llm=_FakeLLM("garbage"))
        args = ex._default_args("write_file", {"title": "x", "detail": ""}, "task")
        # LLM args bera olmasa — {} qaytadi (yolg'on fayl emas)
        self.assertNotIn("generated by Igris", str(args.get("content", "")))
        self.assertTrue(set(args).issubset({"path", "content", "patch", "command", "code"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)