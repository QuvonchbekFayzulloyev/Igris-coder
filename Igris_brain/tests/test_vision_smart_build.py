"""Vision-Smart Build Integration — tests."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestVisionSmartBuildIntegration:
    """Vision-Smart Build integratsiya testlari."""

    def test_integration_creation(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration
        integration = VisionSmartBuildIntegration()
        assert integration is not None

    def test_check_ui_element_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration, ExecutionStatus
        integration = VisionSmartBuildIntegration()
        evidence = integration.check_ui_element("button")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_click_element_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration, ExecutionStatus
        integration = VisionSmartBuildIntegration()
        evidence = integration.click_element("button")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_type_text_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration, ExecutionStatus
        integration = VisionSmartBuildIntegration()
        evidence = integration.type_text("input", "hello")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_check_error_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration, ExecutionStatus
        integration = VisionSmartBuildIntegration()
        evidence = integration.check_error_visible()
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_check_success_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration, ExecutionStatus
        integration = VisionSmartBuildIntegration()
        evidence = integration.check_success_visible()
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_verify_action_no_vision(self):
        from smart_build.vision_integration import VisionSmartBuildIntegration
        integration = VisionSmartBuildIntegration()
        result = integration.verify_action({}, "click button")
        assert result.total == 1
        assert len(result.checks) == 1

    def test_vision_evidence_to_dict(self):
        from smart_build.vision_integration import VisionEvidence, VisionCheckType, ExecutionStatus
        evidence = VisionEvidence(
            check_type=VisionCheckType.UI_ELEMENT_EXISTS,
            status=ExecutionStatus.SUCCESS,
            description="Button found",
            confidence=0.95,
        )
        d = evidence.to_dict()
        assert d["check_type"] == "ui_element_exists"
        assert d["status"] == "success"
        assert d["confidence"] == 0.95

    def test_vision_evidence_to_verifier(self):
        from smart_build.vision_integration import VisionEvidence, VisionCheckType, ExecutionStatus
        evidence = VisionEvidence(
            check_type=VisionCheckType.UI_ELEMENT_EXISTS,
            status=ExecutionStatus.SUCCESS,
            description="Button found",
        )
        v = evidence.to_verifier_evidence()
        assert v.evidence_type == "vision"
        assert v.passed is True

    def test_vision_verification_result(self):
        from smart_build.vision_integration import VisionVerificationResult
        result = VisionVerificationResult(task="click button")
        d = result.to_dict()
        assert d["task"] == "click button"
        assert d["total"] == 0


class TestSmartBuildEngineVision:
    """Smart Build Engine + Vision integratsiya testlari."""

    def test_engine_vision_integration(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        assert engine._vision_integration is not None

    def test_engine_vision_check_ui(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.vision_integration import ExecutionStatus
        engine = SmartBuildEngineV2()
        evidence = engine.vision_check_ui("button")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_engine_vision_click(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.vision_integration import ExecutionStatus
        engine = SmartBuildEngineV2()
        evidence = engine.vision_click("button")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_engine_vision_type(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.vision_integration import ExecutionStatus
        engine = SmartBuildEngineV2()
        evidence = engine.vision_type("input", "hello")
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_engine_vision_check_error(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.vision_integration import ExecutionStatus
        engine = SmartBuildEngineV2()
        evidence = engine.vision_check_error()
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_engine_vision_check_success(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.vision_integration import ExecutionStatus
        engine = SmartBuildEngineV2()
        evidence = engine.vision_check_success()
        assert evidence.status == ExecutionStatus.UNKNOWN

    def test_engine_get_status_with_vision(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        status = engine.get_status()
        assert "vision_integration" in status["components"]


class TestIgrisAgentSmartBuild:
    """IgrisAgent Smart Build integratsiya testlari."""

    def test_agent_smart_build_init(self):
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False)
        assert agent.smart_build_engine is not None

    def test_agent_smart_build_tools(self):
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False)
        tools = agent.smart_build_tools()
        assert len(tools) == 3
        assert tools[0]["function"]["name"] == "smart_build_analyze"

    def test_agent_smart_build_status(self):
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False)
        status = agent.status()
        assert "smart_build" in status

    def test_agent_smart_build_execute(self):
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False)
        result = agent._execute_smart_build_tool("smart_build_check", {"files": []})
        assert "evidence" in result

    def test_agent_smart_build_error_parse(self):
        from agent.igris_agent import IgrisAgent
        agent = IgrisAgent(use_llm=False)
        result = agent._execute_smart_build_tool(
            "smart_build_error",
            {"error": "ModuleNotFoundError: No module named 'x'"}
        )
        assert result["error_type"] == "import"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
