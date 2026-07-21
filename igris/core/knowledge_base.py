"""
igris.core.knowledge_base
----------------------------
A hierarchical knowledge store, deliberately NOT one big flat DB:

    .igris/knowledge/
      project.json              <- Level 1: the whole project's main
                                    parts, cross-cutting rules
      modules/
        backend.json             <- Level 2: a main module (backend,
        frontend.json                frontend are the top-level ones)
        backend.core.json         <- Level 3: sub-modules within a main
        backend.mcp_servers.json     module, dot-addressed
        frontend.components.json
        ...

Searching stays fast and precise because a query is routed to the
smallest relevant scope first (a specific sub-module's handful of
entries) rather than linear-scanning one large collection -- exactly the
accuracy/speed tradeoff a single flat DB gives up. Per
rag-llm-data-integration's own guidance, this stays plain JSON + cosine
similarity in pure Python: each individual file is small (a few dozen
entries at most), so a vector DB server or numpy would be solving a
problem this scale doesn't have.

Every entry is one of three kinds:
    rule        -- a constraint or convention that must hold
    description -- a factual description of how something works/should look
    template    -- a concrete code/text example to pattern-match against

and one of three sources:
    llm          -- drawn from the model's own trained knowledge
    web_verified -- cross-checked against a real, current web source
    manual       -- entered directly (by a human or the agent) as a fact
                    about this specific project, not general knowledge
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class KnowledgeEntry:
    id: str
    text: str
    module_path: str  # "" = top-level project DB; "backend", "backend.core", ...
    kind: str = "rule"  # rule | description | template
    source: str = "manual"  # llm | web_verified | manual
    tags: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeStore:
    def __init__(self, config):
        self.root = config.path_for("knowledge.dir")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "modules").mkdir(parents=True, exist_ok=True)

    def _path_for(self, module_path: str) -> Path:
        if not module_path:
            return self.root / "project.json"
        return self.root / "modules" / f"{module_path}.json"

    def _load_raw(self, module_path: str) -> list[dict]:
        path = self._path_for(module_path)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _save_raw(self, module_path: str, entries: list[dict]) -> None:
        path = self._path_for(module_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, entry: KnowledgeEntry) -> None:
        entries = self._load_raw(entry.module_path)
        entries.append(asdict(entry))
        self._save_raw(entry.module_path, entries)

    def load_module(self, module_path: str) -> list[KnowledgeEntry]:
        return [KnowledgeEntry(**raw) for raw in self._load_raw(module_path)]

    def list_modules(self) -> list[str]:
        modules_dir = self.root / "modules"
        if not modules_dir.exists():
            return []
        return sorted(p.stem for p in modules_dir.glob("*.json"))

    def _ancestor_scopes(self, module_path: str) -> list[str]:
        """['backend.core', 'backend', ''] -- narrowest to broadest, always ending at project-level."""
        if not module_path:
            return [""]
        parts = module_path.split(".")
        scopes = [".".join(parts[: i + 1]) for i in range(len(parts))][::-1]
        scopes.append("")
        return scopes

    def search(self, query_embedding: list[float], module_path: str | None = None, top_k: int = 5) -> list[tuple[float, KnowledgeEntry]]:
        """
        Searches the given module scope plus every ancestor scope up to
        the project level (a query scoped to 'backend.core' also sees
        'backend'-level and project-level rules, since those still apply)
        -- but never the whole tree at once, which is what keeps this
        fast and precise even as more modules accumulate entries.
        """
        scopes = self._ancestor_scopes(module_path or "")
        candidates: list[KnowledgeEntry] = []
        for scope in scopes:
            candidates.extend(self.load_module(scope))

        scored = [
            (_cosine(query_embedding, e.embedding), e)
            for e in candidates
            if e.embedding
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:top_k]
