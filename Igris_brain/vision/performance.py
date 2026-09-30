"""§16 Performance — screenshot caching, perception caching, latency measurement."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PerformanceMetrics:
    """Sahna ko'rish metrikalari."""
    capture_ms: float = 0.0
    preprocess_ms: float = 0.0
    detection_ms: float = 0.0
    ocr_ms: float = 0.0
    spatial_ms: float = 0.0
    ui_analysis_ms: float = 0.0
    context_build_ms: float = 0.0
    total_ms: float = 0.0
    # Cache stats
    cache_hit: bool = False
    cache_size: int = 0

    def to_dict(self) -> dict:
        return {
            "capture_ms": round(self.capture_ms, 1),
            "preprocess_ms": round(self.preprocess_ms, 1),
            "detection_ms": round(self.detection_ms, 1),
            "ocr_ms": round(self.ocr_ms, 1),
            "spatial_ms": round(self.spatial_ms, 1),
            "ui_analysis_ms": round(self.ui_analysis_ms, 1),
            "context_build_ms": round(self.context_build_ms, 1),
            "total_ms": round(self.total_ms, 1),
            "cache_hit": self.cache_hit,
        }


class PerformanceTracker:
    """Sahna ko'rish tezligini kuzatish."""

    def __init__(self):
        self._metrics_history: list[PerformanceMetrics] = []
        self._max_history = 100

    def start_timer(self) -> float:
        """Timer boshlash."""
        return time.time()

    def end_timer(self, start: float) -> float:
        """Timer tugatish — millisekundlarda."""
        return (time.time() - start) * 1000

    def record(self, metrics: PerformanceMetrics) -> None:
        """Metrikalarni saqlash."""
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history:
            self._metrics_history.pop(0)

    def get_average(self, count: int = 10) -> PerformanceMetrics:
        """O'rtacha metrikalar."""
        recent = self._metrics_history[-count:]
        if not recent:
            return PerformanceMetrics()

        return PerformanceMetrics(
            capture_ms=sum(m.capture_ms for m in recent) / len(recent),
            preprocess_ms=sum(m.preprocess_ms for m in recent) / len(recent),
            detection_ms=sum(m.detection_ms for m in recent) / len(recent),
            ocr_ms=sum(m.ocr_ms for m in recent) / len(recent),
            spatial_ms=sum(m.spatial_ms for m in recent) / len(recent),
            ui_analysis_ms=sum(m.ui_analysis_ms for m in recent) / len(recent),
            context_build_ms=sum(m.context_build_ms for m in recent) / len(recent),
            total_ms=sum(m.total_ms for m in recent) / len(recent),
        )

    def get_last(self) -> Optional[PerformanceMetrics]:
        """Oxirgi metrikalar."""
        if self._metrics_history:
            return self._metrics_history[-1]
        return None

    def is_slow(self, threshold_ms: float = 1000.0) -> bool:
        """Sahna ko'rish sekin ekanligini tekshirish."""
        last = self.get_last()
        if last:
            return last.total_ms > threshold_ms
        return False


class ScreenshotCache:
    """Screenshot cache — takroriy capture'larni oldini olish."""

    def __init__(self, ttl_seconds: float = 1.0, max_size: int = 5):
        self._cache: list[dict] = []
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self) -> Optional[Any]:
        """Cache'dan screenshot olish."""
        if not self._cache:
            self._misses += 1
            return None

        entry = self._cache[-1]
        age = time.time() - entry["timestamp"]
        if age > self._ttl:
            self._misses += 1
            return None

        self._hits += 1
        return entry["image"]

    def put(self, image: Any) -> None:
        """Screenshot'ni cache'ga qo'shish."""
        self._cache.append({
            "image": image,
            "timestamp": time.time(),
        })
        if len(self._cache) > self._max_size:
            self._cache.pop(0)

    def clear(self) -> None:
        """Cache'ni tozalash."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """Cache statistikasi."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


class PerceptionCache:
    """Perception natijalarini cache'lash — ROI-based invalidation."""

    def __init__(self, ttl_seconds: float = 2.0):
        self._cache: dict[str, dict] = {}
        self._ttl = ttl_seconds

    def get(self, cache_key: str) -> Optional[Any]:
        """Cache'dan olish."""
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self._ttl:
            del self._cache[cache_key]
            return None
        return entry["data"]

    def put(self, cache_key: str, data: Any) -> None:
        """Cache'ga qo'shish."""
        self._cache[cache_key] = {
            "data": data,
            "timestamp": time.time(),
        }

    def invalidate(self, cache_key: str) -> None:
        """Cache'ni bekor qilish."""
        self._cache.pop(cache_key, None)

    def clear(self) -> None:
        self._cache.clear()
