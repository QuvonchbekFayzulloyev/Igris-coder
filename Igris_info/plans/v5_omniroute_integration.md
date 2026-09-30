# IGRIS v5.0 — OmniRoute Integration
# Barcha LLM'larni bitta endpoint orqali ishlatish

**Sana:** 2026-09-18
**Yondashuv:** OmniRoute gateway → bitta OpenAI-compatible client

---

## OmniRoute Nima?

OmniRoute — bu AI gateway:
- **352+ provider** (OpenAI, Claude, Gemini, DeepSeek, Qwen, ...)
- **Bitta endpoint:** `http://localhost:20128/v1`
- **Format translation:** OpenAI ↔ Claude ↔ Gemini avtomatik
- **Smart routing:** Load balancing, failover, retry
- **Cost tracking:** Dashboard orqali nazorat

---

## Implementatsiya Rejasi

### 1. OmniRoute Client
**Fayl:** `llm/omniroute_client.py` (yangi)

```python
"""
IGRIS BRAIN — OmniRoute Client
================================
Barcha LLM'larni OmniRoute gateway orqali ishlatish.
OpenAI-compatible format — bitta client, barcha modellar.
"""

import os
import json
import time
from typing import Optional, AsyncIterator
import httpx

class OmniRouteClient:
    """OmniRoute gateway client — OpenAI-compatible."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:20128/v1",
        api_key: Optional[str] = None,
        default_model: str = "openai/gpt-4o",
        timeout: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY", "")
        self.default_model = default_model
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout
        )
        self._async_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout
        )
    
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    # ================================================================
    # Core API (OpenAI-compatible)
    # ================================================================
    
    def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> dict:
        """Chat completion — OpenAI format."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if stream:
            return self._stream_chat(payload)
        
        response = self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return self._parse_response(response.json())
    
    async def achat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> dict:
        """Async chat completion."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        response = await self._async_client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return self._parse_response(response.json())
    
    def _stream_chat(self, payload: dict) -> AsyncIterator[dict]:
        """Streaming chat — SSE format."""
        payload["stream"] = True
        
        with self._client.stream("POST", "/chat/completions", json=payload) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    yield json.loads(data)
    
    # ================================================================
    # Model Management
    # ================================================================
    
    def list_models(self) -> list[dict]:
        """Mavjud modellarni ro'yxati."""
        response = self._client.get("/models")
        response.raise_for_status()
        return response.json().get("data", [])
    
    def get_model(self, model_id: str) -> dict:
        """Model haqida ma'lumot."""
        models = self.list_models()
        for model in models:
            if model.get("id") == model_id:
                return model
        return {}
    
    # ================================================================
    # Embeddings (agar OmniRoute qo'llab-quvvatlasa)
    # ================================================================
    
    def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Text embedding."""
        response = self._client.post("/embeddings", json={
            "model": model,
            "input": text
        })
        response.raise_for_status()
        data = response.json().get("data", [])
        if data:
            return data[0].get("embedding", [])
        return []
    
    # ================================================================
    # Tool Conversion (IGRIS format → OpenAI format)
    # ================================================================
    
    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """IGRIS tool formatini OpenAI formatga aylantirish."""
        converted = []
        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            })
        return converted
    
    def _parse_response(self, data: dict) -> dict:
        """OpenAI response'ni IGRIS formatga aylantirish."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        result = {
            "content": message.get("content", ""),
            "role": message.get("role", "assistant"),
            "finish_reason": choice.get("finish_reason"),
            "model": data.get("model"),
            "usage": data.get("usage", {}),
        }
        
        # Tool calls
        if "tool_calls" in message:
            result["tool_calls"] = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                result["tool_calls"].append({
                    "id": tc.get("id"),
                    "name": func.get("name"),
                    "arguments": json.loads(func.get("arguments", "{}"))
                })
        
        return result
    
    # ================================================================
    # Utility
    # ================================================================
    
    def count_tokens(self, text: str) -> int:
        """Taxminiy token hisobi (tiktoken yoki approx)."""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            return len(enc.encode(text))
        except Exception:
            # Approximation: 1 token ≈ 4 chars
            return len(text) // 4
    
    def health_check(self) -> bool:
        """Gateway ishlashini tekshirish."""
        try:
            response = self._client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Clientlarni yopish."""
        self._client.close()
    
    async def aclose(self):
        """Async clientlarni yopish."""
        await self._async_client.aclose()


# ================================================================
# Singleton
# ================================================================

_client: Optional[OmniRouteClient] = None

def get_client() -> OmniRouteClient:
    """Global OmniRoute client."""
    global _client
    if _client is None:
        _client = OmniRouteClient()
    return _client

def init_client(
    base_url: str = "http://localhost:20128/v1",
    api_key: Optional[str] = None,
    default_model: str = "openai/gpt-4o"
) -> OmniRouteClient:
    """Client'ni ishga tushirish."""
    global _client
    _client = OmniRouteClient(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model
    )
    return _client
```

