"""
IGRIS BRAIN — Performance Benchmarks
=====================================
Comprehensive performance testing suite for IGRIS components.

Measures:
    - Tool execution speed
    - Memory usage
    - Response latency
    - Throughput
    - Resource utilization

Usage:
    pytest benchmarks/test_performance.py -v
    pytest benchmarks/test_performance.py --benchmark-only
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = Path(__file__).parent / "results"

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------- #
# Benchmark Framework
# ---------------------------------------------------------------- #

class BenchmarkResult:
    """Benchmark natijasi."""
    
    def __init__(self, name: str, iterations: int = 100):
        self.name = name
        self.iterations = iterations
        self.times: list[float] = []
        self.start_time: float = 0
        self.metadata: dict = {}
    
    def start(self):
        """Timer boshlash."""
        self.start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Timer to'xtatish va natija qo'shish."""
        elapsed = time.perf_counter() - self.start_time
        self.times.append(elapsed)
        return elapsed
    
    def add_metadata(self, key: str, value: Any):
        """Metadata qo'shish."""
        self.metadata[key] = value
    
    @property
    def avg_time(self) -> float:
        """O'rtacha vaqt."""
        return sum(self.times) / len(self.times) if self.times else 0
    
    @property
    def min_time(self) -> float:
        """Eng kam vaqt."""
        return min(self.times) if self.times else 0
    
    @property
    def max_time(self) -> float:
        """Eng ko'p vaqt."""
        return max(self.times) if self.times else 0
    
    @property
    def p50_time(self) -> float:
        """Median (50th percentile)."""
        if not self.times:
            return 0
        sorted_times = sorted(self.times)
        idx = len(sorted_times) // 2
        return sorted_times[idx]
    
    @property
    def p95_time(self) -> float:
        """95th percentile."""
        if not self.times:
            return 0
        sorted_times = sorted(self.times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]
    
    @property
    def p99_time(self) -> float:
        """99th percentile."""
        if not self.times:
            return 0
        sorted_times = sorted(self.times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]
    
    @property
    def std_dev(self) -> float:
        """Standard deviation."""
        if len(self.times) < 2:
            return 0
        avg = self.avg_time
        variance = sum((t - avg) ** 2 for t in self.times) / (len(self.times) - 1)
        return variance ** 0.5
    
    def to_dict(self) -> dict:
        """Dictionary format."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "avg_ms": round(self.avg_time * 1000, 3),
            "min_ms": round(self.min_time * 1000, 3),
            "max_ms": round(self.max_time * 1000, 3),
            "p50_ms": round(self.p50_time * 1000, 3),
            "p95_ms": round(self.p95_time * 1000, 3),
            "p99_ms": round(self.p99_time * 1000, 3),
            "std_dev_ms": round(self.std_dev * 1000, 3),
            "total_ms": round(sum(self.times) * 1000, 3),
            "iterations_per_sec": round(1 / self.avg_time if self.avg_time > 0 else 0, 2),
            "metadata": self.metadata,
        }


class BenchmarkSuite:
    """Benchmark to'plami."""
    
    def __init__(self, name: str = "IGRIS Benchmarks"):
        self.name = name
        self.results: list[BenchmarkResult] = []
        self.start_time: float = 0
    
    def run(self, name: str, func: Callable, iterations: int = 100, 
            warmup: int = 10, **kwargs) -> BenchmarkResult:
        """Benchmark bajarish."""
        result = BenchmarkResult(name, iterations)
        
        # Warmup
        for _ in range(warmup):
            func(**kwargs)
        
        # Actual benchmark
        for _ in range(iterations):
            result.start()
            func(**kwargs)
            result.stop()
        
        self.results.append(result)
        return result
    
    def to_dict(self) -> dict:
        """Dictionary format."""
        return {
            "name": self.name,
            "timestamp": datetime.now().isoformat(),
            "benchmarks": [r.to_dict() for r in self.results],
            "summary": self.summary(),
        }
    
    def summary(self) -> dict:
        """Xulosa."""
        if not self.results:
            return {}
        
        return {
            "total_benchmarks": len(self.results),
            "avg_time_ms": round(sum(r.avg_time for r in self.results) / len(self.results) * 1000, 3),
            "fastest": min(self.results, key=lambda r: r.avg_time).name,
            "slowest": max(self.results, key=lambda r: r.avg_time).name,
        }
    
    def print_report(self):
        """Hisobot chiqarish."""
        print(f"\n{'=' * 60}")
        print(f"  {self.name}")
        print(f"{'=' * 60}\n")
        
        sorted_results = sorted(self.results, key=lambda r: r.avg_time)
        
        for result in sorted_results:
            print(f"  {result.name}")
            print(f"    Average:  {result.avg_time * 1000:.2f} ms")
            print(f"    Min:      {result.min_time * 1000:.2f} ms")
            print(f"    Max:      {result.max_time * 1000:.2f} ms")
            print(f"    P50:      {result.p50_time * 1000:.2f} ms")
            print(f"    P95:      {result.p95_time * 1000:.2f} ms")
            print(f"    Std Dev:  {result.std_dev * 1000:.2f} ms")
            iters_per_sec = 1 / result.avg_time if result.avg_time > 0 else 0
            print(f"    Iters/s:  {iters_per_sec:.0f}")
            print()
        
        summary = self.summary()
        print(f"  Summary")
        print(f"    Total benchmarks: {summary.get('total_benchmarks', 0)}")
        print(f"    Average time:     {summary.get('avg_time_ms', 0):.2f} ms")
        print(f"    Fastest:          {summary.get('fastest', 'N/A')}")
        print(f"    Slowest:          {summary.get('slowest', 'N/A')}")
        print(f"\n{'=' * 60}\n")
    
    def save(self, filepath: str = None):
        """Natijalarni saqlash."""
        if filepath is None:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = RESULTS_DIR / f"benchmark_{timestamp}.json"
        
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        print(f"[benchmark] Results saved to {filepath}")


