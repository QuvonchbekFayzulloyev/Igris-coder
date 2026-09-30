"""WEB strategiya testlari: browser qachon, web AI subagent (delegate) qachon.

Maqsad: agent browser'ni maqsadsiz ishlatmasligi — bilim/qidiruv so'rovlarida
web AI'ga topshiradi (ask_web_ai), faqat interaktiv sahifalarda browser ishlaydi.
"""
import json
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from agent.igris_agent import IgrisAgent  # noqa: E402


class TestWebStrategy(unittest.TestCase):
    def test_url_means_browser(self):
        self.assertEqual(IgrisAgent._web_strategy("https://example.com ochib ber"), "browser")
        self.assertEqual(IgrisAgent._web_strategy("www.olx.uz dan telefon ko'rmoqchiman"), "browser")

    def test_explicit_page_action_means_browser(self):
        self.assertEqual(IgrisAgent._web_strategy("saytni ochib ber"), "browser")
        self.assertEqual(IgrisAgent._web_strategy("brauzerda och"), "browser")
        self.assertEqual(IgrisAgent._web_strategy("sahifani yuklab ol"), "browser")

    def test_research_search_means_delegate(self):
        self.assertEqual(IgrisAgent._web_strategy("googledan qidirib ber"), "delegate")
        self.assertEqual(IgrisAgent._web_strategy("internetdan topib ber"), "delegate")
        self.assertEqual(IgrisAgent._web_strategy("bu mavzuda tadqiq qil"), "delegate")
        self.assertEqual(IgrisAgent._web_strategy("qidirib bilmoqchiman"), "delegate")
        # Umumiy bilim savoli web darvozasidan o'tmaydi — javob bilimdan beriladi
        self.assertEqual(IgrisAgent._web_strategy("bilmoqchiman qanday qilinadi"), "")

    def test_web_ai_name_means_delegate(self):
        self.assertEqual(IgrisAgent._web_strategy("chatgptdan so'ra"), "delegate")
        self.assertEqual(IgrisAgent._web_strategy("gemini bilan tekshir"), "delegate")
        self.assertEqual(IgrisAgent._web_strategy("deepseek dan so'rab ber"), "delegate")

    def test_url_plus_research_means_full(self):
        self.assertEqual(
            IgrisAgent._web_strategy("https://x.com nima deydi, tadqiq qil"),
            "full",
        )

    def test_non_web_messages_get_empty(self):
        self.assertEqual(IgrisAgent._web_strategy("olma rasmini chiz"), "")
        self.assertEqual(IgrisAgent._web_strategy("2+2 nechi?"), "")
        self.assertEqual(IgrisAgent._web_strategy("linked list nima"), "")  # soxta pozitiv YO'Q
        self.assertEqual(IgrisAgent._web_strategy("python kod yoz"), "")

    def test_needs_web_consistent_with_strategy(self):
        for msg in ("https://a.b", "googledan qidir", "saytni och", "chatgptdan so'ra"):
            self.assertTrue(IgrisAgent._needs_web(msg), msg)
            self.assertTrue(IgrisAgent._web_strategy(msg), msg)


class _FakeMCP:
    def __init__(self):
        self.tool_index = {
            "art__draw_custom_svg": {"schema": {
                "description": "draw an svg", "parameters": {"type": "object", "properties": {}}}},
            "art__draw_scene_svg": {"schema": {
                "description": "draw a scene", "parameters": {"type": "object", "properties": {}}}},
            "art__draw_object_png": {"schema": {
                "description": "draw a png object", "parameters": {"type": "object", "properties": {}}}},
            "art__ui_build_spec": {"schema": {
                "description": "build interactive ui", "parameters": {"type": "object", "properties": {}}}},
            "web_ai_bridge__ask_web_ai": {"schema": {
                "description": "ask a web ai", "parameters": {"type": "object", "properties": {}}}},
            "web_ai_bridge__web_ai_check_research": {"schema": {
                "description": "check research", "parameters": {"type": "object", "properties": {}}}},
            "web_ai_bridge__browser_navigate": {"schema": {
                "description": "navigate", "parameters": {"type": "object", "properties": {}}}},
            "web_ai_bridge__browser_click": {"schema": {
                "description": "click", "parameters": {"type": "object", "properties": {}}}},
        }

    def names(self):
        return list(self.tool_index.keys())


