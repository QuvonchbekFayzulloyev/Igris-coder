"""Thinking (reasoning) token streaming testlari.

qwen3 kabi reasoning modellar fikrlashni `message.reasoning_content` da stream
qiladi — `chat_stream_rich()` uni ham uzatadi, agent esa `{"type": "thinking"}`
hodisalari sifatida frontendga yetkazadi.
"""
import json
import os
import sys
import unittest
from unittest import mock

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from llm.ollama_client import OllamaClient  # noqa: E402
from agent.igris_agent import IgrisAgent  # noqa: E402


def _ndjson_lines(*events):
    """Ollama NDJSON oqimini simulyatsiya qiluvchi satrlar (done marker bilan)."""
    lines = [json.dumps(ev, ensure_ascii=False).encode("utf-8") + b"\n" for ev in events]
    lines.append(b'{"model":"m","message":{"role":"assistant","content":""},"done":true}\n')
    return lines


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


class TestOllamaThinkingStream(unittest.TestCase):
    def _client(self):
        return OllamaClient(model="qwen3:8b", base_url="http://localhost:1")

    def test_chat_stream_rich_splits_thinking_and_content(self):
        client = self._client()
        lines = _ndjson_lines(
            {"model": "m", "message": {"role": "assistant", "content": "",
                                       "reasoning_content": "Salom,"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "",
                                       "reasoning_content": "men o'ylayapman"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "Javob:",
                                       "reasoning_content": ""}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": " to'liq",
                                       "reasoning_content": ""}, "done": False},
        )
        with mock.patch("llm.ollama_client.urllib.request.urlopen",
                        return_value=_FakeResp(lines)):
            events = list(client.chat_stream_rich([{"role": "user", "content": "x"}]))
        self.assertEqual(events, [
            {"type": "think", "content": "Salom,"},
            {"type": "think", "content": "men o'ylayapman"},
            {"type": "token", "content": "Javob:"},
            {"type": "token", "content": " to'liq"},
        ])

    def test_chat_stream_keeps_content_only(self):
        """Eski chat_stream API buzilmaydi — faqat content deltalari."""
        client = self._client()
        lines = _ndjson_lines(
            {"model": "m", "message": {"role": "assistant", "content": "",
                                       "reasoning_content": "ichki fikr"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "tashqi javob",
                                       "reasoning_content": ""}, "done": False},
        )
        with mock.patch("llm.ollama_client.urllib.request.urlopen",
                        return_value=_FakeResp(lines)):
            deltas = list(client.chat_stream([{"role": "user", "content": "x"}]))
        self.assertEqual(deltas, ["tashqi javob"])  # thinking yashirin qoladi

    def test_chat_stream_rich_reads_ollama_qwen3_thinking_field(self):
        """Ollama qwen3 fikrlashni `thinking` maydonida yuboradi — u ham olinadi
        (deepseek-r1 `reasoning_content` ishlatadi; ikkalasi ham qo'llab-quvvatlanadi)."""
        client = self._client()
        lines = _ndjson_lines(
            {"model": "m", "message": {"role": "assistant", "content": "",
                                       "thinking": "Bu qwen3 fikrlashi"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "Javob",
                                       "thinking": ""}, "done": False},
        )
        with mock.patch("llm.ollama_client.urllib.request.urlopen",
                        return_value=_FakeResp(lines)):
            events = list(client.chat_stream_rich([{"role": "user", "content": "x"}]))
        self.assertEqual(events, [
            {"type": "think", "content": "Bu qwen3 fikrlashi"},
            {"type": "token", "content": "Javob"},
        ])

    def test_chat_stream_raw_pairs(self):
        client = self._client()
        lines = _ndjson_lines(
            {"model": "m", "message": {"role": "assistant", "content": "",
                                       "reasoning_content": "a"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "b",
                                       "reasoning_content": ""}, "done": False},
        )
        with mock.patch("llm.ollama_client.urllib.request.urlopen",
                        return_value=_FakeResp(lines)):
            pairs = list(client._chat_stream_raw([{"role": "user", "content": "x"}]))
        self.assertEqual(pairs, [(True, "a"), (False, "b")])

    def test_think_true_passed_to_payload(self):
        client = self._client()
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResp([])

        with mock.patch("llm.ollama_client.urllib.request.urlopen",
                        side_effect=fake_urlopen):
            list(client.chat_stream_rich([{"role": "user", "content": "x"}], think=True))
        self.assertTrue(captured["body"]["stream"])
        self.assertIs(captured["body"]["think"], True)


