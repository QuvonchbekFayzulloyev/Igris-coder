"""
Tests for igris.core.execution_graph -- pure asyncio, no LLM/mocks needed.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.execution_graph import ExecutionGraph, GraphError


def test_independent_nodes_run_concurrently():
    """Two 0.2s sleeps with no dependency should take ~0.2s total, not ~0.4s."""
    async def slow(tag):
        await asyncio.sleep(0.2)
        return tag

    graph = ExecutionGraph()
    graph.add("a", lambda: slow("A"))
    graph.add("b", lambda: slow("B"))

    start = time.monotonic()
    results = asyncio.run(graph.run())
    elapsed = time.monotonic() - start

    assert results == {"a": "A", "b": "B"}
    assert elapsed < 0.35, f"expected concurrent execution (~0.2s), took {elapsed:.2f}s"


def test_dependent_node_waits_for_dependency():
    order = []

    async def record(name, delay=0.0):
        if delay:
            await asyncio.sleep(delay)
        order.append(name)
        return name

    graph = ExecutionGraph()
    graph.add("first", lambda: record("first", 0.1))
    graph.add("second", lambda: record("second"), depends_on=["first"])

    results = asyncio.run(graph.run())
    assert results == {"first": "first", "second": "second"}
    assert order == ["first", "second"]


def test_diamond_dependency_layers():
    """a -> (b, c) -> d : b and c run concurrently, both before d."""
    order = []

    async def record(name, delay=0.0):
        if delay:
            await asyncio.sleep(delay)
        order.append(name)
        return name

    graph = ExecutionGraph()
    graph.add("a", lambda: record("a"))
    graph.add("b", lambda: record("b", 0.1), depends_on=["a"])
    graph.add("c", lambda: record("c"), depends_on=["a"])
    graph.add("d", lambda: record("d"), depends_on=["b", "c"])

    asyncio.run(graph.run())
    assert order[0] == "a"
    assert set(order[1:3]) == {"b", "c"}
    assert order[3] == "d"


def test_cycle_detected():
    graph = ExecutionGraph()
    graph.add("a", lambda: asyncio.sleep(0), depends_on=["b"])
    graph.add("b", lambda: asyncio.sleep(0), depends_on=["a"])
    with pytest.raises(GraphError):
        asyncio.run(graph.run())


def test_missing_dependency_raises():
    graph = ExecutionGraph()
    graph.add("a", lambda: asyncio.sleep(0), depends_on=["nonexistent"])
    with pytest.raises(GraphError):
        asyncio.run(graph.run())


def test_duplicate_node_name_raises():
    graph = ExecutionGraph()
    graph.add("a", lambda: asyncio.sleep(0))
    with pytest.raises(GraphError):
        graph.add("a", lambda: asyncio.sleep(0))


def test_node_failure_propagates():
    async def boom():
        raise RuntimeError("branch failed")

    graph = ExecutionGraph()
    graph.add("a", boom)
    with pytest.raises(RuntimeError):
        asyncio.run(graph.run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
