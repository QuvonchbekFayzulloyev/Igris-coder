"""Resource-Aware Executive Controller.

Detects laptop hardware (GPU, CPU, RAM, battery) and monitors FPS to
self-adapt quality tiers (0–4). Used by animation/visual skills via
executive.getQualityLevel() in JS, or via get_quality_tier() in Python.
"""
from __future__ import annotations

import asyncio
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

TIER_NAMES = {0: "battery_saver", 1: "low_power", 2: "balanced", 3: "high", 4: "ultra"}


@dataclass
class HardwareInfo:
    gpu_name: str = ""
    gpu_vram_mb: int = 0
    gpu_is_integrated: bool = True
    cpu_cores: int = 0
    cpu_freq_mhz: float = 0.0
    ram_total_mb: int = 0
    on_battery: bool = True
    battery_percent: float = 100.0


@lru_cache(maxsize=1)
def detect_hardware() -> HardwareInfo:
    info = HardwareInfo()
    system = platform.system()

    if system == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "Win32_VideoController", "get", "Name,AdapterRAM"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("Name"):
                    continue
                parts = re.split(r"\s{2,}", line)
                if parts:
                    info.gpu_name = parts[0].strip()
                if len(parts) > 1:
                    try:
                        info.gpu_vram_mb = int(parts[-1].strip()) // 1048576
                    except (ValueError, TypeError):
                        pass
                break
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "NumberOfCores,MaxClockSpeed"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("NumberOfCores"):
                    continue
                parts = re.split(r"\s{2,}", line)
                if len(parts) >= 1 and parts[0].strip().isdigit():
                    info.cpu_cores = int(parts[0].strip())
                if len(parts) >= 2 and parts[1].strip():
                    try:
                        info.cpu_freq_mhz = float(parts[1].strip())
                    except ValueError:
                        pass
                break
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wmic", "OS", "get", "TotalVisibleMemorySize"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    info.ram_total_mb = int(line) // 1024
                    break
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wmic", "path", "Win32_Battery", "get", "EstimatedChargeRemaining"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    info.on_battery = True
                    info.battery_percent = float(line)
                    break
            else:
                info.on_battery = False
        except Exception:
            info.on_battery = False
    else:
        try:
            result = subprocess.run(["uname", "-a"], capture_output=True, text=True, timeout=5)
            if "microsoft" in result.stdout.lower():
                pass
        except Exception:
            pass

    info.gpu_is_integrated = _classify_gpu(info.gpu_name)
    if info.cpu_cores == 0:
        info.cpu_cores = os.cpu_count() or 4
    if info.ram_total_mb == 0:
        try:
            import psutil
            info.ram_total_mb = psutil.virtual_memory().total // 1048576
        except ImportError:
            info.ram_total_mb = 8192

    return info


def _classify_gpu(name: str) -> bool:
    integrated_keywords = [
        "intel", "uhd", "iris", "hd graphics", "radeon(tm) graphics",
        "radeon r", "vega", "nvidia geforce mx",
    ]
    name_lower = name.lower()
    return any(kw in name_lower for kw in integrated_keywords)


# ---------------------------------------------------------------------------
# Quality tier logic
# ---------------------------------------------------------------------------

def _initial_tier(hw: HardwareInfo) -> int:
    if hw.on_battery and hw.battery_percent < 20:
        return 0
    if hw.gpu_is_integrated:
        if hw.ram_total_mb <= 4096:
            return 1
        if hw.ram_total_mb <= 8192:
            return 2
        return 3 if hw.cpu_cores >= 8 else 2
    if hw.gpu_vram_mb >= 4096:
        return 4
    if hw.gpu_vram_mb >= 2048:
        return 3
    return 2


# ---------------------------------------------------------------------------
# Executive Controller
# ---------------------------------------------------------------------------

@dataclass
class ExecutiveState:
    tier: int = 2
    fps: float = 60.0
    frame_times: list[float] = field(default_factory=list)
    last_adjust: float = 0.0
    adjustment_interval: float = 5.0
    consecutive_low: int = 0
    consecutive_high: int = 0


class ExecutiveController:
    """Self-evolving resource-aware quality controller."""

    def __init__(self):
        hw = detect_hardware()
        self._state = ExecutiveState(tier=_initial_tier(hw))
        self._hw = hw

    @property
    def tier(self) -> int:
        return self._state.tier

    @property
    def hardware(self) -> HardwareInfo:
        return self._hw

    @property
    def tier_name(self) -> str:
        return TIER_NAMES.get(self._state.tier, "balanced")

    def record_frame(self, frame_time_ms: float) -> None:
        now = time.time()
        self._state.frame_times.append(frame_time_ms)
        if len(self._state.frame_times) > 60:
            self._state.frame_times.pop(0)
        if now - self._state.last_adjust < self._state.adjustment_interval:
            return
        self._state.last_adjust = now
        if not self._state.frame_times:
            return
        avg = sum(self._state.frame_times) / len(self._state.frame_times)
        fps = 1000.0 / avg if avg > 0 else 60
        self._state.fps = fps
        if fps < 30:
            self._state.consecutive_low += 1
            self._state.consecutive_high = 0
            if self._state.consecutive_low >= 3 and self._state.tier > 0:
                self._state.tier -= 1
                self._state.consecutive_low = 0
        elif fps > 55:
            self._state.consecutive_high += 1
            self._state.consecutive_low = 0
            if self._state.consecutive_high >= 10 and self._state.tier < 4:
                self._state.tier += 1
                self._state.consecutive_high = 0
        else:
            self._state.consecutive_low = 0
            self._state.consecutive_high = 0
        self._state.frame_times.clear()

    def get_quality_level(self) -> int:
        return self._state.tier

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self._state.tier,
            "tier_name": TIER_NAMES.get(self._state.tier, "balanced"),
            "fps": round(self._state.fps, 1),
            "on_battery": self._hw.on_battery,
            "battery_percent": self._hw.battery_percent,
            "gpu": self._hw.gpu_name,
            "gpu_vram_mb": self._hw.gpu_vram_mb,
            "gpu_is_integrated": self._hw.gpu_is_integrated,
            "cpu_cores": self._hw.cpu_cores,
            "ram_mb": self._hw.ram_total_mb,
        }


# Singleton
_controller: ExecutiveController | None = None


def get_controller() -> ExecutiveController:
    global _controller
    if _controller is None:
        _controller = ExecutiveController()
    return _controller


async def get_quality_tier() -> int:
    return get_controller().get_quality_level()


async def record_frame(frame_time_ms: float) -> None:
    get_controller().record_frame(frame_time_ms)
