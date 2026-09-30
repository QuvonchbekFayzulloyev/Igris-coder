"""
IGRIS BRAIN — OmniRoute Client
================================
Barcha LLM'larni OmniRoute gateway orqali ishlatish.
OpenAI-compatible format — bitta client, barcha modellar.

Setup:
  docker run -d -p 20128:20128 -p 20129:20129 diegosouzapw/omniroute:latest
  Dashboard: http://localhost:20129

Usage:
  from llm.omniroute_client import get_client, init_client
  client = init_client(base_url="http://localhost:20128/v1")
  text = client.chat(messages=[{"role": "user", "content": "Hello"}])  # -> str | None
  full = client.chat_full(messages=[...])                                # -> ChatResponse

AGENT KONTRATI (OllamaClient bilan bir xil):
  complete / chat / chat_fast / chat_with_tools / chat_stream / chat_stream_rich /
  chat_logprobs / extract_code / is_available / list_models / set_turbo + 
  model/turbo/think/fast_model atributlari — shu metodlar orqali IgrisAgent
  OmniRoute'ni to'liq ishlatadi. Xatolar exception ULAMAYDI: None + last_error
  (agent graceful degradation qiladi). `chat()` yakuniy matn qaytaradi,
  to'liq struktura (tool_calls/usage) kerak bo'lsa `chat_full()` ishlating.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

try:
    import httpx as _httpx
    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False


# ------------------------------------------------------------------ #
# Data Classes
# ------------------------------------------------------------------ #

@dataclass
class ChatMessage:
    """Chat xabari."""
    role: str  # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        return d


@dataclass
class ChatResponse:
    """Chat completion natijasi."""
    content: str = ""
    role: str = "assistant"
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    usage: dict = field(default_factory=dict)
    raw: Optional[dict] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class ModelInfo:
    """Model ma'lumotlari."""
    id: str
    owned_by: str = ""
    created: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "ModelInfo":
        return cls(
            id=data.get("id", ""),
            owned_by=data.get("owned_by", ""),
            created=data.get("created", 0),
        )


# TURBO rejim chegaralari (OllamaClient ma'nosi bilan mos)
TURBO_MAX_TOKENS = 1024
TURBO_TIMEOUT = 120.0


def _pick_fast_model(available: list) -> Optional[str]:
    """TURBO rejim uchun eng TEZ modelni tanlaydi (mini/flash/haiku... belgilari).

    available: str yoki ModelInfo (yoki boshqa obyekt `.id` bilan) listi.
    Tez belgi topilmasa None — agent `fast_model or model` bilan ishlaydi.
    """
    ids = [(m.id if hasattr(m, "id") else str(m)) for m in (available or [])]
    ids = [i for i in ids if i]
    if not ids:
        return None
    fast_marks = ("mini", "flash", "haiku", "nano", "lite", "small",
                  "1.5b", "3b", "4b")
    for m in ids:
        low = m.lower()
        if any(k in low for k in fast_marks):
            return m
    return None


# ------------------------------------------------------------------ #
# OmniRoute Client
# ------------------------------------------------------------------ #

