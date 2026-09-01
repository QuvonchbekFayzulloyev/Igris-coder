"""TURBO / offline yo'llarida memory output <-> confidence mosligi testlari.

Audit (AUDIT turbo/offline): memory'ga yoziladigan `output` AYNAN o'sha matndan
hisoblangan `confidence` bilan birga saqlanishi kerak (raw `out` emas,
repair'dan keyingi `data["content"]`). Bundan tashqari bo'sh/xato javoblar
RAG'ga tushmaydi (`_cacheable_out` guard). Stream turbo yo'lida `engine` lokal
o'zgaruvchisi aniqlanmagan edi (NameError) — bu test uni ham ushlaydi.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from igris_agent import IgrisAgent  # noqa: E402
from core.intelligence.self_eval import SelfEvaluator  # noqa: E402


class _FakeIntel:
    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()

    def observe(self, message):
        return None

    def adapt_system(self, system, message):
        return system or "system"

    def reasoning_suffix(self):
        return ""

    def verify_structure(self, output=None):
        """Haqiqiy structure check — `_verify_and_repair` (fail-guard) ishlashi
        uchun (StructureCheck obyekti, .to_dict() bilan)."""
        from core.intelligence.logic import LogicLayer
        return LogicLayer().check_structure(output)

    def evaluate(self, engine="llm", status="ok", output="", tool_calls=None,
                 memory_hits=0, healed=False, verified=None, resolver_score=None,
                 avg_logprob=None):
        """Haqiqiy SelfEvaluator — self_eval ham ishlaydi (agent._intel('evaluate'))."""
        return SelfEvaluator().evaluate(
            engine=engine, status=status, output=output,
            tool_calls=tool_calls, memory_hits=memory_hits, healed=healed,
            verified=verified, resolver_score=resolver_score,
            avg_logprob=avg_logprob,
        )


class _FakeFastLLM:
    """TURBO rejimdagi tez model — chat_fast beradi, tarmoqqa chiqmaydi."""

    model = "qwen3:8b"
    turbo = True
    fast_model = "fake-fast"
    logprobs = False  # ixtiyoriy logprob signali o'chiq (HTTP chaqiruv yo'q)

    def __init__(self, reply):
        self.reply = reply

    def chat_fast(self, messages):
        return self.reply


def _done_event(gen):
    done = None
    for ev in gen:
        if ev.get("type") == "done":
            done = ev
    return done


class TestTurboMemoryConfidenceConsistency(unittest.TestCase):
    def setUp(self):
        self.agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.agent.intelligence = _FakeIntel()
        self.agent.use_llm = True
        self.agent._llm_checked = True
        self.agent._llm_available = True
        self.agent._cag = lambda: None  # CAG keshini chetlab o'tamiz
        # Memory spy: on_resolve chaqiruvlarini yozib oladi (diskga yozmaydi)
        self.calls = []
        self.agent.memory.enabled = True
        self.agent.memory.on_resolve = lambda q, d: self.calls.append((q, d))

    def test_chat_turbo_memory_output_equals_confidence_input(self):
        """chat() turbo: memory output == content == confidence (repair'dan keyingi matn)."""
        self.agent.llm = _FakeFastLLM("Salom! Bugun qanday yordam bera olaman?")
        out = self.agent.chat("salom, qalaysan?", use_memory=False)
        self.assertEqual(out["engine"], "llm-fast")
        self.assertEqual(out["content"], "Salom! Bugun qanday yordam bera olaman?")
        self.assertTrue(self.calls, "memory yozilmadi")
        q, d = self.calls[0]
        self.assertEqual(d["output"], out["content"],
                         "memory output javobdagi content bilan mos emas")
        self.assertEqual(d["confidence"], out["self_eval"]["confidence"],
                         "memory confidence self_eval confidence bilan mos emas")
        self.assertNotIn("_llm_messages", out, "_llm_messages javobga oqib ketdi")

    def test_chat_turbo_junk_not_written_to_memory(self):
        """chat() turbo: xato/bo'sh javob RAG'ga yozilmaydi (_cacheable_out guard)."""
        self.agent.llm = _FakeFastLLM("I could not generate a response.")
        self.agent.chat("salom", use_memory=False)
        self.assertEqual(self.calls, [], "xato javob memoryga yozildi!")

    def test_chat_stream_turbo_no_nameerror_and_consistent(self):
        """chat_stream turbo: NameError yo'q (engine aniqlanmagan edi) + memory == done."""
        self.agent.llm = _FakeFastLLM("Tez javob: bu yerda yetarli uzun matn bor.")
        done = _done_event(self.agent.chat_stream("qalaysan?", use_memory=False))
        self.assertIsNotNone(done, "done voqeasi chiqmadi (NameError?)")
        self.assertEqual(done["engine"], "llm-fast")
        self.assertTrue(self.calls, "stream turbo memory yozilmadi")
        q, d = self.calls[0]
        self.assertEqual(d["output"], done["content"],
                         "stream: memory output done.content bilan mos emas")
        self.assertEqual(d["confidence"], done["self_eval"]["confidence"],
                         "stream: memory confidence done self_eval bilan mos emas")
        self.assertNotIn("_llm_messages", done, "_llm_messages done'ga oqib ketdi")

    def test_chat_stream_turbo_junk_not_written_to_memory(self):
        """chat_stream turbo: \"I could not generate\" RAG'ga yozilmaydi."""
        self.agent.llm = _FakeFastLLM("")
        done = _done_event(self.agent.chat_stream("qalaysan?", use_memory=False))
        self.assertEqual(self.calls, [], "stream xato javob memoryga yozildi!")
        self.assertTrue(done["content"].startswith("I could not generate"))

    def test_chat_stream_turbo_fail_not_written_to_memory(self):
        """chat_stream turbo: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
        RAG'ga yozilmaydi — done baribir fail signali bilan qaytadi (turbo
        yo'li ham plain-stream/tool kabi fail-guardga ega)."""
        self.agent.llm = _FakeFastLLM("{'a': 1")
        done = _done_event(self.agent.chat_stream("qalaysan?", use_memory=False))
        self.assertIsNotNone(done, "done voqeasi chiqmadi")
        self.assertEqual(self.calls, [], "buzilgan chiqish RAG'ga yozildi!")
        self.assertIn("structure_check", done)
        self.assertFalse(done["structure_check"]["ok"])
        self.assertIn("verifier_fail", done["self_eval"].get("notes", []))
        self.assertLess(done["self_eval"]["confidence"], 0.55)

    def test_chat_offline_no_chat_level_memory_write(self):
        """chat() offline: chat darajasida memory YOZILMAYDI (by design — `engine !=
        'offline'` guard). Faqat resolve() ichki deterministik yozuvi bo'lishi mumkin
        (engine='deterministic', o'z-o'ziga mos — offline emas)."""
        self.agent.llm_available = lambda: False
        out = self.agent.chat("salom", use_memory=False)
        self.assertEqual(out["engine"], "offline")
        # chat() o'zi offline javobni yozmaydi — guard `engine != "offline"` uni
        # o'tkazmaydi; resolve() ichki yozuvi esa engine='deterministic' bo'ladi.
        self.assertTrue(
            all(d.get("engine") != "offline" for _, d in self.calls),
            "offline javob chat darajasida yozildi!",
        )


if __name__ == "__main__":
    unittest.main()
