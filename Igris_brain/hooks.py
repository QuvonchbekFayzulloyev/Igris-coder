"""
IGRIS BRAIN — Agent Hook Bus
============================
Agent hayot siklidagi voqealarga ulanish tizimi (hooks/plugins uchun).

Triggers:
    on_plan           - reja tuzildi ({task, plan})
    on_step_start     - bosqich boshlanmoqda ({task, step})
    on_step_done      - bosqich tugadi ({task, step, result})
    on_tool_call      - tool chaqirildi ({task, tool, args, result})
    on_error          - tool/step xato qildi ({task, tool, error})
    on_task_done      - task yakunlandi ({task, result})
    on_chat           - chat javobi ({message, result})
    on_skill_loaded   - skill yuklandi ({name})

Har bir hook — (name, trigger, fn(context) -> dict|None). Priority bo'yicha
ishlaydi. Hook natijalari hook_log'ga yoziladi (status/latency tekshiruvi
uchun). Executor va igris_agent bu bus'ni chaqiradi.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

TriggerFn = Callable[[dict], Optional[dict]]


class AgentHookBus:
    def __init__(self):
        self._hooks: dict[str, list[dict]] = {}   # trigger -> [{name, fn, priority}]
        self._log: list[dict] = []
        # RLock — stats() ichidan registered() (va boshqa _lock'li metodlar)
        # chaqirilganda qayta kirish xavfsiz (oddiy Lock deadlock berardi).
        self._lock = threading.RLock()
        self._log_limit = 200

    # ------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------ #

    def register(self, name: str, trigger: str, fn: TriggerFn, priority: int = 0):
        """Hook ro'yxatdan o'tkazish. Bir xil (name, trigger) almashtiriladi."""
        hook = {"name": name, "trigger": trigger, "fn": fn, "priority": priority}
        with self._lock:
            hooks = [h for h in self._hooks.get(trigger, []) if h["name"] != name]
            hooks.append(hook)
            hooks.sort(key=lambda h: h["priority"])
            self._hooks[trigger] = hooks

    def unregister(self, name: str, trigger: Optional[str] = None):
        with self._lock:
            if trigger:
                self._hooks[trigger] = [h for h in self._hooks.get(trigger, [])
                                        if h["name"] != name]
                return
            for t in list(self._hooks):
                self._hooks[t] = [h for h in self._hooks[t] if h["name"] != name]

    # ------------------------------------------------------------ #
    # Fire
    # ------------------------------------------------------------ #

    def fire(self, trigger: str, context: Optional[dict] = None) -> list[dict]:
        """Trigger'dagi barcha hook'larni chaqiradi. Hech qachon yiqilmaydi."""
        with self._lock:
            hooks = list(self._hooks.get(trigger, []))
        if not hooks:
            return []
        ctx = dict(context or {})
        ctx.setdefault("trigger", trigger)
        results: list[dict] = []
        for h in hooks:
            t0 = time.perf_counter()
            status = "ok"
            error = ""
            out: Optional[dict] = None
            try:
                out = h["fn"](ctx) or {}
            except Exception as exc:  # noqa: BLE001 - hook hech qachon agentni buzmaydi
                status = "error"
                error = str(exc)
            results.append({
                "hook": h["name"],
                "trigger": trigger,
                "status": status,
                "error": error,
                "out": out,
                "ms": round((time.perf_counter() - t0) * 1000, 2),
            })
        with self._lock:
            self._log.extend(results)
            self._log = self._log[-self._log_limit:]
        return results

    # ------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------ #

    def registered(self) -> dict[str, list[str]]:
        with self._lock:
            return {t: [h["name"] for h in hs] for t, hs in self._hooks.items()}

    def stats(self) -> dict:
        """Hook tizimi statistikasi (status endpoint uchun)."""
        with self._lock:
            total = len(self._log)
            errors = sum(1 for e in self._log if e["status"] == "error")
            by_trigger: dict[str, int] = {}
            for e in self._log:
                by_trigger[e["trigger"]] = by_trigger.get(e["trigger"], 0) + 1
            return {
                "registered": self.registered(),
                "events": total,
                "errors": errors,
                "by_trigger": by_trigger,
            }

    def log(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(self._log[-limit:])


# Singleton — server va executor foydalanadi
DEFAULT_BUS = AgentHookBus()


# ------------------------------------------------------------------ #
# Default hooks (Igris'ga xos)
# ------------------------------------------------------------------ #

def _hook_plan_first_check(ctx: dict) -> Optional[dict]:
    """on_step_start — reja-birinchi qoidani qo'llab-quvvatlovchi log."""
    plan = ctx.get("plan") or {}
    if not plan.get("steps") and ctx.get("task"):
        return {"warn": "no_plan", "note": "task started without a visible plan"}
    return None


