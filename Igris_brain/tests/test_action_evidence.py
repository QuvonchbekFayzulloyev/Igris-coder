"""
IGRIS BRAIN — Action Evidence guard testlari (anti-hallucination)
=================================================================
Real muammo (server/chat_history.jsonl): model toolsiz
"Fayl yaratildi: mini_snake_game.py" deb yozardi — fayl yo'q,
ish bajarilmagan, soxta yakunlash (hallucination).

Qamrov:
  - agent/action_evidence.py  : evaluate / nudge_message / honest_rewrite
  - agent/request_classifier  : creator routing + kontekst merosi
  - chat()                    : soxta da'vo → nudge → corrected
                                haqiqiy tool chaqiruvi → executed
"""

import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.action_evidence import (  # noqa: E402
    evaluate,
    honest_rewrite,
    nudge_message,
)
from agent.request_classifier import CREATOR_NEEDS, classify_need  # noqa: E402
from agent.igris_agent import IgrisAgent  # noqa: E402


# ---------------------------------------------------------------- #
# Yordamchilar
# ---------------------------------------------------------------- #

class _FakeIntel:
    """Minimal intellekt — chat() harm-filter/observe tekshiruvlarini o'tkazadi."""

    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()

    def observe(self, message):
        return None

    def adapt_system(self, system, message):
        return system or "system"

    def reasoning_suffix(self):
        return ""

    def quick_math(self, expr):
        return None

    def evaluate(self, **kwargs):
        class _Eval:
            def to_dict(self):
                return {"confidence": 0.5}
        return _Eval()


_WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write a file into the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path"],
        },
    },
}


def _base_agent():
    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.intelligence = _FakeIntel()
    agent._cag = lambda: None  # CAG keshi chetlab o'tiladi
    agent._llm_checked = True
    agent._llm_available = False
    return agent


class _ClaimLLM:
    """Soxta da'vo yozuvchi LLM — tool HECH QACHON chaqirmaydi."""

    model = "qwen3:8b"
    turbo = False
    think = False

    def __init__(self, claim):
        self.claim = claim
        self.calls = 0

    def chat_with_tools(self, messages, tools=None):
        self.calls += 1
        return {"content": self.claim, "tool_calls": []}

    def complete(self, system="", prompt=""):
        return "yes"  # compliance verdict — qayta yozishni bloklaydi

    def chat(self, messages):
        return self.claim


class _WorkThenClaimLLM:
    """Birinchi javobda soxta da'vo, EVIDENCE CHECK nudge'ida HAQIQIY tool
    chaqiradi (natijada isbot paydo bo'ladi)."""

    model = "qwen3:8b"
    turbo = False
    think = False

    def __init__(self, fname):
        self.fname = fname
        self.calls = 0

    def chat_with_tools(self, messages, tools=None):
        self.calls += 1
        msgs = messages or []
        if any(m.get("role") == "tool" for m in msgs):
            # tool bajarildi — yakuniy xulosa
            return {"content": f"Fayl yaratildi: {self.fname} — 1 satr kod.",
                    "tool_calls": []}
        if any("EVIDENCE CHECK" in str(m.get("content") or "") for m in msgs):
            # majburlash — endi haqiqatan bajaramiz
            return {"content": "", "tool_calls": [
                {"name": "write_file",
                 "arguments": {"path": self.fname,
                               "content": "print('ok')"}}]}
        # birinchi javob: isbotsiz soxta da'vo (hallucination)
        return {"content": f"Fayl yaratildi: {self.fname} — o'yin tayyor.",
                "tool_calls": []}

    def complete(self, system="", prompt=""):
        return "yes"

    def chat(self, messages):
        return f"Fayl yaratildi: {self.fname}"


# ---------------------------------------------------------------- #
# 1) module darajasidagi tekshiruvlar
# ---------------------------------------------------------------- #

