"""
IGRIS — Test Suite: OmniRoute Client + Model Selector

Qamrov:
  - OmniRouteClient        : OpenAI-format yadrosi (payload/parse/convert)
  - AGENT KONTRATI         : complete/chat/chat_fast/chat_with_tools/
                             chat_stream_rich/chat_logprobs/is_available/
                             set_turbo/model/extract_code — OllamaClient bilan
                             bir xil shakl (xatolar None + last_error, raise emas)
  - IgrisAgent e2e         : agent OmniRoute bilan chat()/chat_stream() ishlaydi
"""

import json
import math
import os
import sys
import types

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
_mem = os.path.join(os.path.dirname(_root), "Igris_Memory")
if _mem not in sys.path:
    sys.path.insert(0, _mem)

import llm.omniroute_client as om  # noqa: E402
from llm.omniroute_client import (  # noqa: E402
    OmniRouteClient, ChatMessage, ChatResponse, ModelInfo,
)
from llm.model_selector import (  # noqa: E402
    ModelSelector, ModelProfile, PROFILES, TASK_RULES,
)


# ------------------------------------------------------------------ #
# Yordamchilar — httpx stub (tarmoq chaqiruvisiz)
# ------------------------------------------------------------------ #

class _FakeResp:
    def __init__(self, data=None, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class _FakeStreamResp(_FakeResp):
    def __init__(self, lines):
        super().__init__(None)
        self._lines = lines

    def iter_lines(self):
        return iter(self._lines)


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self._resp

    def __exit__(self, *exc):
        return False


def _openai_resp(content="Stub javob", tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return _FakeResp({
        "choices": [{"message": msg, "finish_reason": "stop"}],
        "model": "gpt-4o-mini",
        "usage": {},
    })


def _client_with(handler):
    """httpx stub bilan OmniRouteClient — `handler(method, url, payload)`."""
    client = OmniRouteClient(default_model="openai/gpt-4o-mini")
    client._client = types.SimpleNamespace(
        post=lambda url, json=None: handler("POST", url, json),
        get=lambda url: handler("GET", url, None),
        stream=lambda m, url, json=None: _Ctx(handler("STREAM", url, json)),
        close=lambda: None,
    )
    return client


def _boom(*args, **kwargs):
    raise ConnectionError("gateway down")


# ======================================================================
# OmniRouteClient
# ======================================================================

def test_client_init_defaults():
    """Default values bilan ishga tushirish."""
    client = OmniRouteClient()
    assert client.base_url == "http://localhost:20128/v1"
    assert client.default_model == "openai/gpt-4o-mini"
    assert client.api_key == ""


def test_client_init_custom():
    """Custom values bilan ishga tushirish."""
    client = OmniRouteClient(
        base_url="http://custom:9999/v1",
        api_key="test-key",
        default_model="anthropic/claude-3-5-sonnet",
    )
    assert client.base_url == "http://custom:9999/v1"
    assert client.api_key == "test-key"
    assert client.default_model == "anthropic/claude-3-5-sonnet"


def test_client_headers():
    """Header'lar to'g'ri qurilishi."""
    client = OmniRouteClient(api_key="my-key")
    headers = client._headers()
    assert headers["Authorization"] == "Bearer my-key"
    assert headers["Content-Type"] == "application/json"


def test_client_headers_no_key():
    """API key yo'q bo'lsa Authorization header bo'lmasligi."""
    client = OmniRouteClient(api_key="")
    headers = client._headers()
    assert "Authorization" not in headers


def test_convert_tools():
    """IGRIS tool formatini OpenAI formatga aylantirish."""
    client = OmniRouteClient()
    irgris_tools = [
        {
            "name": "read_file",
            "description": "Faylni o'qish",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        }
    ]
    converted = client._convert_tools(irgris_tools)
    assert len(converted) == 1
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["name"] == "read_file"
    assert converted[0]["function"]["description"] == "Faylni o'qish"


def test_convert_tools_empty():
    """Bo'sh tool list."""
    client = OmniRouteClient()
    assert client._convert_tools([]) == []


def test_parse_response():
    """OpenAI response'ni parse qilish."""
    client = OmniRouteClient()
    openai_response = {
        "choices": [{
            "message": {"content": "Hello!", "role": "assistant"},
            "finish_reason": "stop",
        }],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    result = client._parse_response(openai_response)
    assert result.content == "Hello!"
    assert result.role == "assistant"
    assert result.model == "gpt-4o"
    assert result.finish_reason == "stop"
    assert result.usage["prompt_tokens"] == 10


def test_parse_response_with_tools():
    """Tool calls bilan response'ni parse qilish."""
    client = OmniRouteClient()
    openai_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "test.py"}',
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "model": "gpt-4o",
    }
    result = client._parse_response(openai_response)
    assert result.has_tool_calls
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "read_file"
    assert result.tool_calls[0]["arguments"]["path"] == "test.py"


def test_parse_response_no_content():
    """Content yo'q response."""
    client = OmniRouteClient()
    openai_response = {
        "choices": [{
            "message": {"role": "assistant", "content": None},
            "finish_reason": "stop",
        }],
        "model": "gpt-4o",
    }
    result = client._parse_response(openai_response)
    assert result.content == ""


def test_chat_response_has_tool_calls():
    """ChatResponse.has_tool_calls property."""
    resp1 = ChatResponse(tool_calls=[{"name": "test"}])
    assert resp1.has_tool_calls

    resp2 = ChatResponse(content="hello")
    assert not resp2.has_tool_calls

    resp3 = ChatResponse(tool_calls=None)
    assert not resp3.has_tool_calls


def test_model_info_from_dict():
    """ModelInfo.from_dict."""
    m = ModelInfo.from_dict({"id": "gpt-4o", "owned_by": "openai", "created": 123})
    assert m.id == "gpt-4o"
    assert m.owned_by == "openai"
    assert m.created == 123


def test_model_info_from_dict_empty():
    """ModelInfo.from_dict — bo'sh dict."""
    m = ModelInfo.from_dict({})
    assert m.id == ""
    assert m.owned_by == ""


def test_chat_message_to_dict():
    """ChatMessage.to_dict."""
    msg = ChatMessage(role="user", content="hello")
    d = msg.to_dict()
    assert d == {"role": "user", "content": "hello"}


def test_chat_message_to_dict_tool():
    """ChatMessage.to_dict — tool call."""
    msg = ChatMessage(
        role="assistant",
        tool_calls=[{"id": "1", "function": {"name": "test"}}],
    )
    d = msg.to_dict()
    assert "tool_calls" in d
    assert d["role"] == "assistant"


def test_build_payload():
    """_build_payload to'g'ri payload qurishi."""
    client = OmniRouteClient(default_model="test-model")
    messages = [{"role": "user", "content": "hi"}]
    payload = client._build_payload(messages, None, None, 0.5, 100, False)

    assert payload["model"] == "test-model"
    assert payload["messages"] == messages
    assert payload["temperature"] == 0.5
    assert payload["max_tokens"] == 100
    assert "tools" not in payload
    assert "stream" not in payload


def test_build_payload_with_tools():
    """_build_payload — tools bilan."""
    client = OmniRouteClient()
    tools = [{"name": "test", "description": "desc"}]
    payload = client._build_payload([], None, tools, 0.7, None, False)

    assert "tools" in payload
    assert payload["tool_choice"] == "auto"


def test_build_payload_stream():
    """_build_payload — stream mode."""
    client = OmniRouteClient()
    payload = client._build_payload([], None, None, 0.7, None, True)
    assert payload["stream"] is True


# ======================================================================
# ModelSelector
# ======================================================================

def test_select_code_generation():
    """Code generation uchun model tanlash."""
    selector = ModelSelector()
    model = selector.select("code_generation")
    assert model.provider in ["openai", "anthropic", "deepseek"]
    assert "code" in model.strengths


def test_select_quick_qa():
    """Quick Q&A uchun model tanlash."""
    selector = ModelSelector()
    model = selector.select("quick_qa")
    assert model.cost_per_1k_input <= 0.001


def test_select_with_local_preference():
    """Local model afzallik bilan."""
    selector = ModelSelector(available_models=["qwen3-8b", "gpt-4o"])
    model = selector.select("simple_task", prefer_local=True)
    assert model.is_local


def test_select_exclude():
    """Model exclude qilish."""
    selector = ModelSelector()
    model = selector.select("code_generation", exclude=["gpt-4o", "claude-3-5-sonnet"])
    assert model.model_id != "openai/gpt-4o"
    assert model.model_id != "anthropic/claude-3-5-sonnet"


def test_select_max_cost():
    """Cost limit bilan."""
    selector = ModelSelector()
    model = selector.select("code_generation", max_cost=0.0002)
    assert model.cost_per_1k_input <= 0.0002


def test_classify_task_code():
    """Task aniqlash — code generation."""
    selector = ModelSelector()
    assert selector.classify_task("Python function yoz") == "code_generation"
    assert selector.classify_task("Create a new file") == "code_generation"
    assert selector.classify_task("API yarat va write qil") == "code_generation"


def test_classify_task_review():
    """Task aniqlash — code review."""
    selector = ModelSelector()
    assert selector.classify_task("Kodni tekshir") == "code_review"
    assert selector.classify_task("Review this code") == "code_review"


def test_classify_task_refactor():
    """Task aniqlash — refactoring."""
    selector = ModelSelector()
    assert selector.classify_task("Refactor this function") == "refactoring"
    assert selector.classify_task("Kodni optimize qil") == "refactoring"


def test_classify_task_math():
    """Task aniqlash — math."""
    selector = ModelSelector()
    assert selector.classify_task("100 ni 5 ga bo'l") == "math"
    assert selector.classify_task("Calculate sum") == "math"


def test_classify_task_simple():
    """Task aniqlash — simple task."""
    selector = ModelSelector()
    assert selector.classify_task("Salom") == "simple_task"
    assert selector.classify_task("hello") == "simple_task"


def test_estimate_cost():
    """Xarajatni hisoblash."""
    selector = ModelSelector()
    cost = selector.estimate_cost("gpt-4o", 1000, 500)
    # GPT-4o: $2.50/1M input, $10/1M output
    expected = (1000 * 0.0025 + 500 * 0.01) / 1000
    assert abs(cost - expected) < 0.001


def test_estimate_cost_free():
    """Bepul model xarajati."""
    selector = ModelSelector()
    cost = selector.estimate_cost("qwen3-8b", 10000, 5000)
    assert cost == 0.0


def test_rank_models():
    """Model reytingi."""
    selector = ModelSelector()
    ranked = selector.rank_models("code_generation", top_n=3)
    assert len(ranked) <= 3
    assert all(isinstance(m[0], ModelProfile) for m in ranked)


def test_model_profile_properties():
    """ModelProfile properties."""
    free = ModelProfile(name="free", provider="ollama", model_id="test", cost_per_1k_input=0)
    assert free.is_free
    assert free.is_local

    paid = ModelProfile(name="paid", provider="openai", model_id="test", cost_per_1k_input=0.001)
    assert not paid.is_free
    assert not paid.is_local


def test_profiles_exist():
    """PREDEFINED profillar mavjudligi."""
    assert "gpt-4o" in PROFILES
    assert "claude-3-5-sonnet" in PROFILES
    assert "gemini-1.5-pro" in PROFILES
    assert "qwen3-8b" in PROFILES


def test_task_rules_exist():
    """Task rules mavjudligi."""
    assert "code_generation" in TASK_RULES
    assert "quick_qa" in TASK_RULES
    assert "complex_reasoning" in TASK_RULES


def test_all_profiles_have_required_fields():
    """Barcha profillarda kerakli maydonlar bor."""
    for name, profile in PROFILES.items():
        assert profile.name, f"{name} missing name"
        assert profile.provider, f"{name} missing provider"
        assert profile.model_id, f"{name} missing model_id"
        assert profile.max_tokens > 0, f"{name} invalid max_tokens"
        assert len(profile.strengths) > 0, f"{name} missing strengths"


# ======================================================================
# AGENT KONTRATI — OllamaClient bilan bir xil shakl/ma'no
# ======================================================================

def test_chat_returns_text():
    """chat() -> str (agent kontrati; eski ChatResponse emas)."""
    client = _client_with(lambda m, u, p: _openai_resp("Salom!"))
    out = client.chat([{"role": "user", "content": "salom"}])
    assert isinstance(out, str)
    assert out == "Salom!"


def test_chat_transport_error_returns_none():
    """Transport xatosi -> exception EMAS, None + last_error (agent xavfsiz)."""
    client = _client_with(_boom)
    assert client.chat([{"role": "user", "content": "x"}]) is None
    assert "gateway down" in (client.last_error or "")


def test_chat_full_returns_chat_response():
    """chat_full() -> to'liq ChatResponse (tool_calls/usage uchun)."""
    client = _client_with(lambda m, u, p: _openai_resp("ok"))
    resp = client.chat_full([{"role": "user", "content": "x"}])
    assert isinstance(resp, ChatResponse)
    assert resp.content == "ok"


def test_complete_system_prompt():
    """complete(system=, prompt=) — requirement extractor/assist chaqiruvi."""
    seen = {}

    def handler(method, url, payload):
        seen.update(payload or {})
        return _openai_resp("complete javob")

    client = _client_with(handler)
    out = client.complete(system="S sen", prompt="P savol")
    assert out == "complete javob"
    assert seen["messages"][0] == {"role": "system", "content": "S sen"}
    assert seen["messages"][1] == {"role": "user", "content": "P savol"}


def test_chat_with_tools_maps_calls():
    """chat_with_tools -> Ollama shakli: [{name, arguments}] + payload tools aylanishi."""
    seen = {}

    def handler(method, url, payload):
        seen.update(payload or {})
        return _openai_resp("", tool_calls=[{
            "id": "1",
            "function": {"name": "write_file", "arguments": '{"path": "a.py"}'},
        }])

    client = _client_with(handler)
    out = client.chat_with_tools(
        [{"role": "user", "content": "yoz"}],
        tools=[{"name": "write_file", "description": "d", "parameters": {}}],
    )
    assert out["tool_calls"] == [{"name": "write_file", "arguments": {"path": "a.py"}}]
    # IGRIS tool formati -> OpenAI formatga aylangan
    assert seen["tools"][0]["function"]["name"] == "write_file"
    assert seen["tool_choice"] == "auto"


def test_chat_with_tools_content_only():
    """Tool'siz javob -> {content} (agent loop to'xtatadi)."""
    client = _client_with(lambda m, u, p: _openai_resp("yakun"))
    out = client.chat_with_tools([{"role": "user", "content": "x"}], tools=[])
    assert out == {"content": "yakun"}


def test_chat_with_tools_error_none():
    """Transport xatosi -> None (agent `if not resp: break`)."""
    client = _client_with(_boom)
    assert client.chat_with_tools([{"role": "user", "content": "x"}], tools=[]) is None


def test_set_turbo_and_chat_fast():
    """set_turbo + chat_fast: tez model + TURBO_MAX_TOKENS chegarasi."""
    seen = {}

    def handler(method, url, payload):
        seen.update(payload or {})
        return _openai_resp("tez")

    client = _client_with(handler)
    client.set_turbo(True, available_models=["openai/gpt-4o-mini",
                                             "anthropic/claude-3-opus"])
    assert client.turbo is True
    assert client.fast_model == "openai/gpt-4o-mini"
    assert client.timeout <= client._base_timeout

    out = client.chat_fast([{"role": "user", "content": "salom"}], system="qisqa")
    assert out == "tez"
    assert seen["max_tokens"] == om.TURBO_MAX_TOKENS
    assert seen["model"] == "openai/gpt-4o-mini"
    assert seen["messages"][0] == {"role": "system", "content": "qisqa"}

    client.set_turbo(False, available_models=[])
    assert client.turbo is False
    assert client.fast_model is None
    assert client.timeout == client._base_timeout


def test_set_turbo_accepts_modelinfo_list():
    """set_turbo ModelInfo listini ham qabul qiladi (server list_models kontrati)."""
    client = OmniRouteClient()
    client.set_turbo(True, available_models=[
        ModelInfo(id="anthropic/claude-3-opus"),
        ModelInfo(id="openai/gpt-4o-mini"),
    ])
    assert client.fast_model == "openai/gpt-4o-mini"


def test_turbo_caps_payload_max_tokens():
    """TURBO yoqilganda max_tokens berilmasa payload chegaralanadi."""
    seen = {}

    def handler(method, url, payload):
        seen.update(payload or {})
        return _openai_resp("ok")

    client = _client_with(handler)
    client.set_turbo(True, available_models=[])
    client.chat([{"role": "user", "content": "salom"}])
    assert seen["max_tokens"] == om.TURBO_MAX_TOKENS


def test_chat_logprobs_geometric_mean():
    """chat_logprobs -> exp(mean(logprob)) (Ollama bilan bir xil o'lchov)."""
    def handler(method, url, payload):
        return _FakeResp({"choices": [{"logprobs": {"content": [
            {"token": "a", "logprob": -0.1},
            {"token": "b", "logprob": -0.3},
        ]}}]})

    client = _client_with(handler)
    val = client.chat_logprobs([{"role": "user", "content": "x"}], model="gpt-4o")
    expected = math.exp((-0.1 - 0.3) / 2)
    assert val is not None and abs(val - expected) < 1e-9


def test_chat_logprobs_error_none():
    """Xato -> None (agent signalni neytral qoldiradi)."""
    client = _client_with(_boom)
    assert client.chat_logprobs([{"role": "user", "content": "x"}]) is None


def test_chat_stream_rich_events():
    """chat_stream_rich -> {type: think|token, content} (Ollama shakli)."""
    lines = [
        'data: ' + json.dumps({"choices": [{"delta": {"reasoning_content": "fikr"}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": "Sal"}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": "om"}}]}),
        "data: [DONE]",
    ]
    client = _client_with(lambda m, u, p: _FakeStreamResp(lines))
    events = list(client.chat_stream_rich([{"role": "user", "content": "salom"}],
                                          think=True))
    assert events == [
        {"type": "think", "content": "fikr"},
        {"type": "token", "content": "Sal"},
        {"type": "token", "content": "om"},
    ]