---

### 2. Model Selector
**Fayl:** `llm/model_selector.py` (yangi)

```python
"""
IGRIS BRAIN — Model Selector
==============================
Task turiga qarab model tanlash.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelProfile:
    """Model profili — task turi uchun optimal model."""
    name: str
    provider: str
    model_id: str  # OmniRoute format: "openai/gpt-4o", "anthropic/claude-3-5-sonnet"
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_tokens: int
    strengths: list[str]  # ["code", "reasoning", "creative", "fast"]

class ModelSelector:
    """Task turiga qarab model tanlaydi."""
    
    # OmniRoute model ID'lari
    PROFILES = {
        # OpenAI Models
        "gpt-4o": ModelProfile(
            name="GPT-4o",
            provider="openai",
            model_id="openai/gpt-4o",
            cost_per_1k_input=0.0025,
            cost_per_1k_output=0.01,
            max_tokens=128000,
            strengths=["code", "reasoning", "creative"]
        ),
        "gpt-4o-mini": ModelProfile(
            name="GPT-4o Mini",
            provider="openai",
            model_id="openai/gpt-4o-mini",
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            max_tokens=128000,
            strengths=["fast", "code", "simple"]
        ),
        
        # Anthropic Models
        "claude-3-5-sonnet": ModelProfile(
            name="Claude 3.5 Sonnet",
            provider="anthropic",
            model_id="anthropic/claude-3-5-sonnet-20241022",
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            max_tokens=200000,
            strengths=["code", "reasoning", "long_context"]
        ),
        "claude-3-opus": ModelProfile(
            name="Claude 3 Opus",
            provider="anthropic",
            model_id="anthropic/claude-3-opus-20240229",
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
            max_tokens=200000,
            strengths=["complex_reasoning", "code", "creative"]
        ),
        
        # Google Models
        "gemini-1.5-pro": ModelProfile(
            name="Gemini 1.5 Pro",
            provider="google",
            model_id="google/gemini-1.5-pro",
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.005,
            max_tokens=2000000,
            strengths=["long_context", "code", "multimodal"]
        ),
        
        # Local Models (Ollama via OmniRoute)
        "qwen3-8b": ModelProfile(
            name="Qwen3 8B (Local)",
            provider="ollama",
            model_id="ollama/qwen3:8b",
            cost_per_1k_input=0,
            cost_per_1k_output=0,
            max_tokens=32768,
            strengths=["fast", "free", "privacy"]
        ),
    }
    
    # Task turi → model tanlash qoidalari
    SELECTION_RULES = {
        # Code generation — eng yaxshi code model
        "code_generation": {
            "preferred": ["gpt-4o", "claude-3-5-sonnet"],
            "fallback": ["gpt-4o-mini", "qwen3-8b"],
            "prefer_local": False
        },
        
        # Code review — Claude yaxshi tahlil qiladi
        "code_review": {
            "preferred": ["claude-3-5-sonnet", "gpt-4o"],
            "fallback": ["gpt-4o-mini"],
            "prefer_local": False
        },
        
        # Quick问答 — tez va arzon
        "quick_qa": {
            "preferred": ["gpt-4o-mini", "qwen3-8b"],
            "fallback": ["gpt-4o"],
            "prefer_local": True
        },
        
        # Complex reasoning — eng kuchli model
        "complex_reasoning": {
            "preferred": ["claude-3-opus", "gpt-4o"],
            "fallback": ["claude-3-5-sonnet"],
            "prefer_local": False
        },
        
        # Simple task — tez va arzon
        "simple_task": {
            "preferred": ["gpt-4o-mini", "qwen3-8b"],
            "fallback": ["gpt-4o-mini"],
            "prefer_local": True
        },
        
        # Long context — katta kontekst kerak
        "long_context": {
            "preferred": ["gemini-1.5-pro", "claude-3-5-sonnet"],
            "fallback": ["gpt-4o"],
            "prefer_local": False
        },
        
        # Refactoring — murakkab o'zgarishlar
        "refactoring": {
            "preferred": ["claude-3-5-sonnet", "gpt-4o"],
            "fallback": ["gpt-4o-mini"],
            "prefer_local": False
        },
    }
    
    def __init__(self, available_models: Optional[list[str]] = None):
        self.available = available_models or list(self.PROFILES.keys())
    
    def select(
        self,
        task_type: str,
        prefer_local: bool = False,
        max_cost: Optional[float] = None
    ) -> ModelProfile:
        """Task uchun eng mos modelni tanlash."""
        rules = self.SELECTION_RULES.get(task_type, self.SELECTION_RULES["simple_task"])
        
        # Local model afzallik berilgan bo'lsa
        if prefer_local or rules.get("prefer_local"):
            for model_name in rules["preferred"]:
                profile = self.PROFILES.get(model_name)
                if profile and model_name in self.available and profile.provider == "ollama":
                    return profile
        
        # Preferred modellar
        for model_name in rules["preferred"]:
            profile = self.PROFILES.get(model_name)
            if profile and model_name in self.available:
                if max_cost is None or profile.cost_per_1k_input <= max_cost:
                    return profile
        
        # Fallback modellar
        for model_name in rules["fallback"]:
            profile = self.PROFILES.get(model_name)
            if profile and model_name in self.available:
                return profile
        
        # Default
        return self.PROFILES["gpt-4o-mini"]
    
    def classify_task(self, message: str) -> str:
        """Xabardan task turini aniqlash."""
        message_lower = message.lower()
        
        # Code generation
        if any(word in message_lower for word in ["yoz", "create", "write", "generate", "qil", "build"]):
            if any(word in message_lower for word in ["code", "function", "class", "file", "script"]):
                return "code_generation"
        
        # Code review
        if any(word in message_lower for word in ["review", "tekshir", "check", "analyze", "sharh"]):
            return "code_review"
        
        # Refactoring
        if any(word in message_lower for word in ["refactor", "o'zgartir", "tuzat", "optimize", "yaxshilash"]):
            return "refactoring"
        
        # Complex reasoning
        if any(word in message_lower for word in ["nima", "qanday", "nega", "tushuntir", "explain", "why", "how"]):
            if len(message.split()) > 20:
                return "complex_reasoning"
        
        # Default
        return "simple_task"
    
    def estimate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Taxminiy xarajatni hisoblash."""
        profile = self.PROFILES.get(model_name)
        if not profile:
            return 0.0
        
        return (input_tokens * profile.cost_per_1k_input + 
                output_tokens * profile.cost_per_1k_output) / 1000
```

