from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DataChunk:
    id: str
    index: int
    total: int
    content: str
    summary: str = ""
    connector_prev: str = ""
    connector_next: str = ""
    quality_score: float = 1.0
    validated: bool = True


@dataclass
class ValidationReport:
    passed: bool
    issues: list[str] = field(default_factory=list)
    security_issues: list[str] = field(default_factory=list)
    size_bytes: int = 0
    quality_score: float = 1.0


_MAX_CHUNK_SIZE = 2000
_MIN_CHUNK_SIZE = 300
_SECURITY_PATTERNS = [
    r"(?:-----BEGIN\s+PRIVATE\s+KEY-----)",
    r"(?:sk-[a-zA-Z0-9]{20,})",
    r"(?:ghp_[a-zA-Z0-9]{36,})",
    r"(?:AKIA[0-9A-Z]{16})",
    r"(?:\b(?:password|parol|secret|api[_-]?key)\s*[:=]\s*['\"]?\S{8,})",
]
_SENSITIVE_EXTENSIONS = {".env", ".pem", ".key", ".cred", ".secret"}


def _has_sensitive_data(text: str) -> list[str]:
    found = []
    for pat in _SECURITY_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            found.append(f"Possible secret matched pattern")
    return found


def validate_output(text: str, source_path: str | None = None) -> ValidationReport:
    issues = []
    security = _has_sensitive_data(text)
    size = len(text.encode("utf-8"))

    if size > 1_000_000:
        issues.append(f"Output too large: {size / 1024:.0f} KB")
    if not text.strip():
        issues.append("Empty output")

    score = 1.0
    if security:
        score -= 0.3 * len(security)
    if issues:
        score -= 0.1 * len(issues)
    score = max(0.0, score)

    return ValidationReport(
        passed=len(security) == 0,
        issues=issues,
        security_issues=security,
        size_bytes=size,
        quality_score=score,
    )


def _find_split_points(text: str, target_size: int) -> list[int]:
    if len(text) <= target_size:
        return []

    paragraphs = text.split("\n\n")
    splits = []
    current = 0

    for para in paragraphs:
        if current + len(para) > target_size and current >= _MIN_CHUNK_SIZE:
            splits.append(current)
            current = 0
        current += len(para) + 2

    return splits


def chunk_response(text: str, chunk_callback: Callable[[DataChunk], None] | None = None) -> list[DataChunk]:
    report = validate_output(text)
    if not report.passed and report.security_issues:
        return [DataChunk(id="sec-0", index=0, total=1, content="[Output blocked: contains sensitive data]", validated=False, quality_score=0.0)]

    if len(text) <= _MAX_CHUNK_SIZE:
        chunk = DataChunk(
            id="chunk-0", index=0, total=1, content=text,
            summary="Complete response", validated=True,
        )
        if chunk_callback:
            chunk_callback(chunk)
        return [chunk]

    split_points = _find_split_points(text, _MAX_CHUNK_SIZE)
    if not split_points:
        chunk = DataChunk(
            id="chunk-0", index=0, total=1, content=text,
            summary="Complete response (single block)", validated=True,
        )
        if chunk_callback:
            chunk_callback(chunk)
        return [chunk]

    boundaries = [0] + split_points + [len(text)]
    chunks = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        piece = text[start:end].strip()
        if not piece:
            continue

        summary = piece[:80].replace("\n", " ") + ("..." if len(piece) > 80 else "")
        prev_summary = chunks[-1].summary if chunks else "(start)"
        next_summary = ""

        chunk = DataChunk(
            id=f"chunk-{i}", index=len(chunks), total=0,
            content=piece, summary=summary,
            connector_prev=f"Previous: {prev_summary}",
            connector_next=f"Next: {next_summary}",
            validated=True, quality_score=1.0,
        )
        chunks.append(chunk)

    total = len(chunks)
    for c in chunks:
        c.total = total
        if c.index < total - 1:
            c.connector_next = f"Next: {chunks[c.index + 1].summary}"

    if chunk_callback:
        for c in chunks:
            chunk_callback(c)

    return chunks


__all__ = [
    "DataChunk", "ValidationReport",
    "validate_output", "chunk_response",
]
