"""
IGRIS BRAIN — Request Meaning (so'rov semantikasi) testlari
==========================================================
So'rovni to'liq ma'no strukturasiga aylantirish qatlami:

  muammo/maqsad/definitsiya/detaillar + paradigmaviy tahlil
  (ilmiy/mantiqiy/falsafiy/majoziy/realistik/...) + kanal tartibi
  (LLM-in/LLM-out aralashmasligi, noise bo'lmasin).

Qamrov:
  - core/request_meaning.py : family/intent/language/definition/goal/paradigms/
                              channel/required — deterministik parse + LLM assist
  - assist_fields / MEANING_ASSIST_SYSTEM : ixtiyoriy LLM JSON assist
                              (problem/goal/definition boyitish, sanitize+kesh)
  - IgrisAgent._interpret_request : pipeline need + Requirement signallarini
                              birlashtirish (kesh, xavfsiz fallback, assist gate)
  - chat() / chat_stream()  : `interpretation` javob record'iga kiradi,
                              completion'da qisqa ko'rinishi bor
"""

import json
import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from core.request_meaning import (  # noqa: E402
    MEANING_ASSIST_SYSTEM,
    PARADIGM_TAXONOMY,
    RequestChannel,
    RequestMeaning,
    assist_fields,
    normalize_paradigm,
    parse_request_meaning,
)
from core.requirements import Requirement  # noqa: E402
from agent.igris_agent import IgrisAgent  # noqa: E402


class _FakeIntel:
    """Minimal intellekt — chat() harm-filter/observe/eval tekshiruvlarini o'tkazadi."""

    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()

    def observe(self, message):
        return None

    def adapt_system(self, system, message):
        return system or "system"

    def reasoning_suffix(self):
        return ""

    def quick_math(self, expr):
        import ast
        try:
            node = ast.parse(str(expr), mode="eval")
            return eval(compile(node, "<safe>", "eval"), {"__builtins__": {}})
        except Exception:
            return None

    def evaluate(self, **kwargs):
        class _Eval:
            def to_dict(self):
                return {"confidence": 0.5}
        return _Eval()


def _make_agent():
    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.intelligence = _FakeIntel()
    agent._cag = lambda: None
    agent._llm_checked = True
    agent._llm_available = False
    return agent


# ---------------------------------------------------------------- # #
# Family (oila) aniqlash
# ---------------------------------------------------------------- # #

class TestFamilyDetection(unittest.TestCase):

    def test_plain_chat(self):
        self.assertEqual(parse_request_meaning("salom").family, "chat")

    def test_creator_from_code_file(self):
        m = parse_request_meaning("write a python function in app.py")
        self.assertEqual(m.family, "creator")
        self.assertTrue(m.needs_tools)

    def test_creator_from_uzbek_verb(self):
        m = parse_request_meaning("app.py fayliga kod yozib ber")
        self.assertEqual(m.family, "creator")

    def test_guidance_from_roadmap(self):
        self.assertEqual(parse_request_meaning("roadmap tuzib ber").family, "guidance")

    def test_season_not_creator(self):
        # "yoz ta'tili" — mavsum so'zi, "yoz" (yozmoq) bilan adashmasin
        self.assertEqual(parse_request_meaning("yoz ta'tili qachon?").family, "chat")

    def test_family_override_param(self):
        # pipeline need ustuvor — ichki detektor bilan chalkashmaydi
        m = parse_request_meaning("salom", family="creator")
        self.assertEqual(m.family, "creator")
        self.assertTrue(m.needs_tools)

    def test_substring_words_not_creator(self):
        # "mening"/"shahrida" ichida "men"/"ida" bor — creator bo'lmasin
        self.assertEqual(parse_request_meaning("mening ishim yo'q").family, "chat")
        self.assertEqual(parse_request_meaning("shahrida 5 ta element bor").family, "chat")