def test_chat_stream_content_only():
    """chat_stream -> faqat content deltalari (eski chaqiruvchilar)."""
    lines = [
        'data: ' + json.dumps({"choices": [{"delta": {"reasoning_content": "x"}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": "Salom"}}]}),
        "data: [DONE]",
    ]
    client = _client_with(lambda m, u, p: _FakeStreamResp(lines))
    assert "".join(client.chat_stream([{"role": "user", "content": "salom"}])) == "Salom"


def test_stream_error_does_not_raise():
    """Stream xatosi -> generator to'xtaydi, exception ULINMAYDI."""
    client = _client_with(_boom)
    assert list(client.chat_stream_rich([{"role": "user", "content": "x"}])) == []
    assert client.last_error


def test_is_available_ok_and_down():
    """is_available() — qisqa 2s probe; asosiy client yaratilmaydi."""
    class _HttpxOk:
        class Client:
            def __init__(self, base_url=None, headers=None, timeout=None):
                self.timeout = timeout

            def get(self, url):
                return _FakeResp({"data": []}, status=200)

            def close(self):
                pass

    class _HttpxFail:
        class Client:
            def __init__(self, base_url=None, headers=None, timeout=None):
                pass

            def get(self, url):
                raise ConnectionError("refused")

            def close(self):
                pass

    old_httpx, old_ok = om._httpx, om._HTTPX_OK
    try:
        om._httpx, om._HTTPX_OK = _HttpxOk, True
        client = OmniRouteClient()
        assert client.is_available() is True
        assert client.last_error is None
        assert client._client is None  # probe alohida — 60s timeout kutmaydi

        om._httpx = _HttpxFail
        down = OmniRouteClient()
        assert down.is_available() is False
        assert down.last_error
    finally:
        om._httpx, om._HTTPX_OK = old_httpx, old_ok


def test_model_property():
    """model atribut — agent `llm.model` o'qiydi/yozadi."""
    client = OmniRouteClient(default_model="a/b")
    assert client.model == "a/b"
    client.model = "c/d"
    assert client.model == "c/d" and client.default_model == "c/d"
    client.model = ""  # bo'sh qiymat saqlanmaydi
    assert client.model == "c/d"


def test_list_models_still_modelinfo():
    """list_models() ModelInfo qaytaradi (server /api/status kontrati saqlanadi)."""
    client = _client_with(lambda m, u, p: _FakeResp({"data": [
        {"id": "openai/gpt-4o-mini"}, {"id": "anthropic/claude-3-opus"},
    ]}))
    models = client.list_models()
    assert all(isinstance(m, ModelInfo) for m in models)
    assert client.model_ids() == ["openai/gpt-4o-mini", "anthropic/claude-3-opus"]


def test_extract_code_matches_ollama():
    """extract_code — OllamaClient bilan BIR XIL mantiq (kod blokini ajratadi)."""
    text = "Javob:\n```python\nprint(1)\n```\nTugadi"
    from llm.ollama_client import OllamaClient
    assert (OmniRouteClient.extract_code(text)
            == OllamaClient.extract_code(text))
    assert OmniRouteClient.extract_code("") == ""


# ======================================================================
# IgrisAgent + OmniRoute — end-to-end (agent shu client bilan ishlaydi)
# ======================================================================

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
        return None

    def evaluate(self, **kwargs):
        class _Eval:
            def to_dict(self):
                return {"confidence": 0.5}
        return _Eval()


def _omni_agent(content="OmniRoute javobi"):
    from agent.igris_agent import IgrisAgent

    def handler(method, url, payload):
        if method == "STREAM":
            lines = ['data: ' + json.dumps({"choices": [{"delta": {"content": ch}}]})
                     for ch in ("Omni", "Route")]
            lines.append("data: [DONE]")
            return _FakeStreamResp(lines)
        if method == "GET":
            return _FakeResp({"data": [{"id": "openai/gpt-4o-mini"}]})
        return _openai_resp(content)

    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.intelligence = _FakeIntel()
    agent._cag = lambda: None
    agent.llm = _client_with(handler)
    agent.use_llm = True
    agent._llm_checked = True
    agent._llm_available = True
    agent._meaning_cache.clear()
    return agent


def test_agent_chat_with_omniroute():
    """Agent chat() OmniRoute orqali ishlaydi — engine/content/interpretation bor."""
    agent = _omni_agent()
    assert agent.llm_available() is True
    r = agent.chat("salom, menga kelgusi hafta uchun o'quv rejasini tuzib bera olasanmi?",
                   use_memory=False)
    assert r.get("content") == "OmniRoute javobi"
    assert r.get("engine")
    assert r.get("model") == "openai/gpt-4o-mini"
    assert isinstance(r.get("interpretation"), dict)
    assert r.get("completion", {}).get("pipeline")


def test_agent_stream_with_omniroute():
    """Agent chat_stream() OmniRoute SSE orqali token-token oqadi."""
    agent = _omni_agent()
    events = list(agent.chat_stream("salom, menga qanday yordam bera olasan?",
                                    use_memory=False))
    tokens = [e for e in events if e.get("type") == "token"]
    done = [e for e in events if e.get("type") == "done"]
    assert tokens and done
    assert "".join(t["content"] for t in tokens) == "OmniRoute"
    assert isinstance(done[0].get("interpretation"), dict)


def test_agent_set_speed_with_omniroute():
    """set_speed() ModelInfo listini normalizatsiya qiladi (set_turbo buzilmaydi)."""
    agent = _omni_agent()
    agent.set_speed(True)
    status = agent.speed_status()
    assert status["turbo"] is True
    assert status["model"] == "openai/gpt-4o-mini"
    agent.set_speed(False)
    assert agent.speed_status()["turbo"] is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