class TestWebToolFiltering(unittest.TestCase):
    def setUp(self):
        self.agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.agent._mcp = lambda: _FakeMCP()
        self.agent._registry = lambda: None

    def _names(self, strategy=None):
        tools = self.agent._chat_tools(
            include_web=bool(strategy), web_strategy=strategy or "")
        return {t["function"]["name"] for t in tools}

    def test_delegate_strategy_has_web_ai_but_no_interaction(self):
        names = self._names("delegate")
        self.assertIn("web_ai_bridge__ask_web_ai", names)
        self.assertIn("web_ai_bridge__web_ai_check_research", names)
        self.assertIn("web_ai_bridge__browser_navigate", names)  # minimal zaxira
        self.assertNotIn("web_ai_bridge__browser_click", names)  # interaktiv YO'Q

    def test_browser_strategy_has_interaction_but_no_delegation(self):
        names = self._names("browser")
        self.assertIn("web_ai_bridge__browser_navigate", names)
        self.assertIn("web_ai_bridge__browser_click", names)
        self.assertNotIn("web_ai_bridge__ask_web_ai", names)

    def test_full_strategy_has_everything(self):
        names = self._names("full")
        self.assertIn("web_ai_bridge__ask_web_ai", names)
        self.assertIn("web_ai_bridge__browser_click", names)

    def test_non_web_chat_has_no_web_tools_at_all(self):
        names = self._names()
        self.assertFalse(any(n.startswith("web_ai_bridge__") for n in names))

    def test_web_tool_schemas_include_when_to_use_hints(self):
        """WEB_TOOLS_GUIDE'dan qisqa ko'rsatmalar schema description'ga qo'shiladi."""
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._mcp = lambda: _FakeMCP()
        agent._registry = lambda: None
        tools = agent._chat_tools(include_web=True, web_strategy="delegate")
        by_name = {t["function"]["name"]: t["function"]["description"] for t in tools}
        ask = by_name["web_ai_bridge__ask_web_ai"]
        self.assertIn("WHEN TO USE", ask)
        self.assertIn("DELEGATES", ask)          # subagent ko'rsatmasi
        self.assertIn("ask a web ai", ask)        # asosiy description saqlanadi
        # browser strategiyasida click xavfsizlik eslatmasi bilan keladi
        tools_b = agent._chat_tools(include_web=True, web_strategy="browser")
        by_name_b = {t["function"]["name"]: t["function"]["description"] for t in tools_b}
        click = by_name_b["web_ai_bridge__browser_click"]
        self.assertIn("WHEN TO USE", click)
        self.assertIn("confirm:true", click)
        # uzun hint ham to'liq qoladi (navigate: BLOCKED + Content-Type)
        nav = by_name_b["web_ai_bridge__browser_navigate"]
        self.assertIn("BLOCKED", nav)
        self.assertIn("Content-Type", nav)

    def test_art_tool_schemas_include_hints(self):
        """ART_TOOL_HINTS — model qaysi chizish vositasini QACHON tanlashni ko'radi."""
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._mcp = lambda: _FakeMCP()
        agent._registry = lambda: None
        tools = agent._chat_tools()
        by_name = {t["function"]["name"]: t["function"]["description"] for t in tools}
        custom = by_name["art__draw_custom_svg"]
        self.assertIn("WHEN TO USE", custom)
        self.assertIn("MAIN drawing tool", custom)
        self.assertIn("NO fixed subject list", custom)
        self.assertIn("draw an svg", custom)  # asosiy description saqlanadi
        ui = by_name["art__ui_build_spec"]
        self.assertIn("WHEN TO USE", ui)
        self.assertIn("uibuild.json", ui)
        scene = by_name["art__draw_scene_svg"]
        self.assertIn("WHEN TO USE", scene)
        self.assertIn("Quick layered SCENE", scene)
        png = by_name["art__draw_object_png"]
        self.assertIn("WHEN TO USE", png)
        self.assertIn("PNG/raster", png)

    def test_web_tools_do_not_duplicate_hint_from_server(self):
        """Yangi bridge hint'ni o'zi qo'shadi — agent qayta qo'shmaydi (manba server)."""
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        mcp = _FakeMCP()
        # Yangi server: description hint bilan keladi
        mcp.tool_index["web_ai_bridge__ask_web_ai"] = {"schema": {
            "description": "ask a web ai\n\nWHEN TO USE: serverdagi korsatma",
            "parameters": {"type": "object", "properties": {}},
        }}
        agent._mcp = lambda: mcp
        agent._registry = lambda: None
        tools = agent._chat_tools(include_web=True, web_strategy="delegate")
        by_name = {t["function"]["name"]: t["function"]["description"] for t in tools}
        ask = by_name["web_ai_bridge__ask_web_ai"]
        self.assertEqual(ask.count("WHEN TO USE"), 1)  # dublikat YO'Q
        self.assertIn("serverdagi korsatma", ask)        # server matni saqlanadi
        self.assertNotIn("DELEGATES", ask)               # mahalliy zaxira qo'shilmadi

    def test_web_tool_hints_parity_with_server(self):
        """Manba (server WHEN_TO_USE) va zaxira (WEB_TOOL_HINTS) kalitlari mos — drift YO'Q."""
        import re
        from agent.igris_agent import WEB_TOOL_HINTS
        js_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "..", "web-ai-bridge", "server", "src", "index.js")
        if not os.path.isfile(js_path):
            self.skipTest("web-ai-bridge server fayli topilmadi")
        js = open(js_path, encoding="utf-8").read()
        block = re.search(r"const WHEN_TO_USE = \{.*?\};", js, re.S)
        self.assertIsNotNone(block, "WHEN_TO_USE bloki index.js'da yo'q")
        js_names = set(re.findall(r"^  ([a-z_]+):", block.group(0), re.M))
        py_names = {k.replace("web_ai_bridge__", "")
                    for k in WEB_TOOL_HINTS}
        self.assertEqual(py_names - js_names, set(), "Python'da bor, server'da yo'q")
        self.assertEqual(js_names - py_names, set(), "Server'da bor, Python'da yo'q")
        self.assertIn("ask_web_ai", js_names)

    def test_tool_desc_with_hint_helper_contract(self):
        """_tool_desc_with_hint: base 350 kesiladi, hint to'liq, cap 800, None xavfsiz."""
        from agent.igris_agent import _tool_desc_with_hint
        # hint yo'q -> base 350 ga kesiladi
        self.assertEqual(len(_tool_desc_with_hint({"description": "y" * 500}, None)), 350)
        # hint bor -> base 350 + "\n\nWHEN TO USE: " + hint, cap 800
        d = _tool_desc_with_hint({"description": "y" * 400}, "hint text")
        self.assertIn("WHEN TO USE: hint text", d)
        self.assertEqual(len(d), 350 + len("\n\nWHEN TO USE: hint text"))
        # real o'lchamdagi hint (<=300) cap'da kesilmaydi
        big = _tool_desc_with_hint({"description": "y" * 350}, "z" * 300)
        self.assertLessEqual(len(big), 800)
        self.assertTrue(big.endswith("z" * 300))
        # sun'iy juda uzun hint cap 800 da chegaralanadi, qulash yo'q
        huge = _tool_desc_with_hint({"description": "y" * 350}, "z" * 600)
        self.assertEqual(len(huge), 800)
        # schema description'isiz ham ishlaydi
        self.assertIn("WHEN TO USE", _tool_desc_with_hint({}, "hint"))

    def test_mcp_call_does_not_expose_web_tools(self):
        """mcp_call orqali web tool'lar ko'rinmaydi — strategiyasiz chaqirib bo'lmaydi."""
        tools = self.agent._chat_tools(include_web=False)
        mcp_call = next(t for t in tools if t["function"]["name"] == "mcp_call")
        desc = mcp_call["function"]["description"]
        self.assertNotIn("web_ai_bridge__", desc)
        self.assertIn("art__draw_custom_svg", desc)  # art tool'lari ko'rinadi