# ---------------------------------------------------------------- # #
# Intent / til (faqat KNOWN_INTENTS ichidan fallback)
# ---------------------------------------------------------------- # #

class TestIntentAndLanguage(unittest.TestCase):

    def test_math_intent(self):
        m = parse_request_meaning("3+5*2 = ?")
        self.assertEqual(m.intent, "math")
        self.assertIn("mathematical", m.paradigms)
        self.assertFalse(m.needs_tools)  # matematika — tool'siz
        self.assertIn("deterministic", m.required)

    def test_fact_question_intent(self):
        m = parse_request_meaning("Buxoro qaysi davlatda?")
        self.assertEqual(m.intent, "research")
        self.assertEqual(m.language, "uz")

    def test_default_intent_general(self):
        self.assertEqual(parse_request_meaning("salom").intent, "general")

    def test_creator_intent_code_and_file(self):
        self.assertEqual(
            parse_request_meaning("write a python function in app.py").intent, "code")
        self.assertEqual(
            parse_request_meaning("todo.txt faylgа vazifa yoz").intent, "file")

    def test_language_en(self):
        m = parse_request_meaning("can you please explain recursion quickly")
        self.assertEqual(m.language, "en")

    def test_no_false_deterministic_from_spaces(self):
        # ESKI XATO: har qanday bo'shliqli matn "deterministik" deb hisoblanardi
        # (regex ichida \s bor edi) — endi faqat haqiqiy ifoda.
        self.assertEqual(parse_request_meaning("salom qanday sansiz").required, [])
        self.assertEqual(parse_request_meaning("yil 1991 mustaqillik qaysi sana?").required, [])

    def test_llm_intent_wins(self):
        m = parse_request_meaning("ob-havo qanday", llm_json={"intent": "weather"})
        self.assertEqual(m.intent, "weather")
        self.assertFalse(m.needs_tools)


# ---------------------------------------------------------------- # #
# Definitsiya / maqsad / detaillar
# ---------------------------------------------------------------- # #

class TestDefinitionGoalDetails(unittest.TestCase):

    def test_definition_extraction(self):
        m = parse_request_meaning("What is recursion?")
        self.assertEqual(m.definition, "recursion")

    def test_goal_creator_uses_deliverable(self):
        m = parse_request_meaning("write utils.py", family="creator")
        self.assertIn("utils.py", m.goal)

    def test_goal_llm_override(self):
        m = parse_request_meaning("make a report",
                                  llm_json={"goal": "hisobot tayyorlash"})
        self.assertEqual(m.goal, "hisobot tayyorlash")

    def test_details_detection(self):
        self.assertIn("batafsil", parse_request_meaning("batafsil yozib ber").details)
        self.assertIn("qisqa", parse_request_meaning("qisqa javob ber").details)
        self.assertIn("list", parse_request_meaning("ro'yxat qilib ber").details)

    def test_required_deliverable_file(self):
        m = parse_request_meaning("app.py faylini yarat")
        self.assertIn("deliverable_file", m.required)
        self.assertEqual(m.deliverable_name, "app.py")

    def test_required_llm_override(self):
        m = parse_request_meaning("oddiy savol", llm_json={"required": ["chart"]})
        self.assertEqual(m.required, ["chart"])


# ---------------------------------------------------------------- # #
# Paradigma taxonomiyasi
# ---------------------------------------------------------------- # #

