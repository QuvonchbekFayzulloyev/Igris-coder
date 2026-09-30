"""
IGRIS BRAIN — monitor package
==============================
Benchmarking, degradation tracking, hooks, probes, watchdog.

Import example:
    from monitor.degradation import mark, report
    from monitor.hooks import DEFAULT_BUS
    from monitor.benchmark import run_benchmark
"""

__all__ = [
    "benchmark",
    "degradation",
    "hooks",
    "probe_decisions",
    "probe_pyexec",
    "resource_monitor",
    "watchdog",
]