class TestWebDecisionRules(unittest.TestCase):
    def test_rules_mention_cheapest_first_and_subagent(self):
        rules = IgrisAgent._web_decision_rules("delegate")
        self.assertIn("CHEAPEST", rules)
        self.assertIn("ask_web_ai", rules)
        self.assertIn("SUBAGENT", rules)
        self.assertIn("web_fetch", rules)

    def test_browser_hint(self):
        rules = IgrisAgent._web_decision_rules("browser")
        self.assertIn("browser_navigate", rules)

    def test_full_no_specific_hint(self):
        rules = IgrisAgent._web_decision_rules("full")
        self.assertIn("CHEAPEST", rules)

    def test_rules_include_full_tool_guide(self):
        """GUIDE.md dan TO'LIQ jadval — har bir tool qachon ishlatiladi."""
        rules = IgrisAgent._web_decision_rules("delegate")
        for tool in ("browser_navigate", "browser_check_link", "browser_screenshot",
                     "browser_get_text", "browser_click", "browser_type",
                     "browser_select_option", "browser_upload_file", "browser_press_key",
                     "browser_scroll", "browser_wait_for", "browser_list_tabs",
                     "browser_list_downloads", "browser_info", "browser_dismiss_overlays",
                     "ask_web_ai", "web_ai_start_research", "web_ai_check_research",
                     "web_ai_new_chat", "web_ai_stop_generating", "web_ai_get_conversation"):
            self.assertIn(tool, rules, tool)
        # Xavfsizlik qatlamlari + prefiks tushuntirish + research qoidasi
        self.assertIn("BUTTON SAFETY TIERS", rules)
        self.assertIn("confirm:true", rules)
        self.assertIn("web_ai_bridge__browser_navigate", rules)
        self.assertIn("Never block-wait", rules)

    def test_rules_include_data_checking_section(self):
        """GUIDE.md §3 (data checking) — model natijalarni qanday talqin qiladi."""
        rules = IgrisAgent._web_decision_rules("browser")
        self.assertIn("READING BROWSER RESULTS", rules)
        # blocked vs obstructed (hech qachon ikkalasi birdan emas)
        self.assertIn("BLOCKED", rules)
        self.assertIn("OBSTRUCTED", rules)
        self.assertIn("never both", rules)
        # download aniqlash
        self.assertIn("browser_list_downloads", rules)
        self.assertIn("Content-Type", rules)
        # secret skaneri (escalation -> foydalanuvchiga ayt)
        self.assertIn("confirmation prompt", rules)
        self.assertIn("API keys", rules)
        # degradatsiya -> web_ai_new_chat
        self.assertIn("web_ai_new_chat", rules)

    def test_tools_hint_includes_guide_for_web_request(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._mcp = lambda: _FakeMCP()
        agent._registry = lambda: None
        hint = agent._tools_hint(request="googledan qidirib ber")
        self.assertIn("WEB-TOOLS QUICK GUIDE", hint)
        self.assertIn("ask_web_ai", hint)
        self.assertIn("browser_get_text", hint)
        self.assertIn("confirm:true", hint)

    def test_tools_hint_omits_web_guide_for_non_web(self):
        """Rasm/kod vazifasida 3KB browser shovqini qo'shilmaydi."""
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._mcp = lambda: _FakeMCP()
        agent._registry = lambda: None
        hint = agent._tools_hint(request="olma rasmini chiz")
        self.assertNotIn("WEB-TOOLS QUICK GUIDE", hint)
        self.assertNotIn("web_ai_bridge__", hint)

    def test_tools_hint_no_request_defaults_to_no_web_guide(self):
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._mcp = lambda: _FakeMCP()
        agent._registry = lambda: None
        self.assertNotIn("WEB-TOOLS QUICK GUIDE", agent._tools_hint())


class TestWebStrategyLogging(unittest.TestCase):
    def setUp(self):
        self.agent = IgrisAgent(use_llm=False, memory_enabled=False)
        self.tmp = tempfile.mkdtemp()
        self.agent._web_log_path = os.path.join(self.tmp, "web_strategy.jsonl")

    def _read(self):
        path = self.agent._web_log_path
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_ok_delegate(self):
        self.agent._log_web_strategy(
            "chatgptdan sorab ber", "delegate",
            [{"tool": "web_ai_bridge__ask_web_ai", "result": {"ok": True}}],
            "llm+tools", content_len=42)
        entries = self._read()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["verdict"], "ok-delegate")
        self.assertEqual(entries[0]["strategy"], "delegate")
        self.assertEqual(entries[0]["content_len"], 42)
        self.assertIn("ai_name", entries[0]["matched"])
        self.assertTrue(entries[0]["delegation_used"])

    def test_misuse_browser_in_delegate(self):
        self.agent._log_web_strategy(
            "googledan qidirib ber", "delegate",
            [{"tool": "web_ai_bridge__browser_click"}], "llm+tools")
        self.assertEqual(self._read()[0]["verdict"], "misuse-browser")

    def test_browser_fallback_in_delegate(self):
        self.agent._log_web_strategy(
            "googledan qidirib ber", "delegate",
            [{"tool": "web_ai_bridge__browser_navigate"}], "llm+tools")
        self.assertEqual(self._read()[0]["verdict"], "browser-fallback")

    def test_ok_browser(self):
        self.agent._log_web_strategy(
            "saytni ochib ber", "browser",
            [{"tool": "web_ai_bridge__browser_navigate"}], "llm+tools")
        self.assertEqual(self._read()[0]["verdict"], "ok-browser")

    def test_delegated_instead_of_browsing(self):
        self.agent._log_web_strategy(
            "saytni ochib ber", "browser",
            [{"tool": "web_ai_bridge__ask_web_ai"}], "llm+tools")
        self.assertEqual(self._read()[0]["verdict"], "delegated-instead")

    def test_no_web_tool_flagged(self):
        self.agent._log_web_strategy("saytni ochib ber", "browser", [], "llm")
        self.assertEqual(self._read()[0]["verdict"], "no-web-tool")

    def test_unexpected_web_when_no_strategy(self):
        self.agent._log_web_strategy(
            "olma chiz", "",
            [{"tool": "web_ai_bridge__browser_navigate"}], "llm+tools")
        self.assertEqual(self._read()[0]["verdict"], "unexpected-web")

    def test_skipped_when_no_web_at_all(self):
        self.agent._log_web_strategy("salom", "", [], "llm")
        self.assertEqual(self._read(), [])

    def test_unavailable_when_mcp_down(self):
        self.agent._log_web_strategy("chatgptdan sorab ber", "delegate", [], "llm",
                                     mcp_ok=False)
        self.assertEqual(self._read()[0]["verdict"], "unavailable")

    def test_never_raises_on_weird_inputs(self):
        self.agent._log_web_strategy(None, "delegate", "not-a-list", "llm")
        self.agent._log_web_strategy("x", "delegate", [12345], "llm")
        self.agent._log_web_strategy("y", "browser", [{"tool": None}], "llm")
        self.assertTrue(os.path.isfile(self.agent._web_log_path))

    def test_creates_logs_dir(self):
        path = os.path.join(self.tmp, "nested", "deep", "web_strategy.jsonl")
        self.agent._web_log_path = path
        self.agent._log_web_strategy("googledan qidirib ber", "delegate", [])
        self.assertTrue(os.path.isfile(path))