class TestParadigmTaxonomy(unittest.TestCase):

    def test_taxonomy_has_analysis_families(self):
        # falsafiy/mantiqiy/majoziy/ilmiy/nazariy/fantastik/realistik to'plamlari
        must = {"scientific", "mathematical", "logical", "philosophical",
                "theoretical", "mythical", "fantasy", "realistic", "practical",
                "hypothetical", "thought_experiment", "definitional"}
        self.assertTrue(must.issubset(set(PARADIGM_TAXONOMY)), must - set(PARADIGM_TAXONOMY))

    def test_normalize_exact(self):
        self.assertEqual(normalize_paradigm("scientific"), "scientific")
        self.assertEqual(normalize_paradigm("How-To"), "how-to")

    def test_normalize_single_match(self):
        self.assertEqual(normalize_paradigm("scientific-foo"), "scientific")

    def test_normalize_multi_and_unknown(self):
        self.assertEqual(normalize_paradigm("mythical+fantasy"), "combined")
        self.assertEqual(normalize_paradigm("bogus-name"), "combined")
        self.assertEqual(normalize_paradigm(""), "combined")
        self.assertEqual(normalize_paradigm(None), "combined")

    def test_llm_paradigm_filter(self):
        # notiqiq nom "combined" bo'ladi va filtrlanadi — noise qolmaydi
        m = parse_request_meaning("ilmiy tahlil", family="chat",
                                  llm_json={"paradigms": ["scientific", "zzz"]})
        self.assertEqual(m.paradigms, ["scientific"])
        self.assertEqual(m.paradigm_fits, ["scientific"])

    def test_parse_deterministic(self):
        a = parse_request_meaning("Buxoro qaysi davlatda?")
        b = parse_request_meaning("Buxoro qaysi davlatda?")
        self.assertEqual(a.paradigms, b.paradigms)
        self.assertEqual(a.goal, b.goal)
        self.assertEqual(a.required, b.required)


# ---------------------------------------------------------------- # #
# Kanal tartibi (LLM-in / LLM-out aralashmasligi) + noise guard
# ---------------------------------------------------------------- # #

class TestChannelAndNoise(unittest.TestCase):

    def test_default_channel_order(self):
        ch = RequestChannel()
        self.assertTrue(ch.valid())
        self.assertEqual(ch.ordered(), ["inbound", "process", "outbound", "verify"])
        self.assertFalse(ch.interleave)  # aralashuv yo'q — ketma-ket oqim

    def test_invalid_channel_order(self):
        self.assertFalse(RequestChannel(order=["bogus"]).valid())
        self.assertFalse(RequestChannel(order=[]).valid())

    def test_meaning_channel_in_dict(self):
        m = parse_request_meaning("salom")
        d = m.to_dict()
        self.assertEqual(d["channel"]["order"],
                         ["inbound", "process", "outbound", "verify"])
        self.assertEqual(d["channel"]["interleave"], False)

    def test_validate_ok(self):
        self.assertEqual(parse_request_meaning("salom").validate(), [])

    def test_empty_message(self):
        m = parse_request_meaning("")
        self.assertFalse(m.validated)
        self.assertEqual(m.parse_notes, "empty message")
        self.assertEqual(m.validate(), ["message bo'sh"])

    def test_confidence_clamp(self):
        self.assertEqual(parse_request_meaning("x", llm_json={"confidence": 5.0}).confidence, 1.0)
        self.assertEqual(parse_request_meaning("x", llm_json={"confidence": -1}).confidence, 0.0)
        self.assertEqual(parse_request_meaning("x", llm_json={"confidence": "0.25"}).confidence, 0.25)
        self.assertEqual(parse_request_meaning("x", llm_json={"confidence": "abc"}).confidence, 0.5)


# ---------------------------------------------------------------- # #
# LLM assist (ixtiyoriy) — xato bermaydi, xom JSON faqat assist'da
# ---------------------------------------------------------------- # #

class TestLLMAssist(unittest.TestCase):

    def test_string_deliverable_no_crash(self):
        # ESKI XATO: str `.group(0)` chaqirilardi -> AttributeError
        m = parse_request_meaning("make a report", family="creator",
                                  llm_json={"deliverable_name": "report.md"})
        self.assertEqual(m.deliverable_name, "report.md")

    def test_raw_llm_json_only_with_assist(self):
        with_llm = parse_request_meaning("salom", llm_json={"intent": "answer"})
        self.assertIn("intent", with_llm.raw_llm_json)
        without = parse_request_meaning("salom")
        self.assertEqual(without.raw_llm_json, "")

    def test_constraints_from_llm(self):
        m = parse_request_meaning("javob ber", llm_json={"constraints": ["jadvallar", ""]})
        self.assertEqual(m.constraints, ["jadvallar"])

    def test_bad_constraints_type(self):
        m = parse_request_meaning("javob ber", llm_json={"constraints": "not-a-list"})
        self.assertEqual(m.constraints, [])


