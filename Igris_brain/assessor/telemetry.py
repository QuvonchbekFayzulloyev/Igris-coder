"""
IGRIS BRAIN — Telemetry
=======================
Continuous process analysis: jarayonni uzluksiz tahlil qilish.

Observes every resolution event (query -> status/confidence/engine/chains),
computes rolling statistics, detects degradation, and suggests actions
(healing, consolidation, expansion) per the telemetry rules.

Rules: see standards.TELEMETRY (window_size, thresholds, ...).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .standards import TELEMETRY


# ---------------------------------------------------------------- #
# Event
# ---------------------------------------------------------------- #

@dataclass
class ResolutionEvent:
    """One observed resolution."""

    query: str
    status: str = "ok"              # ok | partial | failed
    confidence: float = 0.0
    engine: str = "deterministic"   # deterministic | healed | llm
    chains: list = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "confidence": round(self.confidence, 3),
            "engine": self.engine,
            "chains": self.chains,
            "duration_ms": round(self.duration_ms, 1),
        }


# ---------------------------------------------------------------- #
# Snapshot
# ---------------------------------------------------------------- #

@dataclass
class ProcessSnapshot:
    """Rolling statistics over the recent window."""

    window_size: int = 0
    total_events: int = 0
    ok_rate: float = 0.0
    partial_rate: float = 0.0
    failed_rate: float = 0.0
    avg_confidence: float = 0.0
    prev_avg_confidence: float = 0.0
    confidence_declining: bool = False
    llm_usage_rate: float = 0.0
    healed_rate: float = 0.0
    top_chains: dict[str, int] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "window_size": self.window_size,
            "total_events": self.total_events,
            "ok_rate": round(self.ok_rate, 3),
            "partial_rate": round(self.partial_rate, 3),
            "failed_rate": round(self.failed_rate, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "confidence_declining": self.confidence_declining,
            "llm_usage_rate": round(self.llm_usage_rate, 3),
            "healed_rate": round(self.healed_rate, 3),
            "top_chains": self.top_chains,
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------- #
# ProcessAnalyzer
# ---------------------------------------------------------------- #

class ProcessAnalyzer:
    """Continuous process analysis over a rolling window.

    persist_path berilsa — har bir event va snapshot JSONL faylga yoziladi,
    qayta ishga tushganda o'qib olinadi (telemetry tarixi yo'qolmaydi).
    """

    def __init__(self, window_size: int = TELEMETRY.window_size,
                 persist_path: Optional[str] = None,
                 max_persist_lines: int = 3000):
        self.window_size = window_size
        self.persist_path = persist_path
        self.max_persist_lines = max_persist_lines
        self.events: list[ResolutionEvent] = []
        self.snapshots: list[ProcessSnapshot] = []
        self._last_consolidate_suggested = 0
        # Konkurent yozuvlarda fayl buzilmasligi uchun lock (FastAPI threadpool)
        self._io_lock = threading.Lock()
        if persist_path:
            self._load()

    # ---- persistence ------------------------------------------ #

    def _append_line(self, obj: dict):
        if not self.persist_path:
            return
        with self._io_lock:
            try:
                os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
                with open(self.persist_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def _trim(self):
        """Fayl cheksiz o'smasligi uchun — faqat so'nggi max_persist_lines."""
        if not self.persist_path or not os.path.isfile(self.persist_path):
            return
        with self._io_lock:
            try:
                with open(self.persist_path, "r", encoding="utf-8") as fh:
                    lines = fh.readlines()
                if len(lines) <= self.max_persist_lines:
                    return
                with open(self.persist_path, "w", encoding="utf-8") as fh:
                    fh.writelines(lines[-self.max_persist_lines:])
            except OSError:
                pass

    def _load(self):
        """JSONL fayldan event/snapshot tarixini qayta yuklaydi."""
        if not self.persist_path or not os.path.isfile(self.persist_path):
            return
        with self._io_lock:
            try:
                with open(self.persist_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        kind = d.pop("kind", "event")
                        if kind == "snapshot":
                            self.snapshots.append(ProcessSnapshot(**d))
                        else:
                            self.events.append(ResolutionEvent(
                                query=d.get("query", ""),
                                status=d.get("status", "ok"),
                                confidence=d.get("confidence", 0.0),
                                engine=d.get("engine", "deterministic"),
                                chains=d.get("chains", []),
                                duration_ms=d.get("duration_ms", 0.0),
                            ))
            except OSError:
                pass

    def record(self, event: ResolutionEvent) -> ProcessSnapshot:
        """Record one event and return the updated snapshot."""
        self.events.append(event)
        if self.persist_path:
            d = event.to_dict()
            d["kind"] = "event"
            self._append_line(d)
        if len(self.events) > self.window_size * 2:
            self.events = self.events[-self.window_size:]
        snapshot = self.snapshot()
        self.snapshots.append(snapshot)
        if self.persist_path:
            s = snapshot.to_dict()
            s["kind"] = "snapshot"
            self._append_line(s)
            self._trim()
        return snapshot

    # ---- rolling stats ---------------------------------------- #

    def snapshot(self) -> ProcessSnapshot:
        window = self.events[-self.window_size:]
        n = len(window)
        snap = ProcessSnapshot(window_size=n, total_events=len(self.events))

        if n == 0:
            return snap

        statuses = {}
        conf_sum = 0.0
        llm_count = 0
        healed_count = 0
        chains_count: dict[str, int] = {}

        for e in window:
            statuses[e.status] = statuses.get(e.status, 0) + 1
            conf_sum += e.confidence
            if e.engine == "llm":
                llm_count += 1
            if e.engine == "healed":
                healed_count += 1
            for c in e.chains:
                chains_count[c] = chains_count.get(c, 0) + 1

        snap.ok_rate = statuses.get("ok", 0) / n
        snap.partial_rate = statuses.get("partial", 0) / n
        snap.failed_rate = statuses.get("failed", 0) / n
        snap.avg_confidence = conf_sum / n
        snap.llm_usage_rate = llm_count / n
        snap.healed_rate = healed_count / n
        snap.top_chains = dict(sorted(chains_count.items(), key=lambda x: -x[1])[:5])

        # compare with the previous window for decline detection
        prev_window = self.events[-2 * self.window_size: -self.window_size]
        if prev_window:
            snap.prev_avg_confidence = sum(e.confidence for e in prev_window) / len(prev_window)
            snap.confidence_declining = (
                snap.prev_avg_confidence - snap.avg_confidence
                > TELEMETRY.confidence_decline_threshold
            )

        snap.suggestions = self._suggest(snap)
        return snap

    def _suggest(self, snap: ProcessSnapshot) -> list[str]:
        """Rule-based suggestions from the telemetry rules."""
        out: list[str] = []
        if snap.failed_rate > TELEMETRY.failure_rate_warn:
            out.append(f"failure rate {snap.failed_rate:.0%} > {TELEMETRY.failure_rate_warn:.0%} — investigate failing queries")
        if snap.avg_confidence < TELEMETRY.healing_trigger_min:
            out.append(f"avg confidence {snap.avg_confidence:.2f} low — consider healing / expanding bricks")
        if snap.confidence_declining:
            out.append(f"confidence declining ({snap.prev_avg_confidence:.2f} -> {snap.avg_confidence:.2f}) — knowledge drift detected")
        if snap.llm_usage_rate > 0.5:
            out.append("LLM fallback used >50% — deterministic coverage is weak; add bricks/rules")
        if snap.healed_rate > 0.3:
            out.append("healing used frequently — consider materializing healed chains")
        if (snap.total_events - self._last_consolidate_suggested
                >= TELEMETRY.consolidate_every):
            self._last_consolidate_suggested = snap.total_events
            out.append(f"at {snap.total_events} events — run consolidation (AutoDream-style)")
        return out

    def trend(self, limit: int = 10) -> list[dict]:
        """Recent snapshots for charting."""
        return [s.to_dict() for s in self.snapshots[-limit:]]

    def stats(self) -> dict:
        last = self.snapshots[-1] if self.snapshots else None
        return {
            "total_events": len(self.events),
            "snapshots": len(self.snapshots),
            "last": last.to_dict() if last else None,
        }
