"""
INTELLEKT qatlami testlari (BuildIntalaganceInstructionRequest.md)
===================================================================
12 intellekt arxitekturasi — qaysi modullar REAL ishlayotganini tekshiradi:

  2.2  Logic      — quick_math tez yo'li + chiqish strukturasi tekshiruvi/ta'mirlash
  2.3  Music      — musiqa so'rovini aniqlash + yo'naltirish
  2.4  Spatial    — loyiha strukturasi konteksti (workspace daraxti)
  2.7  Self-eval  — har bir javobga ishonch kalibratsiyasi birikadi
  2.8  Naturalist — loyiha muhiti taqsimoti (til/kengaytma naqshlari)
  2.10 Harm-filter— zararli so'rov rad etiladi
  2.11 Creative   — multi-temperature variantlar + eng yaxshisini tanlash
"""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.igris_agent import IgrisAgent  # noqa: E402
from core.intelligence import IntelligenceCore  # noqa: E402
from core.intelligence.logic import extract_balanced_json  # noqa: E402
from core.intelligence.self_eval import SelfEvaluator  # noqa: E402
from core.intelligence.naturalist import NaturalistLayer  # noqa: E402
from core.intelligence.music import MusicLayer  # noqa: E402


class _FakeLLM:
    """OllamaClient'ni almashtiruvchi test-double (LLM chaqiruvlari yon ta'sirsiz)."""

    model = "qwen3:8b"
    turbo = False
    think = True

    def __init__(self, complete_out=None):
        self.complete_out = complete_out or []
        self._i = 0
        self.last_error = None

    def is_available(self):
        return True

    def list_models(self):
        return [self.model]

    def complete(self, prompt, system=None, temperature=None):
        if self.complete_out:
            out = self.complete_out[min(self._i, len(self.complete_out) - 1)]
            self._i += 1
            return out
        return "variant javob"

    def chat_fast(self, messages):
        return "fast javob"

    def chat_with_tools(self, messages, tools=None):
        return {"content": "tool javob"}

    def extract_code(self, text):
        from llm.ollama_client import OllamaClient
        # instance metod — haqiqiy logikani instance orqali chaqiramiz
        return OllamaClient().extract_code(text)

    def chat_stream_rich(self, messages, think=None):
        for ev in [{"type": "token", "content": "Stream javob"}]:
            yield ev


def _live_agent(complete_out=None) -> IgrisAgent:
    """Haqiqiy INTELLEKT qatlami + soxta LLM bilan ishlaydigan agent."""
    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.llm = _FakeLLM(complete_out)
    agent.use_llm = True
    agent._llm_checked = True
    agent._llm_available = True
    agent._cag = lambda: None  # CAG keshini chetlab o'tamiz (yon ta'sir yo'q)
    return agent