# ---------------------------------------------------------------- # #
# IgrisAgent._interpret_request — pipeline + Requirement birlashtirish
# ---------------------------------------------------------------- # #

class TestInterpretRequest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.agent = _make_agent()

    def test_chat_need(self):
        out = self.agent._interpret_request("salom", {"need": "chat"})
        self.assertEqual(out["family"], "chat")
        self.assertTrue(out["goal"])
        self.assertIn("channel", out)

    def test_creator_need(self):
        out = self.agent._interpret_request("rasm chiz", {"need": "draw"})
        self.assertEqual(out["family"], "creator")
        self.assertTrue(out["needs_tools"])

    def test_unknown_need_falls_back(self):
        out = self.agent._interpret_request("salom", {"need": "weird"})
        self.assertEqual(out["family"], "chat")

    def test_requirement_intent_answer_uses_fallback(self):
        req = Requirement()  # intent="answer" — deterministik fallback ishlashi kerak
        out = self.agent._interpret_request("Buxoro qaysi davlatda?",
                                            {"need": "chat"}, req)
        self.assertEqual(out["intent"], "research")

    def test_empty_message(self):
        self.assertEqual(self.agent._interpret_request("", {"need": "chat"}), {})

    def test_bad_req_returns_empty(self):
        class _BadReq:
            @property
            def intent(self):
                raise RuntimeError("boom")
        self.assertEqual(self.agent._interpret_request("salom", {"need": "chat"},
                                                      _BadReq()), {})

    def test_cache_returns_copy(self):
        a = self.agent._interpret_request("keshdagi so'rov", {"need": "chat"})
        b = self.agent._interpret_request("keshdagi so'rov", {"need": "chat"})
        self.assertEqual(a, b)
        self.assertIsNot(a, b)          # har bir javob o'z nusxasini oladi
        a["goal"] = "o'zgartirildi"
        c = self.agent._interpret_request("keshdagi so'rov", {"need": "chat"})
        self.assertNotEqual(c["goal"], "o'zgartirildi")  # kesh buzilmadi


# ---------------------------------------------------------------- # #
# chat() / chat_stream() integratsiyasi
# ---------------------------------------------------------------- # #

class TestChatInterpretation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.agent = _make_agent()

    def test_chat_has_interpretation(self):
        r = self.agent.chat("salom", use_memory=False)
        itp = r.get("interpretation")
        self.assertIsInstance(itp, dict)
        self.assertEqual(itp["family"], "chat")
        self.assertTrue(itp["goal"])
        self.assertEqual(itp["channel"]["interleave"], False)

    def test_completion_has_compact_interpretation(self):
        r = self.agent.chat("salom", use_memory=False)
        comp = r.get("completion", {})
        itp = comp.get("interpretation")
        self.assertIsInstance(itp, dict)
        # qisqa ko'rinish: faqat asosiy signal'lar (xom JSON yo'q)
        self.assertTrue(set(itp) <= {"family", "intent", "language", "goal", "paradigms"})
        self.assertIn("family", itp)
        # to'liq struktura response'da, completion'da qisqasi
        self.assertIn("channel", r["interpretation"])

    def test_math_request_interpretation(self):
        r = self.agent.chat("3+4 = ?", use_memory=False)
        itp = r.get("interpretation")
        self.assertIsInstance(itp, dict)
        self.assertEqual(itp["intent"], "math")
        self.assertEqual(itp["family"], "chat")

    def test_no_interpretation_leak_between_requests(self):
        first = self.agent.chat("salom", use_memory=False)
        second = self.agent.chat("3+4 = ?", use_memory=False)
        self.assertEqual(first["interpretation"]["message"], "salom")
        # keyingi so'rov o'z ma'nosini oladi — oldingisi qolmaydi
        self.assertEqual(second["interpretation"]["message"], "3+4 = ?")
        self.assertEqual(second["interpretation"]["intent"], "math")

    def test_stream_done_has_interpretation(self):
        events = list(self.agent.chat_stream("salom qanday sansiz", use_memory=False))
        done = [e for e in events if e.get("type") == "done"]
        self.assertTrue(done, "done voqesi topilmadi")
        itp = done[0].get("interpretation")
        self.assertIsInstance(itp, dict)
        self.assertEqual(itp["family"], "chat")
        self.assertIn("interpretation", done[0].get("completion", {}))

    def test_finalize_without_interp_backwards_compatible(self):
        # eski chaqiruv uslubi (_finalize(data, pipeline)) buzilmaydi
        out = self.agent._finalize({"content": "ok", "message": "m"},
                                   {"need": "chat"})
        self.assertNotIn("interpretation", out)
        self.assertIn("completion", out)