class _FakeIntel:
    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()

    def observe(self, message):
        return None

    def adapt_system(self, system, message):
        return system or "system"

    def reasoning_suffix(self):
        return ""


class _FakeRichLLM:
    model = "qwen3:8b"
    turbo = False
    think = True  # sessiya think sozlamasi (default True)

    def __init__(self, events):
        self.events = events
        self.think_arg = None

    def chat_stream_rich(self, messages, think=None):
        self.think_arg = think
        for e in self.events:
            yield e


class TestAgentThinkingStream(unittest.TestCase):
    def setUp(self):
        self.agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.agent.intelligence = _FakeIntel()
        self.agent.use_llm = True
        self.agent._llm_checked = True
        self.agent._llm_available = True
        self.agent._cag = lambda: None  # CAG keshini chetlab o'tamiz (yon ta'sir yo'q)

    def test_stream_emits_thinking_then_tokens(self):
        llm = _FakeRichLLM([
            {"type": "think", "content": "Fikr 1"},
            {"type": "think", "content": "Fikr 2"},
            {"type": "token", "content": "Assalomu"},
            {"type": "token", "content": " alaykum!"},
        ])
        self.agent.llm = llm
        out = list(self.agent.chat_stream("salom", use_memory=False))
        types = [ev["type"] for ev in out]
        self.assertIn("thinking", types)
        self.assertIn("token", types)
        thinking_evs = [ev for ev in out if ev["type"] == "thinking"]
        self.assertEqual(thinking_evs[0]["content"], "Fikr 1")
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertEqual(done["thinking"], "Fikr 1Fikr 2")   # to'liq fikrlash done'da
        self.assertEqual(done["content"], "Assalomu alaykum!")
        self.assertEqual(llm.think_arg, True)  # thinking streaming ochiq

    def test_turbo_mode_disables_thinking_stream(self):
        """TURBO rejim — stream yo'lida thinking o'chiriladi (tez javob).
        History berilgani uchun chat_fast tez yo'li o'tkazib yuboriladi va
        haqiqiy stream yo'li ishlaydi."""
        llm = _FakeRichLLM([{"type": "token", "content": "Tez javob"}])
        llm.turbo = True
        self.agent.llm = llm
        out = list(self.agent.chat_stream(
            "salom", history=[{"role": "user", "content": "avvalgi xabar"}],
            use_memory=False))
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertEqual(done["content"], "Tez javob")
        self.assertIs(llm.think_arg, False)  # turbo -> thinking yo'q

    def test_session_think_disabled_respected(self):
        """Sessiya think=False bo'lsa — streaming ham o'ylamaydi (sozlama hurmati)."""
        llm = _FakeRichLLM([{"type": "token", "content": "Javob"}])
        llm.think = False
        self.agent.llm = llm
        out = list(self.agent.chat_stream("salom", use_memory=False))
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertEqual(done["content"], "Javob")
        self.assertIs(llm.think_arg, False)

    def test_stream_without_thinking_still_works(self):
        """Thinking qo'llab-quvvatlanmaydigan model — oddiy tokenlar, done'da thinking yo'q."""
        llm = _FakeRichLLM([{"type": "token", "content": "Oddiy javob"}])
        self.agent.llm = llm
        out = list(self.agent.chat_stream("2+2 nechi?", use_memory=False))
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertEqual(done["content"], "Oddiy javob")
        self.assertNotIn("thinking", done)

    def test_empty_stream_falls_back_to_buffered(self):
        """Transport uzilishi — chat()'ga qaytish (thinking yo'qolsa ham javob bor)."""
        llm = _FakeRichLLM([])
        self.agent.llm = llm
        original_chat = self.agent.chat
        self.agent.chat = lambda message, history=None, use_memory=True: {
            "content": "buffered javob", "engine": "llm", "tool_calls": [],
            "image": None, "memory": {"recall_hits": 0, "context_chars": 0},
        }
        try:
            out = list(self.agent.chat_stream("salom", use_memory=False))
        finally:
            self.agent.chat = original_chat
        done = next(ev for ev in out if ev["type"] == "done")
        self.assertEqual(done["content"], "buffered javob")


if __name__ == "__main__":
    unittest.main()
