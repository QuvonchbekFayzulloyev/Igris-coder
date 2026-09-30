"""
IGRIS BRAIN — Silent-degradation REGISTRY (S3 + T1-darsi)
=========================================================
Muammo (2026-09-12 E2E auditida aniqlandi): mudofaa `except Exception: fallback`
naqshlari jim ishlaydi — tizim "ishlayapti" ko'rinadi, lekin aslida zaiflashgan
rejimda (masalan, FTS5 import bo'lmasa BM25 ga qaytib, 3-6x sekinlik saqlanardi;
MCP server ulanmasa browser tool'lar yo'qolardi). Hech qanday signal yo'q.

Yechim: yagona mark() registry — har bir fallback o'zini BU YERGA yozadi,
`/api/system/services` (va UI Settings→Services) esa degraded holatlarni
real vaqtda ko'rsatadi. Agent hech qachon crash qilmaydi — registry
hech qachon exception tashlamaydi (defensive: xato bo'lsa jim tashlab ketadi).

Faylqa yozish: logs/degradations.json (watchdog log papkasida) — server
qayta ishga tushganda ham tarix ko'rinadi. Atomik yozish (tmp+replace).
"""

from __future__ import annotations

import json
import os
import threading
import time

_LOCK = threading.Lock()
_MAX_ENTRIES = 100
_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "degradations.json"
)

# In-memory registry: [{"component", "reason", "ts", "count"}...]
_ENTRIES: list[dict] = []
_LOADED = False


def _load() -> None:
    """Diskdagi oldingi yozuvlarni tiklaydi (server restart'da tarix saqlanadi)."""
    global _LOADED, _ENTRIES
    if _LOADED:
        return
    _LOADED = True
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            _ENTRIES = [e for e in data if isinstance(e, dict)][: _MAX_ENTRIES]
    except Exception:
        _ENTRIES = []


def _save() -> None:
    """Atomik yozish (tmp+replace) — yarim fayl yo'q."""
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        tmp = _LOG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_ENTRIES, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, _LOG_PATH)
    except Exception:
        pass  # registry hech qachon xato tashlamaydi


def mark(component: str, reason: str, fallback: str = "") -> None:
    """Silent fallback sodir bo'lganini belgilaydi.

    Args:
        component: qayerda — "mcp.web_ai_bridge", "memory.fts5", "agent.skill"...
        reason:   nega — import xatosi / ulanmadi / timeout...
        fallback: nimaga qaytdi — "BM25Index", "no-tools", "offline"...
    """
    entry = {
        "component": str(component or "?")[:80],
        "reason": str(reason or "?")[:300],
        "fallback": str(fallback or "")[:80],
        "ts": time.time(),
    }
    try:
        with _LOCK:
            _load()
            # Bir xil component+fallback bo'lsa — yangi yozuv emas, count+1
            # va so'nggi vaqt yangilanadi (ro'yxat shishib ketmasligi uchun).
            for e in _ENTRIES:
                if (e.get("component") == entry["component"]
                        and e.get("fallback") == entry["fallback"]):
                    e["ts"] = entry["ts"]
                    e["reason"] = entry["reason"]
                    e["count"] = int(e.get("count") or 1) + 1
                    _save()
                    return
            entry["count"] = 1
            _ENTRIES.append(entry)
            # Limit: eng so'nggilar qoladi
            if len(_ENTRIES) > _MAX_ENTRIES:
                _ENTRIES[:] = _ENTRIES[-_MAX_ENTRIES:]
            _save()
    except Exception:
        pass  # never break the agent


def report() -> list[dict]:
    """Degradations ro'yxati (eng so'nggi birinchi) — API/UI uchun."""
    try:
        with _LOCK:
            _load()
            out = sorted(_ENTRIES, key=lambda e: e.get("ts") or 0, reverse=True)
            return [dict(e) for e in out]
    except Exception:
        return []


def active_older_than(seconds: float = 600.0) -> list[dict]:
    """So'nggi `seconds` ichida mark qilingan degradatsiyalar (faol deb hisoblanadi)."""
    cutoff = time.time() - seconds
    return [e for e in report() if (e.get("ts") or 0) >= cutoff]


def clear() -> int:
    """Tozalash (UI "reset" tugmasi uchun). Qaytaradi: o'chirilganlar soni."""
    try:
        with _LOCK:
            _load()
            n = len(_ENTRIES)
            _ENTRIES.clear()
            _save()
            return n
    except Exception:
        return 0