# ---------------------------------------------------------------- #
# IXTIYORIY LLM ASSIST — assist_fields (deterministik parse ustiga boyitish)
# ---------------------------------------------------------------- #

class _FakeMeaningLLM:
    """Sintetik LLM — complete() chaqiruvlarini sanaydi."""

    model = "qwen3:8b"
    turbo = False
    think = False

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def is_available(self):
        return True

    def complete(self, prompt="", system=None, **kw):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class _FakeCache:
    """CAG'ga o'xshash kesh (ns, key) -> text)."""

    def __init__(self):
        self.store = {}

    def get(self, ns, key):
        return self.store.get((ns, key))

    def put(self, ns, key, text):
        self.store[(ns, key)] = text


class TestMeaningAssistUnit(unittest.TestCase):

    def test_assist_system_prompt_is_json_only(self):
        # modelga FAQAT JSON so'rash kerak (noise oldini olish)
        self.assertIn("JSON object only", MEANING_ASSIST_SYSTEM)
        self.assertIn("never invent files", MEANING_ASSIST_SYSTEM)

    def test_sanitize_limits_and_filter(self):
        llm = _FakeMeaningLLM(json.dumps({
            "problem": "x" * 500,
            "goal": "  Todo ilovasini qurish  ",
            "definition": "",
            "paradigms": ["scientific", "bogus", "scientific"],
            "details": ["jadvallar", "", "a" * 300],
            "required": ["chart"],
        }))
        f = assist_fields("Menga vazifalarni boshqarish uchun todo ilovasini qurib ber", llm)
        self.assertEqual(len(f["problem"]), 300)          # uzunlik chegarasi
        self.assertEqual(f["goal"], "Todo ilovasini qurish")  # trim
        self.assertNotIn("definition", f)                 # bo'sh maydon tashlanadi
        self.assertEqual(f["paradigms"], ["scientific"])   # noma'lum + takroriy tashlanadi
        self.assertEqual(len(f["details"]), 2)
        self.assertEqual(len(f["details"][1]), 120)        # element chegarasi
        self.assertEqual(f["required"], ["chart"])

    def test_json_wrapped_in_prose(self):
        llm = _FakeMeaningLLM(
            'Natija: {"goal": "hisoblash", "paradigms": ["mathematical"]}')
        f = assist_fields("3+4 ni hisoblab bera olasanmi?", llm)
        self.assertEqual(f["goal"], "hisoblash")
        self.assertEqual(f["paradigms"], ["mathematical"])

    def test_junk_and_non_dict_return_empty(self):
        msg = "yetarli uzun so'rov matni shu yerda"
        self.assertEqual(assist_fields(msg, _FakeMeaningLLM("hello world")), {})
        self.assertEqual(assist_fields(msg, _FakeMeaningLLM("[]")), {})
        self.assertEqual(assist_fields(msg, _FakeMeaningLLM("")), {})

    def test_llm_exception_returns_empty(self):
        msg = "yetarli uzun so'rov matni shu yerda"
        self.assertEqual(assist_fields(msg, _FakeMeaningLLM(RuntimeError("boom"))), {})

    def test_none_or_incomplete_llm(self):
        msg = "yetarli uzun so'rov matni shu yerda"
        self.assertEqual(assist_fields(msg, None), {})
        self.assertEqual(assist_fields(msg, object()), {})  # `complete` yo'q (OmniRoute)

    def test_cache_skips_second_llm_call(self):
        cache = _FakeCache()
        llm = _FakeMeaningLLM('{"goal": "birinchi"}')
        msg = "birinchi so'rov uchun uzun matn"
        a = assist_fields(msg, llm, cache=cache)
        b = assist_fields(msg, llm, cache=cache)
        self.assertEqual(a, b)
        self.assertEqual(llm.calls, 1)  # ikkinchi marta LLM chaqirilmadi


