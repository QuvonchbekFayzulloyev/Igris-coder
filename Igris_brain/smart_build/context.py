"""§5 Codebase Context Engine — taskga relevant fayllarni topish."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelevantFile:
    """Relevant fayl."""
    path: str
    relevance: float = 0.0
    reason: str = ""
    content_preview: str = ""
    line_count: int = 0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "relevance": round(self.relevance, 3),
            "reason": self.reason,
            "line_count": self.line_count,
        }


@dataclass
class ContextResult:
    """Context engine natijasi."""
    relevant_files: list[RelevantFile] = field(default_factory=list)
    summary: str = ""
    total_tokens: int = 0
    budget_remaining: int = 0

    def to_dict(self) -> dict:
        return {
            "relevant_files": [f.to_dict() for f in self.relevant_files],
            "summary": self.summary,
            "total_tokens": self.total_tokens,
        }


class ContextEngine:
    """Task uchun relevant context topish."""

    def __init__(self, project_root: str = "", max_tokens: int = 8000):
        self.project_root = project_root
        self.max_tokens = max_tokens

    def get_context(self, task: str, project_info: dict = None) -> ContextResult:
        """Task uchun context topish."""
        result = ContextResult()

        # 1. Relevant fayllarni topish
        result.relevant_files = self._find_relevant_files(task)

        # 2. Context yaratish
        result.summary = self._build_summary(result.relevant_files, task)

        # 3. Token hisoblash
        result.total_tokens = self._estimate_tokens(result.summary)
        result.budget_remaining = self.max_tokens - result.total_tokens

        return result

    def _find_relevant_files(self, task: str) -> list[RelevantFile]:
        """Task'ga relevant fayllarni topish."""
        relevant = []
        task_words = set(task.lower().split())

        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for fname in files:
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.project_root)

                # Skip binary/hidden files
                if fname.startswith(".") or fname.endswith((".pyc", ".pyo", ".so", ".dll")):
                    continue

                relevance = self._calculate_relevance(rel_path, task_words)
                if relevance > 0.3:
                    content_preview = self._read_preview(fpath)
                    line_count = self._count_lines(fpath)
                    relevant.append(RelevantFile(
                        path=rel_path,
                        relevance=relevance,
                        reason=self._explain_relevance(rel_path, task_words),
                        content_preview=content_preview,
                        line_count=line_count,
                    ))

        # Relevance bo'yicha saralash
        relevant.sort(key=lambda f: f.relevance, reverse=True)
        return relevant[:20]

    def _calculate_relevance(self, path: str, task_words: set) -> float:
        """Fayl relevance'ini hisoblash."""
        score = 0.0
        path_lower = path.lower()

        # Filename match
        for word in task_words:
            if word in path_lower:
                score += 0.3

        # Path structure
        if "src" in path_lower or "lib" in path_lower:
            score += 0.1
        if "test" in path_lower:
            score += 0.05
        if "config" in path_lower:
            score += 0.05

        return min(score, 1.0)

    def _explain_relevance(self, path: str, task_words: set) -> str:
        """Relevance tushuntirishi."""
        reasons = []
        path_lower = path.lower()
        for word in task_words:
            if word in path_lower:
                reasons.append(f"filename contains '{word}'")
        return "; ".join(reasons) or "file in project structure"

    def _read_preview(self, path: str, max_lines: int = 10) -> str:
        """Fayl preview'ini o'qish."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
            return "\n".join(lines)
        except Exception:
            return ""

    def _count_lines(self, path: str) -> int:
        """Fayl qatorlarini hisoblash."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _build_summary(self, files: list[RelevantFile], task: str) -> str:
        """Context xulosasini yaratish."""
        lines = [f"Task: {task}", f"Relevant files: {len(files)}", ""]
        for f in files[:10]:
            lines.append(f"- {f.path} ({f.line_count} lines, relevance: {f.relevance:.0%})")
            if f.content_preview:
                preview = f.content_preview[:200].replace("\n", " ")
                lines.append(f"  Preview: {preview}")
        return "\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """Token sonini taxmin qilish."""
        return len(text) // 4