class TestEvaluate(unittest.TestCase):
    CLAIM = "Fayl yaratildi: ev_fake_claim_9x7.py — o'yin tayyor."

    def test_claim_without_evidence_fails(self):
        ws = os.path.join(tempfile.gettempdir(), "igris_ev_no_such_ws")
        ok, reason = evaluate(self.CLAIM, [], None, ws, allow_promise=True)
        self.assertFalse(ok)
        self.assertTrue(reason, "da'vo matni qaytarilishi kerak")

    def test_no_claim_is_ok(self):
        ok, _ = evaluate("Salom! Qanday yordam bera olaman?", [], None, "")
        self.assertTrue(ok)

    def test_tool_calls_are_evidence(self):
        ok, _ = evaluate(self.CLAIM,
                          [{"tool": "write_file", "args": {"path": "x.py"}}],
                          None, "")
        self.assertTrue(ok)

    def test_image_is_evidence(self):
        ok, _ = evaluate(self.CLAIM, [], "some_drawing.svg", "")
        self.assertTrue(ok)

    def test_file_on_disk_is_evidence(self):
        with tempfile.TemporaryDirectory() as ws:
            fname = "ev_created_snake_9x7.py"
            with open(os.path.join(ws, fname), "w", encoding="utf-8") as f:
                f.write("print('ok')\n")
            ok, _ = evaluate(f"Fayl yaratildi: {fname}", [], None, ws)
            self.assertTrue(ok, "workspace'da mavjud fayl — da'vo to'g'ri")

    def test_missing_file_claim_fails(self):
        with tempfile.TemporaryDirectory() as ws:
            ok, reason = evaluate(
                "Fayl yaratildi: ev_never_written_9x7.py", [], None, ws)
            self.assertFalse(ok)
            self.assertTrue(reason)

    def test_promise_not_claim_in_plain_chat(self):
        # Oddiy suhbatda kelajakdagi va'da — da'vo EMAS
        ok, _ = evaluate("Men rasm chizaman.", [], None, "",
                         allow_promise=False)
        self.assertTrue(ok)

    def test_promise_is_claim_in_creator(self):
        # Creator pipeline'da va'da ham da'vo — isbot talab qilinadi
        ok, _ = evaluate("Men rasm chizaman.", [], None, "",
                         allow_promise=True)
        self.assertFalse(ok)

    def test_honest_rewrite_keeps_body(self):
        out = honest_rewrite(self.CLAIM, "yaratildi")
        self.assertIn("Tasdiqlanmagan", out)
        self.assertIn(self.CLAIM, out)

    def test_nudge_forces_real_action(self):
        self.assertIn("EVIDENCE CHECK", nudge_message("yaratildi"))
        self.assertIn("yaratildi", nudge_message("yaratildi"))


# ---------------------------------------------------------------- #
# 2) routing regressiyasi (soxta yakunlashning 1-sababi)
# ---------------------------------------------------------------- #

class TestCreatorRouting(unittest.TestCase):
    def test_creator_requests_route_to_creator_needs(self):
        self.assertEqual(classify_need("mini iloncha o'yinini yasab ber", []),
                         "code")
        self.assertEqual(classify_need("sxemani yasa", []), "draw")
        self.assertEqual(classify_need("infografika tuzib ber", []), "draw")
        for msg in ("mini iloncha o'yinini yasab ber", "sxemani yasa"):
            self.assertIn(classify_need(msg, []), CREATOR_NEEDS, msg)

    def test_plain_chat_stays_chat(self):
        # `is_continuation` qoidasi — qisqa xabar chat oilasida qoladi
        self.assertEqual(classify_need("salom", []), "chat")
        self.assertEqual(classify_need("buxoro qaysi davlatda?", []), "chat")

    def test_db_schema_is_code_not_draw(self):
        # DB kontekstida "sxema" chizma emas, kod vazifasi
        self.assertNotEqual(classify_need("database sxemasini yarat", []),
                            "draw")

    @staticmethod
    def _history(*user_texts):
        out = []
        for t in user_texts:
            out.append({"role": "user", "content": t})
            out.append({"role": "assistant", "content": "ok"})
        return out

    def test_continuation_inherits_creator_origin(self):
        h = self._history("mini iloncha o'yinini yasab ber")
        self.assertEqual(classify_need("vazifani yakunladingmi?", h), "code")
        self.assertEqual(classify_need("endi uni yon tomondan ko'rsat", h),
                         "code")

    def test_chat_stays_chat_even_with_creator_origin(self):
        # "salom" davomiylik emas — creator tarixda ham chat bo'lib qoladi
        h = self._history("mini iloncha o'yinini yasab ber")
        self.assertEqual(classify_need("salom", h), "chat")
        self.assertEqual(classify_need("buxoro qaysi davlatda?", h), "chat")