# ---------------------------------------------------------------- #
# IgrisAgent assist gate — qachon ishlaydi / qachon O'TKAZIB ketiladi
# ---------------------------------------------------------------- #

_LONG_MSG = "Menga vazifalarni boshqarish uchun todo ilovasini qurib ber"


class TestMeaningAssistAgent(unittest.TestCase):

    @staticmethod
    def _assist_agent(reply):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent.intelligence = _FakeIntel()
        agent._cag = lambda: None
        agent.llm = _FakeMeaningLLM(reply)
        agent.use_llm = True
        agent._llm_checked = True
        agent._llm_available = True
        agent._meaning_cache.clear()
        return agent, agent.llm

    def test_assist_enriches_interpretation(self):
        agent, llm = self._assist_agent(json.dumps({
            "goal": "Interaktiv todo ilova qurish",
            "problem": "Vazifalarni boshqarish kerak",
            "paradigms": ["practical", "bogus"],
            "required": ["WCAG kontrast"],
        }))
        out = agent._interpret_request(_LONG_MSG, {"need": "ui_build"})
        self.assertEqual(out["goal"], "Interaktiv todo ilova qurish")
        self.assertEqual(out["problem"], "Vazifalarni boshqarish kerak")
        self.assertEqual(out["paradigms"], ["practical"])
        self.assertIn("WCAG kontrast", out["required"])
        # xom JSON = faqat assist (req signallari aralashmaydi)
        raw = json.loads(out["raw_llm_json"])
        self.assertEqual(raw["goal"], "Interaktiv todo ilova qurish")
        self.assertEqual(llm.calls, 1)

    def test_deterministic_required_survives_merge(self):
        # assist qo'shadi — lekin deterministik signal (app.py) yo'qolmaydi
        agent, _ = self._assist_agent(json.dumps({"required": ["unit testlar"]}))
        out = agent._interpret_request(
            "Menga app.py fayliga dekorator yozib ber, batafsil", {"need": "code"})
        self.assertIn("deliverable_file", out["required"])
        self.assertIn("unit testlar", out["required"])

    def test_skips_short_and_quick_paths(self):
        agent, llm = self._assist_agent('{"goal": "x"}')
        agent._interpret_request("salom", {"need": "chat"})                       # len < 16
        agent._interpret_request("bugun Toshkentda ob-havo qanday", {"need": "weather"})
        agent._interpret_request("kunlik hisob-kitob masalasi", {"need": "math"})
        self.assertEqual(llm.calls, 0)  # ortiqcha chaqiruv YO'Q

    def test_llm_failure_falls_back_deterministic(self):
        agent, _ = self._assist_agent(RuntimeError("llm down"))
        out = agent._interpret_request(_LONG_MSG, {"need": "ui_build"})
        self.assertTrue(out)                         # deterministik ishlaydi
        self.assertNotIn("raw_llm_json", out)        # assist bo'lmadi -> xom JSON yo'q
        self.assertTrue(out["goal"])                 # fallback goal mavjud

    def test_assist_flag_off(self):
        agent, llm = self._assist_agent('{"goal": "x"}')
        agent._meaning_assist = False
        out = agent._interpret_request(_LONG_MSG, {"need": "ui_build"})
        self.assertEqual(llm.calls, 0)
        self.assertNotIn("raw_llm_json", out)

    def test_ctor_flag_and_env_switch(self):
        off = IgrisAgent(use_llm=False, memory_enabled=False,
                         meaning_llm_assist=False)
        self.assertFalse(off._meaning_assist)
        os.environ["IGRIS_MEANING_ASSIST"] = "0"
        try:
            env_off = IgrisAgent(use_llm=False, memory_enabled=False)
            self.assertFalse(env_off._meaning_assist)
        finally:
            os.environ.pop("IGRIS_MEANING_ASSIST", None)
        default = IgrisAgent(use_llm=False, memory_enabled=False)
        self.assertTrue(default._meaning_assist)

    def test_llm_without_complete_is_safe(self):
        # OmniRoute uslubida `complete()` yo'q — holat xavfsiz bo'lishi kerak
        agent, _ = self._assist_agent('{"goal": "x"}')
        agent.llm = type("NoComplete", (object,), {"model": "x"})()
        out = agent._interpret_request(_LONG_MSG, {"need": "ui_build"})
        self.assertTrue(out)
        self.assertNotIn("raw_llm_json", out)


