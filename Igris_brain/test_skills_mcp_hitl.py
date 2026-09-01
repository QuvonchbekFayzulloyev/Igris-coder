"""
IGRIS BRAIN — Skills / MCP / HITL testlari
==========================================
No-LLM tekshiruvlar: SkillManager discovery, McpBridge (demo art server),
executor agent-tool routing (use_skill, mcp_call, request_human), path
normalization va HITL RunManager logikasi.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills import SkillManager, DEFAULT_MANAGER  # noqa: E402
from mcp_bridge import McpBridge  # noqa: E402
from executor import AgentExecutor  # noqa: E402
from tools import Workspace  # noqa: E402


class TestSkills(unittest.TestCase):
    def test_discovery(self):
        names = [s.name for s in DEFAULT_MANAGER.list()]
        self.assertIn("svg-artist", names)
        self.assertIn("progressive-visual-construction", names)

    def test_skill_content(self):
        s = DEFAULT_MANAGER.get("svg-artist")
        self.assertIsNotNone(s)
        # Professional SVG qo'llanmasi — gradient, soya, qatlamlar
        # (art__draw_custom_svg uchun, eski Pillow/PNG usuli emas)
        self.assertIn("SVG Artist", s.full_text())
        self.assertIn("linearGradient", s.full_text())
        self.assertIn("feDropShadow", s.full_text())
        self.assertIn("art__draw_custom_svg", s.full_text())

    def test_pvc_skill_content(self):
        """S1 progressive-visual-construction skill'i yuklanadi va Igris
tool'lariga bog'lanadi; frontmatter'dan `>-` qoldig'i yo'q."""
        s = DEFAULT_MANAGER.get("progressive-visual-construction")
        self.assertIsNotNone(s)
        self.assertFalse(s.description.startswith(">-"))
        self.assertIn("art__ui_build_spec", s.full_text())
        self.assertIn("art__draw_scene_svg", s.full_text())
        self.assertIn("Oltin qoida", s.full_text())

    def test_unknown_skill(self):
        self.assertIsNone(DEFAULT_MANAGER.get("nope-xyz"))


class TestMcpBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = McpBridge()
        cls.connected = cls.bridge.start()

    def test_server_connects(self):
        self.assertGreaterEqual(self.connected, 1)

    def test_tools_listed(self):
        names = self.bridge.names()
        self.assertTrue(any("draw_object_png" in n for n in names))

    def test_call_draws_png(self):
        # Mutlaq yo'l — test qaysi cwd'dan ishlasa ham (Igris_brain yoki ildiz)
        # fayl qayerda yozilgani aniq bo'ladi (nisbiy yo'l cwd'ga bog'liq edi).
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(here, "reports", "_test_apple.png")
        r = self.bridge.call_tool("art__draw_object_png", {"subject": "apple", "output": out})
        self.assertTrue(r.get("ok"), r.get("error"))
        self.assertTrue(os.path.exists(out))


