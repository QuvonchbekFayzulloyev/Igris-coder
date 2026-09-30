"""Context Intelligence Engine — LLMga minimal, lekin yetarli context berish.

Core principle: LLMga "butun project" emas, "qaror uchun kerakli evidence" beriladi.
Retrieval → Filter → Rank → Compress → LLM
"""
from __future__ import annotations

import ast
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskComplexity(str, Enum):
    """Task murakkabligi."""
    TRIVIAL = "trivial"      # file rename, typo fix — LLM kerak emas
    SIMPLE = "simple"        # add function, small config — kichik LLM
    MEDIUM = "medium"        # new feature, API endpoint — o'rta LLM
    COMPLEX = "complex"      # architecture change, refactor — kuchli LLM
    AMBIGUOUS = "ambiguous"  # conflicting requirements — deep reasoning


class RetrievalType(str, Enum):
    """Retrieval turlari."""
    SEMANTIC = "semantic"
    SYMBOL = "symbol"
    DEPENDENCY = "dependency"
    TEST = "test"
    RECENT = "recent"
    ARCHITECTURE = "architecture"


@dataclass
class RetrievedItem:
    """Bitta retrieval natijasi."""
    item_id: str
    item_type: RetrievalType
    path: str
    content: str = ""
    relevance_score: float = 0.0
    evidence: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "type": self.item_type.value,
            "path": self.path,
            "relevance": round(self.relevance_score, 3),
            "evidence": self.evidence,
            "content_preview": self.content[:100] if self.content else "",
        }


@dataclass
class CompressedContext:
    """LLM uchun siqilgan context."""
    task: str
    complexity: TaskComplexity
    entry_point: str = ""
    framework: str = ""
    language: str = ""
    # Structure
    relevant_files: list[RetrievedItem] = field(default_factory=list)
    relevant_symbols: list[RetrievedItem] = field(default_factory=list)
    dependencies: list[RetrievedItem] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    # Facts
    facts: dict = field(default_factory=dict)
    # Token budget
    token_budget: int = 8000
    tokens_used: int = 0
    # State
    current_step: int = 0
    total_steps: int = 0
    completed_steps: list[int] = field(default_factory=list)
    failed_steps: list[int] = field(default_factory=list)

    def to_llm_prompt(self) -> str:
        """LLM uchun optimal prompt formatida."""
        lines = [
            f"TASK: {self.task}",
            f"COMPLEXITY: {self.complexity.value}",
            f"CONTEXT BUDGET: {self.tokens_used}/{self.token_budget} tokens",
            "",
        ]

        # Entry point
        if self.entry_point:
            lines.append(f"ENTRY: {self.entry_point}")

        # Framework
        if self.framework:
            lines.append(f"FRAMEWORK: {self.framework}")

        # Relevant files
        if self.relevant_files:
            lines.append("\nRELEVANT FILES:")
            for f in self.relevant_files[:10]:
                lines.append(f"  {f.path} (relevance: {f.relevance_score:.0%})")

        # Relevant symbols
        if self.relevant_symbols:
            lines.append("\nRELEVANT SYMBOLS:")
            for s in self.relevant_symbols[:5]:
                lines.append(f"  {s.evidence}")

        # Dependencies
        if self.dependencies:
            lines.append("\nDEPENDENCIES:")
            for d in self.dependencies[:5]:
                lines.append(f"  {d.path}")

        # Constraints
        if self.constraints:
            lines.append("\nCONSTRAINTS:")
            for c in self.constraints:
                lines.append(f"  - {c}")

        # Facts
        if self.facts:
            lines.append("\nFACTS:")
            for k, v in self.facts.items():
                lines.append(f"  {k}: {v}")

        # State
        if self.total_steps > 0:
            lines.append(f"\nSTATE: Step {self.current_step}/{self.total_steps}")
            if self.completed_steps:
                lines.append(f"  Completed: {self.completed_steps}")
            if self.failed_steps:
                lines.append(f"  Failed: {self.failed_steps}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "complexity": self.complexity.value,
            "entry_point": self.entry_point,
            "framework": self.framework,
            "language": self.language,
            "relevant_files": len(self.relevant_files),
            "relevant_symbols": len(self.relevant_symbols),
            "dependencies": len(self.dependencies),
            "constraints": self.constraints,
            "facts": self.facts,
            "tokens_used": self.tokens_used,
            "token_budget": self.token_budget,
        }


