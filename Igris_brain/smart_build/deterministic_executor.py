"""Deterministic Executor — LLMsiz bajariladigan operatsiyalar.

Core principle: LLMning hajmini oshirmasdan agentning intelligence'ini oshirish.
Ko'p narsani LLMsiz bajarish mumkin: filesystem, AST, parser, compiler, runtime.
"""
from __future__ import annotations

import ast
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExecutionAction(str, Enum):
    """Deterministic harakatlar."""
    FILE_EXISTS = "file_exists"
    FILE_NOT_EMPTY = "file_not_empty"
    FILE_READABLE = "file_readable"
    FUNCTION_EXISTS = "function_exists"
    CLASS_EXISTS = "class_exists"
    IMPORT_VALID = "import_valid"
    SYNTAX_VALID = "syntax_valid"
    DEPENDENCY_EXISTS = "dependency_exists"
    TEST_RUNS = "test_runs"
    BUILD_SUCCEEDS = "build_succeeds"
    PROCESS_RUNNING = "process_running"
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    FILE_RENAME = "file_rename"
    DIR_CREATE = "dir_create"
    COMMAND_RUN = "command_run"
    PACKAGE_INSTALL = "package_install"


class ExecutionStatus(str, Enum):
    """Execution holati."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


@dataclass
class ExecutionEvidence:
    """Bitta evidence."""
    action: ExecutionAction
    status: ExecutionStatus
    details: str = ""
    file_path: str = ""
    command: str = ""
    output: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "status": self.status.value,
            "details": self.details[:200],
            "file_path": self.file_path,
            "command": self.command,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class ExecutionPlan:
    """Deterministic execution rejasini yaratish."""
    task: str
    steps: list[dict] = field(default_factory=list)
    evidence: list[ExecutionEvidence] = field(default_factory=list)
    is_complete: bool = False

    def add_step(self, action: ExecutionAction, **kwargs):
        self.steps.append({"action": action.value, **kwargs})

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "step_count": len(self.steps),
            "evidence_count": len(self.evidence),
            "is_complete": self.is_complete,
        }


class DeterministicExecutor:
    """LLM-free execution engine."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root

    # ── FILESYSTEM CHECKS ──────────────────────────────────────

    def check_file_exists(self, path: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, path)
        exists = os.path.exists(full)
        return ExecutionEvidence(
            action=ExecutionAction.FILE_EXISTS,
            status=ExecutionStatus.SUCCESS if exists else ExecutionStatus.FAILED,
            details=f"File {path} {'exists' if exists else 'does not exist'}",
            file_path=path,
        )

    def check_file_not_empty(self, path: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, path)
        if not os.path.exists(full):
            return ExecutionEvidence(
                action=ExecutionAction.FILE_NOT_EMPTY,
                status=ExecutionStatus.FAILED,
                details=f"File {path} does not exist",
                file_path=path,
            )
        size = os.path.getsize(full)
        return ExecutionEvidence(
            action=ExecutionAction.FILE_NOT_EMPTY,
            status=ExecutionStatus.SUCCESS if size > 0 else ExecutionStatus.FAILED,
            details=f"File {path}: {size} bytes",
            file_path=path,
        )

    def check_file_readable(self, path: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, path)
        try:
            with open(full, "r", encoding="utf-8") as f:
                f.read(1)
            return ExecutionEvidence(
                action=ExecutionAction.FILE_READABLE,
                status=ExecutionStatus.SUCCESS,
                details=f"File {path} is readable",
                file_path=path,
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.FILE_READABLE,
                status=ExecutionStatus.FAILED,
                details=f"File {path} not readable: {e}",
                file_path=path,
            )

    # ── CODE CHECKS ────────────────────────────────────────────

    def check_function_exists(self, file_path: str, func_name: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, file_path)
        if not os.path.exists(full):
            return ExecutionEvidence(
                action=ExecutionAction.FUNCTION_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"File {file_path} does not exist",
                file_path=file_path,
            )
        try:
            with open(full, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == func_name:
                        return ExecutionEvidence(
                            action=ExecutionAction.FUNCTION_EXISTS,
                            status=ExecutionStatus.SUCCESS,
                            details=f"Function {func_name} found at line {node.lineno}",
                            file_path=file_path,
                        )
            return ExecutionEvidence(
                action=ExecutionAction.FUNCTION_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"Function {func_name} not found in {file_path}",
                file_path=file_path,
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.FUNCTION_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"AST parse error: {e}",
                file_path=file_path,
            )

    def check_class_exists(self, file_path: str, class_name: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, file_path)
        if not os.path.exists(full):
            return ExecutionEvidence(
                action=ExecutionAction.CLASS_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"File {file_path} does not exist",
                file_path=file_path,
            )
        try:
            with open(full, "r") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name == class_name:
                        return ExecutionEvidence(
                            action=ExecutionAction.CLASS_EXISTS,
                            status=ExecutionStatus.SUCCESS,
                            details=f"Class {class_name} found at line {node.lineno}",
                            file_path=file_path,
                        )
            return ExecutionEvidence(
                action=ExecutionAction.CLASS_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"Class {class_name} not found in {file_path}",
                file_path=file_path,
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.CLASS_EXISTS,
                status=ExecutionStatus.FAILED,
                details=f"AST parse error: {e}",
                file_path=file_path,
            )

    def check_syntax_valid(self, file_path: str) -> ExecutionEvidence:
        full = os.path.join(self.project_root, file_path)
        if not file_path.endswith(".py"):
            return ExecutionEvidence(
                action=ExecutionAction.SYNTAX_VALID,
                status=ExecutionStatus.SUCCESS,
                details="Not a Python file, skipping syntax check",
            )
        if not os.path.exists(full):
            return ExecutionEvidence(
                action=ExecutionAction.SYNTAX_VALID,
                status=ExecutionStatus.FAILED,
                details=f"File {file_path} does not exist",
                file_path=file_path,
            )
        try:
            with open(full, "r") as f:
                compile(f.read(), full, "exec")
            return ExecutionEvidence(
                action=ExecutionAction.SYNTAX_VALID,
                status=ExecutionStatus.SUCCESS,
                details=f"Syntax valid for {file_path}",
                file_path=file_path,
            )
        except SyntaxError as e:
            return ExecutionEvidence(
                action=ExecutionAction.SYNTAX_VALID,
                status=ExecutionStatus.FAILED,
                details=f"Syntax error: {e}",
                file_path=file_path,
            )

    def check_import_valid(self, module: str) -> ExecutionEvidence:
        try:
            result = subprocess.run(
                ["python", "-c", f"import {module}"],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_root,
            )
            return ExecutionEvidence(
                action=ExecutionAction.IMPORT_VALID,
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                details=f"Import {module}: {'OK' if result.returncode == 0 else result.stderr[:100]}",
                command=f"import {module}",
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.IMPORT_VALID,
                status=ExecutionStatus.FAILED,
                details=f"Import check failed: {e}",
            )

    # ── BUILD CHECKS ───────────────────────────────────────────

    def check_build_succeeds(self, command: str = "") -> ExecutionEvidence:
        cmd = command or "python -m py_compile ."
        start = time.time()
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60,
                cwd=self.project_root,
            )
            duration = (time.time() - start) * 1000
            return ExecutionEvidence(
                action=ExecutionAction.BUILD_SUCCEEDS,
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                details=f"Build {'OK' if result.returncode == 0 else 'FAILED'}",
                command=cmd,
                output=result.stdout[-300:] if result.stdout else result.stderr[-300:],
                duration_ms=duration,
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.BUILD_SUCCEEDS,
                status=ExecutionStatus.FAILED,
                details=f"Build error: {e}",
                command=cmd,
            )

    def check_tests_run(self, command: str = "") -> ExecutionEvidence:
        cmd = command or "python -m pytest --tb=short -q"
        start = time.time()
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120,
                cwd=self.project_root,
            )
            duration = (time.time() - start) * 1000
            return ExecutionEvidence(
                action=ExecutionAction.TEST_RUNS,
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                details=f"Tests {'PASSED' if result.returncode == 0 else 'FAILED'}",
                command=cmd,
                output=result.stdout[-300:] if result.stdout else result.stderr[-300:],
                duration_ms=duration,
            )
        except Exception as e:
            return ExecutionEvidence(
                action=ExecutionAction.TEST_RUNS,
                status=ExecutionStatus.FAILED,
                details=f"Test error: {e}",
                command=cmd,
            )

    # ── DETERMINISTIC PLANNING ─────────────────────────────────

    def create_execution_plan(self, task: str, files: list[str]) -> ExecutionPlan:
        """Task uchun deterministic execution plan yaratish."""
        plan = ExecutionPlan(task=task)

        # 1. Pre-checks
        for f in files:
            plan.add_step(ExecutionAction.FILE_EXISTS, path=f)
            plan.add_step(ExecutionAction.FILE_READABLE, path=f)
            plan.add_step(ExecutionAction.SYNTAX_VALID, file_path=f)

        # 2. Dependency checks
        for f in files:
            if f.endswith(".py"):
                plan.add_step(ExecutionAction.IMPORT_VALID, module=os.path.splitext(f)[0])

        # 3. Post-checks
        plan.add_step(ExecutionAction.BUILD_SUCCEEDS)
        plan.add_step(ExecutionAction.TEST_RUNS)

        return plan

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execution plan'ni bajarish."""
        for step in plan.steps:
            action = ExecutionAction(step["action"])

            if action == ExecutionAction.FILE_EXISTS:
                evidence = self.check_file_exists(step.get("path", ""))
            elif action == ExecutionAction.FILE_READABLE:
                evidence = self.check_file_readable(step.get("path", ""))
            elif action == ExecutionAction.SYNTAX_VALID:
                evidence = self.check_syntax_valid(step.get("file_path", ""))
            elif action == ExecutionAction.IMPORT_VALID:
                evidence = self.check_import_valid(step.get("module", ""))
            elif action == ExecutionAction.BUILD_SUCCEEDS:
                evidence = self.check_build_succeeds(step.get("command", ""))
            elif action == ExecutionAction.TEST_RUNS:
                evidence = self.check_tests_run(step.get("command", ""))
            else:
                continue

            plan.evidence.append(evidence)

        plan.is_complete = True
        return plan

    # ── STATUS ─────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "project_root": self.project_root,
            "executor_type": "deterministic",
            "capabilities": [
                "file_exists", "file_not_empty", "file_readable",
                "function_exists", "class_exists", "import_valid",
                "syntax_valid", "dependency_exists", "test_runs",
                "build_succeeds",
            ],
        }
