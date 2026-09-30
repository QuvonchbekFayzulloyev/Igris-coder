"""
IGRIS BRAIN — Web Answer Source Verification (A4) tests
========================================================
problems_to_fix.md :: A4 — Web/fakt savollarida manba tekshiruvi yo'q.

Qamrov:
- web_verify unit: SourceIndex coverage, fragment ajratish, verify_answer verdict
- grounding_signal: verdict -> SelfEvaluator qiymati
- SelfEvaluator: grounding signal (+0.10 grounded / -0.15 ungrounded / None)
- IgrisAgent: web tool natijasi yig'iladi, _with_self_eval grounding yozadi,
  _grounding_result ichki maydoni javobga oqib ketmaydi, fail-safe
"""

import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from web.web_verify import (  # noqa: E402
    GroundingResult,
    SourceIndex,
    extract_fragments,
    grounding_signal,
    verify_answer,
)


SOURCE_TEXT = (
    "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. "
    "It was designed by Gustave Eiffel and completed in 1889. "
    "The tower is 330 metres tall and has three levels for visitors. "
    "It is one of the most famous landmarks in the world and attracts "
    "millions of tourists every year."
)


class TestSourceIndex(unittest.TestCase):
    def test_coverage_full_match(self):
        idx = SourceIndex()
        idx.add(SOURCE_TEXT, "wiki")
        self.assertGreaterEqual(idx.coverage("the tower is 330 metres tall"), 0.9)

    def test_coverage_no_match(self):
        idx = SourceIndex()
        idx.add(SOURCE_TEXT, "wiki")
        self.assertLessEqual(idx.coverage("Berlin is the capital of Germany"), 0.34)

    def test_empty_index(self):
        idx = SourceIndex()
        self.assertTrue(idx.empty)
        # ko'p-so'zli fragment bo'sh indexda 0 qamrov
        self.assertEqual(idx.coverage("some fragment here"), 0.0)
        # 1-tokenlik fragment (son/belgi) — jarimasdan o'tadi
        self.assertEqual(idx.coverage("1889"), 1.0)

    def test_short_fragment_passes(self):
        idx = SourceIndex()
        idx.add(SOURCE_TEXT, "wiki")
        # son/belgi — trigram talab qilinmaydi
        self.assertEqual(idx.coverage("1889"), 1.0)


class TestExtractFragments(unittest.TestCase):
    def test_numeric_sentence_kept_whole(self):
        frags = extract_fragments(
            "The tower is 330 metres tall. It opened in 1889.")
        self.assertTrue(any("330" in f for f in frags))

    def test_long_sentence_windowed(self):
        long_sent = (" ".join(["word"] * 40) + ".")
        frags = extract_fragments(long_sent)
        self.assertTrue(all(len(f.split()) <= 12 for f in frags))

    def test_code_and_urls_skipped(self):
        frags = extract_fragments(
            "```python\nprint(1)\n``` https://example.com/x y z w q e r s t")
        self.assertFalse(any(f.startswith("```") for f in frags))

    def test_cyrillic_uzbek(self):
        frags = extract_fragments("Eyfel minorasi balandligi 330 metr.")
        self.assertTrue(any("330" in f for f in frags))


class TestVerifyAnswer(unittest.TestCase):
    def setUp(self):
        self.idx = SourceIndex()
        self.idx.add(SOURCE_TEXT, "wiki")

    def test_grounded(self):
        res = verify_answer(
            "The Eiffel Tower was completed in 1889 and is 330 metres tall.",
            self.idx)
        self.assertEqual(res.verdict, "grounded")
        self.assertGreaterEqual(res.coverage, 0.55)

    def test_ungrounded(self):
        res = verify_answer(
            "The Eiffel Tower was built in Rome by Leonardo da Vinci in 1500. "
            "It stands 500 metres tall near the Colosseum.",
            self.idx)
        self.assertEqual(res.verdict, "ungrounded")
        self.assertGreater(res.fragments_ungrounded, 0)

    def test_no_sources_neutral(self):
        res = verify_answer("Any answer about anything.", SourceIndex())
        self.assertEqual(res.verdict, "none")
        self.assertIsNone(grounding_signal(res))

    def test_fail_safe_bad_input(self):
        # noto'g'ri input — exception yo'q, neytral natija
        res = verify_answer(None, None)
        self.assertEqual(res.verdict, "none")


