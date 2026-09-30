"""§4 Requirement Analyzer — user taskni tahlil qilish."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Requirement:
    """Bitta requirement."""
    text: str
    type: str = "explicit"  # explicit, implicit, constraint
    priority: str = "medium"  # low, medium, high, critical
    is_testable: bool = True
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class TaskAnalysis:
    """Task tahlili natijasi."""
    original_task: str
    interpreted_task: str = ""
    requirements: list[Requirement] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    expected_output: str = ""
    non_goals: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    complexity: str = "medium"  # simple, medium, complex
    estimated_steps: int = 0

    def to_dict(self) -> dict:
        return {
            "original_task": self.original_task,
            "interpreted_task": self.interpreted_task,
            "requirements": [{"text": r.text, "type": r.type, "priority": r.priority} for r in self.requirements],
            "constraints": self.constraints,
            "expected_output": self.expected_output,
            "non_goals": self.non_goals,
            "subtasks": self.subtasks,
            "ambiguities": self.ambiguities,
            "contradictions": self.contradictions,
            "missing_info": self.missing_info,
            "complexity": self.complexity,
            "estimated_steps": self.estimated_steps,
        }


class RequirementAnalyzer:
    """User taskni tahlil qilish."""

    def analyze(self, task: str, project_context: dict = None) -> TaskAnalysis:
        """Task'ni to'liq tahlil qilish."""
        analysis = TaskAnalysis(original_task=task)
        analysis.interpreted_task = self._interpret_task(task)
        analysis.requirements = self._extract_requirements(task)
        analysis.constraints = self._extract_constraints(task, project_context)
        analysis.expected_output = self._infer_expected_output(task)
        analysis.non_goals = self._infer_non_goals(task)
        analysis.subtasks = self._decompose_task(task)
        analysis.dependencies = self._find_dependencies(task)
        analysis.ambiguities = self._find_ambiguities(task)
        analysis.contradictions = self._find_contradictions(task)
        analysis.missing_info = self._find_missing_info(task)
        analysis.complexity = self._assess_complexity(task)
        analysis.estimated_steps = self._estimate_steps(analysis)
        return analysis

    def _interpret_task(self, task: str) -> str:
        """Task'ni qayta interpretatsiya qilish."""
        # Oddiy qayta yozish
        return task.strip()

    def _extract_requirements(self, task: str) -> list[Requirement]:
        """Task'dan requirement'larni ajratish."""
        requirements = []
        # Explicit requirements
        req_patterns = [
            r"(qil|yarat|tuz|o'zgartir|qo'sh|o'chir|tahrirla)",
            r"(create|add|remove|modify|update|fix|implement)",
            r"(kerak|shart|majburiy| zarur)",
            r"(must|should|need to|have to)",
        ]
        for pattern in req_patterns:
            matches = re.findall(pattern, task.lower())
            for match in matches:
                requirements.append(Requirement(
                    text=match,
                    type="explicit",
                    priority="high",
                ))

        # Implicit requirements
        implicit = [
            "test", "documentation", "error handling", "logging",
            "security", "performance", "accessibility",
        ]
        for word in implicit:
            if word in task.lower():
                requirements.append(Requirement(
                    text=word,
                    type="implicit",
                    priority="medium",
                ))

        return requirements

    def _extract_constraints(self, task: str, project_context: dict = None) -> list[str]:
        """Constraint'larni aniqlash."""
        constraints = []
        # Time constraints
        if any(w in task.lower() for w in ["tez", "fast", "quick", "shoshilinch"]):
            constraints.append("time_constraint")
        # Quality constraints
        if any(w in task.lower() for w in ["sifatli", "clean", "proper", "to'g'ri"]):
            constraints.append("quality_constraint")
        # Compatibility constraints
        if any(w in task.lower() for w in ["backward", "compat", "eski"]):
            constraints.append("compatibility_constraint")
        return constraints

    def _infer_expected_output(self, task: str) -> str:
        """Kutilgan natijani aniqlash."""
        if any(w in task.lower() for w in ["yarat", "create", "build"]):
            return "new_code"
        if any(w in task.lower() for w in ["tuzat", "fix", "repair"]):
            return "fixed_code"
        if any(w in task.lower() for w in ["o'zgartir", "modify", "refactor"]):
            return "modified_code"
        return "unknown"

    def _infer_non_goals(self, task: str) -> list[str]:
        """Nima qilinmasligi kerakligini aniqlash."""
        non_goals = []
        if "rewrite" not in task.lower():
            non_goals.append("full_rewrite")
        if "migrate" not in task.lower():
            non_goals.append("migration")
        return non_goals

    def _decompose_task(self, task: str) -> list[str]:
        """Task'ni kichik qismlarga ajratish."""
        subtasks = []
        # Simple decomposition based on action words
        actions = ["read", "analyze", "plan", "implement", "test", "verify"]
        for action in actions:
            if action in task.lower():
                subtasks.append(action)
        if not subtasks:
            subtasks = ["analyze", "implement", "test"]
        return subtasks

    def _find_dependencies(self, task: str) -> list[str]:
        """Dependency'larni topish."""
        deps = []
        dep_words = ["depend", "require", "need", "use", "leverage"]
        for word in dep_words:
            if word in task.lower():
                deps.append(word)
        return deps

    def _find_ambiguities(self, task: str) -> list[str]:
        """Noaniqliklarni topish."""
        ambiguities = []
        ambiguous_words = ["maybe", "perhaps", "might", "possibly", "shayt", "ehtimol"]
        for word in ambiguous_words:
            if word in task.lower():
                ambiguities.append(f"ambiguous_term: {word}")
        return ambiguities

    def _find_contradictions(self, task: str) -> list[str]:
        """Ziddiyatlarni topish."""
        contradictions = []
        # Simple contradiction detection
        if "tez" in task.lower() and "sifatli" in task.lower():
            contradictions.append("speed vs quality")
        return contradictions

    def _find_missing_info(self, task: str) -> list[str]:
        """Yetarli ma'lumot yo'qligini aniqlash."""
        missing = []
        if "?" in task and len(task.split()) < 10:
            missing.append("unclear_requirements")
        return missing

    def _assess_complexity(self, task: str) -> str:
        """Murakkablikni baholash."""
        word_count = len(task.split())
        if word_count < 10:
            return "simple"
        elif word_count < 30:
            return "medium"
        return "complex"

    def _estimate_steps(self, analysis: TaskAnalysis) -> int:
        """Taxminiy qadam sonini hisoblash."""
        base = len(analysis.subtasks) or 3
        if analysis.complexity == "complex":
            base *= 2
        return base
