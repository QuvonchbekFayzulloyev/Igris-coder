"""
Test: chizish cheklovlarini kamaytirish (Part O+ kengaytmasi)
=============================================================
- Yangi deterministik subyektlar (tuya/it/oqqush/o'rdak/robot/samolyot)
  art__draw_scene_svg orqali aniq chiziladi (LLM'siz).
- CANNED_SCENE_SUBJECTS sinxronligi (request_classifier <-> art_svg.SCENE_OBJECTS).
- Last-chance draw retry: LLM tool chaqirmasa — rad etishdan OLDIN 1 marta
  aniq SVG generatsiya buyrug'i bilan urinish; junk-guard (svg yo'q — voz kechish).
"""
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.igris_agent import IgrisAgent  # noqa: E402
from agent.request_classifier import CANNED_SCENE_SUBJECTS, is_draw_request  # noqa: E402
from mcp_servers.art_svg import SCENE_OBJECTS, build_scene_svg  # noqa: E402


class TestExpandedSceneSubjects(unittest.TestCase):
    """Yangi canned subyektlar deterministik chiziladi (LLM cheklovisiz)."""

    def test_classifier_svg_sync(self):
        # Har bir canned subyekt SVG builder'ida ham bo'lishi SHART
        # (aks holda deterministic scene NOT_SUPPORTED qaytaradi).
        missing = CANNED_SCENE_SUBJECTS - set(SCENE_OBJECTS.keys())
        self.assertEqual(missing, set(),
                         f"builder'siz subyektlar: {sorted(missing)}")

    def test_new_subjects_recognized(self):
        for msg in ("tuya rasmini chiz", "it rasmini chiz", "oqqush chiz",
                    "robot chizib ber", "samolyot rasmini chiz"):
            self.assertTrue(is_draw_request(msg), msg)
            subj = IgrisAgent._detect_subject(IgrisAgent, msg, "draw")
            self.assertIn(subj, CANNED_SCENE_SUBJECTS, msg)

    def test_new_subjects_build_valid_svg(self):
        for subj in ("tuya", "it", "oqqush", "o'rdak", "robot", "samolyot"):
            svg, n = build_scene_svg(subj, "", "none", style="cartoon",
                                     size="standard")
            self.assertTrue(svg.startswith("<svg"), subj)
            self.assertTrue(svg.rstrip().endswith("</svg>"), subj)
            self.assertGreaterEqual(n, 5, subj)

    def test_style_size_variants(self):
        # Bir xil subyekt turli uslub/o'lchamda haqiqatan farq qiladi
        s1, _ = build_scene_svg("tuya", "", "none", style="cartoon", size="standard")
        s2, _ = build_scene_svg("tuya", "", "none", style="flat", size="icon")
        s3, _ = build_scene_svg("tuya", "", "none", style="realistic", size="poster")
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1, s3)
        self.assertIn('viewBox="0 0 256 256"', s2)
        self.assertIn('viewBox="0 0 768 1024"', s3)


class TestLastChanceDrawRetry(unittest.TestCase):
    """Rad etishdan OLDINGI oxirgi chizish urinishi."""

    def _agent(self):
        return IgrisAgent(use_llm=False, memory_enabled=False)

    def test_fallback_when_llm_empty_draw_request(self):
        """LLM bo'sh qaytardi + draw so'rov → last-chance retry ishlaydi."""
        agent = self._agent()

        class FakeLLM:
            def complete(self, system="", prompt=""):
                return ('<svg xmlns="http://www.w3.org/2000/svg" '
                        'viewBox="0 0 512 512">'
                        '<rect width="512" height="512" fill="#f4f1ea"/>'
                        '<circle cx="256" cy="256" r="120" fill="#c9a45c"/></svg>')

        agent.llm = FakeLLM()
        agent.llm_available = lambda: True
        agent._execute_chat_tool = lambda name, args: {
            "ok": True,
            "output": "image saved to " + os.path.join(
                agent.workspace_root, "last_chance.svg"),
        }
        content, img = agent._last_chance_draw("ajoyib narsa chiz")
        self.assertTrue(img, "last-chance rasm ishlab bo'lishi kerak edi")
        self.assertTrue(img.endswith(".svg"))
        self.assertIn("rasm tayyor", content)

    def test_gives_up_without_svg_markup(self):
        """Model to'liq SVG bermasa — junk-guard: darhol voz kechadi."""
        agent = self._agent()

        class FakeLLM:
            def complete(self, system="", prompt=""):
                return "Kechirasiz, men chiza olmaydim."  # SVG yo'q

        agent.llm = FakeLLM()
        agent.llm_available = lambda: True
        content, img = agent._last_chance_draw("tuya chiz")
        self.assertIsNone(img)
        self.assertEqual(content, "")

    def test_not_triggered_offline(self):
        """LLM yo'q bo'lsa retry umuman ishga tushmaydi (xato bermaydi)."""
        agent = self._agent()  # use_llm=False
        content, img = agent._last_chance_draw("tuya chiz")
        self.assertIsNone(img)

    def test_tool_loop_uses_retry_before_refusal(self):
        """_chat_with_tools: LLM bo'sh javob + canned bo'lmagan draw so'rov →
        rad etish o'rniga last-chance retry rasm qaytaradi."""
        agent = self._agent()

        class FakeLLM:
            def chat_with_tools(self, messages, tools=None):
                return {"content": "", "tool_calls": []}

            def complete(self, system="", prompt=""):
                return ('<svg xmlns="http://www.w3.org/2000/svg" '
                        'viewBox="0 0 512 512">'
                        '<rect width="512" height="512" fill="#f4f1ea"/>'
                        '<ellipse cx="256" cy="256" rx="120" ry="80" '
                        'fill="#8f9aa8"/></svg>')

        agent.llm = FakeLLM()
        agent.llm_available = lambda: True
        agent._execute_chat_tool = lambda name, args: {
            "ok": True,
            "output": "image saved to " + os.path.join(
                agent.workspace_root, "retry_rescue.svg"),
        }
        # "ajdarho" canned ro'yxatda YO'Q — deterministik scene o'tmaydi,
        # last-chance retry ishga tushishi kerak.
        content, tool_calls, image = agent._chat_with_tools(
            [{"role": "user", "content": "ajdarho chiz"}], [], web=False)
        self.assertEqual(image, "retry_rescue.svg")
        self.assertTrue(any(
            tc.get("tool") == "art__draw_custom_svg" for tc in tool_calls))

    def test_tool_loop_canned_subject_skips_llm(self):
        """Yangi canned subyekt (samolyot) DETERMINISTIK chiziladi —
        LLM chat_with_tools umuman chaqirilmaydi (cheklov butunlay chetlab o'tiladi)."""
        agent = self._agent()

        class FakeLLM:
            def __init__(self):
                self.llm_called = False

            def chat_with_tools(self, messages, tools=None):
                self.llm_called = True
                return {"content": "", "tool_calls": []}

            def complete(self, system="", prompt=""):
                self.llm_called = True
                return ""

        fake = FakeLLM()
        agent.llm = fake
        agent.llm_available = lambda: True
        agent._execute_chat_tool = lambda name, args: {
            "ok": True,
            "output": "image saved to " + os.path.join(
                agent.workspace_root, "det_plane.svg"),
        }
        content, tool_calls, image = agent._chat_with_tools(
            [{"role": "user", "content": "samolyot chiz"}], [], web=False)
        self.assertEqual(image, "det_plane.svg")
        self.assertFalse(fake.llm_called, "LLM chaqirilmasligi kerak edi")


if __name__ == "__main__":
    unittest.main()