class TestWebStrategyReport(unittest.TestCase):
    def test_report_aggregates_entries(self):
        from web.web_strategy_report import load_entries, build_report
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "web_strategy.jsonl")
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._web_log_path = path
        agent._log_web_strategy("chatgptdan sorab ber", "delegate",
                                [{"tool": "web_ai_bridge__ask_web_ai"}], "llm+tools")
        agent._log_web_strategy("googledan qidirib ber", "delegate",
                                [{"tool": "web_ai_bridge__browser_click"}], "llm+tools")
        agent._log_web_strategy("saytni ochib ber", "browser", [], "llm")
        report = build_report(load_entries(path))
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["strategy_dist"], {"delegate": 2, "browser": 1})
        self.assertEqual(report["verdict_dist"]["ok-delegate"], 1)
        self.assertEqual(report["verdict_dist"]["misuse-browser"], 1)
        self.assertEqual(report["verdict_dist"]["no-web-tool"], 1)
        self.assertEqual(report["problem_count"], 2)
        self.assertEqual(report["delegation_used"], 1)
        self.assertEqual(len(report["problems"]), 2)
        # TOOL TANLASH SIFATI metrikalari
        sel = report["selection"]
        self.assertEqual(sel["correct"], 1)
        self.assertEqual(sel["missed"], 1)
        self.assertEqual(sel["wrong_family"], 1)
        self.assertEqual(sel["gate_breach"], 0)
        self.assertAlmostEqual(sel["correct_rate"], round(1 / 3, 3), places=3)
        hint = report["hint_effectiveness"]
        self.assertEqual(hint["delegate_requests"], 2)
        self.assertEqual(hint["delegation_used"], 1)   # 1/2 ta delegate so'rovda ask_web_ai
        self.assertAlmostEqual(hint["delegation_rate"], 0.5)
        self.assertEqual(hint["browser_requests"], 1)
        self.assertEqual(hint["browser_direct"], 0)
        self.assertEqual(hint["browser_rate"], 0.0)

    def test_report_browser_hint_and_gate_breach_metrics(self):
        from web.web_strategy_report import load_entries, build_report
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "web_strategy.jsonl")
        agent = IgrisAgent(use_llm=False, memory_enabled=False)
        agent._web_log_path = path
        # browser strategiyasida to'g'ri browser tool ishlatildi
        agent._log_web_strategy("saytni ochib ber", "browser",
                                [{"tool": "web_ai_bridge__browser_navigate"}], "llm+tools")
        # strategiyasiz web tool chaqirildi (darvoza chetlab o'tilgan)
        agent._log_web_strategy("olma chiz", "",
                                [{"tool": "web_ai_bridge__browser_navigate"}], "llm+tools")
        # noma'lum web tool ham noto'g'ri oilaga tushadi (other-web)
        agent._log_web_strategy("nomalum tool", "browser",
                                [{"tool": "web_ai_bridge__weird_tool"}], "llm+tools")
        report = build_report(load_entries(path))
        sel = report["selection"]
        self.assertEqual(sel["correct"], 1)          # ok-browser
        self.assertEqual(sel["gate_breach"], 1)      # unexpected-web
        self.assertEqual(sel["wrong_family"], 1)     # other-web
        # Bucket'lar to'liq: correct+missed+wrong_family+gate_breach+unavailable = total
        covered = (sel["correct"] + sel["missed"] + sel["wrong_family"]
                   + sel["gate_breach"] + report["verdict_dist"].get("unavailable", 0))
        self.assertEqual(covered, report["total"])
        self.assertAlmostEqual(sel["correct_rate"], round(1 / 3, 3), places=3)
        hint = report["hint_effectiveness"]
        self.assertEqual(hint["browser_requests"], 2)  # ikkita browser strategiyasi
        self.assertEqual(hint["browser_direct"], 1)    # faqat navigate browser_* edi
        self.assertAlmostEqual(hint["browser_rate"], 0.5)

    def test_report_empty_log(self):
        from web.web_strategy_report import load_entries, build_report
        report = build_report(load_entries("/nonexistent_dir/web_strategy.jsonl"))
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["ok_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
