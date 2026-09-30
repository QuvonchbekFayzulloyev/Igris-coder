"""
IGRIS BRAIN  -  FastAPI Bridge Server
===================================
Exposes the hybrid agent (bricks + RAG memory + Ollama LLM) over HTTP so the
Igris_Interface (web/desktop) can talk to the real backend instead of mock data.

Run:
    cd Igris_brain
    python server.py                # http://localhost:8765
    python server.py --port 8765 --no-llm
    python server.py --model qwen3:8b --memory ../Igris_Memory/brain_data

Endpoints:
    GET  /api/status                -> agent + memory + llm status
    GET  /api/llm/models            -> local Ollama models
    POST /api/resolve               -> hybrid resolution {query}
    POST /api/chat                  -> conversational {message, history[]}
    POST /api/memory/search         -> RAG search {query, top_k}
    GET  /api/memory/status         -> memory manager status
    POST /api/session/start|end     -> memory session control
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from typing import Callable, Optional

_this_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_this_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))
sys.path.insert(0, os.path.join(_brain, "..", "2nd_brain", "backend"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
import uvicorn  # noqa: E402

from agent.igris_agent import IgrisAgent  # noqa: E402
from agent.memory_bridge import MemoryBridge  # noqa: E402
from planning.planner import TaskPlanner  # noqa: E402
from executor.executor import AgentExecutor  # noqa: E402
from agent.layered_agent import CLARIFICATION_MANAGER  # noqa: E402

# ---------------------------------------------------------------------- #
# Request / response models
# ---------------------------------------------------------------------- #

class ResolveRequest(BaseModel):
    query: str
    allow_llm: bool = True
    use_memory: bool = True

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    use_memory: bool = True
    session_id: str = ""

class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SessionRequest(BaseModel):
    session_id: str = ""
    summary: str = ""

class PlanRequest(BaseModel):
    task: str

class RunRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8

class ToolRunRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8

class TaskRequest(BaseModel):
    task: str
    workspace: str = ""
    max_iter: int = 8
    session_id: str = ""

class RespondRequest(BaseModel):
    run_id: str
    answer: str

class ModelRequest(BaseModel):
    model: str

class SpeedRequest(BaseModel):
    turbo: bool = False

class WebAIActionRequest(BaseModel):
    action: str
    url: str = ""
    index: int = 0

class DrawingEditRequest(BaseModel):
    path: str
    request: str
    frozen: dict = Field(default_factory=dict)
    workspace: str = ""

class ChatIdRequest(BaseModel):
    id: str

class ChatStarRequest(BaseModel):
    id: str
    starred: bool = True

class ChatRenameRequest(BaseModel):
    id: str
    title: str


# Surgikal tahrir  --  agent faqat kerakli qismlarni o'zgartiradi, qolganini
# xuddi o'zicha qoldiradi (frozen kontekst asosida).
DRAWING_EDIT_SYSTEM = (
    "You are Igris, a surgical SVG editor. The user is watching an SVG drawing "
    "being built step-by-step and paused it to request a change.\n\n"
    "HARD RULES:\n"
    "1. read_file the target SVG file FIRST. Copy its content into your head.\n"
    "2. Write the ENTIRE modified SVG in ONE write_file call to the SAME path. "
    "Do NOT create a new/placeholder drawing  --  you must reproduce the full file.\n"
    "3. Every element that does not need to change must appear BYTE-IDENTICAL in "
    "the new file: same tags, same attributes, same coordinates, same colors, "
    "same stroke widths, same order. Copy them verbatim from the file you read.\n"
    "4. Change ONLY the specific part(s) the user's request is about, and only the "
    "attributes/values that must change (e.g. change only the roof polygon's fill "
    "from '#c23b3b' to a green hex  --  leave its points and stroke untouched).\n"
    "5. Keep the overall style consistent  --  use a similar palette, stroke widths "
    "and sizes as the rest of the drawing so nothing looks out of place.\n"
    "6. Finish with a 1-2 sentence summary naming EXACTLY which element(s) changed "
    "and which stayed identical.\n"
    "If you need drawing guidance use use_skill('svg-artist')."
)

# ---------------------------------------------------------------------- #
# Universal speed (TURBO) sozlamasi  --  diskda saqlanadi, restart'da qo'llanadi
# ---------------------------------------------------------------------- #

_SPEED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speed_settings.json")
_SPEED = {"turbo": False}


def _load_speed() -> dict:
    """TURBO sozlamasini diskdan o'qiydi (server restart'da yo'qolmaydi)."""
    global _SPEED
    try:
        if os.path.isfile(_SPEED_FILE):
            with open(_SPEED_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "turbo" in data:
                _SPEED["turbo"] = bool(data["turbo"])
    except (OSError, json.JSONDecodeError):
        pass
    return _SPEED


def _persist_speed():
    try:
        with open(_SPEED_FILE, "w", encoding="utf-8") as fh:
            json.dump(_SPEED, fh, ensure_ascii=False)
    except OSError:
        pass


# ---------------------------------------------------------------------- #
# 2nd Brain graf sozlamalari  --  graph_shares.json (server restart'da saqlanadi)
# ---------------------------------------------------------------------- #

_GRAPH_SHARES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "2nd_brain", "backend",
    "graph_shares.json")
# None = default ulushlar; max_nodes None = default chegarasi;
# updated_at/history  --  o'zgarishlar kuzatuvi.
_GRAPH_SHARES: dict = {
    "shares": None, "max_nodes": None, "updated_at": None, "history": []}
# Graf node'larining standart yuqori chegarasi (build_graph default'iga mos).
_GRAPH_MAX_NODES_DEFAULT = 240
# Tarixda eng ko'pi shuncha yozuv qoladi (cheksiz o'smaydi).
_GRAPH_SHARES_HISTORY_LIMIT = 20


def _clamp_max_nodes(v) -> Optional[int]:
    """max_nodes'ni xavfsiz normallashtiradi: [30, 2000] diapazon.

    Noto'g'ri tur/qiymat (None, 'abc', 5, 99999, nan...) -> None (default).
    """
    try:
        n = int(float(v))
    except (TypeError, ValueError, OverflowError):
        # OverflowError: float('inf') -> int() beradi (500 o'rniga default).
        return None
    if not (30 <= n <= 2000):
        return None
    return n


