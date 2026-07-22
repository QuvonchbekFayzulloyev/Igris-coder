"""
Typed memory entries with discriminated union.
Inspired by cognee's entry types, adapted for local-first file storage.

Each entry has:
  - type discriminator (qa, trace, feedback, memo, pattern, decision)
  - structured payload via discriminated fields
  - standard metadata (created_at, tags, priority, ttl)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryPriority(Enum):
    P0_CURRENT = 0
    P1_API = 1
    P2_ARCHITECTURE = 2
    P3_COMPONENT = 3
    P4_RESEARCH = 4
    P5_REFERENCE = 5
    P6_HISTORICAL = 6


class KnowledgeLevel(Enum):
    L1_SUMMARY = 1
    L2_REASONING = 2
    L3_EVIDENCE = 3


@dataclass
class QAEntry:
    type: str = "qa"
    question: str = ""
    answer: str = ""
    context: str = ""
    feedback_text: str | None = None
    feedback_score: int | None = None
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P4_RESEARCH

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class TraceEntry:
    type: str = "trace"
    tool_name: str = ""
    status: str = "success"
    params: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    error: str = ""
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P3_COMPONENT

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class FeedbackEntry:
    type: str = "feedback"
    target_id: str = ""
    score: int = 0
    text: str = ""
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P5_REFERENCE

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class MemoEntry:
    type: str = "memo"
    topic: str = ""
    content: str = ""
    level1: str = ""
    level2: str = ""
    level3: str = ""
    source: str = ""
    confidence: float = 0.0
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P4_RESEARCH

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class PatternEntry:
    type: str = "pattern"
    name: str = ""
    description: str = ""
    category: str = ""
    examples: list[str] = field(default_factory=list)
    frequency: float = 0.0
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P2_ARCHITECTURE

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class DecisionEntry:
    type: str = "decision"
    question: str = ""
    answer: str = ""
    reasoning: str = ""
    alternatives: list[tuple[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    id: str = ""
    created_at: float = 0.0
    last_accessed: float = 0.0
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    priority: MemoryPriority = MemoryPriority.P2_ARCHITECTURE

    def touch(self):
        self.last_accessed = time.time()
        self.access_count += 1


MemoryEntry = QAEntry | TraceEntry | FeedbackEntry | MemoEntry | PatternEntry | DecisionEntry


def make_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


_SERIALIZABLE_TYPES = {
    "qa": QAEntry,
    "trace": TraceEntry,
    "feedback": FeedbackEntry,
    "memo": MemoEntry,
    "pattern": PatternEntry,
    "decision": DecisionEntry,
}


def serialize(entry: MemoryEntry) -> dict:
    d = {}
    for k, v in entry.__dict__.items():
        if isinstance(v, Enum):
            d[k] = v.value
        elif isinstance(v, list) and v and isinstance(v[0], tuple):
            d[k] = [list(t) for t in v]
        else:
            d[k] = v
    if "_kind" not in d:
        d["_kind"] = "entry"
    return d


def deserialize(data: dict) -> MemoryEntry | None:
    cls = _SERIALIZABLE_TYPES.get(data.get("type", ""))
    if cls is None:
        return None
    kwargs = {}
    for k, v in data.items():
        if k == "_kind":
            continue
        if k == "priority" and isinstance(v, int):
            kwargs[k] = MemoryPriority(v)
        elif k == "alternatives" and isinstance(v, list):
            kwargs[k] = [tuple(t) for t in v]
        elif k == "level" and isinstance(v, int):
            kwargs[k] = KnowledgeLevel(v)
        elif k in cls.__dataclass_fields__:
            kwargs[k] = v
    return cls(**kwargs)