class TestLogicQuickMath(unittest.TestCase):
    """2.2 — safe_math tez deterministik yo'li."""

    def test_plain_arithmetic(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("2+2*3", use_memory=False)
        self.assertEqual(data["engine"], "math-quick")
        self.assertEqual(data["content"], "2+2*3 = 8")

    def test_prefix_arithmetic(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("hisobla 15-7", use_memory=False)
        self.assertEqual(data["engine"], "math-quick")
        self.assertEqual(data["content"], "15-7 = 8")

    def test_decimal_and_parens(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("(3.5*2)+1", use_memory=False)
        self.assertEqual(data["engine"], "math-quick")
        self.assertEqual(data["content"], "(3.5*2)+1 = 8")

    def test_code_request_not_math(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("Python dastur yoz", use_memory=False)
        self.assertNotEqual(data["engine"], "math-quick")

    def test_math_stream(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        events = list(agent.chat_stream("2+2", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertEqual(done["engine"], "math-quick")
        self.assertEqual(done["content"], "2+2 = 4")


class TestStructureCheck(unittest.TestCase):
    """2.2 — check_structure + JSON ta'mirlash."""

    def test_repair_wrapped_json(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        out, info = agent._verify_and_repair('{"a": 1} ortiqcha matn')
        self.assertEqual(out, '{"a": 1}')
        self.assertTrue(info["repaired"])

    def test_valid_plain_no_report(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        out, info = agent._verify_and_repair("sodda matn javob")
        self.assertEqual(out, "sodda matn javob")
        self.assertIsNone(info)

    def test_unrepairable_json_reported(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        out, info = agent._verify_and_repair('{"a": }')
        self.assertIsNotNone(info)
        self.assertFalse(info["ok"])
        self.assertEqual(info["kind"], "json")

    def test_extract_balanced_json(self):
        self.assertEqual(extract_balanced_json('Natija: {"a": 1}'), '{"a": 1}')
        self.assertIsNone(extract_balanced_json("hech qanday json yo'q"))

    def test_structure_check_on_stream_done(self):
        agent = _live_agent()
        fake = _FakeLLM([])
        fake.chat_stream_rich = lambda messages, think=None: iter(
            [{"type": "token", "content": '{"a": }'}])
        agent.llm = fake
        events = list(agent.chat_stream("JSON qaytar", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertIn("structure_check", done)
        self.assertFalse(done["structure_check"]["ok"])


class TestSelfEval(unittest.TestCase):
    """2.7 — ishonch kalibratsiyasi har bir javobga birikadi."""

    def test_offline_response_has_self_eval(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("salom", use_memory=False)
        self.assertIn("self_eval", data)
        self.assertIn("confidence", data["self_eval"])
        self.assertIn("uncertainty", data["self_eval"])

    def test_quick_math_has_self_eval(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("2+2", use_memory=False)
        self.assertIn("self_eval", data)
        self.assertGreaterEqual(data["self_eval"]["confidence"], 0.7)

    def test_resolver_score_scales_length_ok_floor(self):
        """A2 — resolver_score kuchsiz rule'da `length_ok`'ni ham scaley qiladi:
        0.825 floor 0.75 ga tushadi (rs=0.5); rs=None (llm/cag/weather) bo'lsa
        o'zgarish yo'q; kuchsiz rule < kuchli rule (monoton)."""
        se = SelfEvaluator()
        out = "np.linalg.inv(np.array) sodda"
        # rs=0.5: 0.5 + 0.35*0.5 + 0.15*0.5 = 0.75 (ilgari 0.825 floor)
        self.assertAlmostEqual(
            se.evaluate(engine="deterministic", output=out, resolver_score=0.5).confidence,
            0.75, places=6)
        # rs=1.0 -> 1.0 (cap), rs=None -> avvalgi kabi 1.0
        self.assertAlmostEqual(
            se.evaluate(engine="deterministic", output=out, resolver_score=1.0).confidence,
            1.0, places=6)
        self.assertAlmostEqual(
            se.evaluate(engine="deterministic", output=out).confidence, 1.0, places=6)
        # LLM dvigatelida resolver_score qo'llanilmaydi (length_ok 0.15 o'zgarishsiz)
        self.assertAlmostEqual(
            se.evaluate(engine="llm", output="oddiy uzun javob matni shu yerda yetarli",
                        resolver_score=0.5).confidence, 0.90, places=6)
        # Monotonlik: kuchsiz rule < kuchli rule
        lo = se.evaluate(engine="deterministic", output=out, resolver_score=0.5).confidence
        hi = se.evaluate(engine="deterministic", output=out, resolver_score=0.9).confidence
        self.assertLess(lo, hi)

    def test_resolver_score_monotonic(self):
        """A2 — resolver_score to'liq [0,1] diapazonida confidence MONOTON
        kamaymaydi: kuchsiz rule hech qachon kuchli rule'dan yuqori ishonch
        bermaydi (deterministic VA healed). Analitik formula 0.5 + 0.5*rs
        (engine 0.35*rs + length 0.15*rs, cap 1.0) bilan mos."""
        se = SelfEvaluator()
        out = "np.linalg.inv(np.array) sodda"
        for engine in ("deterministic", "healed"):
            prev = -1.0
            for rs in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
                conf = se.evaluate(
                    engine=engine, output=out, resolver_score=rs).confidence
                self.assertGreaterEqual(
                    conf, prev,
                    f"{engine} rs={rs}: confidence {conf} < prev {prev} (monoton emas)")
                prev = conf
            # Chekka qiymatlar analitik formulaga mos: 0.5 + 0.5*rs
            self.assertAlmostEqual(
                se.evaluate(engine=engine, output=out, resolver_score=0.0).confidence,
                0.5, places=6)
            self.assertAlmostEqual(
                se.evaluate(engine=engine, output=out, resolver_score=1.0).confidence,
                1.0, places=6)
            # Ichki nuqtada ham: rs=0.6 -> 0.5 + 0.5*0.6 = 0.8
            self.assertAlmostEqual(
                se.evaluate(engine=engine, output=out, resolver_score=0.6).confidence,
                0.8, places=6)

    def test_avg_logprob_signal(self):
        """A2 — avg_logprob signali: 0.9 -> +0.12, 0.2 -> -0.09, None -> neytral.
        Formula 0.15*(2p-1), clamp [0,1]; 0.5 -> neytral; note faqat signal
        berilganda qo'shiladi. Base engine='offline' (0.5+0.10+0.15=0.75) —
        cap/floor'ga urilmasligi uchun zaxira qoldiradi; llm (0.90) bilan
        cap holati alohida tekshiriladi."""
        se = SelfEvaluator()
        out = "oddiy uzun javob matni shu yerda yetarli"
        base = se.evaluate(engine="offline", output=out).confidence
        self.assertAlmostEqual(base, 0.75, places=6)
        # None -> neytral: confidence o'zgarmaydi, note ham yo'q
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=None).confidence,
            base, places=6)
        self.assertNotIn("avg_logprob",
                         se.evaluate(engine="offline", output=out).notes)
        # 0.9 -> +0.12, 0.2 -> -0.09 (delta usuli — base ga nisbatan)
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=0.9).confidence - base,
            +0.12, places=6)
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=0.2).confidence - base,
            -0.09, places=6)
        # 0.5 -> neytral (2*0.5-1 = 0)
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=0.5).confidence,
            base, places=6)
        # Clamp [0,1]: ekstremallar max +-0.15, tashqaridagi qiymat ham ishlaydi
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=1.0).confidence - base,
            +0.15, places=6)
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=0.0).confidence - base,
            -0.15, places=6)
        self.assertAlmostEqual(
            se.evaluate(engine="offline", output=out, avg_logprob=5.0).confidence,
            se.evaluate(engine="offline", output=out, avg_logprob=1.0).confidence,
            places=6)
        # Cap holati: llm bazasi (0.90) + 0.12 = 1.02 -> 1.0 ga qisqaradi
        llm_base = se.evaluate(engine="llm", output=out).confidence
        self.assertAlmostEqual(
            se.evaluate(engine="llm", output=out, avg_logprob=0.9).confidence,
            1.0, places=6)
        self.assertGreaterEqual(llm_base, 0.9)
        # Note format: avg_logprob=0.900
        self.assertIn(
            "avg_logprob=0.900",
            se.evaluate(engine="offline", output=out, avg_logprob=0.9).notes)

    def test_confidence_bounds_across_input_matrix(self):
        """A2 — SelfEvaluator XAVFSIZLIK: status/engine/verified/tool/memory
        kombinatsiyalarida confidence DOIM [0,1] oralig'ida qoladi va hech
        qanday kombinatsiya exception tashlamaydi. Bekor (noma'lum) engine/
        status/verified qiymatlari ham xavfsiz ishlanadi; manfiy/kattalashgan
        resolver_score va avg_logprob clamp qilinadi; uncertainty esa doim
        low/medium/high dan biri bo'ladi."""
        import itertools
        se = SelfEvaluator()
        engines = ["llm", "llm+tools", "llm-fast", "deterministic", "healed",
                   "cag", "weather-quick", "math-quick", "offline", "noma'lum-dvigatel"]
        statuses = ["ok", "failed", "partial", "weird-status"]
        verifieds = [None, "ok", "repaired", "fail", "weird-verified"]
        tool_sets = [
            [],
            [{"ok": True}],
            [{"ok": False}],
            [{"result": {"ok": True}}],
            [{"result": {"ok": False}}],
            [{"name": "no-ok-key"}],
            [{"ok": True}, {"ok": False}],
        ]
        outputs = ["", "yetarli uzun javob matni — 40 belgidan ortiq bo'lishi uchun"]
        others = [
            (0, False, None, None),
            (1, False, None, None),
            (5, True, None, None),
            (0, False, 0.0, None),
            (0, False, 0.5, None),
            (0, False, 1.0, None),
            (0, False, -5.0, None),   # clamp -> 0.0
            (0, False, 5.0, None),    # clamp -> 1.0
            (0, False, None, 0.9),
            (0, False, None, -1.0),   # clamp -> 0.0
            (0, False, None, 5.0),    # clamp -> 1.0
            (3, True, 0.6, 0.4),
        ]
        checked = 0
        for engine, status, verified, tools, out, (mh, healed, rs, lp) in \
                itertools.product(engines, statuses, verifieds, tool_sets,
                                  outputs, others):
            r = se.evaluate(
                engine=engine, status=status, output=out,
                tool_calls=tools, memory_hits=mh, healed=healed,
                verified=verified, resolver_score=rs, avg_logprob=lp)
            self.assertGreaterEqual(
                r.confidence, 0.0,
                f"conf < 0: engine={engine} status={status} verified={verified}")
            self.assertLessEqual(
                r.confidence, 1.0,
                f"conf > 1: engine={engine} status={status} verified={verified}")
            self.assertIn(r.uncertainty, ("low", "medium", "high"),
                          f"uncertainty={r.uncertainty!r} engine={engine}")
            checked += 1
        self.assertGreater(checked, 10000, "sweep yetarli keng bo'lishi kerak")

    def _resolve_llm_fallback(self, llm_out):
        """resolve() LLM fallback yo'lini haydaydi (deterministik miss -> LLM)."""
        agent = _live_agent(complete_out=[llm_out])
        data = agent.resolve(
            "bu yerda hech qanday brick mos kelmaydigan noyob super-so'rov",
            allow_llm=True, use_memory=False)
        self.assertEqual(data["engine"], "llm")  # fallback ishladi
        return data

    def test_resolve_llm_fallback_structure_fail_signal(self):
        """A2 — resolve() LLM fallback: buzilgan code chiqishi structure_check oladi
        va `verified='fail'` signali self_eval'ga ulanadi (confidence pasayadi)."""
        # Fenced ichida buzilgan JSON (bir tirnoq) — extract_code dan keyin
        # `{'a': 1` qoladi, check_structure -> json fail.
        data = self._resolve_llm_fallback("```python\n{'a': 1\n```")
        self.assertIn("structure_check", data)
        self.assertFalse(data["structure_check"]["ok"])
        self.assertEqual(data["structure_check"]["kind"], "json")
        self.assertIn("verifier_fail", data["self_eval"].get("notes", []))
        # Fail jarimasi confidence'ni tushiradi (verified='fail' -> -0.25)
        self.assertLess(data["confidence"], 0.55)

    def test_resolve_llm_fallback_structure_repaired_signal(self):
        """A2 — resolve() LLM fallback: o'ralgan yaroqli JSON repair'dan o'tadi,
        `verified='repaired'` signali birikadi (engil jarima -0.10)."""
        data = self._resolve_llm_fallback(
            "```python\n{\"a\": 1} ortiqcha matn\n```")
        self.assertIn("structure_check", data)
        self.assertTrue(data["structure_check"]["repaired"])
        self.assertIn("verifier_repaired", data["self_eval"].get("notes", []))
        self.assertEqual(data["output"], '{"a": 1}')  # ta'mirlangan matn

    def test_resolve_llm_fallback_clean_code_no_signal(self):
        """A2 — toza code chiqishi hisobotga tushmaydi (structure_check yo'q,
        verified signali qo'shilmaydi — shovqin yo'q)."""
        data = self._resolve_llm_fallback("```python\nprint(\"salom\")\n```")
        self.assertNotIn("structure_check", data)
        self.assertEqual(data["output"], 'print("salom")')
        self.assertTrue(data["confidence"] >= 0.5)

    def test_resolve_llm_fallback_rag_not_polluted(self):
        """A2 — resolve() LLM fallback repair yo'li RAG'ni ifloslantirmaydi:
        1) repair qilinadigan buzilgan chiqish -> xotiraga AYNAN ta'mirlangan
           matn yoziladi (xom emas). chat_history.jsonl'ni server qaytarilgan
           javobdan yozadi — `d["output"] == data["output"]` invariant'u
           tarixga ham xuddi shu toza matn o'tishini kafolatlaydi;
        2) repair qilib BO'LMAYDIGAN chiqish (verified='fail') -> xotiraga
           UMUMAN yozilmaydi (keyingi recall buzilgan code'ni qaytarmaydi),
           lekin javob baribir qaytadi (fail signali + past confidence) —
           transcript'da foydalanuvchi ko'rgan matn saqlanadi (server ixtiyori)."""
        query = "bu yerda hech qanday brick mos kelmaydigan noyob super-so'rov"

        # 1) repaired -> canonical matn xotiraga va javobga
        agent = _live_agent(complete_out=["```python\n{\"a\": 1} ortiqcha matn\n```"])
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))
        data = agent.resolve(query, allow_llm=True, use_memory=False)
        self.assertTrue(calls, "repaired holatda xotiraga yozilishi kerak")
        _q, d = calls[0]
        self.assertEqual(d["output"], '{"a": 1}')      # xom emas
        self.assertNotIn("ortiqcha matn", d["output"])  # xom qoldiq yo'q
        self.assertEqual(d["output"], data["output"])   # persisted == returned
        self.assertTrue(data["structure_check"]["repaired"])

        # 2) fail -> RAG'ga hech narsa yozilmaydi (lekin javob baribir bor)
        agent2 = _live_agent(complete_out=["```python\n{'a': 1\n```"])
        calls2 = []
        agent2.memory.enabled = True
        agent2.memory.on_resolve = lambda q, d: calls2.append((q, d))
        data2 = agent2.resolve(query, allow_llm=True, use_memory=False)
        self.assertFalse(calls2, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertEqual(data2["output"], "{'a': 1")   # javob baribir qaytadi
        self.assertIn("verifier_fail", data2["self_eval"].get("notes", []))
        self.assertLess(data2["confidence"], 0.55)

    def test_stream_done_has_self_eval(self):
        agent = _live_agent()
        events = list(agent.chat_stream("salom", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertIn("self_eval", done)

    def test_chat_final_memory_output_matches_self_eval_source(self):
        """2.7 — chat() final yo'li: memory'ga yoziladigan `output` AYNAN
        self_eval hisoblangan matn bo'ladi (`data["content"]`, repair'dan keyingi)
        — raw `out` emas. Confidence ham shu matndan BIR MARTA evaluate() bilan
        olinadi (memory qiymati == javobdagi self_eval qiymati)."""
        agent = _live_agent()
        # LLM xom JSON + qo'shimcha matn qaytaradi — _verify_and_repair uni
        # tuzatadi (out_final = '{"a": 1}'), raw `out` esa buzilgan holda qoladi.
        broken = '{"a": 1} ortiqcha matn'
        fake = _FakeLLM([])
        fake.chat_with_tools = lambda messages, tools=None: {"content": broken}
        agent.llm = fake
        agent._chat_tools = lambda include_web=False, web_strategy="": []  # MCP/registry chetlab
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        data = agent.chat("JSON qaytar", use_memory=False)

        self.assertEqual(data["engine"], "llm")
        self.assertTrue(calls, "memory yozilmadi")
        q, d = calls[0]
        # Repair ishladi: raw xom matn emas, tozalangan JSON saqlanadi
        self.assertNotEqual(d["output"], broken)
        self.assertEqual(d["output"], '{"a": 1}')
        # Memory output == javobdagi content == self_eval manbai (tafovut yo'q)
        self.assertEqual(d["output"], data["content"])
        # Confidence AYNAN shu matndan hisoblandi — memory va javob BIR xil
        self.assertEqual(d["confidence"], data["self_eval"]["confidence"])
        # Verifikator signali (repaired -> -0.10) ham shu oqimda ishladi
        self.assertIn("verifier_repaired", data["self_eval"].get("notes", []))
        # Xizmat kaliti javobga oqib ketmadi (frontend toza dict oladi)
        self.assertNotIn("_llm_messages", data)

    def test_stream_tool_memory_output_matches_self_eval_source(self):
        """A2 — chat_stream TOOL yo'li: memory'ga yoziladigan `output` AYNAN
        self_eval hisoblangan matn bo'ladi (`data["content"]`, repair'dan
        keyingi) — raw `out` emas; confidence ham BIR xil (pre-repair eskirgan
        qiymat emas). Tool yo'li ham plain-stream/turbo kabi repair-before-write
        qilishi kerak (`_done`'ning keyingi repair'i no-op bo'ladi)."""
        broken = '{"a": 1} ortiqcha matn'
        agent = _live_agent()
        fake = _FakeLLM([])
        fake.chat_with_tools = lambda messages, tools=None: {"content": broken}
        agent.llm = fake
        # TOOL yo'liga yo'naltiramiz: registry bor + "kod" kalit so'zi
        # (tool_needed=True). Model tool tanlamaydi — tool loop'iga tushmaydi,
        # lekin TOOL YO'LI bloki (memory yozuvi bilan) ishlaydi.
        agent._registry = lambda: {"dummy_tool": object}
        agent._chat_tools = lambda include_web=False, web_strategy="": []
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("shu kodni yozib ber", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")

        self.assertEqual(done["engine"], "llm")  # tool yo'li, model tool tanlamadi
        self.assertTrue(calls, "memory yozilmadi")
        _q, d = calls[0]
        # Repair ishladi: raw xom matn emas, tozalangan JSON saqlanadi
        self.assertNotEqual(d["output"], broken)
        self.assertEqual(d["output"], '{"a": 1}')
        # Memory output == done content == self_eval manbai (tafovut yo'q)
        self.assertEqual(d["output"], done["content"])
        # Confidence AYNAN shu matndan hisoblandi — memory va javob BIR xil
        self.assertEqual(d["confidence"], done["self_eval"]["confidence"])
        # Verifikator signali (repaired -> -0.10) ham shu oqimda ishladi
        self.assertIn("verifier_repaired", done["self_eval"].get("notes", []))
        # Xizmat kaliti javobga oqib ketmadi (frontend toza dict oladi)
        self.assertNotIn("_llm_messages", done)

    def test_stream_plain_fail_not_written_to_rag(self):
        """A2 — chat_stream plain-stream yo'li: repair qilib BO'LMAYDIGAN
        chiqish (verified='fail') RAG'ga yozilmaydi — done baribir fail
        signali bilan qaytadi (foydalanuvchi ko'radi, xotira tozalanadi).
        `_cacheable_out` buni ushlab qolmaydi (buzilgan JSON 'junk' emas) —
        guard AYNAN structure_check fail holatini bloklaydi."""
        agent = _live_agent()
        fake = _FakeLLM([])
        fake.chat_stream_rich = lambda messages, think=None: iter(
            [{"type": "token", "content": "{'a': 1"}])
        agent.llm = fake
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("JSON qaytar", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")

        self.assertFalse(calls, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertIn("structure_check", done)
        self.assertFalse(done["structure_check"]["ok"])
        self.assertIn("verifier_fail", done["self_eval"].get("notes", []))
        self.assertLess(done["self_eval"]["confidence"], 0.55)

    def test_stream_tool_fail_not_written_to_rag(self):
        """A2 — chat_stream tool yo'li: repair qilib BO'LMAYDIGAN chiqish
        (verified='fail') RAG'ga yozilmaydi — done baribir fail signali bilan
        qaytadi (transcript'ga ogohlantirish server tomonidan qo'shiladi)."""
        agent = _live_agent()
        fake = _FakeLLM([])
        fake.chat_with_tools = lambda messages, tools=None: {"content": "{'a': 1"}
        # §3.2 review loop regeneratsiya ham BUZILGAN matn qaytaradi —
        # demak "repair qilib bo'lmaydigan" holatni aynan testlaymiz.
        fake.complete_out = ["{'a': 1"]
        agent.llm = fake
        agent._registry = lambda: {"dummy_tool": object}
        agent._chat_tools = lambda include_web=False, web_strategy="": []
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("shu kodni yozib ber", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")

        self.assertFalse(calls, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertEqual(done["content"], "{'a': 1")
        self.assertIn("structure_check", done)
        self.assertFalse(done["structure_check"]["ok"])
        # Review loop HAQIQATAN ishdi (dekorativ emas) va halol hisobot qoldirdi
        self.assertIn("review", done)
        self.assertFalse(done["review"]["ok"])
        self.assertFalse(done["review"]["repaired"])
        self.assertGreaterEqual(done["review"]["attempts"], 1)
        self.assertIn("verifier_fail", done["self_eval"].get("notes", []))
        self.assertLess(done["self_eval"]["confidence"], 0.55)

    def test_chat_final_fail_not_written_to_rag(self):
        """A2 — chat() final yo'li: repair qilib BO'LMAYDIGAN chiqish
        (verified='fail') RAG'ga yozilmaydi — javob baribir qaytadi (fail
        signali + past confidence bilan; stream yo'llari bilan bir xil guard)."""
        agent = _live_agent()
        fake = _FakeLLM([])
        fake.chat_with_tools = lambda messages, tools=None: {"content": "{'a': 1"}
        agent.llm = fake
        agent._chat_tools = lambda include_web=False, web_strategy="": []
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        data = agent.chat("JSON qaytar", use_memory=False)

        self.assertFalse(calls, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertEqual(data["content"], "{'a': 1")
        self.assertIn("structure_check", data)
        self.assertFalse(data["structure_check"]["ok"])
        self.assertIn("verifier_fail", data["self_eval"].get("notes", []))
        self.assertLess(data["self_eval"]["confidence"], 0.55)

    def test_self_eval_stats_increment(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        before = agent.intelligence.self_eval.stats()["evaluations"]
        agent.chat("salom", use_memory=False)
        after = agent.intelligence.self_eval.stats()["evaluations"]
        self.assertGreater(after, before)

    def test_stream_refusal_self_eval_confident(self):
        """Rad etish — to'g'ri deterministik harakat, ishonch past bo'lmaydi."""
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        events = list(agent.chat_stream(
            "qanday qilib odam o'ldirish kerak", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertTrue(done.get("refused"))
        self.assertGreaterEqual(done["self_eval"]["confidence"], 0.7)


class TestHarmFilter(unittest.TestCase):
    """2.10 — zararli so'rov rad etiladi, sabab tushuntiriladi."""

    def test_harmful_request_blocked(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("qanday qilib odam o'ldirish kerak", use_memory=False)
        self.assertTrue(data.get("refused"))
        self.assertIn("content", data)
        self.assertTrue(data["content"])

    def test_harmless_request_allowed(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        data = agent.chat("salom", use_memory=False)
        self.assertNotIn("refused", data)


class TestCreative(unittest.TestCase):
    """2.11 — multi-temperature kreativ variantlar."""

    def test_creative_variants_generated(self):
        agent = _live_agent(complete_out=[
            "Variant A: qisqa va aniq javob batafsil izoh bilan",
            "Variant B: boshqa yondashuv, ancha uzunroq va batafsilroq matn",
            "Variant C: uchinchi usul, yana boshqacha ko'rinishdagi javob",
        ])
        data = agent.chat("3 ta g'oya ber", use_memory=False)
        self.assertEqual(data["engine"], "creative")
        self.assertIn("creative", data)
        self.assertEqual(data["creative"]["n"], 3)
        self.assertTrue(data["content"])

    def test_creative_skipped_for_code_request(self):
        agent = _live_agent()
        data = agent._creative_variants("fayl yaratish uchun variantlar ber",
                                        system="sys", memory_hits=0)
        self.assertIsNone(data)

    def test_creative_detector(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.assertTrue(agent._is_creative_request("3 ta g'oya ber"))
        self.assertTrue(agent._is_creative_request("give me ideas for the app?"))
        self.assertFalse(agent._is_creative_request("salom"))
        # "variant" so'zi boshqa kontekstda kreativ hisoblanmaydi (fe'l yo'q)
        self.assertFalse(agent._is_creative_request("python variantini qidir"))


class TestSpatialNaturalist(unittest.TestCase):
    """2.4 + 2.8 — loyiha strukturasi / muhit tahlili konteksti."""

    def _temp_workspace(self):
        tmp = tempfile.mkdtemp(prefix="igris_ws_")
        for name in ("app.py", "main.py", "style.css", "index.html",
                     "data/config.json", "data/settings.json"):
            full = os.path.join(tmp, *name.split("/"))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write("test")
        return tmp

    def test_spatial_env_context(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent.workspace_root = self._temp_workspace()
        sp = agent._spatial_env_context("loyiha tuzilishi qanday?")
        self.assertIsNotNone(sp)
        block, summary = sp
        self.assertIn("Project layout", block)
        self.assertGreater(summary["entries"], 0)
        self.assertIn("languages", summary)

    def test_spatial_attached_to_chat(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent.workspace_root = self._temp_workspace()
        data = agent.chat("loyiha tuzilishi qanday?", use_memory=False)
        self.assertIn("spatial", data)
        self.assertGreater(data["spatial"]["entries"], 0)

    def test_spatial_attached_to_stream(self):
        agent = _live_agent()
        agent.workspace_root = self._temp_workspace()
        events = list(agent.chat_stream("loyiha tuzilishi qanday?", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertIn("spatial", done)
        self.assertGreater(done["spatial"]["entries"], 0)

    def test_not_structure_request(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.assertFalse(agent._is_structure_request("salom"))

    def test_naturalist_classify(self):
        nats = NaturalistLayer()
        info = nats.classify_paths(["a.py", "b.py", "c.ts", "x/y.go"])
        self.assertEqual(info["languages"]["python"], 2)
        self.assertEqual(info["languages"]["typescript"], 1)
        self.assertEqual(info["languages"]["go"], 1)

    def test_naturalist_text_patterns(self):
        nats = NaturalistLayer()
        info = nats.classify_text("Ko'ring https://example.com va a@b.com")
        self.assertEqual(info["patterns"]["url"], 1)
        self.assertEqual(info["patterns"]["email"], 1)


class TestMusic(unittest.TestCase):
    """2.3 — musiqa/ovoz so'rovini aniqlash + yo'naltirish."""

    def test_music_directive_present(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        d = agent._intel("music_directive", "C major akkordlari nima?")
        self.assertTrue(d)
        self.assertIn("Music reference", d)

    def test_music_directive_absent(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.assertEqual(agent._intel("music_directive", "salom"), "")

    def test_music_layer_detect(self):
        m = MusicLayer()
        self.assertTrue(m.detect("melodiya yozish kerak"))
        self.assertFalse(m.detect("python dastur yoz"))


class TestIntelligenceStatus(unittest.TestCase):
    """Agent status + orchestrator to'liq modullar to'plamini ko'rsatadi."""

    def test_status_has_intelligence(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        st = agent.status()
        self.assertIn("intelligence", st)
        self.assertTrue(st["intelligence"]["enabled"])

    def test_orchestrator_all_modules(self):
        core = IntelligenceCore()
        st = core.status()
        for mod in ("harm_filter", "user_model", "tone_detect", "language",
                    "logic", "self_eval", "spatial", "creative",
                    "naturalist", "music"):
            self.assertIn(mod, st, f"modul yo'q: {mod}")

    def test_orchestrator_helpers(self):
        core = IntelligenceCore()
        self.assertEqual(core.quick_math("2+2"), 4.0)
        self.assertTrue(core.music_directive("ritm haqida"))
        self.assertEqual(core.music_directive("salom"), "")


if __name__ == "__main__":
    unittest.main()
