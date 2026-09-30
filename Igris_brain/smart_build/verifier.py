"""§20 Reality Verifier — LLM claimini evidence bilan solishtirish."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VerificationStatus(str, Enum):
    """Tasdiqlash holati."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    """Bitta dalil."""
    evidence_type: str  # filesystem, build, test, runtime, visual
    description: str
    passed: bool
    details: str = ""
    file_path: str = ""
    command: str = ""
    output: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.evidence_type,
            "description": self.description,
            "passed": self.passed,
            "details": self.details[:200],
        }


@dataclass
class VerificationResult:
    """Tasdiqlash natijasi."""
    status: VerificationStatus
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    claim: str = ""
    summary: str = ""
    remaining_problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "evidence_count": len(self.evidence),
            "evidence_passed": sum(1 for e in self.evidence if e.passed),
            "claim": self.claim,
            "summary": self.summary,
            "remaining_problems": self.remaining_problems,
        }


class RealityVerifier:
    """LLM claimlarini real tizim orqali tasdiqlash."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root

    def verify_file_created(self, file_path: str) -> Evidence:
        """Fayl yaratilganini tekshirish."""
        exists = os.path.exists(os.path.join(self.project_root, file_path))
        return Evidence(
            evidence_type="filesystem",
            description=f"File {file_path} exists",
            passed=exists,
            file_path=file_path,
        )

    def verify_file_not_empty(self, file_path: str) -> Evidence:
        """Fayl bo'sh emasligini tekshirish."""
        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return Evidence(
                evidence_type="filesystem",
                description=f"File {file_path} does not exist",
                passed=False,
                file_path=file_path,
            )
        size = os.path.getsize(full_path)
        return Evidence(
            evidence_type="filesystem",
            description=f"File {file_path} is not empty ({size} bytes)",
            passed=size > 0,
            file_path=file_path,
        )

    def verify_syntax(self, file_path: str) -> Evidence:
        """Python syntax tekshirish."""
        full_path = os.path.join(self.project_root, file_path)
        if not file_path.endswith(".py"):
            return Evidence(
                evidence_type="filesystem",
                description="Not a Python file",
                passed=True,
            )
        if not os.path.exists(full_path):
            return Evidence(
                evidence_type="filesystem",
                description=f"File {file_path} does not exist",
                passed=False,
            )
        try:
            with open(full_path, "r") as f:
                compile(f.read(), full_path, "exec")
            return Evidence(
                evidence_type="filesystem",
                description=f"Syntax check passed for {file_path}",
                passed=True,
            )
        except SyntaxError as e:
            return Evidence(
                evidence_type="filesystem",
                description=f"Syntax error in {file_path}: {e}",
                passed=False,
                details=str(e),
            )

    def verify_import(self, file_path: str, module_name: str) -> Evidence:
        """Import tekshirish."""
        try:
            result = subprocess.run(
                ["python", "-c", f"import {module_name}"],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_root,
            )
            return Evidence(
                evidence_type="build",
                description=f"Import {module_name} {'succeeded' if result.returncode == 0 else 'failed'}",
                passed=result.returncode == 0,
                command=f"import {module_name}",
                output=result.stdout + result.stderr,
            )
        except Exception as e:
            return Evidence(
                evidence_type="build",
                description=f"Import check failed: {e}",
                passed=False,
            )

    def verify_build(self, command: str = "") -> Evidence:
        """Build tekshirish."""
        cmd = command or "python -m py_compile ."
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60,
                cwd=self.project_root,
            )
            return Evidence(
                evidence_type="build",
                description=f"Build {'succeeded' if result.returncode == 0 else 'failed'}",
                passed=result.returncode == 0,
                command=cmd,
                output=result.stdout + result.stderr,
            )
        except Exception as e:
            return Evidence(
                evidence_type="build",
                description=f"Build check failed: {e}",
                passed=False,
            )

    def verify_tests(self, command: str = "") -> Evidence:
        """Test tekshirish."""
        cmd = command or "python -m pytest --tb=short -q"
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120,
                cwd=self.project_root,
            )
            return Evidence(
                evidence_type="test",
                description=f"Tests {'passed' if result.returncode == 0 else 'failed'}",
                passed=result.returncode == 0,
                command=cmd,
                output=result.stdout[-500:] if result.stdout else result.stderr[-500:],
            )
        except Exception as e:
            return Evidence(
                evidence_type="test",
                description=f"Test check failed: {e}",
                passed=False,
            )

    def verify_string_in_file(self, file_path: str, search_string: str) -> Evidence:
        """Fayl ichida matn mavjudligini tekshirish."""
        full_path = os.path.join(self.project_root, file_path)
        if not os.path.exists(full_path):
            return Evidence(
                evidence_type="filesystem",
                description=f"File {file_path} does not exist",
                passed=False,
            )
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            found = search_string in content
            return Evidence(
                evidence_type="filesystem",
                description=f"String '{search_string[:50]}' {'found' if found else 'not found'} in {file_path}",
                passed=found,
            )
        except Exception as e:
            return Evidence(
                evidence_type="filesystem",
                description=f"File read failed: {e}",
                passed=False,
            )

    def verify_task(self, task: str, evidence_list: list[Evidence]) -> VerificationResult:
        """To'liq task verification."""
        result = VerificationResult(
            status=VerificationStatus.UNKNOWN,
            claim=task,
        )
        result.evidence = evidence_list

        passed = sum(1 for e in evidence_list if e.passed)
        total = len(evidence_list)

        if total == 0:
            result.status = VerificationStatus.UNKNOWN
            result.confidence = 0.0
        elif passed == total:
            result.status = VerificationStatus.SUCCESS
            result.confidence = 1.0
        elif passed > total * 0.5:
            result.status = VerificationStatus.PARTIAL
            result.confidence = passed / total
        else:
            result.status = VerificationStatus.FAILED
            result.confidence = passed / total

        # Qoldiq muammolar
        for e in evidence_list:
            if not e.passed:
                result.remaining_problems.append(e.description)

        result.summary = f"{passed}/{total} evidence passed"
        return result