# ---------------------------------------------------------------- #
# Tool Benchmarks
# ---------------------------------------------------------------- #

def benchmark_tools():
    """Tool bajarish tezligini o'lchash."""
    from tools import Workspace, DEFAULT_REGISTRY
    
    suite = BenchmarkSuite("Tool Benchmarks")
    ws = Workspace(str(PROJECT_ROOT / "agent_workspace"))
    
    # Create test file
    ws.write("_bench_test.txt", "Hello, benchmark!")
    
    # read_file benchmark
    def bench_read():
        return DEFAULT_REGISTRY.execute(ws, "read_file", {"path": "_bench_test.txt"})
    
    suite.run("read_file", bench_read, iterations=1000)
    
    # write_file benchmark
    def bench_write():
        return DEFAULT_REGISTRY.execute(ws, "write_file", {"path": "_bench_write.txt", "content": "test"})
    
    suite.run("write_file", bench_write, iterations=500)
    
    # list_files benchmark
    def bench_list():
        return DEFAULT_REGISTRY.execute(ws, "list_files", {"path": "", "depth": 2})
    
    suite.run("list_files", bench_list, iterations=500)
    
    # python_exec benchmark
    def bench_python():
        return DEFAULT_REGISTRY.execute(ws, "python_exec", {"code": "x = 1 + 1"})
    
    suite.run("python_exec", bench_python, iterations=200)
    
    # Cleanup
    try:
        os.remove(ws.resolve("_bench_test.txt"))
        os.remove(ws.resolve("_bench_write.txt"))
    except:
        pass
    
    return suite


# ---------------------------------------------------------------- #
# Memory Benchmarks
# ---------------------------------------------------------------- #