def _load_graph_shares() -> dict:
    """Graf sozlamalarini diskdan o'qiydi (server restart'da yo'qolmaydi).

    Yangi format: {shares, max_nodes, updated_at, history}. Eski format
    (faqat {shares: [...]}) ham qo'llab-quvvatlanadi  -  max_nodes default
    qoladi, tarix bo'sh boshlanadi.
    """
    global _GRAPH_SHARES
    try:
        if os.path.isfile(_GRAPH_SHARES_FILE):
            with open(_GRAPH_SHARES_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                if isinstance(data.get("shares"), list):
                    _GRAPH_SHARES["shares"] = data["shares"]
                if data.get("max_nodes") is not None:
                    _GRAPH_SHARES["max_nodes"] = _clamp_max_nodes(data["max_nodes"])
                _GRAPH_SHARES["updated_at"] = data.get("updated_at")
                hist = data.get("history")
                # Faqat to'g'ri shakldagi yozuvlar olinadi (buzilgan kirsa tashlanadi).
                if isinstance(hist, list):
                    valid = [e for e in hist
                             if isinstance(e, dict)
                             and (isinstance(e.get("shares"), list)
                                  or e.get("max_nodes") is not None)]
                    _GRAPH_SHARES["history"] = valid[-_GRAPH_SHARES_HISTORY_LIMIT:]
                else:
                    _GRAPH_SHARES["history"] = []
    except (OSError, json.JSONDecodeError):
        pass
    return _GRAPH_SHARES


def _persist_graph_shares(shares: Optional[list] = None,
                          max_nodes: Optional[int] = None,
                          updated_at: Optional[float] = None):
    """Graf sozlamalarini diskda saqlaydi; o'zgarish tarixga qo'shiladi.

    Ikkala maydon ham ixtiyoriy  -  None berilgan maydon JORIY qiymatini
    saqlaydi (qisman yangilash: faqat shares yoki faqat max_nodes).
    Qiymat o'zgarmagan bo'lsa yangi yozuv qo'shilmaydi (tarix shovqinsiz).
    """
    now = updated_at if updated_at is not None else time.time()
    cur_shares = _GRAPH_SHARES.get("shares")
    cur_max = _GRAPH_SHARES.get("max_nodes")
    new_shares = list(shares) if shares is not None else \
        (list(cur_shares) if cur_shares else None)
    new_max = max_nodes if max_nodes is not None else cur_max
    prev = _GRAPH_SHARES.get("history", [])
    # Dedup IKKALA qiymatni ko'radi  --  faqat shares bir xil bo'lib max_nodes
    # o'zgarsa ham yangi yozuv kerak (aks holda o'zgarish tarixda yo'qolardi).
    if prev and prev[-1].get("shares") == new_shares \
            and prev[-1].get("max_nodes") == new_max:
        return  # bir xil qiymat  --  takroriy yozuv kerak emas
    _GRAPH_SHARES["shares"] = new_shares
    _GRAPH_SHARES["max_nodes"] = new_max
    _GRAPH_SHARES["updated_at"] = now
    _GRAPH_SHARES["history"] = prev + [{
        "ts": now, "shares": new_shares, "max_nodes": new_max}]
    # Tarix chegarasi  --  eski yozuvlar olib tashlanadi.
    _GRAPH_SHARES["history"] = _GRAPH_SHARES["history"][-_GRAPH_SHARES_HISTORY_LIMIT:]
    try:
        with open(_GRAPH_SHARES_FILE, "w", encoding="utf-8") as fh:
            json.dump(_GRAPH_SHARES, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass


# S5: chat tarixi qatlami server_chat_history.py'da (yagona manba) —
# nomlar qayta eksport qilinadi (testlar kontrakti: from server import ChatHistory).
from server.server_chat_history import (  # noqa: E402, F401
    CHAT_PROGRESS, CHAT_PROGRESS_LOCK, CHAT_HISTORY_PATH,
    _chat_progress_cb, _chat_progress_clear, _structure_fail_warning,
    ChatHistory, CHAT_HISTORY,
)


# ---------------------------------------------------------------------- #
# App + singleton agent
# ---------------------------------------------------------------------- #

app = FastAPI(title="IGRIS Brain Bridge", version="2.0.0")

# Server start time - uptime hisoblash uchun
_SERVER_START_TIME = time.time()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev: allow the vite dev server / tauri webview
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# D1 — umumiy kirish validatsiyasi (problems_to_fix.md :: Q4/D1):
# body hajmi, string uzunlik/kontrol-belgilar, path traversal, inf/nan.
# Local app: `workspace` caller-tanlaydi (qat'iy root Yo'Q) — faqat umumiy
# qoidalar (traversal/sxema/kontrol-belgilar) qo'llanadi; endpoint'lar o'z
# `Workspace.resolve` containment'ini saqlaydi (defense-in-depth).
from safety.input_validation import install_input_validation  # noqa: E402

install_input_validation(app, workspace_root=None)

_AGENT: Optional[IgrisAgent] = None

_DEFAULTS = {
    "model": os.environ.get("IGRIS_MODEL", "qwen3:8b"),
    "base_url": "http://localhost:11434",
    "use_llm": True,
    "memory": True,
    "memory_dir": "",
    "logprobs": os.environ.get("IGRIS_LOGPROBS", "0") == "1",
    # OmniRoute gateway
    "omniroute_url": os.environ.get("OMNIROUTE_URL", ""),
    "omniroute_api_key": os.environ.get("OMNIROUTE_API_KEY", ""),
    "omniroute_model": os.environ.get("OMNIROUTE_DEFAULT_MODEL", ""),
}


# S5: CircuitBreaker server_circuit.py'da (yagona manba) — qayta eksport.
from server.server_circuit import CircuitBreaker, _CIRCUIT  # noqa: E402, F401

from server.server_health import (  # noqa: E402, F401
    _METRICS_MAX_ENTRIES, _metrics_history, _metrics_lock,  # noqa: F401
    collect_health_metrics, metrics_history_size, metrics_snapshot,
    record_metrics,
)

# Process helpers (restart / watchdog / ollama) - S5 moduli
import server.server_process as _proc  # noqa: E402
from server.server_process import (  # noqa: E402, F401
    _install_fatal_handlers, _watchdog_state, _ollama_running,
    _port_in_use, _wait_port_free, _spawn_detached,
    _server_start_command, _persist_launch_info,
    _restart_marker_path, _write_restart_marker,
)


# ------------------------------------------------------------------ #
# Health Monitor  -  fon'da agent sog'lig'ini kuzatadi, avtomatik tiklaydi
# ------------------------------------------------------------------ #

_HEALTH_MONITOR_INTERVAL = 30.0   # har 30 soniyada tekshiradi
_HEALTH_MONITOR_STARTED = False


def _health_monitor_loop():
    """Background thread: agent/LLM sog'lig'ini muntazam tekshiradi.

    Agar LLMavailable bo'lmasa yoki agent xato bersa  --  avtomatik qayta
    yaratadi (circuit breaker orqali). Backend offline bo'lmaydi:
    agent doimo yaratiladi (LLM yo'qsa ham bricks/RAG ishlaydi).

    Har aylanishda metrikalarni tarixga yozadi - monitoring dashboard
    real vaqt metrikalarini olishi uchun.
    """
    global _AGENT
    while True:
        try:
            time.sleep(_HEALTH_MONITOR_INTERVAL)
            # Metrikalarni yig'amiz (har aylanishda)
            try:
                metrics = collect_health_metrics(
                    agent=_AGENT,
                    server_start_time=_SERVER_START_TIME,
                    circuit=_CIRCUIT,
                    chat_progress=CHAT_PROGRESS,
                    chat_progress_lock=CHAT_PROGRESS_LOCK,
                    chat_history=CHAT_HISTORY,
                )
                record_metrics(metrics)
            except Exception:
                pass
            agent = _AGENT
            if agent is None:
                continue
            # LLM sog'lig'ini tekshiramiz  -  model mavjudligini tez tekshirish
            try:
                if hasattr(agent.llm, "last_error") and agent.llm.last_error:
                    # LLM xato  -  avtomatik qayta yaratish
                    print(f"[health] LLM xato: {agent.llm.last_error[:80]}  -  agent qayta yaratilmoqda")
                    try:
                        _AGENT = create_agent(**_DEFAULTS)
                        _CIRCUIT.record_success()
                        print("[health] agent muvaffaqiyatli qayta yaratildi")
                    except Exception as exc:
                        _CIRCUIT.record_failure(str(exc))
                        print(f"[health] agent qayta yaratilmadi: {exc[:80]}")
            except Exception:
                pass
            # Memory sog'lig'ini tekshiramiz  -  RAG yuklanmagan bo'lsa qayta urinamiz
            try:
                if hasattr(agent, 'memory') and agent.memory and not agent.memory.enabled:
                    if hasattr(agent.memory, '_error') and agent.memory._error:
                        print(f"[health] memory disabled: {agent.memory._error[:60]}  -  qayta urinish")
                        try:
                            agent.memory.__init__(
                                enabled=True,
                                session_id=getattr(agent.memory, 'session_id', 'bridge'),
                                base_dir=getattr(agent.memory, 'base_dir', ''),
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception as exc:
            # Health monitor hech qachon o'lmaydi
            try:
                print(f"[health] monitor xatosi (e'tiborsiz): {exc}")
            except Exception:
                pass


def _start_health_monitor():
    """Health monitor'ni background thread'da ishga tushiradi (bir marta)."""
    global _HEALTH_MONITOR_STARTED
    if _HEALTH_MONITOR_STARTED:
        return
    _HEALTH_MONITOR_STARTED = True
    t = threading.Thread(target=_health_monitor_loop, daemon=True, name="health-monitor")
    t.start()
    print("[igris] health monitor ishga tushdi")


def get_agent() -> IgrisAgent:
    """Lazy singleton init  --  circuit breaker bilan himoyalangan.

    Agent yaratishda xato bo'lsa  --  circuit breaker qayd etadi;
    ketma-ket 3 ta xatodan keyin agent qayta yaratiladi (Ollama qulab
    tushganda yoki model yuklanmagan bo'lsa avtomatik tiklash).
    """
    global _AGENT
    if _AGENT is not None and _CIRCUIT.should_allow():
        return _AGENT
    # Circuit OPEN yoki agent yo'q  -  yaratamiz
    try:
        _AGENT = create_agent(**_DEFAULTS)
        _CIRCUIT.record_success()
    except Exception as exc:
        _CIRCUIT.record_failure(str(exc))
        if _AGENT is not None:
            # Oldingi agent mavjud  -  xatoni qayd etdik, lekin eski agentni
            # saqlab qolamiz (qisman ishlaydi: LLM yo'q, lekin bricks/RAG ishlaydi)
            print(f"[circuit] agent qayta yaratilmadi ({exc[:80]}), eski agent ishlatiladi")
            return _AGENT
        # Agent yo'q va yaratib bo'lmadi  -  xato bilan qaytaramiz
        raise
    return _AGENT


def rebuild_agent():
    """Agent'ni majburiy qayta yaratadi  --  UI'dan yoki watchdog'dan."""
    global _AGENT
    _CIRCUIT.force_reset()
    _AGENT = create_agent(**_DEFAULTS)
    print("[igris] agent qayta yaratildi (rebuild)")
    return _AGENT


# Sifat bo'yicha afzal modellar  -  so'ralgan model yo'q bo'lsa mavjudlardan
# eng yaxshisi avtomatik tanlanadi (foydalanuvchi qo'lda o'rnatishni kutmaydi).
from llm.ollama_client import pick_best_model  # noqa: E402


def _auto_select_model(agent: IgrisAgent, requested: str) -> str:
    """So'ralgan model o'rnatilmagan bo'lsa  --  Ollama'dagi eng yaxshi modelni tanlaydi.

    Qaytadi: amalda ishlatiladigan model nomi. Xato/sabab `llm.last_error`ga
    yoziladi  --  /api/status orqali UI'da ko'rinadi.
    """
    try:
        models = agent.llm.list_models()
    except Exception:
        models = []
    if requested in models:
        return requested
    best = pick_best_model(models)
    if best is None:
        agent.llm.last_error = (
            "Ollama ishlamayapti yoki hech qanday model o'rnatilmagan. "
            "`ollama pull qwen3:8b` bajarib, Settings → Services → restart qiling."
        )
        return requested
    agent.llm.model = best
    agent._llm_checked = False
    agent._mark_llm_recovered()
    agent.llm.last_error = (
        f"'{requested}' topilmadi  -  avtomatik ravishda {best} ishlatilmoqda. "
        f"Yaxshiroq sifat uchun `ollama pull {requested}` bajarib, "
        f"Settings → Model'dan tanlang."
    )
    print(f"[igris] model auto-select: '{requested}' -> '{best}'")
    return best


def create_agent(model: str, base_url: str, use_llm: bool, memory: bool, memory_dir: str,
                  logprobs: bool = False,
                  omniroute_url: str = "", omniroute_api_key: str = "",
                  omniroute_model: str = "") -> IgrisAgent:
    global _AGENT, _DEFAULTS
    _AGENT = IgrisAgent(
        use_llm=use_llm,
        llm_model=model,
        llm_base_url=base_url,
        memory_enabled=memory,
        memory_session="bridge",
        memory_dir=memory_dir,
        # Ixtiyoriy OpenAI-mos logprob re-so'ruvi (self-eval signal; 2x narx)
        llm_logprobs=logprobs,
        # OmniRoute gateway
        omniroute_url=omniroute_url,
        omniroute_api_key=omniroute_api_key,
        omniroute_model=omniroute_model,
    )
    if use_llm:
        # So'ralgan model mavjudligini tekshiramiz; yo'q bo'lsa  -  avto tanlov.
        model = _auto_select_model(_AGENT, model)
    _DEFAULTS.update(model=model, base_url=base_url, use_llm=use_llm,
                     memory=memory, memory_dir=memory_dir, logprobs=logprobs,
                     omniroute_url=omniroute_url, omniroute_api_key=omniroute_api_key,
                     omniroute_model=omniroute_model)
    return _AGENT


# ---------------------------------------------------------------------- #
# API
# ---------------------------------------------------------------------- #

# Part N: /api/status TTL kesh  -  takroriy poll'lar (Settings/StatusBar/agentInfo)
# agent.status() ni (Ollama + memory) har safar qayta hisoblamaydi; Ollama band
# bo'lganda ham status tez qaytadi (noto'g'ri "offline" ko'rinmaydi).
_STATUS_TTL_SECONDS = 5.0  # 5s TTL  -  UI poll'lari uchun yetarli (2s ortiqcha yuk)
_status_cache: dict = {"ts": 0.0, "data": None}
_status_lock = threading.Lock()


def _cached_agent_status() -> dict:
    now = time.time()
    with _status_lock:
        if _status_cache["data"] is not None and now - _status_cache["ts"] < _STATUS_TTL_SECONDS:
            return _status_cache["data"]
    agent = get_agent()
    st = agent.status()
    with _status_lock:
        _status_cache["ts"] = time.time()
        _status_cache["data"] = st
    return st


@app.get("/api/status")
def api_status():
    agent = get_agent()          # singleton  -  arzon
    st = _cached_agent_status()  # 2s TTL  -  og'ir status qayta hisoblanmaydi
    
    # OmniRoute status — agent'dagi real client'dan
    omniroute_status = {"connected": False, "url": "", "default_model": "", "models_count": 0, "providers": []}
    try:
        from llm.omniroute_client import get_client
        client = get_client()
        if client and client.health_check():
            models = client.list_models()
            omniroute_status = {
                "connected": True,
                "url": client.base_url,
                "default_model": client.default_model,
                "models_count": len(models),
                "providers": list(set(m.owned_by for m in models if m.owned_by))
            }
    except Exception:
        pass
    
    # LSP status
    lsp_status = {"servers": {}, "languages": []}
    try:
        from lsp.manager import LSPManager
        manager = LSPManager()
        lsp_status = {
            "servers": manager.get_status(),
            "languages": manager.get_available_languages(),
        }
    except Exception:
        pass
    
    return {
        "ok": True,
        "agent": {
            "bricks": st["bricks"]["total"],
            "rules": st["knowledge"]["rules"],
            "chains": list(st["chains"].keys()),
        },
        "llm": {
            "enabled": st["llm"]["enabled"],
            "available": st["llm"]["available"],
            "model": st["llm"]["model"],
            # Nega ishlamayapti  -  UI'da ko'rsatiladi ("model topilmadi" kabi).
            "error": getattr(agent.llm, "last_error", None),
            # Universal tez rejim (TURBO)  -  Settings'da ko'rsatiladi.
            "turbo": bool(getattr(agent.llm, "turbo", False)),
            "fast_model": getattr(agent.llm, "fast_model", None),
            # Graceful degradation holati
            "failure_count": getattr(agent, '_llm_failure_count', 0),
            "degraded": getattr(agent, '_llm_failure_count', 0) > 0,
        },
        "memory": {
            "enabled": st["memory"].get("enabled", False),
            "error": st["memory"].get("error"),
        },
        "intelligence": {
            "enabled": bool((st.get("intelligence") or {}).get("enabled")),
            "modules": sorted(k for k in (st.get("intelligence") or {})
                              if k != "enabled"),
        },
        # Circuit breaker holati  -  UI agent stabilizatsiya ko'rsatadi
        "circuit": _CIRCUIT.status(),
        # OmniRoute gateway status
        "omniroute": omniroute_status,
        # LSP server status
        "lsp": lsp_status,
        # Degradation metrics  -  monitoring dashboard uchun
        "degradation": agent.degradation_status() if hasattr(agent, 'degradation_status') else {},
        # Smart Build Engine status
        "smart_build": st.get("smart_build", {}),
        "timestamp": time.time(),
    }


@app.post("/api/agent/rebuild")
def api_agent_rebuild():
    """Agent'ni majburiy qayta yaratadi  --  UI Settings'dan yoki watchdog'dan.

    Circuit breaker reset + agent qayta yaratiladi (Ollama qulab tushganda
    yoki model yuklanmagan bo'lsa avtomatik tiklash). Backend offline bo'lmasligi
    uchun eng muhim qadam  --  agent'ni tiriltirish.
    """
    try:
        agent = rebuild_agent()
        return {"ok": True, "model": agent.llm.model, "circuit": _CIRCUIT.status()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "circuit": _CIRCUIT.status()}


@app.post("/api/circuit/reset")
def api_circuit_reset():
    """Circuit breaker'ni qo'lda reset qiladi  --  agent qayta yaratilmaydi,
    faqat xato hisoblagichlari tozalanadi.
    """
    _CIRCUIT.force_reset()
    return {"ok": True, "circuit": _CIRCUIT.status()}


class SmartBuildRequest(BaseModel):
    task: str

@app.post("/api/smart-build")
def api_smart_build(req: SmartBuildRequest):
    """Smart Build — Weak LLM + Strong Cognitive Infrastructure.

    Pipeline: Intent → Context Intelligence → Small LLM → Deterministic → Verify
    """
    agent = get_agent()
    if not agent.smart_build_engine:
        return {"ok": False, "error": "Smart Build engine not available"}
    try:
        result = agent.smart_build(req.task)
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/todos")
def api_todos_get():
    """Task ro'yxatini olish."""
    from tools.extra_tools import _todos
    return {"ok": True, "todos": _todos, "total": len(_todos)}


@app.post("/api/todos")
def api_todos_update():
    """Task ro'yxatini yangilash."""
    from tools.extra_tools import _todowrite
    body = Request.body.__wrapped__ if hasattr(Request.body, '__wrapped__') else {}
    try:
        import json
        body = json.loads(Request.body)
    except Exception:
        body = {}
    # Workspace placeholder
    class FakeWS:
        root = "."
    result = _todowrite(FakeWS(), body)
    return result


@app.get("/api/questions")
def api_questions_get():
    """Savollar ro'yxatini olish."""
    from tools.extra_tools import _questions
    unanswered = [q for q in _questions if q.get("answer") is None]
    return {"ok": True, "questions": unanswered, "total": len(unanswered)}


@app.post("/api/questions/<int:qid>/answer")
def api_question_answer(qid: int):
    """Savolga javob berish."""
    from tools.extra_tools import _set_question_answer
    try:
        import json
        body = json.loads(Request.body)
        answer = body.get("answer")
    except Exception:
        answer = None
    result = _set_question_answer(qid, answer)
    return result


@app.get("/api/vision/performance")
def api_vision_performance():
    """Vision system performansini olish."""
    try:
        agent = get_agent()
        return agent.vision_get_performance()
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/api/intelligence/status")
def api_intelligence_status():
    """INTELLEKT qatlami holati (BuildIntalaganceInstructionRequest.md).

    Har bir modulning REAL statistikasini qaytaradi: zarar filtri (bloklar
    soni), foydalanuvchi profili, ohang, lug'at, mantiq (struktura tekshiruvlari),
    ishonch kalibratsiyasi, fazoviy, kreativ, naturalist, musiqa. UI'da
    qaysi intellektlar ishlayotganini ko'rish uchun.
    """
    agent = get_agent()
    try:
        st = agent.intelligence.status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    st["modules"] = sorted(k for k in st if k != "enabled")
    st["timestamp"] = time.time()
    return {"ok": True, **st}


@app.get("/api/health")
def api_health():
    """Yengil sog'liq tekshiruvi  --  agent/LLM'ga TEGMAYDI.

    Watchdog shu endpoint'ni kuzatadi: /api/status agent holatini (model
    ro'yxati, Ollama tekshiruvi bilan) qaytaradi va model yuklanayotganda
    sekinlashishi mumkin  --  band lekin tirik backend'ni "o'lik" deb adashib
    o'ldirmaslik uchun alohida, tezkor sog'liq endpoint'i.
    """
    return {"ok": True, "timestamp": time.time()}


@app.get("/api/health/metrics")
def api_health_metrics():
    """To'liq sog'liq metrikalari - monitoring dashboard uchun.

    Agent, LLM, memory, circuit breaker, chat holati, system resurslari.
    Har so'rovda joriy holat + oxirgi 60 daqiqa tarixi.
    """
    metrics = collect_health_metrics(
        agent=_AGENT,
        server_start_time=_SERVER_START_TIME,
        circuit=_CIRCUIT,
        chat_progress=CHAT_PROGRESS,
        chat_progress_lock=CHAT_PROGRESS_LOCK,
        chat_history=CHAT_HISTORY,
        run_manager=RUN_MANAGER,  # Roadmap v2 C4: queue holati
    )
    record_metrics(metrics)

    # Tarixdan oxirgi N ta nuqtani qaytaramiz (dashboard uchun)
    history_snapshot = metrics_snapshot(60)  # oxirgi 30 daqiqa

    return {
        "ok": True,
        "current": metrics,
        "history_count": metrics_history_size(),
        "history": history_snapshot,
    }


@app.get("/api/health/history")
def api_health_history(limit: int = 60):
    """Sog'liq tarixi - time-series uchun.

    `limit` - nechta oxirgi metrikani qaytarish (max 120).
    Dashboard uchun: graf chizish, tendensiyalarni ko'rish.
    """
    limit = max(1, min(limit, _METRICS_MAX_ENTRIES))
    history = metrics_snapshot(limit)

    # Aggregatsiya - o'rtacha, min, max
    agg = {}
    if history:
        # LLM ping vaqtlari
        pings = [h.get("llm", {}).get("ping_ms", 0) for h in history
                 if h.get("llm", {}).get("ping_ms", 0) > 0]
        if pings:
            agg["llm_ping"] = {
                "avg_ms": round(sum(pings) / len(pings), 1),
                "min_ms": round(min(pings), 1),
                "max_ms": round(max(pings), 1),
            }
        # Xato soni
        errors = sum(1 for h in history
                     if h.get("llm", {}).get("degraded")
                     or h.get("agent", {}).get("status") == "error")
        agg["error_count"] = errors
        agg["uptime_percent"] = round(
            (1 - errors / max(len(history), 1)) * 100, 1
        )
        # Degradation metrics
        degradation_events = [h for h in history
                             if h.get("llm", {}).get("degradation")]
        if degradation_events:
            latest_deg = degradation_events[-1].get("llm", {}).get("degradation", {})
            agg["degradation"] = {
                "total_failures": latest_deg.get("total_degradation_count", 0),
                "total_time_seconds": latest_deg.get("total_degradation_time_seconds", 0),
                "current_failures": latest_deg.get("failure_count", 0),
                "is_degraded": latest_deg.get("is_degraded", False),
            }
        # Xotira hajmi
        rss_values = [h.get("system", {}).get("memory_rss_mb", 0)
                      for h in history
                      if h.get("system", {}).get("memory_rss_mb", 0) > 0]
        if rss_values:
            agg["memory"] = {
                "avg_mb": round(sum(rss_values) / len(rss_values), 1),
                "max_mb": round(max(rss_values), 1),
            }

    return {
        "ok": True,
        "count": len(history),
        "history": history,
        "aggregates": agg,
        "timestamp": time.time(),
    }


@app.get("/api/llm/models")
def api_models():
    agent = get_agent()
    models = agent.llm.list_models()
    return {"ok": True, "models": models}


@app.post("/api/llm/model")
def api_set_model(req: ModelRequest):
    """Ishlayotgan modelni jonli almashtiradi (keyingi LLM chaqiruvlarida qo'llanadi)."""
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    agent = get_agent()
    # Tanlangan model haqiqatan o'rnatilganmi tekshiramiz  -  yo'q bo'lsa xato
    # sababi UI'da ko'rinadi ("qila olmayman" kabi chalg'ituvchi xatolar yo'q).
    agent.llm.model = model
    agent._llm_checked = False  # mavjudlik qayta tekshiriladi
    _DEFAULTS["model"] = model
    return {"ok": True, "model": model, "current": agent.llm.model}


@app.get("/api/settings/speed")
def api_speed_get():
    """Universal tez rejim holati (TURBO)  --  har qanday modelga birdek."""
    agent = get_agent()
    return {"ok": True, **agent.speed_status()}


@app.post("/api/settings/speed")
def api_speed_set(req: SpeedRequest):
    """Universal tez rejimni yoqadi/o'chiradi (BIR kalit  --  barcha modellarga).

    turbo=true: kichik kontekst/token, thinking o'chiq, oddiy savollar tez
    modelga yo'naltiriladi. Sozlama xotirada saqlanadi (server restart'da
    avtomatik qayta qo'llanadi).
    """
    agent = get_agent()
    agent.set_speed(req.turbo)
    _SPEED["turbo"] = bool(req.turbo)
    _persist_speed()
    return {"ok": True, **agent.speed_status()}


@app.get("/api/llm/models/detail")
def api_models_detail():
    """Ollama'dagi modellar: nom + hajm (parametr) + quantizatsiya + GB.

    Settings → Model ro'yxatida foydalanuvchi to'g'ri model tanlashi uchun
    (8b/7b/4b/1.5b farqini ko'rib, sifat bo'yicha qaror qiladi).
    """
    agent = get_agent()
    return {"ok": True, "models": agent.llm.list_models_detailed()}


@app.post("/api/resolve")
def api_resolve(req: ResolveRequest):
    agent = get_agent()
    t0 = time.time()
    try:
        result = agent.resolve(req.query, allow_llm=req.allow_llm, use_memory=req.use_memory)
        result["api_ms"] = round((time.time() - t0) * 1000, 2)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    agent = get_agent()
    t0 = time.time()
    # session_id chat boshlanishidan OLDI aniq bo'ladi  -  jonli progress shu
    # kalit bilan frontend polling'iga ko'rinadi (chat tugaguncha).
    sid = req.session_id or f"conv-{uuid.uuid4().hex[:12]}"
    try:
        result = agent.chat(
            req.message,
            history=req.history,
            use_memory=req.use_memory,
            progress_cb=_chat_progress_cb(sid),
        )
        result["api_ms"] = round((time.time() - t0) * 1000, 2)
        # REAL chat tarixi: session_id berilsa o'sha suhbatga, aks holda yangi suhbat
        CHAT_HISTORY.add_message(sid, "user", req.message)
        warning = _structure_fail_warning(result)
        if result.get("content"):
            CHAT_HISTORY.add_message(
                sid, "assistant", str(result["content"])[:2000], warning=warning,
                # AGENTIK completion: ish yakuni konversatsiyaga to'ldiriladi
                completion=result.get("completion") or None)
        # Transcript ogohlantirishi  -  frontend javob bilan birga oladi
        # (structure_check fail bo'lsa banner ko'rsatadi; bo'sh bo'lsa kalit yo'q).
        if warning:
            result["warning"] = warning
        result["session_id"] = sid
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # chat tugadi  -  progress buferi tozalanadi (keyingi chat yangidan boshlaydi)
        _chat_progress_clear(sid)


@app.post("/api/chat/stream")
def api_chat_stream(req: ChatRequest):
    """TOKEN-USTALI chat using the canonical IgrisAgent pipeline.

    /api/chat sinxron qaytaradi; bu endpoint esa IgrisAgent.chat_stream()
    orqali shu routing, safety, verification, memory va completion
    kontraktlarini token streaming bilan qayta ishlatadi.

    SSE voqealari:
      data: {"type": "stage", "stage": "analyze", "detail": "..."}
      data: {"type": "layer_start", "layer": "planning"}
      data: {"type": "tool_start", "tool": "write_file", ...}
      data: {"type": "token", "content": "<delta>", "source": "tool_name"}
      data: {"type": "tool_done", "tool": "write_file", ...}
      data: {"type": "layer_done", "layer": "execution", ...}
      data: {"type": "final_result", "content": "...", ...}

    LayeredAgent compatibility API sifatida qoladi, lekin serverning asosiy
    chat oqimini boshqarmaydi.
    """
    from fastapi.responses import StreamingResponse
    agent = get_agent()
    t0 = time.time()
    sid = req.session_id or f"conv-{uuid.uuid4().hex[:12]}"
    progress_cb = _chat_progress_cb(sid)

    def sse(ev: dict) -> str:
        return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    def generate():
        try:
            CHAT_HISTORY.add_message(sid, "user", req.message)
            yield sse({"type": "meta", "session_id": sid})

            # IgrisAgent.chat_stream is the canonical streaming path. It owns
            # classification, safety, verification, memory, and completion.
            for ev in agent.chat_stream(
                req.message,
                history=req.history,
                use_memory=req.use_memory,
                progress_cb=progress_cb,
            ):
                if ev.get("type") == "stage":
                    progress_cb(ev.get("stage", ""), ev.get("detail", ""))
                if ev.get("type") == "done":
                    ev.setdefault("api_ms", round((time.time() - t0) * 1000, 2))
                    ev["session_id"] = sid
                    warning = _structure_fail_warning(ev)
                    if warning:
                        ev["warning"] = warning
                    if ev.get("content"):
                        CHAT_HISTORY.add_message(
                            sid, "assistant", str(ev["content"])[:2000],
                            warning=warning,
                            completion=ev.get("completion") or None)
                yield sse(ev)

            yield sse({"type": "end", "session_id": sid})
        except Exception as exc:
            yield sse({"type": "error", "error": str(exc), "session_id": sid})
        finally:
            _chat_progress_clear(sid)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class ClarifyRequest(BaseModel):
    session_id: str
    answer: str


@app.post("/api/chat/clarify")
def api_chat_clarify(req: ClarifyRequest):
    """Clarification javobi  --  layered agent clarification layer kutayotgan javob.

    Frontend clarify eventini olgandan keyin user javobini shu endpointga
    POST qiladi. Agent javobni qabul qilib, layered loopni davom ettiradi.
    """
    ok = CLARIFICATION_MANAGER.respond(req.session_id, req.answer)
    if ok:
        return {"ok": True, "message": "Clarification answer submitted"}
    # Agar sessiya topilmasa  -  ehtimol agent allaqachon davom etgan
    status = CLARIFICATION_MANAGER.get_status(req.session_id)
    if status is None:
        return {"ok": False, "message": "Session not found or already completed"}
    return {"ok": False, "message": f"Cannot submit answer in status: {status.get('status')}"}


@app.get("/api/chat/clarify/status")
def api_chat_clarify_status(session_id: str):
    """Clarification sessiyasi holati  --  frontend polling uchun."""
    status = CLARIFICATION_MANAGER.get_status(session_id)
    if status is None:
        return {"ok": True, "pending": False}
    return {
        "ok": True,
        "pending": CLARIFICATION_MANAGER.is_pending(session_id),
        "question": status.get("question"),
        "answer": status.get("answer"),
        "status": status.get("status"),
    }


@app.get("/api/chat/progress")
def api_chat_progress(session_id: str):
    """Chat run davomidagi JONLI pipeline bosqichi (frontend polling).

    /api/chat sinxron ishlayotganda frontend shu endpointni har ~1.2s so'raydi
     --  PipelineStepper real bosqichni ko'rsatadi (bezaksiz, haqiqiy progress).
    Chat tugagach bufer tozalanadi: active=false qaytadi.
    """
    with CHAT_PROGRESS_LOCK:
        p = CHAT_PROGRESS.get(session_id or "")
    if not p:
        return {"ok": True, "active": False}
    return {
        "ok": True,
        "active": True,
        "stage": p.get("stage"),
        "stage_detail": p.get("stage_detail"),
        "ts": p.get("ts"),
    }


@app.get("/api/chat/history")
def api_chat_history(limit: int = 30):
    """Real chat tarixi  --  sidebar recents va 2nd Brain grafi uchun."""
    return CHAT_HISTORY.list(max(1, min(limit, 100)))


@app.post("/api/chat/clear")
def api_chat_clear():
    """BARCHA suhbatlarni + CAG keshni tozalaydi ("oldingi natijalarni tozala").

    Part N: eski/xato natijalar (chizmalar, javoblar) chat'dan, CAG keshdan
    va 2nd Brain grafidan yo'qoladi  --  yangi so'rovlar toza holatda ishlaydi.
    Part O: workspace'dagi eski chizma/rasm fayllari ham tozalanadi.
    """
    removed = CHAT_HISTORY.clear_all().get("removed", 0)
    try:
        from agent.cag import DEFAULT_CAG
        DEFAULT_CAG.clear()
    except Exception:
        pass
    drawings_removed = _clear_workspace_drawings()
    return {"ok": True, "removed": removed, "cag_cleared": True,
            "drawings_removed": drawings_removed}


_DRAWING_EXTS = (".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                 ".ico", ".uibuild.json")


def _clear_workspace_drawings() -> int:
    """Agent workspace'dagi eski chizma/rasm fayllarini o'chiradi.

    Kod/matn fayllariga tegmaydi  --  faqat rasm kengaytmalari. Chat va kesh
    bilan birga "oldingi rasm natijalari" to'liq tozalanadi.
    """
    root = _workspace_root("")
    removed = 0
    try:
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if fname.lower().endswith(_DRAWING_EXTS):
                    try:
                        os.remove(os.path.join(dirpath, fname))
                        removed += 1
                    except OSError:
                        pass
    except OSError:
        pass
    return removed


@app.get("/api/chat/{chat_id}")
def api_chat_get(chat_id: str):
    """Bitta suhbatni to'liq qaytaradi  --  sidebar'dan chat ochilganda."""
    conv = CHAT_HISTORY.get(chat_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "conversation": conv}


@app.post("/api/chat/star")
def api_chat_star(req: ChatStarRequest):
    """Suhbatni yulduzchalaydi / yulduzchani oladi."""
    if not CHAT_HISTORY.set_starred(req.id, req.starred):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "id": req.id, "starred": req.starred}


@app.post("/api/chat/rename")
def api_chat_rename(req: ChatRenameRequest):
    """Suhbat sarlavhasini o'zgartiradi."""
    if not CHAT_HISTORY.rename(req.id, req.title):
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"ok": True, "id": req.id, "title": req.title.strip()[:80]}


@app.post("/api/chat/delete")
def api_chat_delete(req: ChatIdRequest):
    """Suhbatni tarixdan o'chiradi (idempotent  --  topilmasa ham ok)."""
    CHAT_HISTORY.delete(req.id)
    return {"ok": True, "id": req.id, "deleted": True}


@app.post("/api/memory/search")
def api_memory_search(req: MemorySearchRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False, "results": []}
    return {"ok": True, "enabled": True, **agent.memory.search(req.query, top_k=req.top_k)}


@app.get("/api/memory/status")
def api_memory_status():
    agent = get_agent()
    return {"ok": True, **agent.memory.status()}


@app.get("/api/memory/clarification-analytics")
def api_clarification_analytics():
    """Clarification tahlili  --  chastota, naqshlar, samaradorlik.

    RefactorView uchun clarification analytics ma'lumotlari:
      - total_clarifications: jami clarification soni
      - total_questions: jami savollar soni
      - avg_questions_per_session: o'rtacha savollar soni (session)
      - common_questions: eng ko'p berilgan savollar
      - common_answers: eng ko'p berilgan javoblar
    """
    agent = get_agent()
    if not agent.memory.enabled:
        return {
            "ok": True,
            "enabled": False,
            "total_clarifications": 0,
            "total_questions": 0,
            "avg_questions_per_session": 0,
            "common_questions": [],
            "common_answers": [],
        }
    try:
        analytics = agent.memory.get_clarification_analytics()
        return {"ok": True, "enabled": True, **analytics}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/brain/graph")
def api_brain_graph(shares: Optional[str] = None, max_nodes: Optional[str] = None):
    """2nd Brain knowledge graph  --  Igris_Memory'dan real ma'lumotlar.

    `shares`  --  ixtiyoriy kvota ulushlari (vergul bilan ajratilgan 4 son,
    masalan "0.30,0.30,0.20,0.20"): vault, chat, persistent, runtime.
    `max_nodes`  --  ixtiyoriy graf node chegarasi (masalan "300").
    2nd Brain sozlamalar panelidan yuboriladi; bo'lmasa DISKDA saqlangan
    (graph_shares.json) yoki default qiymatlar ishlatiladi.
    """
    from brain_graph import build_graph, normalize_shares
    parsed = None
    if shares:
        try:
            parsed = [float(x.strip()) for x in shares.split(",") if x.strip()]
        except ValueError:
            parsed = None  # noto'g'ri format  -  default ulushlar
    # Query param bo'lmasa  -  diskdagi sozlangan ulushlar (server persist).
    if parsed is None and _GRAPH_SHARES.get("shares"):
        parsed = normalize_shares(_GRAPH_SHARES["shares"])
    # max_nodes: query param -> diskdagi sozlangan -> default.
    parsed_max = None
    if max_nodes:
        parsed_max = _clamp_max_nodes(max_nodes)
    if parsed_max is None and _GRAPH_SHARES.get("max_nodes"):
        parsed_max = _clamp_max_nodes(_GRAPH_SHARES["max_nodes"])
    return build_graph(
        max_nodes=parsed_max if parsed_max else _GRAPH_MAX_NODES_DEFAULT,
        shares=parsed if parsed else None,
    )


class GraphSharesRequest(BaseModel):
    """2nd Brain graf sozlamalari  --  kvota ulushlari + node chegarasi.

    Ikkala maydon ham ixtiyoriy: berilmagani joriy qiymatini saqlaydi
    (qisman yangilash  --  masalan faqat max_nodes o'zgartirilsa, ulushlar
    buzilmaydi).
    """
    shares: Optional[list] = None
    max_nodes: Optional[int] = None


def _graph_shares_response() -> dict:
    """GET/POST uchun umumiy javob  --  ulushlar + max_nodes + o'zgarish tarixi."""
    from brain_graph import DEFAULT_SHARES, normalize_shares
    saved = _GRAPH_SHARES.get("shares")
    return {
        "ok": True,
        "shares": normalize_shares(saved) if saved else list(DEFAULT_SHARES),
        "max_nodes": _GRAPH_SHARES.get("max_nodes") or _GRAPH_MAX_NODES_DEFAULT,
        "updated_at": _GRAPH_SHARES.get("updated_at"),
        "history": _GRAPH_SHARES.get("history") or [],
    }


@app.get("/api/brain/graph/shares")
def api_brain_shares_get():
    """Saqlangan graf sozlamalari + o'zgarish tarixi (default bo'lsa default'lar)."""
    return _graph_shares_response()


@app.post("/api/brain/graph/shares")
def api_brain_shares_set(req: GraphSharesRequest):
    """Graf sozlamalarini diskda saqlaydi  --  keyingi yuklanishda qo'llaniladi.

    Har bir o'zgarish tarixga yoziladi (ts + shares + max_nodes)  --  qachon,
    qaysi qiymatga o'zgargani graph_shares.json'da kuzatiladi. Berilmagan
    maydon joriy qiymatini saqlaydi (qisman yangilash mumkin).
    """
    from brain_graph import normalize_shares
    if req.shares is None and req.max_nodes is None:
        return _graph_shares_response()  # hech narsa o'zgartirilmagan
    shares = normalize_shares(req.shares) if req.shares is not None \
        else _GRAPH_SHARES.get("shares")
    max_nodes = _clamp_max_nodes(req.max_nodes) if req.max_nodes is not None \
        else _GRAPH_SHARES.get("max_nodes")
    _persist_graph_shares(shares, max_nodes=max_nodes)
    return _graph_shares_response()


@app.get("/api/brain/graph/version")
def api_brain_graph_version():
    """Graf manbalari versiyasi  --  FAQAT SEZILARLI o'zgarishlar uchun engil fingerprint.

    Frontend har ~8 soniyada SHU endpoint'ni so'raydi (grafikni emas)  --  grafik
    faqat mazmunli o'zgarishda qayta yuklanadi:
      - yangi vault .md / L2 xotira yozuvi / yangi xotira fayli (yangi modul)
      - yangi suhbat ochildi / o'chirildi / nomi o'zgardi
    L1 runtime'ga doimiy yozishlar va mavjud suhbatga xabarlar versiyani
    o'zgartirmaydi  --  2nd Brain chat davomida 'sakrab' qayta yuklanmaydi,
    turg'un turadi (noqulaylik va 'fake' holatlar yo'q).

    `reason`  --  so'nggi SEZILARLI o'zgarish sababi ("yangi xotira moduli:
    ...", "yangi suhbat: ..."); o'zgarish bo'lmasa null. Frontend graf nega
    yangilanganini shu maydondan ko'rsatadi (real sabab, bezaksiz).

    `changed_at`  --  so'nggi SEZILARLI o'zgarish ANIQLANGAN vaqt (epoch
    sekund; real fayl o'zgarishi vaqtiga poll oralig'i (~8s) gacha yaqin).
    O'zgarishsiz poll'lar eski vaqtni saqlaydi, hech o'zgarish bo'lmagan
    bo'lsa null (graf qachondan beri turg'un  --  frontend ko'rsatadi).
    """
    from brain_graph import graph_version_fingerprint
    digest, sources, reason, changed_at = graph_version_fingerprint()
    return {"ok": True, "version": digest, "sources": sources,
            "reason": reason, "changed_at": changed_at}


@app.post("/api/session/start")
def api_session_start(req: SessionRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False}
    return {"ok": True, **agent.memory.start_session(req.session_id)}


@app.post("/api/session/end")
def api_session_end(req: SessionRequest):
    agent = get_agent()
    if not agent.memory.enabled:
        return {"ok": True, "enabled": False}
    return {"ok": True, **agent.memory.end_session(req.summary)}


@app.post("/api/session/cleanup")
def api_session_cleanup():
    """ESKI SESSIYALARNI TO'LIQ TOZALAYDI (chat tarixi + xotira + run'lar).

    Nima tozalanadi:
      1. chat_history.jsonl  --  30 kundan eski suhbatlar (eng so'nggi 20 ta + yulduzchalar saqlanadi)
      2. L1 runtime xotira  --  muddati o'tgan yozuvlar (cleanup_expired)
      3. L2 persistent  --  eskirgan yozuvlar arxivga/ochirish (cleanup_stale)
      4. tugagan agent run'lar (1 soatdan eski done/error)  --  xotira tozalanadi
      5. CHAT_PROGRESS buferi  --  eski (10 daqiqadan katta) yozuvlar

    Qaytaradi: batafsil hisobot {chat, runtime, persistent, runs, progress, ...}
    """
    report: dict = {"ok": True}

    # 1. Chat tarixi  -  eski suhbatlarni kesamiz
    report["chat"] = CHAT_HISTORY.prune(days=30, keep=20)

    # 2-3. Xotira (L1 runtime + L2 persistent)
    agent = get_agent()
    report["memory_enabled"] = agent.memory.enabled
    if agent.memory.enabled and getattr(agent.memory, "manager", None) is not None:
        mgr = agent.memory.manager
        try:
            if hasattr(mgr, "runtime") and hasattr(mgr.runtime, "cleanup_expired"):
                report["runtime_removed"] = mgr.runtime.cleanup_expired()
        except Exception as exc:
            report["runtime_error"] = str(exc)
        try:
            if hasattr(mgr, "persistent") and hasattr(mgr.persistent, "cleanup_stale"):
                report["persistent"] = mgr.persistent.cleanup_stale(archive_days=30, delete_days=90)
        except Exception as exc:
            report["persistent_error"] = str(exc)

    # 4. Tugagan agent run'lar  -  eski sessiya qoldiqlari
    report["runs_pruned"] = RUN_MANAGER.prune_finished(older_than_seconds=3600)

    # 5. CHAT_PROGRESS buferi  -  eski yozuvlar
    with CHAT_PROGRESS_LOCK:
        stale = [k for k, v in CHAT_PROGRESS.items() if time.time() - (v.get("ts") or 0) > 600]
        for k in stale:
            CHAT_PROGRESS.pop(k, None)
    report["progress_pruned"] = len(stale)

    report["timestamp"] = time.time()
    return report


# ------------------------------------------------------------------ #
# Human-in-the-loop run manager
# ------------------------------------------------------------------ #

class RunManager:
    """Agent run'larini fon thread'ida bajaradi; HITL savollarini to'playdi.

    Oqim:
      1. start(task) -> run_id  (thread ishga tushadi)
      2. agent request_human chaqirsa -> provider bloklanadi, savol saqlanadi
      3. frontend GET /api/agent/run/{id} -> status: awaiting_human + question
      4. frontend POST /api/agent/respond -> answer queue'ga tushadi
      5. agent davom etadi, yakuniy natija saqlanadi
    """

    def __init__(self, max_concurrent: int = 1,
                 runner: Optional[Callable[..., None]] = None):
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # Phase 4 (§15): run_id -> cancel Event — cancel endpoint event'ni set()
        # qiladi; executor har step/iteration boshida event'ni tekshiradi va
        # Graceful to'xtaydi (checkpoint saqlanadi — keyinroq resume mumkin).
        self._cancel_events: dict[str, threading.Event] = {}
        # Roadmap v2 C4 (§15 right-sizing): FIFO task queue — bir vaqtda
        # max_concurrent ta run ishlaydi (default 1), ortiqchalari "queued"
        # holatda navbatda kutadi. `runner` — DI nuqtasi (test/stublar uchun):
        # berilsa, real _run() o'rniga chaqiriladi va runner to'liq siklni
        # boshqaradi (tugagach _on_run_finished(run_id) chaqirishi SHART).
        self._max_concurrent = max(1, int(max_concurrent))
        self._queue: deque[tuple] = deque()   # FIFO: (run_id, launch_fn)
        self._active: set = set()             # hozir ishlayotgan run_id'lar
        self._runner = runner

    def start(self, task: str, workspace_root: str, max_iter: int = 8,
              system: Optional[str] = None, allow_human: bool = True,
              session_id: str = "") -> str:
        run_id = uuid.uuid4().hex[:12]
        state = {
            "id": run_id,
            "status": "running",
            "question": None,
            "result": None,
            "error": None,
            "answers": queue.Queue(),
            "task": task,
            "started_at": time.time(),
            "session_id": session_id or f"conv-{uuid.uuid4().hex[:12]}",
            # REAL pipeline progress  -  executor progress_cb orqali jonli yangilanadi.
            "stage": "plan",
            "stage_detail": "task tahlil qilinmoqda…",
            "last_tool": None,
            "tool_count": 0,
        }
        with self._lock:
            self._runs[run_id] = state
        # ⚡ Task boshlangandayoq REAL chat tarixiga yoziladi  -  backend restart
        # bo'lsa ham task yozuvi yo'qolmaydi ("chala qolib ketgan" tasklar oldini
        # oladi). Yakuniy javob esa run tugagach qo'shiladi.
        CHAT_HISTORY.add_message(state["session_id"], "user", task)

        def _progress(stage: str, detail: str, record=None):
            """Executor'dan kelgan jonli bosqich  --  frontend polling'da ko'radi.

            record: bajarilgan tool yozuvi  --  RUN DAVOMIDA frontend chizma
            kartalarini jonli ko'rsatishi uchun `tool_calls_partial`ga qo'shiladi
            (run tugashini kutmaydi  --  real jarayonni vizual kuzatish imkoni).
            """
            state["stage"] = stage
            state["stage_detail"] = str(detail or "")[:120]
            if " → " in state["stage_detail"]:
                state["last_tool"] = state["stage_detail"].split(" → ", 1)[0]
                # Faqat HAQIQIY tool voqealari sanaladi (plan/review xabarlari emas)
                state["tool_count"] = int(state.get("tool_count") or 0) + 1
            if isinstance(record, dict) and record.get("tool"):
                # IMMUTABLE swap: har append'da YANGI ro'yxat yaratiladi  -  o'qiyotgan
                # thread (status/JSON serialize) eski snapshot'ni xavfsiz iteratsiya
                # qiladi. In-place append + parallel serialize -> "list changed size"
                # RuntimeError berishi mumkin edi (real race).
                entry = {
                    "tool": record.get("tool"),
                    "args": record.get("args") or {},
                    "result": record.get("result") or {},
                    "output_preview": str(record.get("output_preview") or "")[:300],
                }
                partial = state.get("tool_calls_partial") or []
                state["tool_calls_partial"] = (partial + [entry])[-60:]

        def _run():
            try:
                agent = get_agent()
                from executor.executor import AgentExecutor
                from skills import DEFAULT_MANAGER
                from tools.mcp_bridge import DEFAULT_BRIDGE

                if DEFAULT_BRIDGE.status()["servers"] is None or not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][mcp] bridge start: {exc}")

                cancel_ev = threading.Event()
                with self._lock:
                    self._cancel_events[run_id] = cancel_ev
                ex = AgentExecutor(
                    workspace_root=workspace_root,
                    llm=agent.llm,
                    memory=agent.memory if agent.memory.enabled else None,
                    skills=DEFAULT_MANAGER,
                    mcp=DEFAULT_BRIDGE,
                    human_provider=(lambda q: self._human_provider(state, q)) if allow_human else None,
                    max_iter=max_iter,
                    progress_cb=_progress,
                    cancel_event=cancel_ev,
                )
                result = ex.run_native(task, system=system)
                state["result"] = result
                # Phase 4 (§15): executor "cancelled" bilan yakunlagan bo'lsa —
                # run holati ham "cancelled" (done emas — frontend farqlashi kerak).
                if (result or {}).get("status") == "cancelled":
                    state["status"] = "cancelled"
                else:
                    state["status"] = "done"
                # ⚡ task yakunini REAL chat tarixiga yozamiz  -  sidebar va grafda ko'rinadi
                final = (result or {}).get("final") or (result or {}).get("status") or "done"
                CHAT_HISTORY.add_message(state["session_id"], "assistant", str(final)[:2000])
            except Exception as exc:
                state["error"] = str(exc)
                state["status"] = "error"
                CHAT_HISTORY.add_message(state["session_id"], "assistant", f"✗ ERROR  -  {str(exc)[:2000]}")
            finally:
                # Phase 4 (§15): cancel event tozalanadi (xotira o'smasligi uchun).
                with self._lock:
                    self._cancel_events.pop(run_id, None)
                # Roadmap v2 C4 (§15): FIFO queue — run tugadi, navbatdagini
                # ishga tushiramiz (recursion'ga yo'q — faqat launch).
                try:
                    self._on_run_finished(run_id)
                except Exception as exc:
                    print(f"[igris][queue] on_run_finished: {exc}")

        # Roadmap v2 C4 (§15): FIFO queue — sig'im etmasa run navbatga qo'yiladi.
        # Eski xatti-harakat (/thread darhol ishga tushadi) runner=None yo'li
        # orqali saqlanadi (backward-compatible). Default yo'lda ham navbat
        # hisoblanadi: faqat bitta run real executor thread'ini egallaydi.
        def _launch():
            t = threading.Thread(target=self._runner or _run,
                                 daemon=True, name=f"agent-run-{run_id}")
            t.start()

        self._enqueue(run_id, state, _launch)
        return run_id

    # ------------------------------------------------------------------ #
    # Roadmap v2 C4 (§15 right-sizing): FIFO TASK QUEUE
    # ------------------------------------------------------------------ #

    def _enqueue(self, run_id: str, state: dict, launch_fn: Callable[..., None]) -> None:
        """Run'ni navbatga qo'yadi yoki (sig'im bo'sh bo'lsa) darhol ishga tushiradi.

        Sig'im to'la bo'lsa: state.status = "queued", navbat FIFO tartibida
        saqlanadi; oldingi run tugaganda `_on_run_finished` navbatdagini oladi.
        """
        with self._lock:
            self._runs[run_id] = state
            if len(self._active) < self._max_concurrent:
                self._active.add(run_id)
                state["status"] = "running"
                launch_fn()
            else:
                self._queue.append((run_id, launch_fn))
                state["status"] = "queued"
                state["stage"] = "queued"
                state["stage_detail"] = \
                    f"navbatda: {len(self._queue)}-o'rinda kutmoqda…"

    def _on_run_finished(self, run_id: str) -> None:
        """Run tugaganda chaqiriladi: sig'im bo'shadi, navbatdagi keyingi run
        ishga tushadi. Runner/DI yo'lida runner oxirida bu metodi chaqirishi
        SHART; default yo'lda `_run()` finally bloki (avvaldan ulangan).
        """
        next_id = None
        launch_fn = None
        with self._lock:
            self._active.discard(run_id)
            if self._queue and len(self._active) < self._max_concurrent:
                next_id, launch_fn = self._queue.popleft()
                self._active.add(next_id)
                nxt = self._runs.get(next_id)
                if nxt is not None:
                    nxt["status"] = "running"
                    nxt["stage"] = "plan"
                    nxt["stage_detail"] = "navbatdan olindi — bajarilmoqda…"
        if launch_fn is None:
            return
        try:
            launch_fn()
        except Exception as exc:
            # Navbatdagi run ishga tushmadi — uning holatini error qilib,
            # zanjirni davom ettirish uchun yana o'zini chaqiramiz.
            with self._lock:
                st = self._runs.get(next_id)
                if st is not None:
                    st["status"] = "error"
                    st["error"] = f"queue launch failed: {exc}"
            self._on_run_finished(next_id)

    def queue_info(self) -> dict:
        """Queue holati — monitoring uchun (/api/health/metrics'ga boradi)."""
        with self._lock:
            return {
                "max_concurrent": self._max_concurrent,
                "active": len(self._active),
                "queued": len(self._queue),
                "queued_ids": [rid for rid, _ in self._queue],
            }

    def _human_provider(self, state: dict, question: str) -> str:
        """Agent savolini to'xtatadi va frontend javobini kutadi (max 15 min)."""
        state["question"] = question
        state["status"] = "awaiting_human"
        try:
            answer = state["answers"].get(timeout=900)
        except queue.Empty:
            state["question"] = None
            return "(timeout: no human answer received)"
        state["question"] = None
        return str(answer)

    def prune_finished(self, older_than_seconds: float = 3600) -> int:
        """Tugagan/error run'larni xotiradan tozalaydi (eski sessiya qoldiqlari).

        Run'lar xotirada cheksiz o'smasligi uchun: `done`/`error` holatidagi
        va belgilangan vaqtdan eski run'lar o'chiriladi. Qaytaradi: o'chirilgan
        run soni.
        """
        now = time.time()
        removed = 0
        with self._lock:
            for rid, state in list(self._runs.items()):
                if state.get("status") not in ("done", "error", "cancelled"):
                    continue
                started = state.get("started_at") or now
                if now - started > older_than_seconds:
                    self._runs.pop(rid, None)
                    removed += 1
        return removed

    def respond(self, run_id: str, answer: str) -> bool:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return False
        state["answers"].put(answer)
        return True

    # ------------------------------------------------------------------ #
    # Phase 4 (§15): CANCELLATION — run'ni tashqaridan to'xtatish.
    # ------------------------------------------------------------------ #

    def cancel(self, run_id: str) -> bool:
        """Run'ni bekor qilish signalini yuboradi (graceful).

        Event set() qilinadi — executor keyingi step/iteration boshida
        signalni ko'rib, "cancelled" holatda to'xtaydi (checkpoint
        SAQLANADI — keyinroq resume mumkin). Qaytadi: run topildimi?
        """
        with self._lock:
            state = self._runs.get(run_id)
            ev = self._cancel_events.get(run_id)
        if state is None:
            return False
        # Allaqachon tugagan run — cancel ma'nosiz (False: holat o'zgarmaydi).
        if state.get("status") in ("done", "error", "cancelled"):
            return False
        # Roadmap v2 C4: navbatdagi run — navbatdan olib tashlanadi, hech qachon
        # ishga tushmaydi (cancel event ham kerak emas).
        if state.get("status") == "queued":
            with self._lock:
                self._queue = deque((rid, fn) for rid, fn in self._queue
                                    if rid != run_id)
            state["status"] = "cancelled"
            return True
        if ev is not None:
            ev.set()
        state["cancel_requested"] = True
        # HITL kutayotgan bo'lsa — javob navbatiga to'siq qo'yamiz:
        # provider timeout'ni kutmasdan tezroq qaytishi mumkin emas, lekin
        # flag status'da ko'rinadi va javob kelganda ham cancel ustun.
        return True

    def status(self, run_id: str) -> Optional[dict]:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return None
        return {
            "id": run_id,
            "status": state["status"],
            "question": state.get("question"),
            "task": state.get("task"),
            "result": state.get("result"),
            "error": state.get("error"),
            # Real pipeline progress (frontend PipelineStepper buni ko'rsatadi).
            "stage": state.get("stage"),
            "stage_detail": state.get("stage_detail"),
            "last_tool": state.get("last_tool"),
            "tool_count": state.get("tool_count"),
            # RUN DAVOMIDA bajarilgan tool'lar  -  frontend jonli chizma kartalarini
            # shu manbadan oladi (run tugagach `result.tool_calls` to'liqroq).
            "tool_calls": state.get("tool_calls_partial") or [],
            # Phase 4 (§15): cancel so'rovi yuborilganmi (graceful to'xtash kutilmoqda).
            "cancel_requested": bool(state.get("cancel_requested")),
        }


RUN_MANAGER = RunManager()

# §15: sync executor endpointlari (/api/agent/run, /api/agent/toolrun) uchun
# umumiy navbat — bir vaqtda faqat BITA run executor'ni egallaydi. Qolganlari
# shu yerda bloklanadi (RunManager'ning FIFO navbatiga parallel: HITL yo'li).
_EXEC_SEMAPHORE = threading.Semaphore(1)


def _execution_succeeded(result: dict) -> bool:
    """Return whether an executor result proves successful completion."""
    if not isinstance(result, dict):
        return False
    if result.get("cancelled") or result.get("errors"):
        return False
    return str(result.get("status", "")).lower() in {
        "ok", "verified", "completed",
    }


# ------------------------------------------------------------------ #
# Agent execution (smart planning & execution)
# ------------------------------------------------------------------ #

def _workspace_root(req_ws: str) -> str:
    """Agent ish maydoni: berilgan yoki default (Igris_brain/agent_workspace)."""
    if req_ws:
        return req_ws
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")


@app.post("/api/agent/plan")
def api_agent_plan(req: PlanRequest):
    agent = get_agent()
    planner = TaskPlanner(llm=agent.llm)
    plan = planner.plan(req.task)
    return {"ok": True, **plan}


@app.post("/api/agent/run")
def api_agent_run(req: RunRequest):
    agent = get_agent()
    root = _workspace_root(req.workspace)
    executor = AgentExecutor(
        workspace_root=root,
        llm=agent.llm,
        memory=agent.memory if agent.memory.enabled else None,
        max_iter=req.max_iter,
    )
    try:
        # §15 (AUDIT FIX): sync run'lar ham cheklangan — parallel request'lar
        # bir vaqtda LLM/executor'ga bosmaydi (semaphore navbat beradi).
        with _EXEC_SEMAPHORE:
            result = executor.run(req.task)
        return {"ok": _execution_succeeded(result), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/queue/status")
def api_queue_status():
    """§15 Task queue holati — navbat, active, completed."""
    try:
        # AUDIT FIX: `_run_manager` degan nom YO'Q edi (NameError — endpoint
        # har doim {"ok": False} qaytardi). Global RUN_MANAGER ishlatiladi.
        rm = RUN_MANAGER
        with rm._lock:
            return {
                "ok": True,
                "queued": len(rm._queue),
                "active": len(rm._active),
                "max_concurrent": rm._max_concurrent,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/agent/toolrun")
def api_agent_toolrun(req: ToolRunRequest):
    """Native tool-calling: the LLM picks the tools itself (schema-based)."""
    agent = get_agent()
    root = _workspace_root(req.workspace)
    executor = AgentExecutor(
        workspace_root=root,
        llm=agent.llm,
        memory=agent.memory if agent.memory.enabled else None,
        max_iter=req.max_iter,
    )
    try:
        # §15: sync run'lar uchun bir xil navbat cheklovi (api_agent_run bilan).
        with _EXEC_SEMAPHORE:
            result = executor.run_native(req.task)
        return {"ok": _execution_succeeded(result), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/agent/task")
def api_agent_task(req: TaskRequest):
    """HITL agent run'ini boshlaydi (background thread). Returns run_id."""
    root = _workspace_root(req.workspace)
    run_id = RUN_MANAGER.start(req.task, root, max_iter=req.max_iter, session_id=req.session_id)
    return {"ok": True, "run_id": run_id}


@app.get("/api/agent/run/{run_id}")
def api_agent_run_status(run_id: str):
    state = RUN_MANAGER.status(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, **state}


@app.post("/api/agent/run/{run_id}/cancel")
def api_agent_run_cancel(run_id: str):
    """Phase 4 (§15): joriy run'ni bekor qilish (graceful cancellation).

    Executor keyingi checkpoint nuqtasida to'xtaydi, "cancelled" holati
    bilan yakunlanadi va checkpoint SAQLANADI (keyinroq resume mumkin).
    """
    ok = RUN_MANAGER.cancel(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found or already finished")
    return {"ok": True, "cancelled": run_id}


@app.post("/api/agent/respond")
def api_agent_respond(req: RespondRequest):
    ok = RUN_MANAGER.respond(req.run_id, req.answer)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, "delivered": True}


@app.get("/api/agent/skills")
def api_agent_skills():
    from skills import DEFAULT_MANAGER
    return {"ok": True, "skills": [
        {"name": s.name, "description": (s.description or "")[:200]}
        for s in DEFAULT_MANAGER.list()
    ]}


# ------------------------------------------------------------------ #
# Web AI Bridge (real browser automation via web_ai_bridge MCP server)
# ------------------------------------------------------------------ #

WEBAI_ACTIONS = {
    "navigate": ("web_ai_bridge__browser_navigate", ["url"]),
    "back": ("web_ai_bridge__browser_go_back", []),
    "forward": ("web_ai_bridge__browser_go_forward", []),
    "new_tab": ("web_ai_bridge__browser_new_tab", ["url"]),
    "switch_tab": ("web_ai_bridge__browser_switch_tab", ["index"]),
    "close_tab": ("web_ai_bridge__browser_close_tab", ["index"]),
    "refresh": ("web_ai_bridge__browser_press_key", ["key"]),
    "scroll_up": ("web_ai_bridge__browser_scroll", []),
    "scroll_down": ("web_ai_bridge__browser_scroll", []),
    "zoom_in": ("web_ai_bridge__browser_press_key", ["key"]),
    "zoom_out": ("web_ai_bridge__browser_press_key", ["key"]),
    "zoom_reset": ("web_ai_bridge__browser_press_key", ["key"]),
    "dismiss_overlays": ("web_ai_bridge__browser_dismiss_overlays", []),
    "page_text": ("web_ai_bridge__browser_get_text", []),
}


def _webai_bridge():
    """web_ai_bridge MCP serveri ulangan bo'lsa qaytaradi, aks holda None."""
    try:
        from tools.mcp_bridge import DEFAULT_BRIDGE
    except Exception:
        return None
    if not DEFAULT_BRIDGE.status()["servers"]:
        try:
            DEFAULT_BRIDGE.start()
        except Exception:
            pass
    servers = DEFAULT_BRIDGE.status()["servers"] or []
    if "web_ai_bridge" not in servers:
        return None
    return DEFAULT_BRIDGE


@app.get("/api/webai/status")
def api_webai_status():
    """Real web-ai-bridge holati: ulanganmi, qaysi brauzer, ochiq tablar."""
    bridge = _webai_bridge()
    if bridge is None:
        return {"ok": True, "connected": False, "tabs": [], "error": "web_ai_bridge MCP server not connected"}
    info = bridge.call_tool("web_ai_bridge__browser_info", {})
    tabs_raw = bridge.call_tool("web_ai_bridge__browser_list_tabs", {})
    tabs = []
    if tabs_raw.get("ok"):
        try:
            parsed = json.loads(tabs_raw.get("output") or "[]")
            tabs = parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            tabs = []
    browser = {"channel": None, "mode": None}
    for line in (info.get("output") or "").splitlines():
        if line.startswith("Browser:"):
            browser["channel"] = line.split(":", 1)[1].strip()
        elif line.startswith("Mode:"):
            browser["mode"] = line.split(":", 1)[1].strip()
    return {"ok": True, "connected": True, "browser": browser,
            "tabs": tabs, "info": (info.get("output") or "")[:400]}


@app.post("/api/webai/action")
def api_webai_action(req: WebAIActionRequest):
    """Whitelisted web-ai-bridge tool proxy: navigate/back/forward/new_tab/..."""
    bridge = _webai_bridge()
    if bridge is None:
        return {"ok": False, "error": "web_ai_bridge MCP server not connected"}
    if req.action not in WEBAI_ACTIONS:
        return {"ok": False, "error": f"unknown action: {req.action}"}
    tool, params = WEBAI_ACTIONS[req.action]
    args = {}
    if "url" in params and req.url:
        args["url"] = req.url
    if "index" in params:
        args["index"] = req.index
    # Yangi tab (url bo'sh) — bo'sh yangi tab ochiladi (Ctrl+T ga o'xshash)
    if req.action == "new_tab" and not req.url:
        args.pop("url", None)
    if req.action == "refresh":
        args["key"] = "F5"
    elif req.action == "scroll_up":
        args["direction"] = "up"
        args["amount_px"] = 600
    elif req.action == "scroll_down":
        args["direction"] = "down"
        args["amount_px"] = 600
    elif req.action == "zoom_in":
        args["key"] = "Control+Equal"
    elif req.action == "zoom_out":
        args["key"] = "Control+Minus"
    elif req.action == "zoom_reset":
        args["key"] = "Control+0"
    return bridge.call_tool(tool, args)


@app.get("/api/webai/screenshot")
def api_webai_screenshot(full: int = 0):
    """Aktiv tabning real PNG screenshot'i (web-ai-bridge browser_screenshot).
    full=1 — scroll qilib bo'ladigan TO'LIQ sahifani rasmga oladi."""
    from fastapi.responses import Response
    import base64 as _b64
    bridge = _webai_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="web_ai_bridge not connected")
    result = bridge.call_tool("web_ai_bridge__browser_screenshot", {"full_page": bool(full)})
    img = result.get("image") if isinstance(result, dict) else None
    if not img or not img.get("data"):
        raise HTTPException(status_code=502, detail=(result.get("output") or result.get("error") or "no screenshot"))
    try:
        raw = _b64.b64decode(img["data"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(content=raw, media_type=img.get("mimeType") or "image/png")


@app.get("/api/cag/status")
def api_cag_status():
    """CAG (response cache) holati."""
    agent = get_agent()
    cache = agent._cag()
    return {"ok": True, "enabled": cache is not None,
            "cag": cache.status() if cache else None}


@app.post("/api/cag/invalidate")
def api_cag_invalidate():
    """CAG keshini tozalash (kontekst o'zgarganda)."""
    agent = get_agent()
    cache = agent._cag()
    if cache is None:
        return {"ok": True, "cleared": 0}
    cleared = cache.invalidate()
    return {"ok": True, "cleared": cleared}


@app.get("/api/mag/status")
def api_mag_status():
    """MAG (memory-augmented context) holati."""
    agent = get_agent()
    mag = agent._mag()
    return {"ok": True, "enabled": mag is not None,
            "mag": mag.status() if mag else None}


@app.get("/api/hooks/status")
def api_hooks_status():
    """Agent hook bus holati."""
    from monitor.hooks import DEFAULT_BUS
    return {"ok": True, **DEFAULT_BUS.stats()}


@app.get("/api/agent/mcp")
def api_agent_mcp():
    from tools.mcp_bridge import DEFAULT_BRIDGE
    if not DEFAULT_BRIDGE.status()["servers"]:
        try:
            DEFAULT_BRIDGE.start()
        except Exception as exc:
            return {"ok": True, "connected": False, "error": str(exc)}
    st = DEFAULT_BRIDGE.status()
    return {"ok": True, "connected": bool(st["servers"]), "servers": st["servers"],
            "tools": st["tools"], "error": st["error"]}


@app.get("/api/agent/tools")
def api_agent_tools():
    from tools import DEFAULT_REGISTRY
    return {"ok": True, "tools": [t["name"] for t in DEFAULT_REGISTRY.schemas()]}


@app.get("/api/agent/state")
def api_agent_state():
    """Agent real-time holati — frontend status panel uchun.
    
    Returns:
      - state: idle/thinking/planning/executing/verifying/error/paused
      - capabilities: available agent capabilities
      - task_queue: current task queue
      - completed_today: tasks completed today
      - auto_mode: automatic mode status
    """
    agent = get_agent()
    
    # Determine agent state based on current activity
    current_state = "idle"
    current_task = None
    current_step = None
    
    # Check if there's an active run
    try:
        from executor.executor import RUN_MANAGER
        active_runs = RUN_MANAGER.active_runs() if hasattr(RUN_MANAGER, 'active_runs') else []
        if active_runs:
            current_state = "executing"
            current_task = active_runs[0].get('task', '') if isinstance(active_runs[0], dict) else str(active_runs[0])
    except Exception:
        pass
    
    # Check circuit breaker state
    if _CIRCUIT.state == "open":
        current_state = "error"
    elif _CIRCUIT.state == "half_open":
        current_state = "verifying"
    
    # Get capabilities from tools registry
    capabilities = []
    try:
        from tools import DEFAULT_REGISTRY
        tools = DEFAULT_REGISTRY.schemas()
        capability_map = {
            'code_write': {'icon': '💻', 'description': 'Kod yozish va tahrirlash', 'tools': ['write_file', 'edit_file', 'create_file']},
            'code_read': {'icon': '📖', 'description': 'Fayllarni o\'qish va tahlil qilish', 'tools': ['read_file', 'list_files', 'search_code']},
            'file_management': {'icon': '📁', 'description': 'Fayl tizimini boshqarish', 'tools': ['read_file', 'write_file', 'list_files', 'run_command']},
            'web_research': {'icon': '🌐', 'description': 'Web\'dan ma\'lumot olish', 'tools': ['web_search', 'web_browse', 'fetch_url']},
            'draw': {'icon': '🎨', 'description': 'SVG rasm chizish', 'tools': ['use_skill']},
            'shell': {'icon': '⚡', 'description': 'Buyruq satri amallari', 'tools': ['run_command']},
            'data_analysis': {'icon': '📊', 'description': 'Ma\'lumotlarni tahlil qilish', 'tools': ['run_command']},
            'skill_use': {'icon': '🧩', 'description': 'Maxsus ko\'nikmalardan foydalanish', 'tools': ['use_skill']},
        }
        
        tool_names = [t['name'] for t in tools]
        for cap_name, cap_info in capability_map.items():
            enabled = any(t in tool_names for t in cap_info['tools'])
            capabilities.append({
                'name': cap_name,
                'icon': cap_info['icon'],
                'description': cap_info['description'],
                'enabled': enabled,
                'tools': [t for t in cap_info['tools'] if t in tool_names],
            })
    except Exception:
        pass
    
    # Get task queue stats
    task_queue = []
    completed_today = 0
    try:
        from server_chat_history import CHAT_HISTORY
        # Count completions from today
        import datetime
        today = datetime.date.today().isoformat()
        for session in CHAT_HISTORY._sessions.values():
            if hasattr(session, 'messages') and session.messages:
                for msg in session.messages:
                    if hasattr(msg, 'ts') and msg.ts:
                        msg_date = datetime.datetime.fromtimestamp(msg.ts).date().isoformat()
                        if msg_date == today and hasattr(msg, 'completion') and msg.completion:
                            completed_today += 1
    except Exception:
        pass
    
    # Get memory stats
    memory_entries = 0
    try:
        if hasattr(agent, 'memory') and agent.memory:
            memory_entries = getattr(agent.memory, 'total_entries', 0)
    except Exception:
        pass
    
    return {
        "ok": True,
        "state": current_state,
        "current_task": current_task,
        "current_step": current_step,
        "capabilities": capabilities,
        "task_queue": task_queue,
        "completed_today": completed_today,
        "tools_available": len(tool_names) if 'tool_names' in dir() else 0,
        "memory_entries": memory_entries,
        "uptime_seconds": int(time.time() - _SERVER_START_TIME),
        "auto_mode": False,  # Will be managed by frontend
    }


@app.post("/api/agent/drawing/edit")
def api_drawing_edit(req: DrawingEditRequest):
    """Pauza qilingan chizmaga surgikal o'zgartirish kiritadi.

    Agent frozen kontekstni oladi (qaysi elementlar allaqachon chizilgan) va
    faqat kerakli qismlarni o'zgartiradi, qolganini buzmaydi. Asinxron run
     --  run_id qaytariladi, frontend /api/agent/run/{id} orqali poll qiladi.
    """
    root = _workspace_root(req.workspace)
    from tools import Workspace
    ws = Workspace(root)
    try:
        abs_path = ws.resolve(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"file not found: {req.path}")

    frozen = req.frozen or {}
    drawn = frozen.get("revealed", 0)
    total = frozen.get("total", 0)
    elements = frozen.get("elements", []) or []
    task = (
        f"Modify the drawing file '{req.path}' in the workspace.\n"
        f"Context: the user paused the live build after {drawn}/{total} elements "
        f"were drawn. Elements already visible: {', '.join(str(e) for e in elements[:12]) or 'n/a'}.\n"
        f"User's change request: {req.request}\n"
        "Apply the change surgically  -  keep everything that does not need to change "
        "identical, change only what the request requires, keep the style consistent."
    )
    run_id = RUN_MANAGER.start(task, root, max_iter=10, system=DRAWING_EDIT_SYSTEM, allow_human=False)
    return {"ok": True, "run_id": run_id}


@app.get("/api/ui/compose")
def api_ui_compose(app_name: str = "dashboard", theme: str = "dark"):
    """UI spec -> universal kompozitsiya rejasi (qavatlar + exec_order + overlap).

    'Detal-ma-detal qurish' texnologiyasining PLANNING bosqichi: barcha
    elementlar rejada aniqlanadi, qavatlar (layers) hisoblanadi, bosh menyu
    kontentga xalaqit qilmaydimi tekshiriladi, g'isht (brick) qayta ishlatish
    tahlil qilinadi. Frontend LIVE BUILD puzzle tartibi uchun ishlatadi.
    """
    from ui.ui_compose import compose_app
    try:
        plan = compose_app(app_name, theme)
        return {"ok": True, **plan}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/agent/workspace")
def api_agent_workspace(ws: str = ""):
    from tools import Workspace
    root = _workspace_root(ws)
    ws_obj = Workspace(root)
    listing = ws_obj.list("", depth=2)
    return {"ok": True, "root": root, **listing}


@app.get("/api/agent/workspace/file")
def api_agent_workspace_file(path: str, ws: str = ""):
    """Serve a workspace file (text or image) to the UI preview.

    Path traversal himoyasi: fayl faqat workspace root ichida bo'lishi mumkin.
    """
    from fastapi.responses import FileResponse
    from tools import Workspace
    root = _workspace_root(ws)
    ws_obj = Workspace(root)
    try:
        abs_path = ws_obj.resolve(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"file not found: {path}")

    # Content-Type: rasm va matn fayllari uchun
    ext = os.path.splitext(abs_path)[1].lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".py": "text/x-python; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".yaml": "text/yaml; charset=utf-8",
        ".yml": "text/yaml; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".ts": "text/plain; charset=utf-8",
        ".tsx": "text/plain; charset=utf-8",
        ".jsx": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".log": "text/plain; charset=utf-8",
    }
    media_type = media.get(ext, "application/octet-stream")
    return FileResponse(
        abs_path,
        media_type=media_type,
        filename=os.path.basename(abs_path),
        content_disposition_type="inline",
    )


# ------------------------------------------------------------------ #
# Decision-quality probe (real agent runs -> reasoning scores)
# ------------------------------------------------------------------ #

class ProbeRequest(BaseModel):
    tasks: str = "all"   # all | code_csv,multi_notes,draw_apple,fix_code


class ProbeManager:
    """Probe'ni fon thread'ida ishga tushiradi; status'ni saqlaydi.

    Oqim:
      1. POST /api/probe/run -> run_id (thread ishga tushadi)
      2. GET /api/probe/run/{id} -> status: running + bajarilgan tasklar
      3. tugagach report JSON'ga yoziladi, GET /api/probe/report dan o'qiladi
    """

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, tasks: str = "all") -> str:
        run_id = uuid.uuid4().hex[:12]
        state = {
            "id": run_id,
            "status": "running",
            "tasks": tasks,
            "completed": [],
            "report": None,
            "error": None,
        }
        with self._lock:
            self._runs[run_id] = state

        def _run():
            try:
                from monitor.probe_decisions import run_probe
                from tools.mcp_bridge import DEFAULT_BRIDGE
                agent = get_agent()

                # Mavjud bridge'ni ishlatamiz  -  yangi McpBridge yaratilmaydi
                if not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][probe] mcp start: {exc}")
                bridge = DEFAULT_BRIDGE if DEFAULT_BRIDGE.status()["servers"] else None

                def progress(task_id: str, status: str):
                    if status == "done" and task_id not in state["completed"]:
                        state["completed"].append(task_id)

                report = run_probe(
                    model=agent.llm.model,
                    base_url=agent.llm.base_url,
                    tasks=tasks,
                    progress=progress,
                    bridge=bridge,
                )
                state["report"] = report
                state["status"] = "done"
            except Exception as exc:
                state["error"] = str(exc)
                state["status"] = "error"

        t = threading.Thread(target=_run, daemon=True, name=f"probe-run-{run_id}")
        t.start()
        return run_id

    def status(self, run_id: str) -> Optional[dict]:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            return None
        return {k: state.get(k) for k in ("id", "status", "tasks", "completed", "error", "report")}


PROBE_MANAGER = ProbeManager()


# ------------------------------------------------------------------ #
# Refactor Machine (assessment / telemetry / query evaluation)
# ------------------------------------------------------------------ #

class AssessRequest(BaseModel):
    query: str
    lang: str = "en"


@app.get("/api/refactor/standards")
def api_refactor_standards():
    """Baholash standarti (4 o'lchov, og'irliklar, chegaralar)."""
    agent = get_agent()
    return {"ok": True, "standard": agent.refactor.standards()}


@app.get("/api/refactor/report")
def api_refactor_report():
    """To'liq refactor hisoboti: inventory, tasniflar, aloqalar, telemetry."""
    agent = get_agent()
    return {"ok": True, **agent.refactor.refactor_report()}


@app.get("/api/refactor/telemetry")
def api_refactor_telemetry():
    """Jarayon telemetry: stats + oxirgi snapshotlar trendi."""
    agent = get_agent()
    return {
        "ok": True,
        "stats": agent.refactor.telemetry.stats(),
        "trend": agent.refactor.telemetry.trend(limit=20),
    }


@app.post("/api/refactor/assess")
def api_refactor_assess(req: AssessRequest):
    """So'rovni baholaydi: query semantikasi + resolution + telemetry snapshot."""
    agent = get_agent()
    query = (req.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    return {"ok": True, **agent.refactor.evaluate_query(query, lang=req.lang)}


@app.post("/api/probe/run")
def api_probe_run(req: ProbeRequest):
    """Decision-quality probe'ni fon thread'ida boshlaydi. Returns run_id."""
    run_id = PROBE_MANAGER.start(tasks=req.tasks or "all")
    return {"ok": True, "run_id": run_id}


@app.get("/api/probe/run/{run_id}")
def api_probe_run_status(run_id: str):
    state = PROBE_MANAGER.status(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True, **state}


@app.get("/api/probe/report")
def api_probe_report():
    """Eng so'nggi probe hisoboti (decision_probe.json)  --  UI'ga beradi."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "decision_probe.json")
    if not os.path.isfile(path):
        return {"ok": True, "exists": False, "report": None}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            report = json.load(fh)
        return {"ok": True, "exists": True, "report": report}
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "exists": False, "error": str(exc), "report": None}


# ---------------------------------------------------------------------- #
# System services  -  UI'dan backend / ollama / frontend restart qilish
# ---------------------------------------------------------------------- #

@app.get("/api/system/services")
def api_system_services():
    """Xizmatlar holati: backend (o'zi), ollama, MCP serverlar.

    S3 (2026-09-12): `degradations` — silent fallbacklar registrysi.
    Komponent jim zaiflashgan rejimga o'tsa (FTS5→BM25, MCP→no-tools,
    CAG→no-cache...), bu yerda ko'rinadi. `active` — so'nggi 10 daqiqada
    mark qilinganlar (eski yozuvlar tarix sifatida qoladi).
    """
    mcp = {"connected": False, "servers": []}
    try:
        from tools.mcp_bridge import DEFAULT_BRIDGE
        st = DEFAULT_BRIDGE.status()
        mcp = {"connected": bool(st.get("servers")), "servers": st.get("servers") or []}
    except Exception:
        pass
    degradations: list[dict] = []
    try:
        from monitor.degradation import report, active_older_than
        degradations = report()
        active = active_older_than(600.0)
        if active:
            mcp["degraded"] = True  # UI'da to'g'ridan-to'g'ri flag
    except Exception:
        active = []
    return {
        "ok": True,
        "backend": {"running": True, "host": _proc._RUN_HOST, "port": _proc._RUN_PORT, "version": app.version},
        "ollama": {"running": _ollama_running()},
        # Watchdog holati  -  backend qulab tushsa uni avtomatik qayta ishga
        # tushiradigan qo'riqchi jarayon (UI'da ko'rsatiladi).
        "watchdog": _watchdog_state(),
        "mcp": mcp,
        # S3: silent-degradation registry (barcha tarix + faol flag)
        "degradations": degradations,
        "degradations_active": len(active),
        "timestamp": time.time(),
    }


@app.post("/api/system/degradations/clear")
def api_system_degradations_clear():
    """S3: silent-degradation registry tozalash (UI Settings→Services 'clear' tugmasi)."""
    try:
        from monitor.degradation import clear
        n = clear()
        return {"ok": True, "cleared": n}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/system/restart")
def api_system_restart():
    """Backend'ni o'zini qayta ishga tushiradi (asl sozlamalari bilan).

    Javob darhol qaytadi; ~1 soniyadan so'ng yangi jarayon ochiladi va
    agent'ni muvaffaqiyatli boshlagach (marker handshake) eski jarayon
    tugatiladi. Yangi jarayon qulab tushsa  --  eski jarayon ishlashda davom
    etadi (soxta restart yo'q, backend o'lik qolmaydi). Frontend ping orqali
    qayta ulanishni kutadi.
    """
    def _restart():
        time.sleep(1.0)
        token = uuid.uuid4().hex[:12]
        proc = None
        try:
            # Yangi server jarayoni log'larini ham saqlaymiz (oyna yo'q,
            # lekin xato bo'lsa logs/server.log.da ko'rinadi). Popen handle'i
            # saqlanadi  -  marker'dan tashqari jarayon tirikligi ham tekshiriladi.
            proc = _spawn_detached(
                "IGRIS Brain Server",
                _server_start_command(restart_token=token),
                os.path.dirname(os.path.abspath(__file__)),
                # Kanonik log: Igris_brain/logs/server.log (run.bat bilan bir xil —
                # har qanday yo'l bilan ishga tushgan backend bitta joyga yozadi).
                log_file=os.path.join(_proc._LOGS_DIR, "server.log"),
            )
        except Exception as exc:
            print(f"[igris][system] restart spawn failed: {exc}")
        # Yangi jarayon ochilgan bo'lsagina uni KUTAMIZ  -  faqat agent'ni to'liq
        # boshlagach (marker fayl yozilgach) eskisini tugatamiz. Marker 60s ichida
        # kelmasa YOKI yangi jarayon o'lib qolsa (proc.poll() is not None)  -  eski
        # jarayon yashab qoladi, backend o'lik qolib ketmaydi (soxta restart yo'q).
        if proc is not None:
            deadline = time.time() + 60.0
            while time.time() < deadline:
                # Yangi jarayon import/agent bosqichida qulab tushgan  -  marker
                # yozilgan bo'lsa ham eskisini o'ldirmaymiz (backend o'lik qolmasin).
                if proc.poll() is not None:
                    print(
                        "[igris][system] yangi jarayon erta chiqib ketdi "
                        f"(exit={proc.poll()})  -  eski jarayon ishlashda davom etadi. "
                        "Log: logs/server.log"
                    )
                    return
                if os.path.isfile(_restart_marker_path(token)):
                    try:
                        os.unlink(_restart_marker_path(token))
                    except OSError:
                        pass
                    os._exit(0)
                    return
                time.sleep(0.5)
            print(
                "[igris][system] restart TIMEOUT  -  yangi server ishga tushmadi, "
                "eski jarayon ishlashda davom etadi. Log: logs/server.log"
            )

    threading.Thread(target=_restart, daemon=True, name="system-restart").start()
    return {"ok": True, "restarting": True, "port": _proc._RUN_PORT}


@app.post("/api/system/ollama/start")
def api_system_ollama_start():
    """Ollama serve'ni ishga tushiradi (agar ishlamayotgan bo'lsa).

    Yangi oyna ochilmaydi  --  jarayon fon rejimida, log'lari
    Igris_brain/logs/ollama.log fayliga yoziladi.
    """
    if _ollama_running():
        return {"ok": True, "running": True, "started": False, "note": "already running"}
    try:
        _spawn_detached(
            "IGRIS Ollama", "ollama serve", os.path.expanduser("~"),
            log_file=os.path.join(_proc._LOGS_DIR, "ollama.log"),
        )
        return {"ok": True, "started": True, "note": "ollama serve started (hidden)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/system/ollama/restart")
def api_system_ollama_restart():
    """Ollama'ni qayta ishga tushiradi: eski jarayonni to'xtatib, yana ochadi.

    UI'dagi '⟳ restart' tugmasi buni chaqiradi. Windows'da port 11434 dagi
    jarayon topilib o'ldiriladi, so'ng `ollama serve` yangi, oynasiz
    jarayon sifatida qayta ochiladi.
    """
    if _ollama_running():
        _kill_port(11434)
        # Port bo'shashini kutamiz (max ~5s)
        for _ in range(10):
            if not _ollama_running(timeout=0.5):
                break
            time.sleep(0.5)
    try:
        _spawn_detached(
            "IGRIS Ollama", "ollama serve", os.path.expanduser("~"),
            log_file=os.path.join(_proc._LOGS_DIR, "ollama.log"),
        )
        time.sleep(0.8)
        return {"ok": True, "running": _ollama_running(timeout=2.0), "started": True,
                "note": "ollama serve restarted (hidden)"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _port_pids(port: int) -> set[str]:
    """Berilgan portda LISTENING qilayotgan jarayon PIDs (Windows netstat)."""
    pids: set[str] = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout or ""
        for line in out.splitlines():
            if f":{port} " not in line:
                continue
            if "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    except Exception:
        pass
    return pids


def _kill_port(port: int) -> bool:
    """Portni egallagan jarayon(lar)ni to'xtatadi (Ollama restart uchun)."""
    killed = False
    for pid in _port_pids(port):
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", pid],
                capture_output=True, timeout=10,
            )
            killed = True
        except Exception:
            pass
    return killed


# ---------------------------------------------------------------------- #
# Entrypoint
# ---------------------------------------------------------------------- #

def main() -> int:
    # Kutilmagan xatolar log'ga yoziladi (watchdog sababni topa oladi)
    _install_fatal_handlers()
    parser = argparse.ArgumentParser(description="IGRIS Brain FastAPI bridge")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--model", default=os.environ.get("IGRIS_MODEL", "qwen3:8b"))
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--no-llm", action="store_true", help="disable Ollama fallback")
    parser.add_argument("--no-memory", action="store_true", help="disable Igris_Memory")
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--logprobs", action="store_true",
                        help="LLM javoblari uchun OpenAI-mos logprob re-so'ruvi "
                             "(self-eval ishonch signali; 2x inference narxi)")
    parser.add_argument("--restart-token", default="", help=argparse.SUPPRESS)  # noqa: E501
    # Eslatma: default="" (SUPPRESS emas)  --  flag berilmasa ham atribut mavjud bo'ladi.
    args = parser.parse_args()
    # Restart'da saqlanadigan asl flaglar. --host/--port VA ularning qiymatlari
    # tashlanadi (aks holda eski port qiymati "--port 9999" restart komandasida
    # qolib, argparse xatosi bilan yangi server o'lib qolardi).
    extra_args: list[str] = []
    argv = list(sys.argv[1:])
    i = 0
    while i < len(argv):
        a = argv[i]
        # --host=X / --port=X ko'rinishi ham tashlanadi (argparse ikkala
        # usulni qabul qiladi  --  restart komandasi dublikat flag olmasin).
        if a in ("--host", "--port") or a.startswith(("--host=", "--port=")):
            i += 2 if "=" not in a else 1  # flag + qiymatini o'tkazib yuboramiz
            continue
        if a == "--restart-token" or a.startswith("--restart-token="):
            i += 2 if "=" not in a else 1
            continue
        extra_args.append(a)
        i += 1

    _proc.configure(
        server_path=os.path.abspath(__file__),
        host=args.host or _proc._RUN_HOST,
        port=args.port or _proc._RUN_PORT,
        extra_args=extra_args,
    )

    create_agent(
        model=args.model,
        base_url=args.base_url,
        use_llm=not args.no_llm,
        memory=not args.no_memory,
        memory_dir=args.memory_dir,
        logprobs=args.logprobs,
    )
    # Diskdagi TURBO sozlamasini qayta qo'llaymiz (restart'da yo'qolmaydi)
    _load_speed()
    if _SPEED.get("turbo"):
        get_agent().set_speed(True)
        print("[igris] speed: turbo=on (restored from speed_settings.json)")
    # 2nd Brain graf sozlamalarini diskdan yuklaymiz (restart'da yo'qolmaydi)
    _load_graph_shares()
    saved_shares = _GRAPH_SHARES.get("shares")
    saved_max = _GRAPH_SHARES.get("max_nodes")
    if saved_shares or saved_max:
        print(f"[igris] brain graph settings restored: shares={saved_shares} max_nodes={saved_max}")
    print(f"[igris] agent ready: model={args.model} llm={not args.no_llm} memory={not args.no_memory}")
    print(f"[igris] listening on http://{args.host}:{args.port}")
    # Health monitor  --  agent sog'lig'ini fon'da kuzatadi
    _start_health_monitor()
    # Restart jarayonida bo'lsak  --  agent muvaffaqiyatli boshlangani marker fayl
    # orqali eski jarayonga xabar beriladi (u shundan keyin o'zini tugatadi).
    # Marker create_agent'dan KEYIN, port kutishdan OLDI yoziladi  --  yangi server
    # portni eski jarayon bo'shatgach bog'laydi; eski jarayon marker ko'rishi bilan
    # chiqadi (hech qanday deadlock yo'q). Agar create_agent qulab tushsa marker
    # yozilmaydi va eski jarayon ishlashda davom etadi.
    if args.restart_token:
        _write_restart_marker(args.restart_token)
    # Watchdog'ga restart komandasini yozamiz  --  backend qulab tushsa uni
    # xuddi shu sozlamalar bilan qayta ochadi ("birdan offline" oldini oladi).
    _persist_launch_info()
    # Restart'da eski jarayon portni bo'shatishini kutamiz  --  yangi server
    # "address already in use" xatosiz ishga tushadi (UI restart ishonchli).
    if _port_in_use(args.port):
        print(f"[igris] port {args.port} band  --  bo'shatilishini kutmoqda… (restart)")
        _wait_port_free(args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
