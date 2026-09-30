"""Smart Build Engine v2 — Weak LLM + Strong Cognitive Infrastructure.

Pipeline:
Task → Intent Engine → Task Decomposer → Context Intelligence →
Small LLM → Deterministic Executor → Verification → Evidence
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from smart_build.state import BuildSession, BuildState
from smart_build.discovery import ProjectDiscovery
from smart_build.analyzer import RequirementAnalyzer
from smart_build.context_intelligence import ContextIntelligenceEngine, TaskComplexity
from smart_build.deterministic_executor import DeterministicExecutor, ExecutionEvidence, ExecutionPlan
from smart_build.error_parser import SmartErrorParser, ParsedError
from smart_build.verifier import RealityVerifier, VerificationResult
from smart_build.vision_integration import VisionSmartBuildIntegration, VisionEvidence


@dataclass
class SmartBuildResult:
    """Smart Build natijasi."""
    session_id: str
    status: str
    task: str
    complexity: str
    evidence: list[dict] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tokens_saved: int = 0
    duration_seconds: float = 0.0
    report: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "task": self.task,
            "complexity": self.complexity,
            "evidence_count": len(self.evidence),
            "files_changed": self.files_changed,
            "tokens_saved": self.tokens_saved,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class SmartBuildEngineV2:
    """Weak LLM + Strong Cognitive Infrastructure.

    Core principles:
    1. LLMga butun projectni bermaslik
    2. LLMdan retrieval ishini olib tashlash
    3. Deterministic intelligence
    4. Reasoning budget taskga qarab
    5. LLMga raw error bermaslik
    6. Context compression
    7. LLM→tool loop qisqartirish
    8. Memory dump bermaslik
    9. State qayta tushuntirmaslik
    10. Verifier LLM ishlatmaslik
    11. LLMlar sonini ko'paytirmaslik
    """

    def __init__(self, project_root: str = "", vision_engine=None):
        self.project_root = project_root
        self._discovery = ProjectDiscovery(project_root)
        self._analyzer = RequirementAnalyzer()
        self._context_engine = ContextIntelligenceEngine(project_root)
        self._executor = DeterministicExecutor(project_root)
        self._error_parser = SmartErrorParser(project_root)
        self._verifier = RealityVerifier(project_root)
        self._vision_integration = VisionSmartBuildIntegration(vision_engine)
        self._sessions: dict[str, BuildSession] = {}

    def start_session(self, task: str) -> BuildSession:
        """Yangi session boshlash."""
        session = BuildSession(task=task)
        session.project_root = self.project_root
        self._sessions[session.session_id] = session
        return session

    def run(self, task: str) -> SmartBuildResult:
        """To'liq pipeline: Intent → Decompose → Context → LLM → Execute → Verify."""
        start = time.time()
        session = self.start_session(task)

        try:
            # 1. Intent Engine — task complexity aniqlash
            session.transition(BuildState.DISCOVERING)
            project_info = self._discovery.discover()
            context = self._context_engine.process(task)

            # 2. Adaptive intelligence — complexity ga qarab LLM budget
            complexity = context.complexity
            token_budget = self._get_token_budget(complexity)

            # 3. Context Intelligence — faqat relevant data
            session.transition(BuildState.ANALYZING)
            enriched_context = self._context_engine.process(task, token_budget)

            # 4. Deterministic pre-checks
            session.transition(BuildState.PLAN_VALIDATED)
            pre_evidence = self._run_deterministic_checks(enriched_context)

            # 5. Execute (stub — real implementation would use LLM decision)
            session.transition(BuildState.IMPLEMENTING)
            exec_evidence = self._execute_deterministic(enriched_context)

            # 6. Verification
            session.transition(BuildState.VERIFYING)
            all_evidence = pre_evidence + exec_evidence
            verification = self._verify_with_evidence(all_evidence, task)

            # 7. Result
            if verification.status.value == "success":
                session.transition(BuildState.COMPLETED)
                session.final_status = "SUCCESS"
            elif verification.status.value == "partial":
                session.transition(BuildState.COMPLETED)
                session.final_status = "PARTIAL"
            else:
                session.transition(BuildState.FAILED)
                session.final_status = "FAILED"

            # 8. Tokens saved calculation
            baseline_tokens = len(task) * 100  # naive baseline
            tokens_saved = baseline_tokens - enriched_context.tokens_used

            duration = time.time() - start
            return SmartBuildResult(
                session_id=session.session_id,
                status=session.final_status,
                task=task,
                complexity=complexity.value,
                evidence=[e.to_dict() for e in all_evidence],
                files_changed=enriched_context.relevant_files[:5],
                tokens_saved=max(0, tokens_saved),
                duration_seconds=duration,
                report=session.to_dict(),
            )

        except Exception as e:
            session.transition(BuildState.FAILED)
            session.last_error = str(e)
            session.final_status = "FAILED"
            return SmartBuildResult(
                session_id=session.session_id,
                status="FAILED",
                task=task,
                complexity="unknown",
                duration_seconds=time.time() - start,
                report={"error": str(e)},
            )

    def handle_error(self, raw_error: str, changed_files: list[str] = None) -> ParsedError:
        """Error parse qilish — LLM ga structured evidence berish."""
        return self._error_parser.parse(raw_error, changed_files)

    def get_status(self) -> dict:
        return {
            "project_root": self.project_root,
            "engine_version": "2.0",
            "principle": "Weak LLM + Strong Cognitive Infrastructure",
            "components": {
                "context_engine": "active",
                "deterministic_executor": "active",
                "error_parser": "active",
                "verifier": "active",
                "vision_integration": "active" if self._vision_integration._vision else "inactive",
            },
            "sessions": len(self._sessions),
        }

    # ── VISION INTEGRATION ─────────────────────────────────────

    def vision_check_ui(self, description: str) -> VisionEvidence:
        """Vision orqali UI element tekshirish."""
        return self._vision_integration.check_ui_element(description)

    def vision_click(self, description: str) -> VisionEvidence:
        """Vision orqali click."""
        return self._vision_integration.click_element(description)

    def vision_type(self, target: str, text: str) -> VisionEvidence:
        """Vision orqali type."""
        return self._vision_integration.type_text(target, text)

    def vision_check_error(self, error_text: str = "") -> VisionEvidence:
        """Vision orqali error tekshirish."""
        return self._vision_integration.check_error_visible(error_text)

    def vision_check_success(self, success_text: str = "") -> VisionEvidence:
        """Vision orqali success tekshirish."""
        return self._vision_integration.check_success_visible(success_text)

    def vision_verify_action(self, before_scene: dict, action: str):
        """Vision orqali amal tasdig'i."""
        return self._vision_integration.verify_action(before_scene, action)

    # ── PRIVATE ────────────────────────────────────────────────

    def _get_token_budget(self, complexity: TaskComplexity) -> int:
        """Complexity ga qarab token budget."""
        budgets = {
            TaskComplexity.TRIVIAL: 0,      # LLM kerak emas
            TaskComplexity.SIMPLE: 1000,     # kichik LLM
            TaskComplexity.MEDIUM: 4000,     # o'rta LLM
            TaskComplexity.COMPLEX: 8000,    # kuchli LLM
            TaskComplexity.AMBIGUOUS: 12000, # deep reasoning
        }
        return budgets.get(complexity, 4000)

    def _run_deterministic_checks(self, context) -> list[ExecutionEvidence]:
        """Deterministic pre-checks."""
        evidence = []
        for item in context.relevant_files[:10]:
            e = self._executor.check_file_exists(item.path)
            evidence.append(e)
            if e.status.value == "success":
                syntax = self._executor.check_syntax_valid(item.path)
                evidence.append(syntax)
        return evidence

    def _execute_deterministic(self, context) -> list[ExecutionEvidence]:
        """Deterministic execution."""
        evidence = []
        # Build check
        build = self._executor.check_build_succeeds()
        evidence.append(build)
        # Test check
        tests = self._executor.check_tests_run()
        evidence.append(tests)
        return evidence

    def _verify_with_evidence(self, evidence: list[ExecutionEvidence], task: str) -> VerificationResult:
        """Evidence bilan verification."""
        from smart_build.verifier import Evidence as VerifierEvidence
        v_evidence = []
        for e in evidence:
            v_evidence.append(VerifierEvidence(
                evidence_type="deterministic",
                description=e.details,
                passed=e.status.value == "success",
            ))
        return self._verifier.verify_task(task, v_evidence)
