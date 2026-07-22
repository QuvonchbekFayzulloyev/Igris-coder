"""Integration test for the full pipeline."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from igris.config import Config
from igris.core.intent_resolver import IntentResolver


# ===========================================================================
# 1. Provider Router
# ===========================================================================

class TestProviderRouter:
    def test_query_to_capability_maps_known_patterns(self):
        from igris.core.provider_router import query_to_capability
        assert query_to_capability("draw a cat") == "image_gen"
        assert query_to_capability("what is python") == "research"
        assert query_to_capability("write code for sorting") == "coding"

    def test_query_to_capability_falls_back(self):
        from igris.core.provider_router import query_to_capability
        cap = query_to_capability("hello how are you")
        assert cap in ("conversation", "research")

    def test_select_returns_string_or_none(self):
        from igris.core.provider_router import select
        result = select("research")
        assert result is None or isinstance(result, str)

    def test_select_multi_returns_list(self):
        from igris.core.provider_router import select_multi
        result = select_multi("research", 3)
        assert isinstance(result, list)

    def test_health_tracking(self):
        from igris.core.provider_router import (
            mark_failure, mark_success, get_health_summary,
        )
        mark_failure("perplexity", "rate_limited")
        summary = get_health_summary()
        assert "perplexity" in summary
        assert summary["perplexity"] in ("rate_limited", "available")
        mark_success("perplexity")

    def test_decision_path_structure(self):
        from igris.core.provider_router import get_decision_path
        path = get_decision_path("write a python function")
        assert isinstance(path, dict)

    def test_format_decision(self):
        from igris.core.provider_router import format_decision
        formatted = format_decision("explain quantum computing")
        assert isinstance(formatted, str)

    def test_provider_capabilities_structure(self):
        from igris.core.provider_router import PROVIDER_CAPABILITIES
        for name, caps in PROVIDER_CAPABILITIES.items():
            assert "capabilities" in caps, f"{name} missing capabilities"
            assert isinstance(caps["capabilities"], set)

    def test_capability_providers_invert(self):
        from igris.core.provider_router import CAPABILITY_PROVIDERS
        assert "research" in CAPABILITY_PROVIDERS
        assert "coding" in CAPABILITY_PROVIDERS
        assert "image_gen" in CAPABILITY_PROVIDERS


# ===========================================================================
# 2. Translation
# ===========================================================================

class TestTranslation:
    def test_detect_language_uzbek(self):
        from igris.core.translation import detect_language
        assert detect_language("salom dunyo") == "uz"

    def test_detect_language_english(self):
        from igris.core.translation import detect_language
        assert detect_language("hello world") == "en"

    def test_detect_language_cyrillic(self):
        from igris.core.translation import detect_language
        lang = detect_language(u"\u044d\u0442\u043e \u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435")
        assert lang in ("ru", "kk", "be", "uk", "uz")

    def test_needs_translation_uzbek(self):
        from igris.core.translation import needs_translation
        needs, lang = needs_translation("salom dunyo")
        assert needs is True
        assert lang == "uz"

    def test_needs_translation_english(self):
        from igris.core.translation import needs_translation
        needs, lang = needs_translation("hello world")
        assert needs is False
        assert lang == "en"

    def test_translate_to_canonical_is_async_fn(self):
        import inspect
        from igris.core.translation import translate_to_canonical
        assert inspect.iscoroutinefunction(translate_to_canonical)

    def test_translate_from_canonical_is_async_fn(self):
        import inspect
        from igris.core.translation import translate_from_canonical
        assert inspect.iscoroutinefunction(translate_from_canonical)


# ===========================================================================
# 3. Intent Resolution (using resolver fixture)
# ===========================================================================

@pytest.fixture
def resolver():
    config = Config.load(project_root=Path("/tmp"))
    return IntentResolver(config, llm=None)


class TestIntentResolverInline:
    def test_uzbek_list_files(self, resolver):
        intent = asyncio.run(resolver.classify("fayllarni ko'rsat"))
        assert intent.category in ("command", "read_only")

    def test_english_list_files(self, resolver):
        intent = asyncio.run(resolver.classify("list files in this directory"))
        assert intent.category in ("command", "read_only")

    def test_uzbek_search(self, resolver):
        intent = asyncio.run(resolver.classify("internetdan malumot qidir"))
        assert intent.category in ("research", "command", "ambiguous")

    def test_vague_query(self, resolver):
        intent = asyncio.run(resolver.classify("something"))
        assert intent.category in ("ambiguous", "question")

    def test_complex_code_task(self, resolver):
        intent = asyncio.run(resolver.classify("build an ecommerce site with frontend and backend"))
        assert intent.category in ("code_task", "research")


# ===========================================================================
# 4. Executive Controller
# ===========================================================================

class TestExecutiveController:
    def test_controller_singleton(self):
        from igris.core.executive_controller import get_controller
        c1 = get_controller()
        c2 = get_controller()
        assert c1 is c2

    def test_tier_is_integer(self):
        from igris.core.executive_controller import get_controller
        ctrl = get_controller()
        assert isinstance(ctrl.tier, int)
        assert 0 <= ctrl.tier <= 4

    def test_tier_name(self):
        from igris.core.executive_controller import get_controller
        ctrl = get_controller()
        names = ["battery_saver", "low_power", "balanced", "high", "ultra"]
        assert ctrl.tier_name == names[ctrl.tier]

    def test_record_frame(self):
        from igris.core.executive_controller import get_controller
        ctrl = get_controller()
        for _ in range(3):
            ctrl.record_frame(50.0)
        assert ctrl._state.fps > 0

    def test_hardware_detection_returns_data(self):
        from igris.core.executive_controller import detect_hardware
        hw = detect_hardware()
        assert hw.cpu_cores > 0
        assert hw.ram_total_mb > 0

    def test_get_quality_tier_async(self):
        from igris.core.executive_controller import get_quality_tier
        tier = asyncio.run(get_quality_tier())
        assert isinstance(tier, int)
        assert 0 <= tier <= 4

    def test_to_dict(self):
        from igris.core.executive_controller import get_controller
        ctrl = get_controller()
        d = ctrl.to_dict()
        assert "tier" in d
        assert "fps" in d
        assert "gpu" in d
        assert "ram_mb" in d


# ===========================================================================
# 5. Browser Runtime (import-only — no browser launch)
# ===========================================================================

class TestBrowserRuntimeImport:
    def test_import_all_symbols(self):
        from igris.core.browser_runtime import (
            SUPPORTED_SITES, BrowserRuntime, SessionState,
            ChatState, ProviderTab, get_runtime,
        )
        assert len(SUPPORTED_SITES) >= 6
        assert "chatgpt" in SUPPORTED_SITES
        assert "perplexity" in SUPPORTED_SITES

    def test_session_state_enum(self):
        from igris.core.browser_runtime import SessionState
        assert SessionState.LOGGED_IN.value == "logged_in"
        assert SessionState.RATE_LIMITED.value == "rate_limited"

    def test_browser_runtime_init(self):
        from igris.core.browser_runtime import BrowserRuntime
        rt = BrowserRuntime()
        assert rt._browser is None
        assert rt._playwright is None

    def test_provider_tab_defaults(self):
        from igris.core.browser_runtime import ProviderTab
        tab = ProviderTab(provider="test")
        assert tab.session.value == "unknown"
        assert tab.chat.value == "idle"


# ===========================================================================
# 6. Web Trending
# ===========================================================================

class TestTrendingImport:
    def test_web_trending_imports(self):
        from igris.mcp_servers.web_server import web_trending
        assert web_trending is not None
