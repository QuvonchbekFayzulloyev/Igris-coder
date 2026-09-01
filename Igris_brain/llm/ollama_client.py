"""
IGRIS BRAIN — Ollama Client
===========================
Hybrid fallback: when the deterministic brick resolver is below confidence
threshold, delegate to a local LLM (qwen3:8b etc.) via Ollama HTTP API.

The GUI (Igris_Interface) already assumes an Ollama runtime; this client
talks to the same endpoint (default http://localhost:11434).

Aloqa ishonchliligi:
  - `keep_alive` — model RAM'da qoladi (har so'rovda sovuq yuklanish yo'q).
  - retry/backoff — vaqtinchalik xatolarda (Ollama band, qayta yuklanmoqda)
    so'rov avtomatik qayta uriniladi.
  - `last_error` — oxirgi xato sababi saqlanadi; server /api/status orqali
    UI'ga ko'rsatadi ("model topilmadi" / "Ollama ishlamayapti" kabi).
  - `pick_best_model` — so'ralgan model o'rnatilmagan bo'lsa, Ollama'da
    mavjud eng sifatli modelni tanlaydi (qwen3:8b > qwen2.5-coder:7b > ...).
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.request
import urllib.error
from typing import Optional

DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Sifat bo'yicha afzal modellar (so'ralgan model yo'q bo'lganda tanlash tartibi).
PREFERRED_MODELS = [
    "qwen3:8b",
    "qwen2.5-coder:7b",
    "qwen3:4b",
    "qwen2.5:7b",
    "qwen3:1.7b",
    "qwen2.5-coder:1.5b",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "qwen3:0.6b",
]

# TURBO rejim — universal tezlashtirish (har qanday modelga birdek qo'llanadi).
# Tez rejimda oddiy chat savollari shu ro'yxatdan eng tez modelga yo'naltiriladi
# (katta model faqat murakkab/tool vazifalar uchun qoladi). Bu 'har bir model
# uchun alohida sozlash' emas — BIR umumiy kalit barcha modellarni tezlashtiradi.
FAST_MODELS = [
    "qwen2.5:1.5b",
    "qwen2.5-coder:1.5b",
    "qwen3:1.7b",
    "llama3.2:1b",
    "qwen3:0.6b",
    "tinyllama",
    "phi3:mini",
]

# TURBO rejimdagi token/kontekst chegaralari — model RAM'da qoladi (keep_alive),
# lekin javob qisqa va tez keladi. Katta kontekst -> sekin fikrlash.
TURBO_MAX_TOKENS = 1024
TURBO_NUM_CTX = 8192
TURBO_TIMEOUT = 120.0


def pick_best_model(available: list[str], preferred: Optional[list[str]] = None) -> Optional[str]:
    """Ollama'da mavjud modellardan eng sifatlisini tanlaydi.

    Tartib: PREFERRED_MODELS ro'yxati, keyin istalgan qwen3, keyin
    qwen2.5-coder, keyin birinchi mavjud model. Ro'yxat bo'sh bo'lsa None.
    """
    avail = [m for m in (available or []) if m]
    if not avail:
        return None
    for m in (preferred or PREFERRED_MODELS):
        if m in avail:
            return m
    for m in avail:
        if m.startswith("qwen3"):
            return m
    for m in avail:
        if m.startswith("qwen2.5-coder"):
            return m
    for m in avail:
        if "qwen" in m.lower():
            return m
    return avail[0]


def pick_fast_model(available: list[str]) -> Optional[str]:
    """TURBO rejim uchun eng TEZ modelni tanlaydi (eng kichik parametrli).

    Tartib: FAST_MODELS ro'yxatidagi birinchi mavjud; topilmasa — eng kichik
    parametrli model (nomidagi 'X.XXb' qiymatiga qarab). None — model yo'q.
    """
    avail = [m for m in (available or []) if m]
    if not avail:
        return None
    for m in FAST_MODELS:
        if m in avail:
            return m
    # nomidan parametr o'lchamini ajratamiz: 'qwen2.5-coder:1.5b' -> 1.5
    def _size(name: str) -> float:
        m = re.search(r"(\d+(?:\.\d+)?)b", name.lower())
        return float(m.group(1)) if m else float("inf")
    return min(avail, key=_size)


class OllamaClient:
    """Minimal client for the Ollama /api/chat endpoint."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout: float = 300.0,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        # num_ctx 16K — qwen3:8b kabi lokal modellar 32K kontekstda juda sekin
        # fikrlaydi (javob 2-4x kechikadi). 16K kod/chat uchun yetarli, sezilarli
        # tezroq. Katta kontekst kerak bo'lsa server.py turbo sozlamalari o'zgaradi.
        num_ctx: int = 16384,
        think: bool = True,
        keep_alive: str = "30m",
        retries: int = 2,
        # Ixtiyoriy logprob re-so'ruvi (self-eval ishonch signali): native
        # /api/chat logprob qaytarmaydi, shuning uchun OpenAI-mos
        # /v1/chat/completions orqali ALOHIDA (2-so'rov) o'lchov yuboriladi.
        # 2x inference narxi bor — default O'CHIQ (server --logprobs bilan
        # yoqiladi).
        logprobs: bool = False,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        # qwen3 kabi reasoning modellar uchun thinking rejimi. Qisqa/fikr
        # talab qilmaydigan modellarda Ollama buni shunchaki e'tiborsiz
        # qoldiradi — xavfsiz.
        self.think = think
        # Modelni RAM'da ushlab turish — har so'rovda qayta yuklanmasligi
        # uchun (sovuq start 20-60s kutyurar edi, "aloqa yomon" hissi shundan).
        # '0' -> so'rovdan keyin tushiradi, '-1' -> doim qoldiradi.
        self.keep_alive = keep_alive
        # Vaqtinchalik xatolarda qayta urinishlar soni (Ollama band bo'lsa).
        self.retries = retries
        # OpenAI-mos logprob re-so'ruvi yoqilganmi (self-eval signal; 2x narx).
        self.logprobs = bool(logprobs)
        # Oxirgi xato sababi — UI'da ko'rsatish uchun (model topilmadi / offline).
        self.last_error: Optional[str] = None
        # Part N: model yuklana olmasa (GPU xotira / OOM) avtomatik kichikroq
        # modelga o'tish. Bitta so'rovda 1 marta fallback (cheksiz aylanish yo'q).
        self._fallback_tried = False
        self._failed_models: set[str] = set()

        # TURBO rejim — universal tezlashtirish (har qanday modelga birdek).
        # Yoqilganda: kichik kontekst/token, thinking o'chiq, qisqa timeout,
        # va oddiy savollar tez modelga yo'naltiriladi (katta model faqat
        # murakkab vazifalarga). `fast_model` TURBO yoqilganda avtomatik
        # tanlanadi (pick_fast_model) — foydalanuvchi o'zi tanlamaydi.
        self.turbo = False
        self.fast_model: Optional[str] = None
        # Asl (turbo'siz) timeout — o'chirilganda qayta tiklanadi (foydalanuvchi
        # maxsus timeout bilan yaratgan bo'lsa ham saqlanib qoladi).
        self._base_timeout = timeout

    def set_turbo(self, enabled: bool, available_models: Optional[list[str]] = None):
        """Universal tez rejimni yoqadi/o'chiradi (BIR kalit, barcha modellar).

        enabled=True: kichik va tez sozlamalar qo'llanadi + oddiy savollar uchun
        avtomatik tez model tanlanadi. enabled=False: hammasi avvalgi holatga.
        """
        self.turbo = bool(enabled)
        if enabled:
            models = available_models if available_models is not None else self.list_models()
            self.fast_model = pick_fast_model(models)
            # Timeout'ni ham qisqartiramiz — tez rejimda sekin kutish yo'q.
            self.timeout = TURBO_TIMEOUT
        else:
            self.fast_model = None
            self.timeout = self._base_timeout

    # ------------------------------------------------------------ #

    def is_available(self) -> bool:
        """Ping Ollama; return False when it is not running."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                self.last_error = None  # muvaffaqiyat — eski xato belgisini tozalaymiz
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            self.last_error = "Ollama ishlamayapti (localhost:11434 ga ulanishmadi)."
            return False

    def list_models(self) -> list[str]:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                names = [m.get("name", "") for m in data.get("models", [])]
                self.last_error = None if names else "Ollama ishlayapti, lekin hech qanday model o'rnatilmagan."
                return names
        except (urllib.error.URLError, OSError) as exc:
            self.last_error = f"Ollama aloqasi uzildi: {exc}"
            return []
        except Exception:
            return []

    def list_models_detailed(self) -> list[dict]:
        """Model nomlari + hajm/o'lcham/quantizatsiya (Settings modal uchun).

        /api/tags bitta so'rovda barcha ma'lumotni beradi — /api/show kabi
        har modelga alohida so'rov yuborilmaydi (tez).
        """
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                out: list[dict] = []
                for m in data.get("models", []):
                    d = m.get("details") or {}
                    size = (m.get("size") or 0) / (1024 ** 3)
                    out.append({
                        "name": m.get("name", ""),
                        "parameter_size": d.get("parameter_size", "?"),
                        "quantization": d.get("quantization_level", "?"),
                        "size_gb": round(size, 1),
                    })
                return out
        except Exception:
            return []

    # ------------------------------------------------------------ #

    def _is_model_load_error(self, detail: str) -> bool:
        """Model YUKLANA olmasa (GPU xotira / OOM / fayl buzilgan) — True.

        Bunday xato bilan qayta urinish befoyda; kichikroq modelga o'tish
        to'g'ri. Boshqa 500 (masalan noto'g'ri so'rov) — fallback QILINMAYDI.
        """
        low = (detail or "").lower()
        return any(k in low for k in (
            "out of memory", "cudamalloc", "cuda0 buffer", "unable to allocate",
            "failed to load model", "failed to allocate", "insufficient",
            "allocate_tensor", "ggml_backend_cuda", "oom",
        ))

    def _next_fallback_model(self) -> Optional[str]:
        """Mavjud modellardan eng kichigini (sig'mayotgan/har safar xato
        berganlardan tashqari) tanlaydi. Ulcham bo'yicha tartiblanadi."""
        try:
            detailed = self.list_models_detailed()
        except Exception:
            detailed = []
        cands = sorted(detailed, key=lambda d: float(d.get("size_gb") or 99))
        for d in cands:
            name = str(d.get("name") or "")
            if not name:
                continue
            if name == self.model or name in self._failed_models:
                continue
            return name
        return None

    def _request(self, payload: dict, endpoint: str = "/api/chat") -> Optional[dict]:
        """Bitta POST so'rov: retry/backoff + aniq xato yozuvi bilan.

        HTTPError (masalan 404 model not found) — qayta urinilmaydi, sabab
        `last_error`ga yoziladi. Transport xatolari (Ollama band/qayta
        yuklanmoqda) — 2 marta qayta uriniladi.
        """
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err: Optional[Exception] = None
        # Har bir mantiqiy so'rov uchun bitta fallback imkoniyati.
        self._fallback_tried = False
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    self.last_error = None
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                # Server javob berdi — real xato (model topilmadi, noto'g'ri payload...)
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
                # Part N: model YUKLANA OLMASA (GPU xotira/OOM) — kichikroq modelga
                # avtomatik o'tib, shu so'rovni qayta urinamiz (bitta urinish).
                if exc.code == 500 and not self._fallback_tried and self._is_model_load_error(detail):
                    fb = self._next_fallback_model()
                    if fb is not None:
                        self._fallback_tried = True
                        self._failed_models.add(self.model)
                        self.last_error = (
                            f"Model '{self.model}' yuklana olmadi (GPU xotira) — "
                            f"avtomatik '{fb}' ga o'tildi."
                        )
                        self.model = fb
                        self.fast_model = None
                        # Fallback modellar odatda reasoning'ni qo'llamaydi —
                        # `think` parametri ularga 500 beradi (payload ham yangilanadi).
                        self.think = False
                        payload["model"] = fb
                        payload["think"] = False
                        req = urllib.request.Request(
                            f"{self.base_url}{endpoint}",
                            data=json.dumps(payload).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        continue
                self.last_error = f"Ollama HTTP {exc.code}: {exc.reason}"
                if detail and "error" in detail.lower():
                    try:
                        self.last_error = f"Ollama: {json.loads(detail).get('error', detail)[:160]}"
                    except (ValueError, TypeError):
                        self.last_error += f" — {detail[:120]}"
                return None
            except TimeoutError as exc:
                # TIMEOUT: model hali ishlayotgan edi (sekin fikrlash) — qayta
                # urinish GENERATSIYANI BOSHDAN qayta boshlardi va 300s x 3 =
                # 15 daqiqa tutilib qolardi. Timeout'da qayta urinilmaydi!
                last_err = exc
                self.last_error = (
                    f"Ollama {self.timeout}s ichida javob bermadi — model juda "
                    "sekin/band. (Timeout 300s, num_ctx 32K, thinking rejimi.)"
                )
                break
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    # ba'zi Python versiyalarida timeout URLError ichida keladi
                    last_err = exc
                    self.last_error = f"Ollama {self.timeout}s ichida javob bermadi (timeout)."
                    break
                last_err = exc
                self.last_error = f"Ollama aloqasi uzildi: {exc}"
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s backoff
            except OSError as exc:
                # connection refused/reset — Ollama qayta ochilayotgan bo'lishi
                # mumkin; qisqa kutish bilan qayta urinamiz.
                last_err = exc
                self.last_error = f"Ollama aloqasi uzildi: {exc}"
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))
            except json.JSONDecodeError as exc:
                last_err = exc
                self.last_error = f"Ollama noto'g'ri javob qaytardi: {exc}"
                if attempt < self.retries:
                    time.sleep(0.3)
        if last_err is not None:
            self.last_error = f"Ollama murojaat qilib bo'lmadi: {last_err}"
        return None

    def _turbo_options(self) -> dict:
        """TURBO rejimdagi kichik/tez options — aks holda standart."""
        if self.turbo:
            return {
                "temperature": self.temperature,
                "num_predict": min(self.max_tokens, TURBO_MAX_TOKENS),
                "num_ctx": min(self.num_ctx, TURBO_NUM_CTX),
            }
        return {
            "temperature": self.temperature,
            "num_predict": self.max_tokens,
            "num_ctx": self.num_ctx,
        }

    def chat(self, messages: list[dict], stream: bool = False,
             temperature: Optional[float] = None) -> Optional[str]:
        """Send a chat request; returns assistant text (or None on failure).

        temperature berilsa — sessiya temperature'sini vaqtincha bekor qiladi
        (kreativ multi-candidate generatsiya uchun: turli xil temperature'lar
        bilan bir nechta variant olinadi).
        """
        options = self._turbo_options()
        if temperature is not None:
            options = dict(options)
            options["temperature"] = float(temperature)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            # TURBO rejimda thinking o'chiriladi — tez javob uchun.
            "think": self.think and not self.turbo,
            "keep_alive": self.keep_alive,
            "options": options,
        }
        data = self._request(payload)
        if data is None:
            return None
        # qwen3 thinking: message.thinking ichki fikrlash, content esa
        # YAKUNIY javob. content bo'sh bo'lsa None qaytaramiz — chaqiruvchi
        # (planner/resolver) allaqachon None/bo'shni boshqaradi; xom fikrlash
        # zanjirini javob sifatida qaytarmaymiz.
        return data.get("message", {}).get("content")

    def chat_stream(self, messages: list[dict], temperature: Optional[float] = None,
                    think: Optional[bool] = None) -> "generator[str]":
        """Stream a chat completion token-by-token (Ollama NDJSON stream).

        Yields CONTENT deltas as they arrive (fikrlash/reasoning tokenlari
        kirmaydi — ularni ham istasangiz `chat_stream_rich()`). Agar
        `think=False` berilsa qwen3 ichki fikrlash bosqichi ham YO'Q bo'ladi
        (default: sessiya sozlamasi) — birinchi token DARHOL keladi. Transport
        xatoligida generator to'xtaydi va `last_error` yoziladi; chaqiruvchi
        qisman yig'ilgan matnni saqlab qoladi.

        Ushbu generator server'da SSE (/api/chat/stream) uchun ishlatiladi —
        frontend javobni TOKEN-KETMA-TOKEN ko'radi (bir necha daqiqa kutish
        o'rniga darhol yozilayotganini kuzatadi).
        """
        # Faqat CONTENT deltalari — thinking tokenlari eski chaqiruvchilarga
        # aralashmasligi uchun tashlab yuboriladi (ularni `chat_stream_rich`
        # beradi).
        for is_think, delta in self._chat_stream_raw(
            messages, temperature=temperature, think=think
        ):
            if not is_think and delta:
                yield delta

    def chat_stream_rich(self, messages: list[dict], temperature: Optional[float] = None,
                         think: Optional[bool] = None) -> "generator[dict]":
        """`chat_stream`'ning TO'LIQ varianti — thinking tokenlari ham stream.

        Har bir yield dict (SSE'ga bevosita uzatiladi):

          {"type": "think", "content": "<fikrlash deltasi>"}  — qwen3 reasoning
          {"type": "token", "content": "<javob deltasi>"}     — yakuniy javob

        Frontend "thinking" blokini token-ketma-token ko'rsatadi, so'ng javob
        xuddi shunday oqadi. Thinking qo'llab-quvvatlanmaydigan modellarda
        faqat "token" hodisalari chiqadi (degradatsiya xavfsiz).
        """
        for is_think, delta in self._chat_stream_raw(
            messages, temperature=temperature, think=think
        ):
            if delta:
                yield {"type": "think" if is_think else "token", "content": delta}

    def _chat_stream_raw(self, messages: list[dict], temperature: Optional[float] = None,
                         think: Optional[bool] = None) -> "generator[tuple[bool, str]]":
        """Ollama NDJSON oqimini (is_thinking, delta) juftligi sifatida beradi.

        `is_thinking=True` — qwen3 ichki fikrlash (`reasoning_content`) deltasi;
        `False` — yakuniy javob (`content`) deltasi. Transport xatoligida
        generator to'xtaydi va `last_error` yoziladi; chaqiruvchi qisman
        yig'ilgan matnni saqlab qoladi.
        """
        options = self._turbo_options()
        if temperature is not None:
            options = dict(options)
            options["temperature"] = float(temperature)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            # Streaming'da thinking ochiq bo'lsa — fikrlash tokenlari
            # `reasoning_content` sifatida keladi (frontend ularni jonli
            # ko'radi). `think=False` berilsa — birinchi token darhol keladi.
            "think": (self.think and not self.turbo) if think is None else bool(think),
            "keep_alive": self.keep_alive,
            "options": options,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("done"):
                        break
                    msg = data.get("message") or {}
                    # qwen3 kabi reasoning modellar fikrlashni content'dan
                    # ALOHIDA stream qiladi. Maydon nomi model/provayderga
                    # bog'liq: qwen3 (Ollama) -> `thinking`, deepseek-r1 va
                    # boshqalar -> `reasoning_content`. Ikkalasi ham olinadi.
                    reasoning = msg.get("reasoning_content") or msg.get("thinking") or ""
                    if reasoning:
                        yield True, reasoning
                    content = msg.get("content") or ""
                    if content:
                        yield False, content
                    self.last_error = None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            self.last_error = f"Ollama HTTP {exc.code}: {exc.reason}"
            if "error" in detail.lower():
                try:
                    self.last_error = f"Ollama: {json.loads(detail).get('error', detail)[:160]}"
                except (ValueError, TypeError):
                    self.last_error += f" — {detail[:120]}"
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            self.last_error = f"Ollama stream uzildi: {exc}"
        except json.JSONDecodeError as exc:
            self.last_error = f"Ollama noto'g'ri stream javob: {exc}"

    def chat_fast(self, messages: list[dict], system: Optional[str] = None) -> Optional[str]:
        """TURBO: oddiy savollarni tez/kichik modelga yo'naltiradi.

        Katta model faqat murakkab vazifalarga qoladi. `fast_model` topilmagan
        bo'lsa — joriy modelning o'zi TURBO sozlamalari bilan ishlatiladi
        (hamon tezroq: kichik kontekst, thinking yo'q, qisqa javob).
        """
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        model = self.fast_model or self.model
        # Ikkala model ham RAM'da (keep_alive) — kichigiga o'tish tez.
        payload = {
            "model": model,
            "messages": msgs,
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": TURBO_MAX_TOKENS,
                "num_ctx": TURBO_NUM_CTX,
            },
        }
        data = self._request(payload)
        if data is None:
            return None
        return data.get("message", {}).get("content")

    # ------------------------------------------------------------ #
    # Ixtiyoriy logprob re-so'ruvi — OpenAI-mos /v1/chat/completions
    # ------------------------------------------------------------ #

    def chat_logprobs(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 128,
    ) -> Optional[float]:
        """OpenAI-mos endpoint orqali o'rtacha token ehtimoli (0..1).

        Native /api/chat logprob QAYTARMAYDI (options'da ham, javobda ham
        per-token probability yo'q) — shuning uchun bu ALOHIDA (2-so'rov)
        OpenAI-mos chaqiruv: `logprobs: true` + `top_logprobs: 1` bilan
        greedy (temperature=0) qayta generatsiya qilinadi va chiqish
        tokenlari ehtimolining geometrik o'rtachasi
        (exp(mean(logprob)), perplexity'ga teskari) qaytadi.

        1.0 — model o'z javobiga juda ishonchli; past qiymat — noaniq javob.
        Ollama eski/offline bo'lsa yoki logprob qaytarmasa None qaytadi —
        chaqiruvchi signalni neytral qoldiradi (agent buzilmaydi).

        Izoh: qwen3 kabi thinking modellarda reasoning tokenlari ham
        logprobs.content'ga kirishi mumkin (jonli serverda tekshirilishi
        kerak) — bu o'lchovni biroz chalg'itishi mumkin, lekin heuristika
        sifatida qabul qilinadi.

        Ixtiyoriy: self-eval ishonch signali uchun (2x inference narxi —
        faqat `logprobs=True` sozlanganida ishlatiladi).
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0,     # greedy — takrorlanuvchi o'lchov
            "max_tokens": max_tokens,
            "logprobs": True,
            "top_logprobs": 1,
        }
        data = self._request(payload, endpoint="/v1/chat/completions")
        if data is None:
            return None
        try:
            choice = (data.get("choices") or [{}])[0]
            lps = ((choice.get("logprobs") or {}).get("content")) or []
            return self._avg_token_probability(lps)
        except Exception:
            return None

    @staticmethod
    def _avg_token_probability(content_items: list) -> Optional[float]:
        """OpenAI logprobs.content ro'yxatidan geometrik o'rtacha ehtimol.

        Har bir element `{"token": str, "logprob": float, ...}` —
        `exp(mean(logprob))` per-token ehtimollarning geometrik o'rtachasi
        (logprob'lar o'rtachasi => perplexity'ga teskari ishonch o'lchovi).
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
        mean_lp = sum(logps) / len(logps)
        return max(0.0, min(1.0, math.exp(mean_lp)))

    def complete(self, prompt: str, system: Optional[str] = None,
                 temperature: Optional[float] = None) -> Optional[str]:
        """One-shot completion helper."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)

    # ------------------------------------------------------------ #
    # Native tool-calling (Ollama tools API)
    # ------------------------------------------------------------ #

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> Optional[dict]:
        """Send a chat request with tool schemas; model decides which tool to call.

        Args:
            messages: [{role, content}, ...] (already includes system + history)
            tools: list of tool JSON-schemas (from ToolRegistry.schemas())

        Returns a dict with either:
            {"content": str}                          — final answer (no tool call)
            {"tool_calls": [{"name": str, "arguments": dict}, ...]} — model wants tools
        or None on transport failure.
        """
        # TEZLIK: qwen3 kabi reasoning modellarda `think` har round'da 30-60s
        # ichki fikrlash qo'shadi. Birinchi round'da (tool xabarlari yo'q) model
        # reja/thinking ishlatishi mumkin — keyingi tool round'larida esa faqat
        # natijani qayta ishlash kerak, fikrlash keraksiz. Shuning uchun tool
        # round'larida think o'chiriladi (2-4x tezroq kod/rasm yozish, sifatga
        # zarar yo'q — model natijani to'g'ridan-to'g'ri ko'radi).
        has_tool_round = any(m.get("role") == "tool" for m in messages)
        think = self.think and not self.turbo and not has_tool_round
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": think,
            "tools": tools,
            "keep_alive": self.keep_alive,
            "options": self._turbo_options(),
        }
        data = self._request(payload)
        if data is None:
            return None

        message = data.get("message", {})
        content = message.get("content") or ""
        raw_calls = message.get("tool_calls") or []
        thinking = message.get("thinking") or ""

        if raw_calls:
            calls = []
            for c in raw_calls:
                fn = c.get("function") or {}
                name = fn.get("name") or c.get("name") or ""
                arguments = fn.get("arguments")
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                calls.append({"name": name, "arguments": arguments or {}})
            return {"tool_calls": calls}

        # Fallback: ba'zi modellar (qwen2.5-coder) tool call'ni
        # `tool_calls` maydonida emas, content ichida JSON sifatida qaytaradi:
        #   content = '{"name": "get_weather", "arguments": {"city": "Paris"}}'
        content_call = self._parse_content_tool_call(content)
        if content_call:
            return {"tool_calls": [content_call], "content": content}

        # content bo'sh bo'lishi mumkin — qwen3 faqat thinking berib, yakuniy
        # javob hali chiqmagan bo'lsa. Xom fikrlashni content O'RNIGA qaytarmaymiz
        # (agent loop'lar bo'sh javobni o'zlari qayta-urinish bilan boshqaradi);
        # thinking'ni alohida maydonda beramiz — loop'lar xohlasa ishlatadi.
        result = {"content": content}
        if thinking:
            result["thinking"] = thinking
        return result

    @staticmethod
    def _parse_content_tool_call(content: str) -> Optional[dict]:
        """Content ichidagi JSON tool-call ni ajratib oladi (agar mavjud bo'lsa)."""
        text = (content or "").strip()
        if not text:
            return None
        # fenced JSON yoki to'g'ridan-to'g'ri object
        candidates = []
        if "```json" in text:
            import re
            m = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
            if m:
                candidates.append(m.group(1))
        candidates.append(text)
        for c in candidates:
            try:
                parsed = json.loads(c)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("name"):
                args = parsed.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                return {"name": parsed["name"], "arguments": args or {}}
        return None

    def supports_tools(self) -> bool:
        """Heuristic: most Ollama models (qwen*) support tools; assume true."""
        info = self.model_info(self.model)
        return True  # schema-level; failures surface as None responses

    # ------------------------------------------------------------ #

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate (chars/4, matches typical local models)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def model_info(self, model: str) -> Optional[dict]:
        """Fetch details for one model (parameter size, context, quant)."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/show",
                data=json.dumps({"model": model}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                details = data.get("details", {})
                return {
                    "name": model,
                    "parameter_size": details.get("parameter_size", "?"),
                    "quantization": details.get("quantization_level", "?"),
                    "context_length": data.get("model_info", {}).get("context_length", "?"),
                    "size": data.get("size", 0),
                }
        except Exception:
            return None

    # ------------------------------------------------------------ #

    def extract_code(self, text: Optional[str]) -> str:
        """Best-effort extraction of a code block from LLM output."""
        if not text:
            return ""
        # fenced block
        if "```" in text:
            parts = text.split("```")
            for part in parts[1:]:
                if "\n" in part:
                    lines = part.strip("\n").split("\n")
                    # first line may be a language tag (python, bash, ...)
                    if lines and len(lines[0].split()) == 1 and lines[0].isidentifier():
                        return "\n".join(lines[1:])
                    return "\n".join(lines)
        return text.strip()