def benchmark_memory():
    """Xotira ishlatishini o'lchash."""
    import tracemalloc
    
    suite = BenchmarkSuite("Memory Benchmarks")
    
    def measure(func, *args, **kwargs):
        tracemalloc.start()
        result = func(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return current / 1024 / 1024, peak / 1024 / 1024
    
    # Tool registry memory
    def mem_tool_registry():
        from tools import ToolRegistry
        return ToolRegistry()
    
    current, peak = measure(mem_tool_registry)
    result = BenchmarkResult("ToolRegistry init", 10)
    result.add_metadata("current_mb", current)
    result.add_metadata("peak_mb", peak)
    result.times = [current] * 10  # Placeholder
    suite.results.append(result)
    
    # Workspace memory
    def mem_workspace():
        from tools import Workspace
        return Workspace(str(PROJECT_ROOT / "agent_workspace"))
    
    current, peak = measure(mem_workspace)
    result = BenchmarkResult("Workspace init", 10)
    result.add_metadata("current_mb", current)
    result.add_metadata("peak_mb", peak)
    result.times = [current] * 10
    suite.results.append(result)
    
    return suite


# ---------------------------------------------------------------- #
# Skill Benchmarks
# ---------------------------------------------------------------- #

def benchmark_skills():
    """Skill yuklash tezligini o'lchash."""
    from skills import SkillManager
    
    suite = BenchmarkSuite("Skill Benchmarks")
    
    # Skill discovery
    def bench_discover():
        return SkillManager()
    
    suite.run("SkillManager init", bench_discover, iterations=100)
    
    # Skill loading
    mgr = SkillManager()
    
    def bench_load_svg():
        return mgr.get("svg-artist")
    
    suite.run("Skill load (svg-artist)", bench_load_svg, iterations=100)
    
    def bench_load_pvc():
        return mgr.get("progressive-visual-construction")
    
    suite.run("Skill load (pvc)", bench_load_pvc, iterations=100)
    
    return suite


# ---------------------------------------------------------------- #
# Hook Benchmarks
# ---------------------------------------------------------------- #

def benchmark_hooks():
    """Hook bus ishlashini o'lchash."""
    from hooks import AgentHookBus, register_default_hooks
    
    suite = BenchmarkSuite("Hook Benchmarks")
    
    # Hook bus init
    def bench_hook_init():
        bus = AgentHookBus()
        register_default_hooks(bus)
        return bus
    
    suite.run("HookBus init", bench_hook_init, iterations=100)
    
    # Hook fire
    bus = AgentHookBus()
    register_default_hooks(bus)
    
    def bench_hook_fire():
        return bus.fire("on_step_start", {"task": "test", "step": {"id": 1}})
    
    suite.run("Hook fire (on_step_start)", bench_hook_fire, iterations=1000)
    
    def bench_tool_fire():
        return bus.fire("on_tool_call", {"task": "test", "tool": "read_file", "args": {}, "result": {}})
    
    suite.run("Hook fire (on_tool_call)", bench_tool_fire, iterations=1000)
    
    return suite


# ---------------------------------------------------------------- #
# Parser Benchmarks
# ---------------------------------------------------------------- #

def benchmark_parsers():
    """Parser tezligini o'lchash."""
    suite = BenchmarkSuite("Parser Benchmarks")
    
    # Version parsing
    from version_bumper import Version
    
    def bench_parse_version():
        return Version.parse("1.2.3-alpha.1")
    
    suite.run("Version.parse", bench_parse_version, iterations=10000)
    
    # Commit parsing
    from changelog_generator import parse_commit
    
    def bench_parse_commit():
        return parse_commit("feat(scope): add new feature (#123)")
    
    suite.run("parse_commit", bench_parse_commit, iterations=10000)
    
    return suite


# ---------------------------------------------------------------- #
# Main Benchmark Runner
# ---------------------------------------------------------------- #

def run_all_benchmarks():
    """Barcha benchmarklarni bajarish."""
    print("\n[benchmark] Running all benchmarks...\n")
    
    all_suites = []
    
    # Run each benchmark suite
    try:
        suite = benchmark_tools()
        all_suites.append(suite)
        suite.print_report()
    except Exception as e:
        print(f"[benchmark] Tool benchmarks failed: {e}")
    
    try:
        suite = benchmark_memory()
        all_suites.append(suite)
        suite.print_report()
    except Exception as e:
        print(f"[benchmark] Memory benchmarks failed: {e}")
    
    try:
        suite = benchmark_skills()
        all_suites.append(suite)
        suite.print_report()
    except Exception as e:
        print(f"[benchmark] Skill benchmarks failed: {e}")
    
    try:
        suite = benchmark_hooks()
        all_suites.append(suite)
        suite.print_report()
    except Exception as e:
        print(f"[benchmark] Hook benchmarks failed: {e}")
    
    try:
        suite = benchmark_parsers()
        all_suites.append(suite)
        suite.print_report()
    except Exception as e:
        print(f"[benchmark] Parser benchmarks failed: {e}")
    
    # Save combined results
    combined = {
        "timestamp": datetime.now().isoformat(),
        "suites": [s.to_dict() for s in all_suites],
    }
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RESULTS_DIR / f"benchmark_{timestamp}.json"
    
    with open(filepath, "w") as f:
        json.dump(combined, f, indent=2)
    
    print(f"\n[benchmark] Combined results saved to {filepath}")
    
    return combined


if __name__ == "__main__":
    run_all_benchmarks()