class _FakeLiveLLM:
    """To'liq soxta LLM (test_intelligence namunasi) — chat() uchun."""

    model = "qwen3:8b"
    turbo = False
    think = True

    def __init__(self, extract_out):
        self.extract_out = extract_out
        self.assist_calls = 0

    def is_available(self):
        return True

    def list_models(self):
        return [self.model]

    def complete(self, prompt="", system=None, **kw):
        if system and "request-semantics analyzer" in system:
            self.assist_calls += 1
            return json.dumps({"goal": "ASSIST_GOAL_1", "problem": "PROBLEM_1",
                               "paradigms": ["planning", "bogus"]})
        return self.extract_out

    def chat_fast(self, messages):
        return "fast javob"

    def chat_with_tools(self, messages, tools=None):
        return {"content": "tool javob"}

    def chat_stream_rich(self, messages, think=None):
        yield {"type": "token", "content": "Stream javob"}


class TestAssistChatEndToEnd(unittest.TestCase):
    """chat() ichida assist chaqiriladi va interpretationga kiradi."""

    def test_chat_uses_assist(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent.intelligence = _FakeIntel()
        agent._cag = lambda: None
        agent.llm = _FakeLiveLLM(json.dumps(
            {"intent": "general", "language": "uz", "confidence": 0.9}))
        agent.use_llm = True
        agent._llm_checked = True
        agent._llm_available = True
        agent._meaning_cache.clear()

        msg = "salom, menga kelgusi hafta uchun o'quv rejasini tuzib bera olasanmi?"
        r = agent.chat(msg, use_memory=False)
        itp = r.get("interpretation")
        self.assertIsInstance(itp, dict)
        self.assertEqual(itp["goal"], "ASSIST_GOAL_1")
        self.assertEqual(itp["problem"], "PROBLEM_1")
        self.assertEqual(itp["paradigms"], ["planning"])  # bogus filtrlangan
        self.assertEqual(agent.llm.assist_calls, 1)        # bir marta chaqirildi
        # completion record'da qisqa ko'rinish
        comp_itp = r.get("completion", {}).get("interpretation", {})
        self.assertEqual(comp_itp.get("goal"), "ASSIST_GOAL_1")


if __name__ == "__main__":
    unittest.main()
