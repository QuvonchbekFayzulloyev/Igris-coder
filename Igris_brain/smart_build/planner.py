"""§7 Build Plan Generator — qurilish rejasini yaratish."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PlanStepType(str, Enum):
    """Plan qadami turlari."""
    READ = "read"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    MOVE = "move"
    RENAME = "rename"
    EXECUTE = "execute"
    TEST = "test"
    VERIFY = "verify"
    DEPENDENCY = "dependency"


@dataclass
class PlanStep:
    """Bitta plan qadami."""
    step_id: str
    step_type: PlanStepType
    description: str
    target_file: str = ""
    expected_result: str = ""
    failure_condition: str = ""
    evidence_type: str = ""  # filesystem, build, test, runtime
    is_critical: bool = False
    rollback_plan: str = ""

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "description": self.description,
            "target_file": self.target_file,
            "expected_result": self.expected_result,
            "failure_condition": self.failure_condition,
            "evidence_type": self.evidence_type,
            "is_critical": self.is_critical,
        }


@dataclass
class BuildPlan:
    """To'liq build rejasini yaratish."""
    plan_id: str = ""
    task: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    # Validation
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    # Estimates
    estimated_time_seconds: int = 0
    estimated_files_changed: int = 0

    def add_step(self, step_type: PlanStepType, description: str, **kwargs) -> PlanStep:
        """Step qo'shish."""
        step = PlanStep(
            step_id=f"step_{len(self.steps) + 1}",
            step_type=step_type,
            description=description,
            **kwargs,
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "task": self.task,
            "steps": [s.to_dict() for s in self.steps],
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "estimated_time_seconds": self.estimated_time_seconds,
            "estimated_files_changed": self.estimated_files_changed,
        }


class BuildPlanner:
    """Build rejasini yaratish."""

    def generate_plan(self, task: str, context: dict = None) -> BuildPlan:
        """Task uchun build rejasini yaratish."""
        plan = BuildPlan(
            plan_id=f"plan_{int(time.time())}",
            task=task,
        )

        # 1. Read steps
        plan.add_step(
            PlanStepType.READ,
            "Read existing codebase",
            evidence_type="filesystem",
        )

        # 2. Analysis
        plan.add_step(
            PlanStepType.READ,
            "Analyze requirements",
            evidence_type="filesystem",
        )

        # 3. Implementation steps (task-dependent)
        if self._needs_new_file(task):
            plan.add_step(
                PlanStepType.CREATE,
                "Create new file",
                target_file=self._suggest_filename(task),
                expected_result="File exists and is valid",
                failure_condition="File not created or syntax error",
                evidence_type="filesystem",
                is_critical=True,
            )
        elif self._needs_modification(task):
            plan.add_step(
                PlanStepType.MODIFY,
                "Modify existing file",
                expected_result="Changes applied correctly",
                failure_condition="Logic error or regression",
                evidence_type="filesystem",
                is_critical=True,
            )

        # 4. Test
        plan.add_step(
            PlanStepType.TEST,
            "Run tests",
            expected_result="All tests pass",
            failure_condition="Test failure",
            evidence_type="test",
            is_critical=True,
        )

        # 5. Verify
        plan.add_step(
            PlanStepType.VERIFY,
            "Verify build success",
            expected_result="Build succeeds",
            failure_condition="Build error",
            evidence_type="build",
            is_critical=True,
        )

        # Estimates
        plan.estimated_time_seconds = len(plan.steps) * 5
        plan.estimated_files_changed = sum(1 for s in plan.steps
                                            if s.step_type in (PlanStepType.CREATE, PlanStepType.MODIFY))

        return plan

    def validate_plan(self, plan: BuildPlan, project_info: dict = None) -> BuildPlan:
        """Plan'ni tekshirish."""
        errors = []

        # 1. Critical steps mavjudligi
        if not any(s.is_critical for s in plan.steps):
            errors.append("No critical steps defined")

        # 2. Evidence type mavjudligi
        if not any(s.evidence_type for s in plan.steps):
            errors.append("No evidence types defined")

        # 3. Circular dependency check
        # (simple check for now)

        plan.validation_errors = errors
        plan.is_valid = len(errors) == 0
        return plan

    def _needs_new_file(self, task: str) -> bool:
        """Yangi fayl kerakligini aniqlash."""
        return any(w in task.lower() for w in ["yarat", "create", "add", "qo'sh"])

    def _needs_modification(self, task: str) -> bool:
        """Fayl o'zgartirish kerakligini aniqlash."""
        return any(w in task.lower() for w in ["o'zgartir", "modify", "update", "tuzat", "fix"])

    def _suggest_filename(self, task: str) -> str:
        """Fayl nomini taklif qilish."""
        # Simple heuristic
        words = task.lower().split()
        if "test" in words:
            return "test_new_feature.py"
        if "config" in words:
            return "config.py"
        return "new_module.py"