---

### 3. Config Integration
**Fayl:** `config/llm_config.py` (yangilanadi)

```python
"""
IGRIS BRAIN — LLM Configuration
=================================
OmniRoute + Ollama konfiguratsiya.
"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMConfig:
    """LLM konfiguratsiyasi."""
    # OmniRoute
    omniroute_enabled: bool = True
    omniroute_url: str = "http://localhost:20128/v1"
    omniroute_api_key: Optional[str] = None
    
    # Ollama (fallback)
    ollama_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    
    # Default model
    default_model: str = "openai/gpt-4o-mini"
    
    # Limits
    max_tokens: int = 4096
    temperature: float = 0.7
    
    # Cost limits
    daily_cost_limit: float = 10.0  # USD
    monthly_cost_limit: float = 100.0  # USD

def load_llm_config() -> LLMConfig:
    """Environment variables dan config yuklash."""
    return LLMConfig(
        omniroute_enabled=os.environ.get("OMNIROUTE_ENABLED", "true").lower() == "true",
        omniroute_url=os.environ.get("OMNIROUTE_URL", "http://localhost:20128/v1"),
        omniroute_api_key=os.environ.get("OMNIROUTE_API_KEY"),
        ollama_enabled=os.environ.get("OLLAMA_ENABLED", "true").lower() == "true",
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        default_model=os.environ.get("DEFAULT_MODEL", "openai/gpt-4o-mini"),
        max_tokens=int(os.environ.get("MAX_TOKENS", "4096")),
        temperature=float(os.environ.get("TEMPERATURE", "0.7")),
        daily_cost_limit=float(os.environ.get("DAILY_COST_LIMIT", "10.0")),
        monthly_cost_limit=float(os.environ.get("MONTHLY_COST_LIMIT", "100.0")),
    )
```

