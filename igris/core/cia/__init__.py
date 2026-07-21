"""
igris.core.cia
----------------
Compact Intelligence Architecture (CIA) — memory system for 4-8B models.

Every design decisions minimizes token usage:
1. Never store raw data — store distilled knowledge
2. Never load full context — load progressive levels
3. Never re-think — cache decisions
4. Never keep unused data — lifecycle-managed

Memory levels (P0 = highest priority, loaded first, never evicted):
  P0: Current file / active task
  P1: API contracts, interface definitions
  P2: Architecture decisions, ADRs
  P3: Component structure, dependencies
  P4: Research memory (patterns, evidence)
  P5: Reference docs, examples
  P6: Historical, nice-to-have

Knowledge levels:
  L1 (20 tokens): Executive summary
  L2 (100 tokens): Reasoning with key facts
  L3 (1000+ tokens): Full evidence with sources
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryPriority(Enum):
    P0_CURRENT = 0  # Current file / task
    P1_API = 1       # API contracts
    P2_ARCHITECTURE = 2  # ADRs, decisions
    P3_COMPONENT = 3     # Component deps
    P4_RESEARCH = 4     # Patterns, evidence
    P5_REFERENCE = 5    # Docs, examples
    P6_HISTORICAL = 6   # Archive


class MemoryStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class KnowledgeLevel(Enum):
    L1_SUMMARY = 1   # 20 tokens
    L2_REASONING = 2 # 100 tokens
    L3_EVIDENCE = 3  # 1000+ tokens


@dataclass
class DistilledKnowledge:
    topic: str
    level1: str  # 20 token executive summary
    level2: str  # 100 token reasoning
    level3: str  # 1000+ token full evidence
    source: str = ""
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0


@dataclass
class MemoryEntry:
    id: str
    text: str
    memory_type: str  # project, module, component, function, decision, research, symbol, pattern
    priority: MemoryPriority = MemoryPriority.P4_RESEARCH
    level: KnowledgeLevel = KnowledgeLevel.L3_EVIDENCE

    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    ttl_seconds: float = 86400.0 * 30  # 30 days
    status: MemoryStatus = MemoryStatus.ACTIVE

    tags: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return time.time() - self.last_accessed > self.ttl_seconds

    @property
    def access_score(self) -> float:
        age = time.time() - self.created_at
        if age < 1:
            return 1.0
        return min(1.0, self.access_count / (age / 3600 + 1))

    def touch(self) -> None:
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class Decision:
    id: str
    question: str
    answer: str
    reasoning: str
    alternatives: list[tuple[str, str]] = field(default_factory=list)  # (name, reason_rejected)
    created_at: float = 0.0
    last_used: float = 0.0
    use_count: int = 0
    related_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def touch(self) -> None:
        self.last_used = time.time()
        self.use_count += 1


class CIAStore:
    """File-backed storage for CIA memory entries and decisions."""

    def __init__(self, store_dir: str | Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._decisions: dict[str, Decision] = {}
        self._load()

    def _path(self, name: str) -> Path:
        return self.store_dir / name

    def _load(self) -> None:
        for p in self.store_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text("utf-8"))
                kind = data.get("_kind", "")
                if kind == "entry":
                    e = MemoryEntry(**{k: v for k, v in data.items() if k != "_kind"})
                    self._entries[e.id] = e
                elif kind == "decision":
                    d = Decision(**{k: v for k, v in data.items() if k != "_kind"})
                    self._decisions[d.id] = d
            except Exception:
                pass

    def _save_entry(self, entry: MemoryEntry) -> None:
        data = entry.__dict__.copy()
        data["_kind"] = "entry"
        data["priority"] = entry.priority.value
        data["level"] = entry.level.value
        data["status"] = entry.status.value
        self._path(f"entry_{entry.id}.json").write_text(json.dumps(data, indent=2, default=str), "utf-8")

    def _save_decision(self, decision: Decision) -> None:
        data = decision.__dict__.copy()
        data["_kind"] = "decision"
        self._path(f"decision_{decision.id}.json").write_text(json.dumps(data, indent=2, default=str), "utf-8")

    def put_entry(self, entry: MemoryEntry) -> None:
        self._entries[entry.id] = entry
        self._save_entry(entry)

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        e = self._entries.get(entry_id)
        if e:
            e.touch()
            self._save_entry(e)
        return e

    def delete_entry(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)
        p = self._path(f"entry_{entry_id}.json")
        if p.exists():
            p.unlink()

    def put_decision(self, decision: Decision) -> None:
        self._decisions[decision.id] = decision
        self._save_decision(decision)

    def get_decision(self, decision_id: str) -> Decision | None:
        d = self._decisions.get(decision_id)
        if d:
            d.touch()
            self._save_decision(d)
        return d

    def find_decision(self, question: str) -> Decision | None:
        q_lower = question.lower()
        for d in self._decisions.values():
            if q_lower in d.question.lower():
                return d
        return None

    def list_active(self, memory_type: str | None = None) -> list[MemoryEntry]:
        result = [e for e in self._entries.values() if e.status == MemoryStatus.ACTIVE]
        if memory_type:
            result = [e for e in result if e.memory_type == memory_type]
        result.sort(key=lambda e: (e.priority.value, -e.access_score))
        return result

    def list_archived(self) -> list[MemoryEntry]:
        return [e for e in self._entries.values() if e.status == MemoryStatus.ARCHIVED]

    def query(self, text: str, top_k: int = 5) -> list[MemoryEntry]:
        text_lower = text.lower()
        scored = []
        for e in self._entries.values():
            if e.status != MemoryStatus.ACTIVE:
                continue
            score = 0
            if text_lower in e.text.lower():
                score += 3
            if text_lower in e.id.lower():
                score += 2
            for tag in e.tags:
                if text_lower in tag.lower():
                    score += 1
            if score > 0:
                scored.append((score / (e.priority.value + 1), e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]