class OmniRouteClient:
    """OmniRoute gateway client — OpenAI-compatible.

    Barcha LLM provider'larni (OpenAI, Claude, Gemini, DeepSeek, Qwen...)
    bitta endpoint orqali ishlatadi.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:20128/v1",
        api_key: Optional[str] = None,
        default_model: str = "openai/gpt-4o-mini",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY", "")
        self.default_model = default_model
        self.timeout = timeout
        self._client: Optional[Any] = None
        self._async_client: Optional[Any] = None
        self._last_error: Optional[str] = None
        self._models_cache: Optional[list[ModelInfo]] = None
        self._models_cache_ts: float = 0
        # --- Agent kontrati (OllamaClient bilan mos atributlar) ---
        self.think = True          # reasoning rejimi (gateway e'tiborsiz qoldirishi mumkin)
        self.turbo = False         # TURBO tez rejim
        self.fast_model: Optional[str] = None
        self.logprobs = False      # ixtiyoriy logprob re-so'ruvi (self-eval signali)
        self._base_timeout = timeout

    # ------------------------------------------------------------------ #
    # Internal — lazy client init
    # ------------------------------------------------------------------ #

    def _get_client(self):
        if self._client is None:
            if not _HTTPX_OK:
                raise RuntimeError("httpx not installed: pip install httpx")
            self._client = _httpx.Client(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=self.timeout,
            )
        return self._client

    def _get_async_client(self):
        if self._async_client is None:
            if not _HTTPX_OK:
                raise RuntimeError("httpx not installed: pip install httpx")
            self._async_client = _httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=self.timeout,
            )
        return self._async_client

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------ #
    # Core API — Chat Completion
    # ------------------------------------------------------------------ #

    def chat_full(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """Chat completion — TO'LIQ response (OpenAI format; xatolar raise).

        Tool_calls/usage/model kabi to'liq struktura kerak bo'lgan chaqiruvchilar
        uchun. Agent faqat matn oladi — u `chat()` ishlatadi (xatosiz).
        """
        payload = self._build_payload(
            messages, model, tools, temperature, max_tokens, stream
        )

        if stream:
            return self._stream_chat(payload)

        client = self._get_client()
        try:
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            self._last_error = str(e)
            raise

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tokens: Optional[int] = None,
        **kw,
    ) -> Optional[str]:
        """Chat completion — AGENT kontrati: yakuniy matn (str | None).

        OllamaClient.chat() bilan bir xil xulq: transport xatosida exception
        ULINMAYDI — None qaytadi va `last_error` yoziladi (agent graceful
        degradation qiladi). Bo'sh javob — bo'sh str (agent o'zi boshqaradi).
        """
        try:
            resp = self.chat_full(
                messages,
                model=model or kw.get("model"),
                tools=tools,
                temperature=0.7 if temperature is None else float(temperature),
                max_tokens=max_tokens,
                stream=stream,
            )
        except Exception as e:
            self._last_error = str(e)
            return None
        if resp is None:
            return None
        return resp.content or ""

    async def achat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """Async chat completion."""
        payload = self._build_payload(
            messages, model, tools, temperature, max_tokens, stream=False
        )

        client = self._get_async_client()
        try:
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            self._last_error = str(e)
            raise

    def _build_payload(
        self,
        messages: list[dict],
        model: Optional[str],
        tools: Optional[list[dict]],
        temperature: float,
        max_tokens: Optional[int],
        stream: bool,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"
        if max_tokens:
            payload["max_tokens"] = max_tokens
        elif self.turbo:
            # TURBO: qisqa javob (OllamaClient TURBO_MAX_TOKENS ma'nosi bilan mos)
            payload["max_tokens"] = TURBO_MAX_TOKENS
        if stream:
            payload["stream"] = True
        return payload

    def _stream_events(self, payload: dict):
        """SSE oqimini agent hodisalariga aylantiradi (hech qachon raise qilmaydi).

          {"type": "think", "content": ...}  — reasoning deltasi (gateway qaytarsa:
                                               reasoning_content / reasoning)
          {"type": "token", "content": ...}  — yakuniy javob deltasi

        Transport xatoligida generator to'xtaydi va `last_error` yoziladi
        (chaqiruvchi qisman yig'ilgan matnni saqlab qoladi — Ollama bilan bir xil).
        """
        client = self._get_client()
        try:
            with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}) or {}
                    except (json.JSONDecodeError, TypeError):
                        continue
                    think_delta = delta.get("reasoning_content") or delta.get("reasoning") or ""
                    if think_delta:
                        yield {"type": "think", "content": think_delta}
                    content = delta.get("content")
                    if content:
                        yield {"type": "token", "content": content}
        except Exception as e:
            self._last_error = str(e)

    def _stream_chat(self, payload: dict) -> ChatResponse:
        """Streaming chat — SSE format; to'plangan matn bilan ChatResponse."""
        full_content = ""
        for ev in self._stream_events(payload):
            if ev.get("type") == "token":
                full_content += ev.get("content") or ""
        return ChatResponse(content=full_content, role="assistant", finish_reason="stop")

    # ------------------------------------------------------------------ #
    # AGENT KONTRATI — OllamaClient bilan bir xil shakl/ma'no
    # ------------------------------------------------------------------ #

    def chat_stream_rich(self, messages: list[dict], temperature: Optional[float] = None,
                         think: Optional[bool] = None, model: Optional[str] = None,
                         **kw):
        """Token/think hodisalari oqimi — OllamaClient.chat_stream_rich BILAN BIR XIL.

        Har bir yield dict (SSE'ga bevosita uzatiladi):

          {"type": "think", "content": "<fikrlash deltasi>"}  — gateway reasoning qaytarsa
          {"type": "token", "content": "<javob deltasi>"}     — yakuniy javob

        `think` OpenAI-format'da bevosita yuborilmaydi (gateway hal qiladi) —
        faqat xohlovchi signal; reasoning qaytmasa faqat "token" chiqadi
        (degradatsiya xavfsiz).
        """
        payload = self._build_payload(
            messages, model, None,
            0.7 if temperature is None else float(temperature),
            None, stream=True,
        )
        for ev in self._stream_events(payload):
            yield ev

    def chat_stream(self, messages: list[dict], temperature: Optional[float] = None,
                    think: Optional[bool] = None, model: Optional[str] = None,
                    **kw):
        """Faqat CONTENT deltalari (eski chaqiruvchilar uchun — bir xil SSE)."""
        for ev in self.chat_stream_rich(
            messages, temperature=temperature, think=think, model=model,
        ):
            if ev.get("type") == "token" and ev.get("content"):
                yield ev["content"]

    def chat_fast(self, messages: list[dict], system: Optional[str] = None,
                  **kw) -> Optional[str]:
        """TURBO: oddiy savollarga qisqa javob (tez model + qisqa token).

        `fast_model` topilgan bo'lsa shu modelga murojaat qilinadi; aks holda
        gateway default modeli TURBO chegaralari bilan ishlatiladi (Ollama bilan
        bir xil xulq: None — transport xatosi, str — javob).
        """
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        return self.chat(msgs, model=self.fast_model or None,
                         max_tokens=TURBO_MAX_TOKENS)

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: Optional[str] = None,
        **kw,
    ) -> Optional[dict]:
        """Tool-calling chat — OllamaClient.chat_with_tools BILAN BIR XIL shakl.

        Args:
            messages: [{role, content}, ...] (system + history + tool natijalari)
            tools: tool JSON-schemalari (ToolRegistry.schemas())

        Returns:
            {"tool_calls": [{"name": str, "arguments": dict}, ...]}  — model tool chaqirmoqchi
            {"content": str}                                          — yakuniy javob (tool'siz)
            None                                                      — transport xatosi
        """
        try:
            resp = self.chat_full(messages, model=model, tools=tools or None)
        except Exception as e:
            self._last_error = str(e)
            return None
        if resp is None:
            return None
        out: dict = {"content": resp.content or ""}
        if resp.tool_calls:
            out["tool_calls"] = [
                {"name": str(tc.get("name") or ""),
                 "arguments": tc.get("arguments") or {}}
                for tc in resp.tool_calls
            ]
        # Reasoning (gateway qaytarsa) — alohida maydonda, content emas
        try:
            msg = ((resp.raw or {}).get("choices") or [{}])[0].get("message") or {}
            thinking = msg.get("reasoning_content") or msg.get("reasoning") or ""
        except Exception:
            thinking = ""
        if thinking:
            out["thinking"] = thinking
        return out

    def complete(self, prompt: str, system: Optional[str] = None,
                 temperature: Optional[float] = None, **kw) -> Optional[str]:
        """One-shot completion — OllamaClient.complete bilan BIR XIL shakl.

        Agent barcha deterministik/ixtiyoriy chaqiruvlari shu orqali o'tadi
        (requirement extractor, meaning assist, compliance, creative variants...).
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature,
                         max_tokens=kw.get("max_tokens"))

    def chat_logprobs(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 128,
        **kw,
    ) -> Optional[float]:
        """OpenAI `logprobs` orqali o'rtacha token ehtimoli (0..1).

        OllamaClient.chat_logprobs bilan BIR XIL shakl/ma'no: greedy
        (temperature=0) qayta generatsiya + exp(mean(logprob)) — 1.0 = model
        o'z javobiga juda ishonchli. Endpoint/logprobs qaytarmasa None
        (agent signalni neytral qoldiradi — buzilmaydi).
        """
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "logprobs": True,
            "top_logprobs": 1,
        }
        try:
            client = self._get_client()
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self._last_error = str(e)
            return None
        try:
            lps = ((data.get("choices") or [{}])[0].get("logprobs") or {}).get("content") or []
            return self._avg_token_probability(lps)
        except Exception:
            return None

    @staticmethod
    def _avg_token_probability(content_items: list) -> Optional[float]:
        """OpenAI logprobs.content ro'yxatidan geometrik o'rtacha ehtimol.

        Har bir element `{"token": str, "logprob": float, ...}` —
        exp(mean(logprob)) per-token ehtimollarning geometrik o'rtachasi.
        Bo'sh/noto'g'ri ro'yxat -> None.
        """
        logps = []
        for item in content_items or []:
            if isinstance(item, dict):
                lp = item.get("logprob")
                if isinstance(lp, (int, float)):
                    logps.append(float(lp))
        if not logps:
            return None
        return max(0.0, min(1.0, math.exp(sum(logps) / len(logps))))

    # ------------------------------------------------------------------ #
    # Model Management
    # ------------------------------------------------------------------ #

    def list_models(self, use_cache: bool = True) -> list[ModelInfo]:
        """Mavjud modellarni ro'yxati (5 daqiqa cache)."""
        now = time.time()
        if use_cache and self._models_cache and (now - self._models_cache_ts < 300):
            return self._models_cache

        client = self._get_client()
        try:
            response = client.get("/models")
            response.raise_for_status()
            data = response.json().get("data", [])
            self._models_cache = [ModelInfo.from_dict(m) for m in data]
            self._models_cache_ts = now
            return self._models_cache
        except Exception:
            return self._models_cache or []

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Model haqida ma'lumot."""
        for m in self.list_models():
            if m.id == model_id:
                return m
        return None

    def model_ids(self) -> list[str]:
        """Faqat model ID'lar ro'yxati."""
        return [m.id for m in self.list_models()]

    # ------------------------------------------------------------------ #
    # Embeddings
    # ------------------------------------------------------------------ #

    def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Text embedding."""
        client = self._get_client()
        try:
            response = client.post("/embeddings", json={
                "model": model,
                "input": text,
            })
            response.raise_for_status()
            data = response.json().get("data", [])
            if data:
                return data[0].get("embedding", [])
            return []
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Tool Conversion (IGRIS → OpenAI)
    # ------------------------------------------------------------------ #

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """IGRIS tool formatini OpenAI formatga aylantirish."""
        converted = []
        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", tool.get("input_schema", {})),
                },
            })
        return converted

    # ------------------------------------------------------------------ #
    # Response Parsing
    # ------------------------------------------------------------------ #

    def _parse_response(self, data: dict) -> ChatResponse:
        """OpenAI response'ni ChatResponse ga aylantirish."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": args,
                })

        return ChatResponse(
            content=message.get("content", "") or "",
            role=message.get("role", "assistant"),
            finish_reason=choice.get("finish_reason"),
            model=data.get("model"),
            tool_calls=tool_calls if tool_calls else None,
            usage=data.get("usage", {}),
            raw=data,
        )

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def count_tokens(self, text: str) -> int:
        """Taxminiy token hisobi."""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def health_check(self) -> bool:
        """Gateway ishlashini tekshirish."""
        try:
            client = self._get_client()
            response = client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    def is_available(self) -> bool:
        """Gateway mavjudmi? — AGENT kontrati (OllamaClient bilan bir xil).

        Alohida qisqa (2s) probe: agent birinchi tekshiruvda 60s timeout bilan
        kutmaydi. Muvaffaqiyatda `last_error` tozalanadi, xatoda yoziladi.
        """
        if not _HTTPX_OK:
            self._last_error = "httpx not installed: pip install httpx"
            return False
        probe = None
        try:
            probe = _httpx.Client(base_url=self.base_url,
                                  headers=self._headers(), timeout=2.0)
            response = probe.get("/models")
            ok = response.status_code == 200
            self._last_error = None if ok else f"OmniRoute gateway HTTP {response.status_code}"
            return ok
        except Exception as e:
            self._last_error = str(e)
            return False
        finally:
            if probe is not None:
                try:
                    probe.close()
                except Exception:
                    pass

    # ------------------------------------------------------------ #
    # AGENT atributlari — OllamaClient bilan mos
    # ------------------------------------------------------------ #

    @property
    def model(self) -> str:
        """Joriy model nomi (agent `llm.model` ni o'qiydi/yozadi)."""
        return self.default_model

    @model.setter
    def model(self, value: str):
        if value:
            self.default_model = str(value)

    def set_turbo(self, enabled: bool, available_models: Optional[list] = None):
        """TURBO tez rejimni yoqadi/o'chiradi (agent `set_speed` chaqiradi).

        available_models: str yoki ModelInfo listi — ikkalasi ham qabul
        qilinadi (server `list_models()` ModelInfo qaytaradi).
        """
        self.turbo = bool(enabled)
        if enabled:
            models = self.model_ids() if available_models is None else available_models
            self.fast_model = _pick_fast_model(models)
            self.timeout = min(self._base_timeout, TURBO_TIMEOUT)
        else:
            self.fast_model = None
            self.timeout = self._base_timeout

    @staticmethod
    def extract_code(text: Optional[str]) -> str:
        """LLM chiqishidan kod blokini ajratish (OllamaClient bilan BIR XIL mantiq)."""
        try:
            from llm.ollama_client import OllamaClient
            return OllamaClient.extract_code(text)
        except Exception:
            return (text or "").strip()

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def close(self):
        """Clientlarni yopish."""
        if self._client:
            self._client.close()
            self._client = None

    async def aclose(self):
        """Async clientlarni yopish."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None


# ------------------------------------------------------------------ #
# Singleton
# ------------------------------------------------------------------ #

_client: Optional[OmniRouteClient] = None


def get_client() -> Optional[OmniRouteClient]:
    """Global OmniRoute client (init qilinmagan bo'lsa None)."""
    return _client


def init_client(
    base_url: str = "http://localhost:20128/v1",
    api_key: Optional[str] = None,
    default_model: str = "openai/gpt-4o-mini",
) -> OmniRouteClient:
    """Client'ni ishga tushirish va global sifatida saqlash."""
    global _client
    _client = OmniRouteClient(
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
    )
    return _client


def is_available() -> bool:
    """OmniRoute gateway mavjud va ishlayaptimi?"""
    client = get_client()
    if client is None:
        return False
    return client.health_check()


__all__ = [
    "OmniRouteClient",
    "ChatMessage",
    "ChatResponse",
    "ModelInfo",
    "get_client",
    "init_client",
    "is_available",
]
