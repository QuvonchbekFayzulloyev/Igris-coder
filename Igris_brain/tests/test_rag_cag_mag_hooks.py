"""
IGRIS BRAIN — CAG / MAG / Hooks / Skills tests
==============================================
- CagCache: LRU, TTL, invalidate, stats
- AgentHookBus: register/fire/stats, error safety
- New skills (S2-S6) load via SkillManager and link to modules
- MagAssembler degrades gracefully when memory disabled
"""

import os
import sys
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.cag import CagCache  # noqa: E402
from monitor.hooks import AgentHookBus, DEFAULT_BUS, register_default_hooks  # noqa: E402
from agent.mag import MagAssembler  # noqa: E402
from skills import SkillManager  # noqa: E402


class TestCagCache(unittest.TestCase):
    def setUp(self):
        self.c = CagCache(max_entries=3, ttl_seconds=3600)

    def test_hit_miss(self):
        self.assertIsNone(self.c.get("sys", "hello"))
        self.c.put("sys", "hello", "world")
        self.assertEqual(self.c.get("sys", "hello"), "world")
        self.assertEqual(self.c.stats["hits"], 1)
        self.assertEqual(self.c.stats["misses"], 1)

    def test_lru_eviction(self):
        for i in range(5):
            self.c.put("s", f"q{i}", f"a{i}")
        # max 3 — eng eskilari evict bo'ldi
        self.assertEqual(self.c.size(), 3)
        self.assertIsNone(self.c.get("s", "q0"))

    def test_invalidate(self):
        self.c.put("s", "x", "1")
        self.c.put("s", "y", "2")
        self.c.invalidate("")
        self.assertEqual(self.c.size(), 0)
        self.assertEqual(self.c.stats["invalidates"], 2)

    def test_ttl(self):
        c = CagCache(ttl_seconds=-1)  # darhol eskiradi
        c.put("s", "q", "a")
        self.assertIsNone(c.get("s", "q"))

    def test_empty_not_cached(self):
        self.c.put("s", "q", "   ")
        self.assertEqual(self.c.size(), 0)


class _FakeLLM:
    """LLM yo'lini haydovchi test-double (chat_with_tools orqali)."""

    model = "qwen3:8b"
    turbo = False
    think = True
    logprobs = False

    def __init__(self, tool_reply):
        self.tool_reply = tool_reply

    def is_available(self):
        return True

    def list_models(self):
        return [self.model]

    def chat_with_tools(self, messages, tools=None):
        return {"content": self.tool_reply}

    def chat_stream_rich(self, messages, think=None):
        yield {"type": "token", "content": self.tool_reply}


