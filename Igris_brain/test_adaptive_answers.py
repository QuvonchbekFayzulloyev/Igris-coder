"""
IGRIS — Adaptive answers tests (Part L, CP-L6)
==============================================
- Bir xil vazifa, TURLI talab → turli javob shakli (adaptivlik).
- Final xulosa ko'rsatmasi req verbosity/format'ga mos (qotib qolgan
  "2-3 short sentences" o'rniga).
- Placeholder/canned natijalar yo'qligi tekshiriladi.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.requirements import Requirement  # noqa: E402
from planner import TaskPlanner  # noqa: E402


class _FakeLLM:
    def __init__(self):
        self.prompts = []

    def complete(self, system="", prompt=""):
        self.prompts.append(prompt)
        return "{}"

    def chat(self, messages):
        # Xulosa ko'rsatmasini yozib olamiz (final user qatori)
        for m in messages:
            if m.get("role") == "user":
                self.prompts.append(str(m.get("content")))
        return "Bajarildi."


class TestAdaptivity(unittest.TestCase):
    def test_same_task_different_verbosity_changes_plan(self):
        p = TaskPlanner(llm=None)
        task = "hisobot tayyorla"
        detailed = p.plan(task, Requirement(intent="file", output_format="file",
                                            verbosity="detailed", deliverable_name="hisobot.md"))
        concise = p.plan(task, Requirement(intent="answer", output_format="text",
                                           verbosity="concise"))
        d_titles = " | ".join(s["title"] for s in detailed["steps"])
        c_titles = " | ".join(s["title"] for s in concise["steps"])
        # detailed (fayl) rejasi fayl yaratishni o'z ichiga oladi; concise — yo'q
        self.assertIn("hisobot.md", d_titles)
        self.assertNotIn("hisobot.md", c_titles)
        self.assertNotEqual(d_titles, c_titles)

    def test_summary_instruction_honors_verbosity(self):
        from executor import AgentExecutor
        llm = _FakeLLM()
        tmp = tempfile.mkdtemp(prefix="igris_adapt_")
        ex = AgentExecutor(workspace_root=tmp, llm=llm)
        msgs = [{"role": "system", "content": "sys"},
                {"role": "user", "content": "vazifa"}]
        ex._ask_final_summary(msgs, Requirement(intent="code", language="uz",
                                                verbosity="detailed"))
        detail_prompt = llm.prompts[-1]
        self.assertIn("detailed summary", detail_prompt)
        self.assertIn("uz", detail_prompt)

        llm.prompts.clear()
        ex._ask_final_summary(msgs, Requirement(intent="answer", language="en",
                                                verbosity="concise"))
        concise_prompt = llm.prompts[-1]
        self.assertIn("1-2 short sentences", concise_prompt)
        self.assertIn("en", concise_prompt)


class TestNoCanned(unittest.TestCase):
    def test_requirement_to_block_marks_tool_needed(self):
        r = Requirement(intent="file", output_format="file", needs_tools=True)
        block = r.to_block()
        self.assertIn("requires tools", block)

    def test_llm_bad_parse_falls_back_safely(self):
        from core.requirements import RequirementExtractor

        class Bad:
            def complete(self, system="", prompt=""):
                return "%%% not json"

        r = RequirementExtractor(llm=Bad()).extract("rasm chizib ber")
        # Deterministik fallback — xatolikda crash emas
        self.assertEqual(r.intent, "draw")


if __name__ == "__main__":
    unittest.main(verbosity=2)