class ContextIntelligenceEngine:
    """LLM workload reducer — retrieval, filter, rank, compress.

    Pipeline:
    Task → Retrieval → Filter → Rank → Compress → LLM
    """

    def __init__(self, project_root: str = "", token_budget: int = 8000):
        self.project_root = project_root
        self.token_budget = token_budget
        self._file_cache: dict[str, str] = {}

    # ── RETRIEVAL ──────────────────────────────────────────────

    def retrieve_by_semantic(self, task: str) -> list[RetrievedItem]:
        """Task'ga semantic mos fayllarni topish."""
        items = []
        task_words = set(task.lower().split())
        keywords = {w for w in task_words if len(w) > 3}

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith(".") or fname.endswith((".pyc", ".pyo")):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.project_root)
                score = self._semantic_score(rel_path, keywords)
                if score > 0.2:
                    items.append(RetrievedItem(
                        item_id=f"sem_{rel_path}",
                        item_type=RetrievalType.SEMANTIC,
                        path=rel_path,
                        relevance_score=score,
                        evidence=f"semantic match: {rel_path}",
                    ))
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items[:20]

    def retrieve_by_symbol(self, task: str) -> list[RetrievedItem]:
        """Task'da tilga olingan symbol'larni topish."""
        items = []
        # Extract identifiers from task
        identifiers = set(re.findall(r'\b[A-Z][a-zA-Z]+\b', task))
        identifiers.update(re.findall(r'\b[a-z_]+(?:_[a-z]+)+\b', task))

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.project_root)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name in identifiers:
                                items.append(RetrievedItem(
                                    item_id=f"sym_{rel_path}:{node.name}",
                                    item_type=RetrievalType.SYMBOL,
                                    path=rel_path,
                                    evidence=f"function {node.name} at line {node.lineno}",
                                    metadata={"line": node.lineno, "name": node.name},
                                ))
                        elif isinstance(node, ast.ClassDef):
                            if node.name in identifiers:
                                items.append(RetrievedItem(
                                    item_id=f"sym_{rel_path}:{node.name}",
                                    item_type=RetrievalType.SYMBOL,
                                    path=rel_path,
                                    evidence=f"class {node.name} at line {node.lineno}",
                                    metadata={"line": node.lineno, "name": node.name},
                                ))
                except Exception:
                    continue
        return items[:15]

    def retrieve_by_dependency(self, file_path: str) -> list[RetrievedItem]:
        """Fayl dependencylarini topish."""
        items = []
        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return items

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        items.append(RetrievedItem(
                            item_id=f"dep_{alias.name}",
                            item_type=RetrievalType.DEPENDENCY,
                            path=alias.name,
                            evidence=f"import {alias.name}",
                        ))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        items.append(RetrievedItem(
                            item_id=f"dep_{node.module}",
                            item_type=RetrievalType.DEPENDENCY,
                            path=node.module,
                            evidence=f"from {node.module} import ...",
                        ))
        except Exception:
            pass
        return items

    def retrieve_by_test(self, file_path: str) -> list[RetrievedItem]:
        """Faylga tegishli testlarni topish."""
        items = []
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.project_root)
                if "test" in rel_path.lower() and base_name.lower() in fname.lower():
                    items.append(RetrievedItem(
                        item_id=f"test_{rel_path}",
                        item_type=RetrievalType.TEST,
                        path=rel_path,
                        relevance_score=0.8,
                        evidence=f"test file for {file_path}",
                    ))
        return items

    # ── FILTER ─────────────────────────────────────────────────

    def filter_by_relevance(self, items: list[RetrievedItem],
                            min_score: float = 0.3) -> list[RetrievedItem]:
        """Past relevance score'li itemlarni filtrlash."""
        return [i for i in items if i.relevance_score >= min_score]

    def filter_by_duplicates(self, items: list[RetrievedItem]) -> list[RetrievedItem]:
        """Duplicate path'larni olib tashlash."""
        seen = set()
        result = []
        for item in items:
            key = item.path
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    # ── RANK ───────────────────────────────────────────────────

    def rank_items(self, items: list[RetrievedItem],
                   task: str) -> list[RetrievedItem]:
        """Itemlarni relevance bo'yicha saralash."""
        # Type weight
        type_weights = {
            RetrievalType.SYMBOL: 1.0,
            RetrievalType.SEMANTIC: 0.8,
            RetrievalType.DEPENDENCY: 0.7,
            RetrievalType.TEST: 0.6,
            RetrievalType.RECENT: 0.5,
            RetrievalType.ARCHITECTURE: 0.4,
        }
        for item in items:
            weight = type_weights.get(item.item_type, 0.5)
            item.relevance_score *= weight

        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items

    # ── COMPRESS ───────────────────────────────────────────────

    def compress_context(self, items: list[RetrievedItem],
                         task: str,
                         token_budget: int = None) -> CompressedContext:
        """Itemlarni LLM uchun siqilgan context ga aylantirish."""
        budget = token_budget or self.token_budget
        complexity = self._assess_complexity(task)

        context = CompressedContext(
            task=task,
            complexity=complexity,
            token_budget=budget,
        )

        tokens_used = 0
        for item in items:
            item_tokens = len(item.content) // 4 if item.content else 50
            if tokens_used + item_tokens > budget:
                break

            if item.item_type == RetrievalType.SYMBOL:
                context.relevant_symbols.append(item)
            elif item.item_type == RetrievalType.DEPENDENCY:
                context.dependencies.append(item)
            else:
                context.relevant_files.append(item)
            tokens_used += item_tokens

        context.tokens_used = tokens_used
        return context

    # ── FULL PIPELINE ──────────────────────────────────────────

    def process(self, task: str, token_budget: int = None) -> CompressedContext:
        """To'liq pipeline: retrieve → filter → rank → compress."""
        budget = token_budget or self.token_budget

        # 1. Semantic retrieval
        semantic_items = self.retrieve_by_semantic(task)

        # 2. Symbol retrieval
        symbol_items = self.retrieve_by_symbol(task)

        # 3. Combine
        all_items = semantic_items + symbol_items

        # 4. Filter
        filtered = self.filter_by_relevance(all_items, min_score=0.2)
        filtered = self.filter_by_duplicates(filtered)

        # 5. Rank
        ranked = self.rank_items(filtered, task)

        # 6. Compress
        context = self.compress_context(ranked, task, budget)

        return context

    # ── HELPERS ────────────────────────────────────────────────

    def _semantic_score(self, path: str, keywords: set) -> float:
        """Semantic relevance score."""
        score = 0.0
        path_lower = path.lower()
        for kw in keywords:
            if kw in path_lower:
                score += 0.3
        if "src" in path_lower:
            score += 0.1
        if "test" in path_lower:
            score += 0.05
        return min(score, 1.0)

    def _assess_complexity(self, task: str) -> TaskComplexity:
        """Task murakkabligini aniqlash."""
        task_lower = task.lower()
        if any(w in task_lower for w in ["rename", "typo", "comment"]):
            return TaskComplexity.TRIVIAL
        if any(w in task_lower for w in ["add function", "small", "config"]):
            return TaskComplexity.SIMPLE
        if any(w in task_lower for w in ["feature", "api", "endpoint", "module"]):
            return TaskComplexity.MEDIUM
        if any(w in task_lower for w in ["architecture", "refactor", "migrate"]):
            return TaskComplexity.COMPLEX
        if any(w in task_lower for w in ["conflict", "ambiguous", "unclear"]):
            return TaskComplexity.AMBIGUOUS
        return TaskComplexity.MEDIUM
