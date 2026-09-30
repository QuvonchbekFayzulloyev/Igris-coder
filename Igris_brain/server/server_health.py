"""
IGRIS BRAIN — ServerHealth — S5 modullashtirish
================================================
problems_to_fix.md :: S5 (qism) — server.py god-file'dan ajratilgan.

Health metrikalari (monitoring dashboard):
  _METRICS_MAX_ENTRIES / _metrics_history / _metrics_lock
                                      — ring buffer (60 daqiqa tarix)
  record_metrics(metrics)             — tarixga yozish
  metrics_snapshot(limit)             — lock ostida nusxa olish
  metrics_history_size()              — jami yozuvlar soni
  collect_health_metrics(...)         — to'liq metrika yig'uvchi (DI paramlar)

collect_health_metrics TASHQI HOLATNI DI (dependency injection) orqali oladi:
  agent, server_start_time, circuit, chat_progress(+lock), chat_history.
Shu tufayli bu modul FastAPI/agent modullariga bog'liq emas (import tsikli yo'q)
va birlik testlarda soxta holat bilan chaqirilishi mumkin.

BUGFIX (S5 audit): uptime avval `'_SERVER_START_TIME' in dir()` bilan tekshirilar
edi — funksiya ichida dir() faqat lokal nomlarni qaytargani uchun uptime doim
~0 edi. Endi server_start_time argument sifatida uzatiladi.

Bu modul FAQAT stdlib'dan foydalanadi — server.py import qilib qayta eksport
qiladi (eski ichki nomlar kontrakti saqlanadi).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

__all__ = [
    "_METRICS_MAX_ENTRIES", "_metrics_history", "_metrics_lock",
    "record_metrics", "metrics_snapshot", "metrics_history_size",
    "collect_health_metrics",
]

# Metrics tarixi: oxirgi N ta yozuv (ring buffer). Har 30 soniyada yangilanadi.
_METRICS_MAX_ENTRIES = 120  # 30s * 120 = 60 daqiqa tarix
_metrics_history: list[dict] = []
_metrics_lock = threading.Lock()


def record_metrics(metrics: dict) -> None:
    """Metrikalarni tarixga yozadi (ring buffer)."""
    with _metrics_lock:
        _metrics_history.append(metrics)
        if len(_metrics_history) > _METRICS_MAX_ENTRIES:
            _metrics_history.pop(0)


def metrics_snapshot(limit: int) -> list[dict]:
    """Tarixdan oxirgi `limit` ta yozuvning nusxasini qaytaradi (lock ostida)."""
    with _metrics_lock:
        return list(_metrics_history[-limit:])


def metrics_history_size() -> int:
    """Ring bufferdagi jami yozuvlar soni."""
    with _metrics_lock:
        return len(_metrics_history)


def _err(exc: Any) -> dict:
    """Bo'lim xatosi uchun bir xil shakl (eski xatti-harakat bilan bir xil)."""
    return {"error": str(exc)[:100]}


def collect_health_metrics(
    *,
    agent: Any = None,
    server_start_time: Optional[float] = None,
    circuit: Any = None,
    chat_progress: Optional[dict] = None,
    chat_progress_lock: Any = None,
    chat_history: Any = None,
    run_manager: Any = None,
) -> dict:
    """Joriy holat metrikalarini yig'adi. Har 30 soniyada health monitor
    thread'i tomonidan chaqiriladi yoki /api/health/metrics so'rovda.

    Tashqi holat argument sifatida uzatiladi (DI). Biror holat berilmasa,
    mos bo'lim xato obyekti bilan qaytadi — javob shakli o'zgarmaydi.
    """
    now = time.time()
    start = now if server_start_time is None else server_start_time
    metrics: dict = {
        "timestamp": now,
        "uptime": now - start,
    }

    # 1. Agent holati
    if agent is None:
        metrics["agent"] = {"status": "not_initialized"}
        return metrics

    try:
        st = agent.status()
        metrics["agent"] = {
            "status": "ok",
            "bricks": st.get("bricks", {}).get("total", 0),
            "rules": st.get("knowledge", {}).get("rules", 0),
            "chains": len(st.get("chains", {})),
        }
    except Exception as exc:
        metrics["agent"] = {"status": "error", "error": str(exc)[:100]}

    # 2. LLM holati (graceful degradation bilan)
    try:
        llm_data = {
            "enabled": agent.use_llm,
            "available": agent.llm_available(),
            "model": agent.llm.model,
            "failure_count": getattr(agent, '_llm_failure_count', 0),
            "degraded": getattr(agent, '_llm_failure_count', 0) > 0,
            "last_error": getattr(agent.llm, 'last_error', None),
            "turbo": bool(getattr(agent.llm, 'turbo', False)),
        }
        # LLM availability check timeout
        t0 = time.perf_counter()
        try:
            is_up = agent.llm.is_available()
            llm_data["ping_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            llm_data["reachable"] = is_up
        except Exception:
            llm_data["ping_ms"] = -1
            llm_data["reachable"] = False
        # Degradation metrics
        try:
            llm_data["degradation"] = agent.degradation_status()
        except Exception:
            llm_data["degradation"] = {}
        metrics["llm"] = llm_data
    except Exception as exc:
        metrics["llm"] = {"error": str(exc)[:100]}

    # 3. Memory / RAG holati
    try:
        mem = agent.memory
        metrics["memory"] = {
            "enabled": mem.enabled,
            "error": getattr(mem, '_error', None),
            "corpus_loaded": getattr(mem, '_load_done', threading.Event()).is_set(),
        }
    except Exception as exc:
        metrics["memory"] = {"error": str(exc)[:100]}

    # 4. Circuit breaker holati
    try:
        if circuit is None:
            raise RuntimeError("circuit breaker not provided")
        metrics["circuit"] = circuit.status()
    except Exception as exc:
        metrics["circuit"] = _err(exc)

    # 5. Chat holati
    try:
        if chat_progress_lock is None or chat_history is None or chat_progress is None:
            raise RuntimeError("chat state not provided")
        with chat_progress_lock:
            active_chats = len(chat_history._convs)
            active_runs = len(chat_progress)
        metrics["chat"] = {
            "conversations": active_chats,
            "active_runs": active_runs,
        }
    except Exception as exc:
        metrics["chat"] = _err(exc)

    # 5b. Run queue holati (Roadmap v2 C4, §15 right-sizing)
    try:
        if run_manager is None:
            raise RuntimeError("run manager not provided")
        qi = run_manager.queue_info()
        qi["runs_total"] = len(run_manager._runs)
        metrics["runs"] = qi
    except Exception as exc:
        metrics["runs"] = _err(exc)

    # 6. System resurslari
    try:
        import psutil
        proc = psutil.Process()
        mem_info = proc.memory_info()
        metrics["system"] = {
            "pid": proc.pid,
            "memory_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
            "memory_vms_mb": round(mem_info.vms / 1024 / 1024, 1),
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "threads": proc.num_threads(),
        }
    except ImportError:
        # psutil yo'q - lightweight alternativa
        try:
            import os
            metrics["system"] = {
                "pid": os.getpid(),
                "threads": 0,
            }
        except Exception:
            metrics["system"] = {}
    except Exception as exc:
        metrics["system"] = {"error": str(exc)[:100]}

    return metrics