def _hook_tool_call_tracker(ctx: dict) -> Optional[dict]:
    """on_tool_call — tool chaqiruvlarini kuzatish va statistika yig'ish."""
    tool = ctx.get("tool", "")
    args = ctx.get("args", {})
    result = ctx.get("result", {})
    # Tool nomi va muvaffaqiyat holatini qayd qilamiz
    ok = result.get("ok", True) if isinstance(result, dict) else True
    return {
        "tool": tool,
        "ok": ok,
        "args_keys": list(args.keys()) if isinstance(args, dict) else [],
        "output_len": len(str(result.get("output", ""))) if isinstance(result, dict) else 0,
    }


def _hook_error_logger(ctx: dict) -> Optional[dict]:
    """on_error — xatoliklarni log qilish va qayta urinish strategiyasi."""
    tool = ctx.get("tool", "")
    error = ctx.get("error", "")
    task = ctx.get("task", "")
    # Xato turiga qarab qayta urinish tavsiyasi
    retry_suggestion = ""
    if "timeout" in str(error).lower():
        retry_suggestion = "increase_timeout"
    elif "not found" in str(error).lower() or "no such file" in str(error).lower():
        retry_suggestion = "check_path"
    elif "permission" in str(error).lower():
        retry_suggestion = "check_permissions"
    elif "connection" in str(error).lower():
        retry_suggestion = "retry_connection"
    return {
        "tool": tool,
        "error": str(error)[:200],
        "task": str(task)[:100],
        "retry_suggestion": retry_suggestion,
    }


def _hook_task_done_tracker(ctx: dict) -> Optional[dict]:
    """on_task_done — task yakunlanishini kuzatish va natijani tahlil qilish."""
    result = ctx.get("result", {})
    if not isinstance(result, dict):
        return None
    status = result.get("status", "unknown")
    stats = result.get("stats", {})
    tool_calls = result.get("tool_calls", [])
    return {
        "status": status,
        "steps": stats.get("steps", 0),
        "tool_calls": stats.get("tool_calls", 0),
        "corrections": stats.get("corrections", 0),
        "duration_ms": stats.get("duration_ms", 0),
        "tool_names": [t.get("tool", "") for t in (tool_calls or [])[:10]],
    }


def _hook_chat_responder(ctx: dict) -> Optional[dict]:
    """on_chat — chat javoblarini kuzatish va sifat belgilari."""
    result = ctx.get("result", {})
    if not isinstance(result, dict):
        return None
    content = result.get("content", "")
    engine = result.get("engine", "")
    tool_calls = result.get("tool_calls", [])
    return {
        "engine": engine,
        "content_len": len(str(content)),
        "has_tools": bool(tool_calls),
        "tool_count": len(tool_calls),
        "duration_ms": result.get("duration_ms", 0),
    }


def _hook_skill_loaded_tracker(ctx: dict) -> Optional[dict]:
    """on_skill_loaded — skill yuklanishini kuzatish."""
    name = ctx.get("name", "")
    return {
        "skill": name,
        "loaded_at": time.time(),
    }


def _hook_iteration_guard(ctx: dict) -> Optional[dict]:
    """on_step_start — iteratsiya chegarasini tekshirish (cheksiz loop oldini olish)."""
    plan = ctx.get("plan") or {}
    step = ctx.get("step") or {}
    # Agar juda ko'p qadam bo'lsa — ogohlantiramiz
    steps = plan.get("steps", [])
    step_id = step.get("id", 0)
    if step_id > 10:
        return {
            "warn": "high_iteration",
            "note": f"Step {step_id} of {len(steps)} — check for infinite loop",
        }
    return None


def register_default_hooks(bus: AgentHookBus = DEFAULT_BUS) -> None:
    """Igris'ga xos default hook'larni ro'yxatdan o'tkazadi."""
    bus.register("plan-first-check", "on_step_start", _hook_plan_first_check, priority=10)
    bus.register("tool-call-tracker", "on_tool_call", _hook_tool_call_tracker, priority=5)
    bus.register("error-logger", "on_error", _hook_error_logger, priority=5)
    bus.register("task-done-tracker", "on_task_done", _hook_task_done_tracker, priority=5)
    bus.register("chat-responder", "on_chat", _hook_chat_responder, priority=5)
    bus.register("skill-loaded-tracker", "on_skill_loaded", _hook_skill_loaded_tracker, priority=5)
    bus.register("iteration-guard", "on_step_start", _hook_iteration_guard, priority=20)


__all__ = ["AgentHookBus", "DEFAULT_BUS", "register_default_hooks"]