---

### 4. IgrisAgent Integration
**Fayl:** `agent/igris_agent.py` (yangilanadi)

```python
# ... mavjud kod ...

class IgrisAgent:
    def __init__(self, ...):
        # ... mavjud init ...
        
        # LLM client tanlash
        self.llm = self._init_llm()
    
    def _init_llm(self):
        """LLM client'ni ishga tushirish."""
        from config.llm_config import load_llm_config
        from llm.omniroute_client import OmniRouteClient, init_client
        from llm.ollama_client import OllamaClient
        
        config = load_llm_config()
        
        # OmniRoute mavjud bo'lsa — ishlatish
        if config.omniroute_enabled:
            client = init_client(
                base_url=config.omniroute_url,
                api_key=config.omniroute_api_key,
                default_model=config.default_model
            )
            
            # Health check
            if client.health_check():
                return client
            else:
                print("Warning: OmniRoute not available, falling back to Ollama")
        
        # Fallback: Ollama
        if config.ollama_enabled:
            return OllamaClient(base_url=config.ollama_url)
        
        raise RuntimeError("No LLM available")
    
    def chat(self, message: str, ...) -> dict:
        """Chat — OmniRoute yoki Ollama."""
        # Model selector
        from llm.model_selector import ModelSelector
        selector = ModelSelector()
        task_type = selector.classify_task(message)
        model = selector.select(task_type)
        
        # Chat
        if hasattr(self.llm, 'chat'):
            # OmniRoute client
            return self.llm.chat(
                messages=[...],
                model=model.model_id,
                tools=self.tools
            )
        else:
            # Ollama client (eski format)
            return self.llm.chat(...)
```

---

### 5. Environment Variables
**Fayl:** `.env.example` (yangi)

```bash
# OmniRoute Configuration
OMNIROUTE_ENABLED=true
OMNIROUTE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=oma_live_xxx  # Optional: dashboard'dan olish

# Ollama Configuration (fallback)
OLLAMA_ENABLED=true
OLLAMA_URL=http://localhost:11434

# Default Model
DEFAULT_MODEL=openai/gpt-4o-mini

# Limits
MAX_TOKENS=4096
TEMPERATURE=0.7

# Cost Limits
DAILY_COST_LIMIT=10.0
MONTHLY_COST_LIMIT=100.0
```

---

### 6. Tests
**Fayl:** `tests/test_omniroute.py` (yangi)

