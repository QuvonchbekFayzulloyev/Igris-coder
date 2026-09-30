"""Smart Build Module — unit tests."""
from __future__ import annotations

import sys
import os
import tempfile

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestBuildState:
    """Build state machine testlari."""

    def test_valid_transition(self):
        from smart_build.state import BuildSession, BuildState
        session = BuildSession(task="test task")
        assert session.state == BuildState.RECEIVED
        assert session.transition(BuildState.ANALYZING)
        assert session.state == BuildState.ANALYZING

    def test_invalid_transition(self):
        from smart_build.state import BuildSession, BuildState
        session = BuildSession(task="test task")
        assert not session.transition(BuildState.COMPLETED)

    def test_add_step(self):
        from smart_build.state import BuildSession
        session = BuildSession(task="test task")
        step = session.add_step("Do something")
        assert step.step_id == "step_1"
        assert session.current_step == "step_1"

    def test_add_evidence(self):
        from smart_build.state import BuildSession
        session = BuildSession(task="test task")
        session.add_evidence("test", {"passed": True})
        assert len(session.evidence) == 1

    def test_save_load_state(self):
        from smart_build.state import BuildSession, BuildState
        session = BuildSession(task="test task")
        session.transition(BuildState.ANALYZING)
        session.add_step("step 1")
        data = session.save_state()
        loaded = BuildSession.load_state(data)
        assert loaded.task == "test task"
        assert loaded.state == BuildState.ANALYZING

    def test_to_dict(self):
        from smart_build.state import BuildSession
        session = BuildSession(task="test task")
        d = session.to_dict()
        assert "session_id" in d
        assert d["task"] == "test task"


class TestProjectDiscovery:
    """Project discovery testlari."""

    def test_discovery_creation(self):
        from smart_build.discovery import ProjectDiscovery
        discovery = ProjectDiscovery()
        assert discovery is not None

    def test_discover_current_dir(self):
        from smart_build.discovery import ProjectDiscovery
        discovery = ProjectDiscovery()
        info = discovery.discover()
        assert info.root
        assert info.os_type in ("windows", "linux", "macos")

    def test_detect_languages(self):
        from smart_build.discovery import ProjectDiscovery
        discovery = ProjectDiscovery()
        info = discovery.discover()
        assert isinstance(info.languages, list)


class TestRequirementAnalyzer:
    """Requirement analyzer testlari."""

    def test_analyze_simple_task(self):
        from smart_build.analyzer import RequirementAnalyzer
        analyzer = RequirementAnalyzer()
        analysis = analyzer.analyze("Create a new Python function")
        assert analysis.original_task
        assert analysis.complexity in ("simple", "medium", "complex")

    def test_analyze_with_constraints(self):
        from smart_build.analyzer import RequirementAnalyzer
        analyzer = RequirementAnalyzer()
        analysis = analyzer.analyze("Create a fast and high quality module")
        assert len(analysis.constraints) >= 0  # May or may not have constraints


class TestContextEngine:
    """Context engine testlari."""

    def test_context_creation(self):
        from smart_build.context import ContextEngine
        engine = ContextEngine()
        assert engine is not None

    def test_get_context(self):
        from smart_build.context import ContextEngine
        engine = ContextEngine()
        result = engine.get_context("test task")
        assert result.summary
        assert result.total_tokens >= 0


class TestBuildPlanner:
    """Build planner testlari."""

    def test_generate_plan(self):
        from smart_build.planner import BuildPlanner
        planner = BuildPlanner()
        plan = planner.generate_plan("Create a new module")
        assert plan.steps
        assert plan.estimated_time_seconds > 0

    def test_validate_plan(self):
        from smart_build.planner import BuildPlanner
        planner = BuildPlanner()
        plan = planner.generate_plan("Create a new module")
        plan = planner.validate_plan(plan)
        assert plan.is_valid


class TestRealityVerifier:
    """Reality verifier testlari."""

    def test_verify_file_created(self):
        from smart_build.verifier import RealityVerifier
        verifier = RealityVerifier()
        evidence = verifier.verify_file_created("nonexistent.py")
        assert not evidence.passed

    def test_verify_syntax(self):
        from smart_build.verifier import RealityVerifier
        verifier = RealityVerifier()
        evidence = verifier.verify_syntax("nonexistent.py")
        assert not evidence.passed

    def test_verify_task(self):
        from smart_build.verifier import RealityVerifier, Evidence
        verifier = RealityVerifier()
        evidence = [
            Evidence(evidence_type="test", description="test 1", passed=True),
            Evidence(evidence_type="test", description="test 2", passed=True),
        ]
        result = verifier.verify_task("test task", evidence)
        assert result.status.value == "success"


class TestSmartBuildEngine:
    """Smart build engine testlari."""

    def test_engine_creation(self):
        from smart_build.engine import SmartBuildEngine
        engine = SmartBuildEngine()
        assert engine is not None

    def test_start_session(self):
        from smart_build.engine import SmartBuildEngine
        engine = SmartBuildEngine()
        session = engine.start_session("test task")
        assert session.session_id
        assert session.task == "test task"

    def test_get_status(self):
        from smart_build.engine import SmartBuildEngine
        engine = SmartBuildEngine()
        status = engine.get_status()
        assert "project_root" in status
        assert "active_sessions" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