class TestChatCAGIntegration(unittest.TestCase):
    """igris_agent.chat() CAG path: kesh kaliti STABIL (CHAT_TOOLS_SYSTEM +
    message) — birinchi javobdan keyin xotira o'zgarsa ham hit bo'lishi kerak.

    AUDIT (CAG put/hit): keshlangan matn AYNAN `data["content"]` (repair'dan
    keyingi) bo'ladi — xom `out` emas; hit yo'lida eski/buzilgan yozuv ham
    repair'dan o'tadi va memory output == content == confidence saqlanadi."""

    def _llm_agent(self, tool_reply):
        """Haqiqiy intellekt + fake LLM — chat() final yo'lini haydaydi."""
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent.llm = _FakeLLM(tool_reply)
        agent.use_llm = True
        agent._llm_checked = True
        agent._llm_available = True
        agent._chat_tools = lambda include_web=False, web_strategy="": []
        return agent

    class _SpyCache:
        """put() chaqiruvlarini yozib oladigan soxta kesh (hech qachon hit bermaydi)."""

        def __init__(self):
            self.puts = []

        def get(self, system, prompt):
            return None

        def put(self, system, prompt, text):
            self.puts.append((system, prompt, text))

    def test_cag_put_caches_repaired_content_not_raw_out(self):
        """CAG PUT: keshlangan matn AYNAN `data["content"]` (repair'dan keyingi)
        bo'ladi — xom `out` emas (keshlangan out vs content tafovuti yo'q).

        AUDIT: `_compliance` (req-kesh, 'req' sistemasi) ham put qilishi
        mumkin — shuning uchun puts ICHIDA CHAT_TOOLS_SYSTEM put'ini topamiz
        (birinchi put emas, mos kalitdagi put)."""
        from agent.igris_agent import CHAT_TOOLS_SYSTEM
        broken = '{"a": 1} ortiqcha matn'  # LLM xom JSON + qo'shimcha matn
        agent = self._llm_agent(broken)
        spy = self._SpyCache()
        agent._cag = lambda: spy

        data = agent.chat("JSON qaytar", use_memory=False)

        self.assertEqual(data["engine"], "llm")
        self.assertEqual(data["content"], '{"a": 1}')  # repair ishladi
        self.assertTrue(spy.puts, "keshga yozilmadi")
        chat_puts = [(s, p, text) for s, p, text in spy.puts
                     if s == CHAT_TOOLS_SYSTEM]
        self.assertTrue(chat_puts, "CHAT_TOOLS_SYSTEM kalitli put topilmadi")
        s, p, text = chat_puts[0]
        self.assertEqual(p, "JSON qaytar")
        self.assertEqual(text, '{"a": 1}')     # repair'dan keyingi matn
        self.assertNotEqual(text, broken)        # xom out emas

    def test_cag_hit_repairs_and_keeps_memory_consistent(self):
        """CAG HIT: eski/buzilgan kesh yozuvi ham repair'dan o'tadi; memory
        output == content == confidence (final yo'li bilan bir xil)."""
        from agent.igris_agent import IgrisAgent, CHAT_TOOLS_SYSTEM
        from agent.cag import CagCache
        broken = '{"a": 1} ortiqcha matn'
        cache = CagCache()
        cache.put(CHAT_TOOLS_SYSTEM, "JSON qaytar", broken)

        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._cag = lambda: cache
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        data = agent.chat("JSON qaytar", use_memory=False)

        self.assertEqual(data["engine"], "cag")
        self.assertEqual(data["content"], '{"a": 1}')  # repair ishladi
        self.assertIn("structure_check", data)
        self.assertTrue(calls, "memory yozilmadi")
        q, d = calls[0]
        self.assertEqual(d["output"], data["content"], "memory output != content")
        self.assertEqual(d["confidence"], data["self_eval"]["confidence"],
                         "memory confidence != self_eval confidence")
        self.assertIn("verifier_repaired", data["self_eval"].get("notes", []))

    def test_cag_put_stream_caches_repaired_content(self):
        """chat_stream plain-stream: CAG PUT ham repair'dan keyingi matnni oladi
        (chat() bilan bir xil kalitda bir xil qiymat — inter-path tafovut yo'q)."""
        from agent.igris_agent import CHAT_TOOLS_SYSTEM
        broken = '{"a": 1} ortiqcha matn'
        agent = self._llm_agent(broken)
        spy = self._SpyCache()
        agent._cag = lambda: spy
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("JSON qaytar", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")
        self.assertEqual(done["content"], '{"a": 1}')  # repair ishladi
        self.assertTrue(spy.puts, "stream keshga yozilmadi")
        # AUDIT: req-kesh ('req' system) ham put qilishi mumkin —
        # CHAT_TOOLS_SYSTEM kalitli put'ni ICHIDAN topamiz.
        chat_puts = [(s, p, text) for s, p, text in spy.puts
                     if s == CHAT_TOOLS_SYSTEM]
        self.assertTrue(chat_puts, "CHAT_TOOLS_SYSTEM kalitli put topilmadi")
        s, p, text = chat_puts[0]
        self.assertEqual(text, '{"a": 1}')  # repair'dan keyingi matn
        self.assertNotEqual(text, broken)        # xom out emas
        # memory ham AYNAN done content (post-repair) bilan bir xil
        self.assertTrue(calls, "stream memory yozilmadi")
        q, d = calls[0]
        self.assertEqual(d["output"], done["content"])
        self.assertEqual(d["confidence"], done["self_eval"]["confidence"])

    def test_cag_hit_stream_repairs_and_keeps_memory_consistent(self):
        """chat_stream CAG hit: eski/buzilgan kesh yozuvi ham repair'dan o'tadi;
        memory output == done content == confidence."""
        from agent.igris_agent import IgrisAgent, CHAT_TOOLS_SYSTEM
        from agent.cag import CagCache
        broken = '{"a": 1} ortiqcha matn'
        cache = CagCache()
        cache.put(CHAT_TOOLS_SYSTEM, "JSON qaytar", broken)

        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._cag = lambda: cache
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("JSON qaytar", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")

        self.assertEqual(done["engine"], "cag")
        self.assertEqual(done["content"], '{"a": 1}')  # repair ishladi
        self.assertIn("structure_check", done)
        self.assertTrue(calls, "stream memory yozilmadi")
        q, d = calls[0]
        self.assertEqual(d["output"], done["content"], "stream memory output != content")
        self.assertEqual(d["confidence"], done["self_eval"]["confidence"],
                         "stream memory confidence != self_eval confidence")
        self.assertIn("verifier_repaired", done["self_eval"].get("notes", []))

    def test_cag_hit_fail_not_written_to_memory(self):
        """A2 — chat() CAG hit: keshlangan REPAIR QILIB BO'LMAYDIGAN chiqish
        (verified='fail') RAG'ga yozilmaydi — javob baribir fail signali bilan
        qaytadi (stream yo'llari bilan bir xil guard)."""
        from agent.igris_agent import IgrisAgent, CHAT_TOOLS_SYSTEM
        from agent.cag import CagCache
        cache = CagCache()
        cache.put(CHAT_TOOLS_SYSTEM, "JSON qaytar", "{'a': 1")

        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._cag = lambda: cache
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        data = agent.chat("JSON qaytar", use_memory=False)

        self.assertEqual(data["engine"], "cag")
        self.assertFalse(calls, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertIn("structure_check", data)
        self.assertFalse(data["structure_check"]["ok"])
        self.assertIn("verifier_fail", data["self_eval"].get("notes", []))

    def test_cag_hit_stream_fail_not_written_to_memory(self):
        """A2 — chat_stream CAG hit: keshlangan REPAIR QILIB BO'LMAYDIGAN chiqish
        RAG'ga yozilmaydi — done baribir fail signali bilan qaytadi."""
        from agent.igris_agent import IgrisAgent, CHAT_TOOLS_SYSTEM
        from agent.cag import CagCache
        cache = CagCache()
        cache.put(CHAT_TOOLS_SYSTEM, "JSON qaytar", "{'a': 1")

        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._cag = lambda: cache
        calls = []
        agent.memory.enabled = True
        agent.memory.on_resolve = lambda q, d: calls.append((q, d))

        events = list(agent.chat_stream("JSON qaytar", use_memory=False))
        done = next(ev for ev in events if ev["type"] == "done")

        self.assertEqual(done["engine"], "cag")
        self.assertFalse(calls, "buzilgan chiqish RAG'ga yozilmasligi kerak")
        self.assertIn("structure_check", done)
        self.assertFalse(done["structure_check"]["ok"])
        self.assertIn("verifier_fail", done["self_eval"].get("notes", []))

    def test_stable_cache_key_across_memory_change(self):
        from agent.igris_agent import CHAT_TOOLS_SYSTEM
        from agent.cag import CagCache
        c = CagCache()
        # birinchi javob: xotira konteksti A bo'lsa ham kesh kaliti system+msg
        c.put(CHAT_TOOLS_SYSTEM, "2+2 nechi?", "4")
        # xotira o'zgargan bo'lsa ham (system o'zgarmaydi) — hit bo'ladi
        self.assertEqual(c.get(CHAT_TOOLS_SYSTEM, "2+2 nechi?"), "4")

    def test_draw_request_not_cached(self):
        from agent.igris_agent import IgrisAgent
        self.assertTrue(IgrisAgent._is_draw_request("olma rasm chiz"))
        self.assertTrue(IgrisAgent._is_draw_request("draw a dashboard"))
        self.assertTrue(IgrisAgent._is_draw_request("bu UI qur"))
        self.assertFalse(IgrisAgent._is_draw_request("2+2 nechi?"))


class TestAgentHookBus(unittest.TestCase):
    def test_register_and_fire(self):
        bus = AgentHookBus()
        seen = []
        bus.register("h1", "on_tool_call", lambda ctx: seen.append(ctx["tool"]))
        bus.register("h2", "on_tool_call", lambda ctx: None)
        results = bus.fire("on_tool_call", {"tool": "read_file"})
        self.assertEqual(len(results), 2)
        self.assertEqual(seen, ["read_file"])
        self.assertTrue(all(r["status"] == "ok" for r in results))

    def test_error_safety(self):
        bus = AgentHookBus()
        def boom(ctx):
            raise RuntimeError("x")
        bus.register("bad", "on_error", boom)
        results = bus.fire("on_error", {})
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("x", results[0]["error"])

    def test_priority_order(self):
        bus = AgentHookBus()
        order = []
        bus.register("low", "t", lambda ctx: order.append("low"), priority=100)
        bus.register("high", "t", lambda ctx: order.append("high"), priority=0)
        bus.fire("t", {})
        self.assertEqual(order, ["high", "low"])

    def test_default_hooks(self):
        register_default_hooks(DEFAULT_BUS)
        self.assertIn("plan-first-check", DEFAULT_BUS.registered().get("on_step_start", []))

    def test_stats_does_not_deadlock(self):
        """stats() ichida registered() chaqiriladi — RLock bo'lmasa deadlock."""
        bus = AgentHookBus()
        bus.register("h", "on_tool_call", lambda ctx: None)
        bus.fire("on_tool_call", {"tool": "read_file"})
        st = bus.stats()  # ilgari bu yerda qotib qolardi
        self.assertIn("registered", st)
        self.assertIn("on_tool_call", st["by_trigger"])
        self.assertEqual(st["events"], 1)

    def test_stats_after_fire_error(self):
        bus = AgentHookBus()
        def boom(ctx):
            raise RuntimeError("x")
        bus.register("bad", "on_error", boom)
        bus.fire("on_error", {})
        st = bus.stats()
        self.assertEqual(st["errors"], 1)


class TestMagAssembler(unittest.TestCase):
    def test_disabled_degrades(self):
        mag = MagAssembler(memory=None)
        res = mag.assemble("test")
        self.assertEqual(res["context"], "")
        self.assertEqual(res["hits"], 0)
        self.assertEqual(mag.remember_result("q", "a")["status"], "disabled")


class TestNewSkills(unittest.TestCase):
    def setUp(self):
        self.mgr = SkillManager([os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")])

    def test_new_skills_loaded(self):
        names = self.mgr.names()
        for expected in ("plan-first-fix", "rag-recall", "cag-cache",
                         "mag-memory", "preview-live-usage"):
            self.assertIn(expected, names, f"missing skill {expected}")

    def test_skill_content_links_modules(self):
        self.assertIn("CagCache", self.mgr.get("cag-cache").full_text())
        self.assertIn("MemoryBridge", self.mgr.get("mag-memory").full_text())
        self.assertIn("plan-first", self.mgr.get("plan-first-fix").full_text())
        self.assertIn("LiveBuildView", self.mgr.get("preview-live-usage").full_text())
        self.assertIn("recall", self.mgr.get("rag-recall").full_text())

    def test_plan_first_in_executor(self):
        from executor.executor import PLAN_FIRST_SYSTEM
        self.assertIn("plan", PLAN_FIRST_SYSTEM.lower())
        self.assertIn("MANDATORY", PLAN_FIRST_SYSTEM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