```python
"""
IGRIS — OmniRoute Integration Tests
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

# Mock httpx
import sys
sys.modules['httpx'] = MagicMock()

from llm.omniroute_client import OmniRouteClient
from llm.model_selector import ModelSelector, ModelProfile


class TestOmniRouteClient:
    """OmniRoute client testlari."""
    
    def test_init_default(self):
        """Default values bilan ishga tushirish."""
        client = OmniRouteClient()
        assert client.base_url == "http://localhost:20128/v1"
        assert client.default_model == "openai/gpt-4o"
    
    def test_init_custom(self):
        """Custom values bilan ishga tushirish."""
        client = OmniRouteClient(
            base_url="http://custom:9999/v1",
            api_key="test-key",
            default_model="anthropic/claude-3-5-sonnet"
        )
        assert client.base_url == "http://custom:9999/v1"
        assert client.api_key == "test-key"
    
    def test_convert_tools(self):
        """IGRIS tool formatini OpenAI formatga aylantirish."""
        client = OmniRouteClient()
        
        irgris_tools = [
            {
                "name": "read_file",
                "description": "Faylni o'qish",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    }
                }
            }
        ]
        
        converted = client._convert_tools(irgris_tools)
        
        assert len(converted) == 1
        assert converted[0]["type"] == "function"
        assert converted[0]["function"]["name"] == "read_file"
    
    def test_parse_response(self):
        """OpenAI response'ni parse qilish."""
        client = OmniRouteClient()
        
        openai_response = {
            "choices": [{
                "message": {
                    "content": "Hello!",
                    "role": "assistant"
                },
                "finish_reason": "stop"
            }],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
        
        result = client._parse_response(openai_response)
        
        assert result["content"] == "Hello!"
        assert result["role"] == "assistant"
        assert result["model"] == "gpt-4o"
    
    def test_parse_response_with_tools(self):
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
                            "arguments": '{"path": "test.py"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }],
            "model": "gpt-4o"
        }
        
        result = client._parse_response(openai_response)
        
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "read_file"
        assert result["tool_calls"][0]["arguments"]["path"] == "test.py"


class TestModelSelector:
    """Model selector testlari."""
    
    def test_select_code_generation(self):
        """Code generation uchun model tanlash."""
        selector = ModelSelector()
        model = selector.select("code_generation")
        
        assert model.provider in ["openai", "anthropic"]
        assert "code" in model.strengths
    
    def test_select_quick_qa(self):
        """Quick Q&A uchun model tanlash."""
        selector = ModelSelector()
        model = selector.select("quick_qa")
        
        # Tez va arzon model
        assert model.cost_per_1k_input <= 0.001
    
    def test_select_with_local_preference(self):
        """Local model afzallik bilan."""
        selector = ModelSelector(available_models=["qwen3-8b", "gpt-4o"])
        model = selector.select("simple_task", prefer_local=True)
        
        assert model.provider == "ollama"
    
    def test_classify_task(self):
        """Task turini aniqlash."""
        selector = ModelSelector()
        
        assert selector.classify_task("Python function yoz") == "code_generation"
        assert selector.classify_task("Kodni tekshir") == "code_review"
        assert selector.classify_task("Nima uchun bu xatolik?") == "complex_reasoning"
    
    def test_estimate_cost(self):
        """Xarajatni hisoblash."""
        selector = ModelSelector()
        cost = selector.estimate_cost("gpt-4o", 1000, 500)
        
        # GPT-4o: $2.50/1M input, $10/1M output
        expected = (1000 * 0.0025 + 500 * 0.01) / 1000
        assert abs(cost - expected) < 0.001
```

---

## OmniRoute Setup Qo'llanmasi

### 1. OmniRoute'ni ishga tushirish

**Docker bilan:**
```bash
docker run -d --name omniroute \
  --restart unless-stopped \
  -p 20128:20128 \
  -p 20129:20129 \
  diegosouzapw/omniroute:latest
```

**Docker Compose bilan:**
```yaml
version: '3.8'
services:
  omniroute:
    image: diegosouzapw/omniroute:latest
    container_name: omniroute
    restart: unless-stopped
    ports:
      - "20128:20128"
      - "20129:20129"
    volumes:
      - omniroute-data:/app/data
    environment:
      - OMNIROUTE_PASSWORD=changeme

volumes:
  omniroute-data:
```

### 2. Dashboard'dan API Key olish

1. Browser'da oching: `http://localhost:20129`
2. Default parol: `CHANGEME`
3. Dashboard → Endpoint → API Key ni nusxalang

### 3. Provider qo'shish (Dashboard orqali)

Dashboard → Providers → Add Provider:
- OpenAI uchun: OpenAI API key kiriting
- Anthropic uchun: Anthropic API key kiriting
- Gemini uchun: Google API key kiriting

### 4. IGRIS konfiguratsiyasi

`.env` faylga qo'shing:
```bash
OMNIROUTE_ENABLED=true
OMNIROUTE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=oma_live_xxx
DEFAULT_MODEL=openai/gpt-4o-mini
```

---

## Xulosa

OmniRoute integratsiyasi orqali IGRIS:
- ✅ 352+ LLM modelga kirish
- ✅ Bitta client, barcha provider
- ✅ Avtomatik format translation
- ✅ Smart routing va failover
- ✅ Cost tracking va nazorat
- ✅ Local (Ollama) + Cloud modellar

**Keyingi qadam:** `llm/omniroute_client.py` yaratish va testlash.