# ---------------------------------------------------------------- #
# 3) chat() integratsiyasi — soxta da'vo hech qachon o'tmaydi
# ---------------------------------------------------------------- #

class TestChatEvidence(unittest.TestCase):
    MSG = "mini iloncha o'yinini yasab ber"

    def _agent(self, llm):
        agent = _base_agent()
        agent.llm = llm
        agent.llm_available = lambda: True
        # MCP ulanmagan test muhitida tool ro'yxatini soddalashtiramiz
        agent._chat_tools = lambda *a, **k: [dict(_WRITE_TOOL)]
        return agent

    def test_fake_claim_is_corrected(self):
        """Model toolsiz 'Fayl yaratildi' yozsa — nudge, keyin halol rewrite."""
        llm = _ClaimLLM("Fayl yaratildi: ev_fake_claim_9x7.py — o'yin tayyor.")
        agent = self._agent(llm)
        data = agent.chat(self.MSG, use_memory=False)

        # tool yo'li ochildi (CREATOR_NEEDS) + BIR marta nudge qilindi
        self.assertGreaterEqual(llm.calls, 2,
                                "tool yo'li + evidence nudge kutilardi")
        note = data.get("action_evidence")
        self.assertIsNotNone(note, "evidence natijasi javobda bo'lishi shart")
        self.assertEqual(note["status"], "corrected")
        self.assertIn("Tasdiqlanmagan", data.get("content", ""))
        # completion record'da ham audit izi qoladi
        comp = data.get("completion") or {}
        self.assertEqual((comp.get("action_evidence") or {}).get("status"),
                         "corrected")

    def test_tool_path_opens_for_creator_request(self):
        """Creator so'rovda toolsiz javob ham tool yo'lini ochadi."""
        llm = _ClaimLLM("Fayl yaratildi: ev_fake_claim_9x7.py — o'yin tayyor.")
        agent = self._agent(llm)
        agent.chat(self.MSG, use_memory=False)
        self.assertGreaterEqual(
            llm.calls, 1,
            "chat_with_tools chaqirilishi kerak — so'rov creator pipeline")

    def test_evidence_executed_when_tool_actually_runs(self):
        """Nudge'dan keyin model tool chaqirsa — status 'executed'."""
        fname = "ev_created_snake_9x7.py"
        llm = _WorkThenClaimLLM(fname)
        agent = self._agent(llm)

        ws = getattr(agent, "workspace_root", None)
        self.assertTrue(ws, "workspace_root kerak")
        os.makedirs(ws, exist_ok=True)
        path = os.path.join(ws, fname)

        def _exec(name, args):
            if name == "write_file":
                target = os.path.join(ws, str(args.get("path", "")))
                os.makedirs(os.path.dirname(target) or ws, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(str(args.get("content", "")))
                return {"ok": True,
                        "output": f"File created: {args.get('path')}"}
            return {"ok": False, "error": f"unknown tool: {name}"}

        agent._execute_chat_tool = _exec
        try:
            data = agent.chat(self.MSG, use_memory=False)
            self.assertTrue(os.path.isfile(path),
                            "tool haqiqatan fayl yaratishi kerak")
            note = data.get("action_evidence")
            self.assertIsNotNone(note)
            self.assertEqual(note["status"], "executed")
            # isbotlangan javob — ogohlantirish YO'Q
            self.assertNotIn("Tasdiqlanmagan", data.get("content", ""))
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_plain_chat_has_no_evidence_note(self):
        llm = _ClaimLLM("Salom! Men IGRIS yordamchisiman.")
        agent = self._agent(llm)
        data = agent.chat("salom", use_memory=False)
        self.assertNotIn("action_evidence", data)
        self.assertNotIn("Tasdiqlanmagan", data.get("content", ""))


if __name__ == "__main__":
    unittest.main()
