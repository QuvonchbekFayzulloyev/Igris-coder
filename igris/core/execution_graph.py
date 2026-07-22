"""
igris.core.execution_graph
-----------------------------
Runs a set of named async jobs as a DAG. Independent branches run
concurrently; dependent ones wait. Single-branch sequences run
sequentially with optional verification between steps.

Every task goes through this engine -- no more single giant LLM calls.
Instead, each mini work cycle gets its own focused scope.
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
    pass


class ExecutionGraph:
    def __init__(self):
        self._nodes: dict[str, _Node] = {}

    def add(self, name: str, coro_factory: Callable[[], Awaitable[Any]], depends_on: list[str] | None = None) -> None:
        if name in self._nodes:
            raise GraphError(f"Duplicate node name '{name}'")
        self._nodes[name] = _Node(name=name, coro_factory=coro_factory, depends_on=list(depends_on or []))

    def _layers(self) -> list[list[str]]:
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
        results: dict[str, Any] = {}
        for layer in self._layers():
            coros = [self._nodes[name].coro_factory() for name in layer]
            layer_results = await asyncio.gather(*coros)
            for name, result in zip(layer, layer_results):
                results[name] = result
        return results

    async def run_sequential(self, verify_fn: Callable[[str, Any], Awaitable[bool]] | None = None) -> dict[str, Any]:
        """
        Run nodes in dependency order but one at a time (not concurrent).
        If verify_fn is provided, call it after each node with (name, result).
        If it returns False, stop and return partial results.
        """
        results: dict[str, Any] = {}
        for layer in self._layers():
            for name in layer:
                result = await self._nodes[name].coro_factory()
                results[name] = result
                if verify_fn:
                    ok = await verify_fn(name, result)
                    if not ok:
                        break
        return results