class TestExecutorAgentTools(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace("agent_workspace")
        self.ex = AgentExecutor(workspace_root="agent_workspace", llm=None, skills=DEFAULT_MANAGER)

    def test_use_skill_routes(self):
        out = self.ex._execute_agent_tool("use_skill", {"name": "svg-artist"})
        self.assertTrue(out.get("ok"))
        self.assertIn("linearGradient", out.get("output", ""))

    def test_mcp_call_routes(self):
        self.mcp = McpBridge()
        self.mcp.start()
        self.ex.mcp = self.mcp
        out = self.ex._execute_agent_tool("mcp_call", {"tool": "art__draw_object_png", "args": {"subject": "star", "output": "_test_star.png"}})
        self.assertTrue(out.get("ok"), out.get("error"))
        self.assertTrue(os.path.exists(os.path.join("agent_workspace", "_test_star.png")))

    def test_request_human_routes(self):
        got = []
        self.ex.human_provider = lambda q: got.append(q) or "answer-42"
        out = self.ex._execute_agent_tool("request_human", {"question": "what color?"})
        self.assertTrue(out.get("ok"))
        self.assertIn("answer-42", out.get("output", ""))
        self.assertEqual(got, ["what color?"])

    def test_mcp_args_normalize(self):
        self.mcp = McpBridge()
        self.mcp.start()
        self.ex.mcp = self.mcp
        norm = self.ex._normalize_mcp_args("art__draw_object_png", {"object": "apple", "output_path": "apple.png"})
        self.assertEqual(norm.get("subject"), "apple")
        self.assertIn("apple.png", norm.get("output", ""))
        self.assertTrue(os.path.isabs(norm.get("output", "")))
        self.assertIn("agent_workspace", norm.get("output", ""))

    def test_schemas_include_agent_tools(self):
        self.ex.human_provider = lambda q: "answer"
        names = [s["function"]["name"] for s in self.ex._agent_schemas()]
        self.assertIn("use_skill", names)
        self.assertIn("request_human", names)

    def test_mcp_args_escape_returns_error(self):
        """Path workspace'dan chiqsa — error qaytishi kerak (dead-code emas)."""
        self.mcp = McpBridge()
        self.mcp.start()
        self.ex.mcp = self.mcp
        norm = self.ex._normalize_mcp_args(
            "art__draw_object_png", {"subject": "apple", "output": "../../etc/evil.png"})
        self.assertFalse(norm.get("ok"))
        self.assertIn("escapes workspace", norm.get("error", ""))

    def test_mcp_call_path_escape_routes_error(self):
        """mcp_call tool'i escape xatoligini MCP'ga yubormasdan qaytaradi."""
        self.mcp = McpBridge()
        self.mcp.start()
        self.ex.mcp = self.mcp
        out = self.ex._execute_agent_tool(
            "mcp_call",
            {"tool": "art__draw_object_png", "args": {"subject": "apple", "output": "../../etc/evil.png"}},
        )
        self.assertFalse(out.get("ok"))
        self.assertIn("escapes workspace", out.get("error", ""))


class _FakeLLM:
    """run_native loop'ini test qilish uchun skriptlashgan LLM stub."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def chat_with_tools(self, messages, tools):
        if self.calls >= len(self.responses):
            return {"content": "done."}
        resp = self.responses[self.calls]
        self.calls += 1
        return resp

    def complete(self, prompt, system=None):
        # Sifat eshigi (corrective pass) so'rasa — haqiqiy deliverable yozamiz:
        # loop-resilience testlari "ok" ni saqlab qolishi uchun.
        sys_txt = system or ""
        if "CORRECTIVE_SYSTEM" in sys_txt or "deliverable" in sys_txt.lower():
            return '{"path": "apple.png", "content": "A blue apple drawn with Pillow."}'
        return None


class TestNativeLoopResilience(unittest.TestCase):
    """Model tool'lar muvaffaqiyatli bajarilib, bo'sh javob qaytarsa
    — vazifa 'stopped' emas, 'ok' bo'lib yakunlanishi kerak."""

    def _mk(self, llm):
        return AgentExecutor(
            workspace_root="agent_workspace",
            llm=llm,
            memory=None,
            skills=DEFAULT_MANAGER,
            mcp=None,
            human_provider=None,
            max_iter=8,
        )

    def test_empty_content_after_success_is_complete(self):
        # 1) use_skill -> ok; 2..6) model bo'sh javob qaytaradi (5 marta)
        llm = _FakeLLM([
            {"tool_calls": [{"name": "use_skill", "arguments": {"name": "svg-artist"}}]},
            {"content": ""},
            {"content": ""},
            {"content": ""},
            {"content": ""},
            {"content": ""},
        ])
        res = self._mk(llm).run_native("draw an apple")
        self.assertEqual(res["status"], "ok")
        self.assertIn("complete", res["final"].lower())
        self.assertNotIn("Stopped", res["final"])
        self.assertGreaterEqual(res["stats"]["gap_reprompted"], 4)
        # Sifat eshigi (quality gate) model bo'sh qolgan faylni tuzatuvchi
        # write_file bilan to'ldiradi — tool_calls = use_skill + write_file.
        self.assertEqual(len(res["tool_calls"]), 2)
        self.assertEqual(res["tool_calls"][0]["tool"], "use_skill")
        self.assertEqual(res["tool_calls"][1]["tool"], "write_file")

    def test_empty_content_after_failure_is_partial(self):
        # Tool xato qiladi (noto'g'ri skill), keyin model bo'sh javob qaytaradi
        llm = _FakeLLM([
            {"tool_calls": [{"name": "use_skill", "arguments": {"name": "nope-xyz"}}]},
            {"content": ""},
            {"content": ""},
            {"content": ""},
            {"content": ""},
            {"content": ""},
        ])
        res = self._mk(llm).run_native("draw an apple")
        self.assertEqual(res["status"], "partial")
        self.assertIn("partial", res["final"].lower())

    def test_final_content_stops_loop(self):
        llm = _FakeLLM([
            {"tool_calls": [{"name": "use_skill", "arguments": {"name": "svg-artist"}}]},
            {"content": "Apple drawn successfully."},
        ])
        res = self._mk(llm).run_native("draw an apple")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["final"], "Apple drawn successfully.")
        self.assertEqual(llm.calls, 2)  # loop ikkinchi javobda to'xtadi


class TestRunManager(unittest.TestCase):
    def test_respond_queue(self):
        from server import RunManager
        rm = RunManager()
        # state'ni to'g'ridan-to'g'ri tekshiramiz
        state = {"answers": __import__("queue").Queue()}
        rm.respond("missing", "x")  # not found -> False
        self.assertFalse(rm.respond("missing-id", "x"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
