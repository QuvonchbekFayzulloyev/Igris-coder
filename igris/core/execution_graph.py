"""
igris.core.execution_graph
------------------------------
The "Execution Graph Engine" from the architecture plan: runs a set of
named async jobs as a DAG instead of a flat sequence, so independent
branches (e.g. the multi_agent LoopPlan.branches from loop_generator.py)
execute concurrently while dependent ones wait for their inputs.

Not tied to LLM calls at all -- it's a generic DAG executor over any
zero-argument async callables, which is what makes it independently
testable with plain asyncio.sleep-based fixtures instead of a live model.

Usage:
    graph = ExecutionGraph()
    graph.add("frontend", lambda: run_branch("frontend", spec))
    graph.add("backend", lambda: run_branch("backend", spec))
    graph.add("integration", lambda: run_integration(), depends_on=["frontend", "backend"])
    results = await graph.run()   # {"frontend": ..., "backend": ..., "integration": ...}
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class _Node:
    name: str
    coro_factory: Callable[[], Awaitable[Any]]
    depends_on: list[str] = field(default_factory=list)


class GraphError(ValueError):
    """Raised for cycles, missing dependencies, or duplicate node names."""


class ExecutionGraph:
    def __init__(self):
        self._nodes: dict[str, _Node] = {}

    def add(
        self,
        name: str,
        coro_factory: Callable[[], Awaitable[Any]],
        depends_on: list[str] | None = None,
    ) -> None:
        if name in self._nodes:
            raise GraphError(f"Duplicate node name '{name}'")
        self._nodes[name] = _Node(name=name, coro_factory=coro_factory, depends_on=list(depends_on or []))

    def _layers(self) -> list[list[str]]:
        """Kahn's algorithm: group nodes into layers that can run concurrently."""
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    raise GraphError(f"Node '{node.name}' depends on unknown node '{dep}'")

        remaining = dict(self._nodes)
        done: set[str] = set()
        layers: list[list[str]] = []

        while remaining:
            ready = [n for n, node in remaining.items() if all(d in done for d in node.depends_on)]
            if not ready:
                raise GraphError(f"Cycle detected among: {', '.join(remaining)}")
            layers.append(sorted(ready))
            for n in ready:
                done.add(n)
                del remaining[n]

        return layers

    async def run(self) -> dict[str, Any]:
        """
        Execute all nodes, respecting dependencies, running each layer's
        independent nodes concurrently via asyncio.gather. If a node in a
        layer raises, the whole run() raises (fail-fast) -- callers that
        want partial results should catch per-branch inside their own
        coro_factory instead.
        """
        results: dict[str, Any] = {}
        for layer in self._layers():
            coros = [self._nodes[name].coro_factory() for name in layer]
            layer_results = await asyncio.gather(*coros)
            for name, result in zip(layer, layer_results):
                results[name] = result
        return results