class TestGroundingSignal(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(grounding_signal(None), None)
        for verdict, expected in (
            ("grounded", 1.0), ("partial", 0.5), ("ungrounded", 0.0),
            ("none", None),
        ):
            r = GroundingResult(0.5, verdict, 0, 0, [], [], 0)
            self.assertEqual(grounding_signal(r), expected)


class TestSelfEvaluatorGrounding(unittest.TestCase):
    def _eval(self, **kw):
        from core.intelligence.self_eval import SelfEvaluator
        return SelfEvaluator().evaluate(**kw)

    def test_grounded_bonus(self):
        base = self._eval(engine="llm", output="ok answer text that is long enough")
        boosted = self._eval(engine="llm", output="ok answer text that is long enough",
                             grounding=1.0)
        self.assertAlmostEqual(
            boosted.confidence - base.confidence, 0.10, places=3)
        self.assertIn("web_grounded", boosted.notes)

    def test_ungrounded_penalty(self):
        base = self._eval(engine="llm", output="ok answer text that is long enough")
        penalized = self._eval(engine="llm", output="ok answer text that is long enough",
                               grounding=0.0)
        self.assertAlmostEqual(
            penalized.confidence - base.confidence, -0.15, places=3)
        self.assertIn("web_ungrounded", penalized.notes)

    def test_partial_neutral_and_none(self):
        base = self._eval(engine="llm", output="ok answer text that is long enough")
        partial = self._eval(engine="llm", output="ok answer text that is long enough",
                             grounding=0.5)
        self.assertAlmostEqual(partial.confidence, base.confidence, places=3)
        none_res = self._eval(engine="llm", output="ok answer text that is long enough",
                              grounding=None)
        self.assertAlmostEqual(none_res.confidence, base.confidence, places=3)

    def test_backward_compatible(self):
        # grounding parametrisiz eski chaqiruv buzilmaydi
        res = self._eval(engine="deterministic", output="42")
        self.assertIsNotNone(res)


class TestAgentIntegration(unittest.TestCase):
    """IgrisAgent bilan integratsiya (LLM yo'q — faqat verify yo'li)."""

    def _agent(self):
        from agent.igris_agent import IgrisAgent
        return IgrisAgent(use_llm=False, memory_enabled=False)

    def test_web_sources_captured_and_verified(self):
        agent = self._agent()
        # web tool natijasi yig'ilganini simulyatsiya qilamiz
        # (haqiqiy tool chaqiruvi emas — _WEB_SOURCE_TOOLS yo'li)
        from web.web_verify import SourceIndex
        agent._web_sources = SourceIndex()
        agent._web_sources.add(SOURCE_TEXT, "web_fetch")
        data = {"message": "x", "content": "The tower is 330 metres tall.",
                "engine": "llm+tools"}
        agent._with_self_eval(data)
        self.assertIn("web_grounding", data)
        self.assertEqual(data["web_grounding"]["verdict"], "grounded")
        self.assertIn("web_grounded", data["self_eval"]["notes"])
        # ichki maydon javobga oqib ketmagan
        self.assertNotIn("_grounding_result", data)

    def test_no_web_tools_no_grounding(self):
        agent = self._agent()
        data = {"message": "x", "content": "Oddiy javob.", "engine": "llm"}
        agent._with_self_eval(data)
        self.assertNotIn("web_grounding", data)
        self.assertNotIn("grounding", data.get("self_eval", {}).get("signals", {}))

    def test_ungrounded_flagged(self):
        agent = self._agent()
        from web.web_verify import SourceIndex
        agent._web_sources = SourceIndex()
        agent._web_sources.add(SOURCE_TEXT, "web_fetch")
        data = {"message": "x",
                "content": ("The Eiffel Tower stands in Rome and was built "
                            "by Leonardo da Vinci around 1500."),
                "engine": "llm+tools"}
        agent._with_self_eval(data)
        self.assertEqual(data["web_grounding"]["verdict"], "ungrounded")
        self.assertIn("web_ungrounded", data["self_eval"]["notes"])

    def test_web_sources_tool_capture(self):
        """_chat_with_tools web tool natijasini yig'adi (fail-safe yo'l)."""
        agent = self._agent()
        calls = {"n": 0}

        def fake_chat_with_tools_resp(messages, tools=None, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"tool_calls": [
                    {"name": "web_fetch",
                     "arguments": {"url": "https://example.com/eiffel"}}]}
            return {"content": "The Eiffel Tower is in Paris."}

        def fake_execute(name, args):
            return {"ok": True, "output": SOURCE_TEXT}

        agent.llm = type("L", (), {
            "chat_with_tools": staticmethod(fake_chat_with_tools_resp),
        })()
        agent._execute_chat_tool = fake_execute
        messages = [{"role": "user", "content": "Eiffel tower info"}]
        content, tool_calls, image = agent._chat_with_tools(messages, [])
        self.assertEqual(calls["n"], 2)
        self.assertTrue(tool_calls)
        self.assertIsNotNone(agent._web_sources)
        self.assertFalse(agent._web_sources.empty)


if __name__ == "__main__":
    unittest.main()
