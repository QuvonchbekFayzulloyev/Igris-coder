"""
IGRIS BRAIN — MAG (Memory-Augmented Generation)
================================================
Xotira qatlamlaridan (L1 runtime + L2 persistent + RAG retrieval) uzluksiz
kontekst yig'ib, LLM generatsiyasiga boyitilgan holat beradi.

MemoryBridge mavjud (recall/remember). MAG uni to'ldiradi:
  - assemble(query)  -> {context, layers, hits}  (L1 + L2 + retrieval)
  - remember_result(query, output) -> L2 solution-memory + L1 short-turn
  - session open/end -> konsolidatsiya uchun sessiya boshqaruvi

MAG ishlashi uchun Igris_Memory import qilinishi shart emas — MemoryBridge
orqali ishlaydi (bridge o'zi Igris_Memory'ni yuklaydi).
"""

from __future__ import annotations

import json
import time
from typing import Optional

from memory_bridge import MemoryBridge


class MagAssembler:
    def __init__(self, memory: Optional[MemoryBridge] = None, session_id: str = ""):
        self.memory = memory
        self.session_id = session_id or "mag"
        self._latency: dict[str, float] = {}

    # ------------------------------------------------------------ #
    # Context assembly (L1 + L2 + RAG)
    # ------------------------------------------------------------ #

    def assemble(self, query: str, top_k: int = 3, max_chars: int = 2000) -> dict:
        """Query uchun xotira kontekstini yig'adi.

        Qaytaradi:
            {"context": str, "layers": {"l1": n, "l2": n, "rag": n},
             "hits": int, "latency_ms": float}
        """
        if self.memory is None or not self.memory.enabled:
            return {"context": "", "layers": {"l1": 0, "l2": 0, "rag": 0},
                    "hits": 0, "latency_ms": 0.0}
        t0 = time.perf_counter()
        parts: list[str] = []
        layers = {"l1": 0, "l2": 0, "rag": 0}

        # 1) RAG retrieval (MemoryBridge.recall -> L4 retrieval pipeline)
        try:
            ctx, hits = self.memory.recall(query, top_k=top_k, max_chars=max_chars)
            if ctx:
                parts.append(ctx)
                layers["rag"] = hits
        except Exception:
            pass

        # 2) L1 runtime (short-turn / task-memory) — session'ning so'nggi yozuvlari
        try:
            mgr = self.memory.manager
            for type_name in ("short-turn", "task-memory"):
                entries = mgr.runtime.read(type_name, limit=2) if hasattr(mgr, "runtime") else []
                for e in entries:
                    text = e.get("content") or e.get("summary") or json.dumps(e, ensure_ascii=False)
                    if text:
                        parts.append(f"[L1:{type_name}] {str(text)[:300]}")
                        layers["l1"] += 1
        except Exception:
            pass

        # 3) L2 persistent (solution-memory) — so'nggi yechimlar
        try:
            mgr = self.memory.manager
            res = mgr.search(query, top_k=top_k) if hasattr(mgr, "search") else {}
            for e in (res.get("results", []) or [])[:top_k]:
                text = e.get("entry", {}).get("content") or e.get("summary") or ""
                if text:
                    parts.append(f"[L2] {str(text)[:300]}")
                    layers["l2"] += 1
        except Exception:
            pass

        joined = "\n".join(p for p in parts if p)[:max_chars]
        latency = (time.perf_counter() - t0) * 1000
        self._latency["assemble_ms"] = round(latency, 2)
        return {
            "context": joined,
            "layers": layers,
            "hits": sum(layers.values()),
            "latency_ms": round(latency, 2),
        }

    # ------------------------------------------------------------ #
    # Remember (L2 + L1)
    # ------------------------------------------------------------ #

    def remember_result(self, query: str, output: str, tags: Optional[list[str]] = None) -> dict:
        """Natijani xotiraga yozadi (MAG'ning yopilish qismi)."""
        if self.memory is None or not self.memory.enabled or not output:
            return {"status": "disabled"}
        try:
            return self.memory.on_resolve(query, {"output": output, "engine": "mag"})
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # ------------------------------------------------------------ #
    # Sessions
    # ------------------------------------------------------------ #

    def start_session(self, session_id: str = "") -> dict:
        if self.memory is None or not self.memory.enabled:
            return {"status": "disabled"}
        self.session_id = session_id or self.session_id
        return self.memory.start_session(self.session_id)

    def end_session(self, summary: str = "") -> dict:
        if self.memory is None or not self.memory.enabled:
            return {"status": "disabled"}
        return self.memory.end_session(summary or "mag session end")

    # ------------------------------------------------------------ #

    def status(self) -> dict:
        base = self.memory.status() if self.memory else {"enabled": False}
        base["mag"] = {"session_id": self.session_id,
                       "latency_ms": {k: round(v, 2) for k, v in self._latency.items()}}
        return base


__all__ = ["MagAssembler"]
