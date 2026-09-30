"""Smart Build Engine — barcha komponentlarni birlashtiruvchi yagona kirish nuqtasi."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from smart_build.state import BuildSession, BuildState, BuildStep
from smart_build.discovery import ProjectDiscovery, ProjectInfo
from smart_build.analyzer import RequirementAnalyzer, TaskAnalysis
from smart_build.context import ContextEngine
from smart_build.planner import BuildPlanner, BuildPlan
from smart_build.verifier import RealityVerifier, VerificationResult


@dataclass
class BuildResult:
    """Build natijasi."""
    session_id: str
    status: str  # SUCCESS, FAILED, PARTIAL, UNKNOWN
    task: str
    evidence: list[dict] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    duration_seconds: float = 0.0
    report: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "task": self.task,
            "evidence_count": len(self.evidence),
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class SmartBuildEngine:
    """IGRIS Smart Build — LLM-independent build system.

    Core principle: LLM faqat reasoning uchun, execution tizim orqali.
    LLMning javobi natija emas; real tizimdagi tasdiqlangan holat natija.
    """

    def __init__(self, project_root: str = ""):
        self.project_root = project_root
        self._discovery = ProjectDiscovery(project_root)
        self._analyzer = RequirementAnalyzer()
        self._context = ContextEngine(project_root)
        self._planner = BuildPlanner()
        self._verifier = RealityVerifier(project_root)
        self._sessions: dict[str, BuildSession] = {}

    def start_session(self, task: str) -> BuildSession:
        """Yangi build session boshlash."""
        session = BuildSession(task=task)
        session.project_root = self.project_root
        self._sessions[session.session_id] = session
        return session

    def run(self, task: str) -> BuildResult:
        """To'liq build pipeline'ni ishga tushirish."""
        start_time = time.time()
        session = self.start_session(task)

        try:
            # 1. Discovery
            session.transition(BuildState.DISCOVERING)
            project_info = self._discovery.discover()
            session.project_type = project_info.project_type
            session.language = project_info.project_type
            session.framework = ", ".join(project_info.frameworks) if project_info.frameworks else ""

            # 2. Analysis
            session.transition(BuildState.ANALYZING)
            analysis = self._analyzer.analyze(task)

            # 3. Context
            session.transition(BuildState.MAPPING)
            context = self._context.get_context(task)

            # 4. Planning
            session.transition(BuildState.PLANNING)
            plan = self._planner.generate_plan(task)
            plan = self._planner.validate_plan(plan)

            if not plan.is_valid:
                session.transition(BuildState.FAILED)
                session.last_error = f"Plan validation failed: {plan.validation_errors}"
                return self._build_result(session, start_time)

            # 5. Plan Validated
            session.transition(BuildState.PLAN_VALIDATED)

            # 6. Implementation (stub — real implementation would execute plan)
            session.transition(BuildState.IMPLEMENTING)
            for step in plan.steps:
                build_step = session.add_step(step.description)
                # Real execution would happen here
                build_step.state = "completed"

            # 7. Build
            session.transition(BuildState.BUILDING)
            build_evidence = self._verifier.verify_build()
            session.add_evidence("build", build_evidence.to_dict())

            # 8. Test
            session.transition(BuildState.TESTING)
            test_evidence = self._verifier.verify_tests()
            session.add_evidence("test", test_evidence.to_dict())

            # 9. Verify
            session.transition(BuildState.VERIFYING)

            # 10. Reality verification
            all_evidence = [build_evidence, test_evidence]
            verification = self._verifier.verify_task(task, all_evidence)
            session.add_evidence("verification", verification.to_dict())

            # 11. Complete
            if verification.status.value == "success":
                session.transition(BuildState.COMPLETED)
                session.final_status = "SUCCESS"
            elif verification.status.value == "partial":
                session.transition(BuildState.COMPLETED)
                session.final_status = "PARTIAL"
            else:
                session.transition(BuildState.FAILED)
                session.final_status = "FAILED"

            return self._build_result(session, start_time)

        except Exception as e:
            session.transition(BuildState.FAILED)
            session.last_error = str(e)
            session.final_status = "FAILED"
            return self._build_result(session, start_time)

    def get_session(self, session_id: str) -> Optional[BuildSession]:
        """Session olish."""
        return self._sessions.get(session_id)

    def get_status(self) -> dict:
        """Engine holatini olish."""
        return {
            "project_root": self.project_root,
            "active_sessions": len(self._sessions),
            "sessions": {sid: s.to_dict() for sid, s in self._sessions.items()},
        }

    def _build_result(self, session: BuildSession, start_time: float) -> BuildResult:
        """Build result yaratish."""
        duration = time.time() - start_time
        return BuildResult(
            session_id=session.session_id,
            status=session.final_status,
            task=session.task,
            evidence=session.evidence,
            files_created=session.files_created,
            files_modified=session.files_modified,
            tests_passed=session.tests_passed,
            tests_failed=session.tests_failed,
            duration_seconds=duration,
            report=session.to_dict(),
        )
