"""
IGRIS BRAIN — Resource Monitor (Roadmap §15 + §17)
===================================================
CPU/RAM/disk monitoring + limit enforcement.

§15: get_resources() — CPU%, RAM usage, disk I/O
§17: ResourceControl — max_ram_mb, max_cpu_s, max_disk_mb limitlari

psutil bilan ishlaydi; fallback: lightweight estimates.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


# ------------------------------------------------------------------ #
# Resource Snapshot
# ------------------------------------------------------------------ #

@dataclass
class ResourceSnapshot:
    """Bir lahzadagi resurs holati."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    ram_mb: float = 0.0
    ram_percent: float = 0.0
    disk_read_mb: float = 0.0
    disk_write_mb: float = 0.0
    threads: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 1),
            "ram_mb": round(self.ram_mb, 1),
            "ram_percent": round(self.ram_percent, 1),
            "disk_read_mb": round(self.disk_read_mb, 2),
            "disk_write_mb": round(self.disk_write_mb, 2),
            "threads": self.threads,
        }


def get_resources() -> ResourceSnapshot:
    """Joriy resurs holatini olish."""
    snap = ResourceSnapshot()

    if not _PSUTIL_OK:
        # Fallback: faqat jarayon holati
        try:
            snap.threads = threading.active_count()
        except Exception:
            pass
        return snap

    try:
        proc = _psutil.Process(os.getpid())
        snap.cpu_percent = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info()
        snap.ram_mb = mem.rss / (1024 * 1024)
        sys_mem = _psutil.virtual_memory()
        snap.ram_percent = sys_mem.percent
        disk = proc.io_counters()
        snap.disk_read_mb = disk.read_bytes / (1024 * 1024)
        snap.disk_write_mb = disk.write_bytes / (1024 * 1024)
        snap.threads = proc.num_threads()
    except Exception:
        pass

    return snap


# ------------------------------------------------------------------ #
# Resource Control (§17)
# ------------------------------------------------------------------ #

@dataclass
class ResourceLimits:
    """Resurs cheklovlari."""
    max_ram_mb: float = 512.0
    max_cpu_s: float = 30.0  # sekund — umumiy CPU vaqti
    max_disk_mb: float = 100.0  # disk yozuvi

    def to_dict(self) -> dict:
        return {
            "max_ram_mb": self.max_ram_mb,
            "max_cpu_s": self.max_cpu_s,
            "max_disk_mb": self.max_disk_mb,
        }


@dataclass
class ResourceViolation:
    """Limit buzilishi haqida xabar."""
    resource: str  # "ram" | "cpu" | "disk"
    limit: float
    actual: float
    message: str


class ResourceControl:
    """Resurs monitoring + limit enforcement.

    Har iteratsiyada check() chaqiriladi:
        violations = rc.check(snapshot)
        if violations:
            abort + error

    ishlatilishi:
        rc = ResourceControl(limits=ResourceLimits(max_ram_mb=512))
        snapshot = get_resources()
        violations = rc.check(snapshot)
    """

    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self._start_time = time.time()
        self._start_disk_write = 0.0
        self._violations: list[ResourceViolation] = []
        self._snapshots: list[ResourceSnapshot] = []

    def check(self, snapshot: ResourceSnapshot) -> list[ResourceViolation]:
        """Snapshot tekshirish — limit bo'yicha xatoliklar."""
        self._snapshots.append(snapshot)
        violations = []

        # RAM check
        if snapshot.ram_mb > self.limits.max_ram_mb:
            v = ResourceViolation(
                resource="ram",
                limit=self.limits.max_ram_mb,
                actual=snapshot.ram_mb,
                message=f"RAM {snapshot.ram_mb:.0f}MB exceeds limit {self.limits.max_ram_mb:.0f}MB",
            )
            violations.append(v)
            self._violations.append(v)

        # CPU time check
        elapsed = time.time() - self._start_time
        if elapsed > self.limits.max_cpu_s:
            v = ResourceViolation(
                resource="cpu",
                limit=self.limits.max_cpu_s,
                actual=elapsed,
                message=f"CPU time {elapsed:.1f}s exceeds limit {self.limits.max_cpu_s:.1f}s",
            )
            violations.append(v)
            self._violations.append(v)

        # Disk write check
        if snapshot.disk_write_mb > self.limits.max_disk_mb:
            v = ResourceViolation(
                resource="disk",
                limit=self.limits.max_disk_mb,
                actual=snapshot.disk_write_mb,
                message=f"Disk write {snapshot.disk_write_mb:.1f}MB exceeds limit {self.limits.max_disk_mb:.1f}MB",
            )
            violations.append(v)
            self._violations.append(v)

        return violations

    def should_abort(self) -> bool:
        """Har qanday limit buzilganmi?"""
        return len(self._violations) > 0

    def summary(self) -> dict:
        """Monitoring xulosasi."""
        return {
            "limits": self.limits.to_dict(),
            "total_violations": len(self._violations),
            "violations": [
                {"resource": v.resource, "message": v.message}
                for v in self._violations
            ],
            "snapshots_count": len(self._snapshots),
            "elapsed_s": round(time.time() - self._start_time, 1),
        }

    def reset(self):
        """Qayta ishga tushirish."""
        self._start_time = time.time()
        self._violations.clear()
        self._snapshots.clear()


__all__ = [
    "ResourceSnapshot", "get_resources",
    "ResourceLimits", "ResourceViolation", "ResourceControl",
]
