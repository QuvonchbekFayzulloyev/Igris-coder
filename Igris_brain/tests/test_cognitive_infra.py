"""Weak LLM + Strong Cognitive Infrastructure — tests."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestContextIntelligenceEngine:
    """Context Intelligence Engine testlari."""

    def test_retrieve_by_semantic(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        items = engine.retrieve_by_semantic("agent test task")
        assert isinstance(items, list)

    def test_retrieve_by_symbol(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        items = engine.retrieve_by_symbol("Agent class method")
        assert isinstance(items, list)

    def test_retrieve_by_dependency(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        items = engine.retrieve_by_dependency("smart_build/engine.py")
        assert isinstance(items, list)

    def test_retrieve_by_test(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        items = engine.retrieve_by_test("engine.py")
        assert isinstance(items, list)

    def test_filter_by_relevance(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine, RetrievedItem, RetrievalType
        engine = ContextIntelligenceEngine()
        items = [
            RetrievedItem("1", RetrievalType.SEMANTIC, "a.py", relevance_score=0.8),
            RetrievedItem("2", RetrievalType.SEMANTIC, "b.py", relevance_score=0.1),
        ]
        filtered = engine.filter_by_relevance(items, min_score=0.3)
        assert len(filtered) == 1

    def test_filter_by_duplicates(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine, RetrievedItem, RetrievalType
        engine = ContextIntelligenceEngine()
        items = [
            RetrievedItem("1", RetrievalType.SEMANTIC, "a.py"),
            RetrievedItem("2", RetrievalType.SEMANTIC, "a.py"),
        ]
        filtered = engine.filter_by_duplicates(items)
        assert len(filtered) == 1

    def test_compress_context(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine, RetrievedItem, RetrievalType
        engine = ContextIntelligenceEngine()
        items = [
            RetrievedItem("1", RetrievalType.SYMBOL, "a.py", content="x" * 100, relevance_score=0.9),
            RetrievedItem("2", RetrievalType.SEMANTIC, "b.py", content="y" * 100, relevance_score=0.7),
        ]
        context = engine.compress_context(items, "test task", token_budget=50)
        assert context.task == "test task"
        assert context.tokens_used > 0

    def test_full_pipeline(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        context = engine.process("test task", token_budget=2000)
        assert context.task == "test task"
        assert context.complexity.value in ("trivial", "simple", "medium", "complex", "ambiguous")

    def test_to_llm_prompt(self):
        from smart_build.context_intelligence import ContextIntelligenceEngine
        engine = ContextIntelligenceEngine()
        context = engine.process("create a new module")
        prompt = context.to_llm_prompt()
        assert "TASK:" in prompt
        assert "COMPLEXITY:" in prompt


class TestDeterministicExecutor:
    """Deterministic Executor testlari."""

    def test_check_file_exists(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        evidence = executor.check_file_exists("nonexistent.py")
        assert evidence.status.value == "failed"

    def test_check_file_not_empty(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        evidence = executor.check_file_not_empty("nonexistent.py")
        assert evidence.status.value == "failed"

    def test_check_file_readable(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        evidence = executor.check_file_readable("nonexistent.py")
        assert evidence.status.value == "failed"

    def test_check_function_exists(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        evidence = executor.check_function_exists("nonexistent.py", "func")
        assert evidence.status.value == "failed"

    def test_check_syntax_valid(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        evidence = executor.check_syntax_valid("nonexistent.py")
        assert evidence.status.value == "failed"

    def test_create_execution_plan(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        plan = executor.create_execution_plan("test task", ["file1.py", "file2.py"])
        assert len(plan.steps) > 0

    def test_execute_plan(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        plan = executor.create_execution_plan("test task", ["nonexistent.py"])
        plan = executor.execute_plan(plan)
        assert plan.is_complete
        assert len(plan.evidence) > 0

    def test_get_status(self):
        from smart_build.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        status = executor.get_status()
        assert "capabilities" in status


class TestSmartErrorParser:
    """Smart Error Parser testlari."""

    def test_parse_syntax_error(self):
        from smart_build.error_parser import SmartErrorParser, ErrorType
        parser = SmartErrorParser()
        error = 'File "test.py", line 5\n    def foo(\n            ^\nSyntaxError: unexpected EOF while parsing'
        parsed = parser.parse(error)
        assert parsed.error_type == ErrorType.SYNTAX
        assert parsed.severity.value == "critical"

    def test_parse_import_error(self):
        from smart_build.error_parser import SmartErrorParser, ErrorType
        parser = SmartErrorParser()
        error = "ModuleNotFoundError: No module named 'nonexistent_package'"
        parsed = parser.parse(error)
        assert parsed.error_type == ErrorType.IMPORT

    def test_parse_runtime_error(self):
        from smart_build.error_parser import SmartErrorParser, ErrorType
        parser = SmartErrorParser()
        error = "KeyError: 'missing_key'"
        parsed = parser.parse(error)
        assert parsed.error_type == ErrorType.RUNTIME

    def test_to_llm_prompt(self):
        from smart_build.error_parser import SmartErrorParser
        parser = SmartErrorParser()
        error = "ModuleNotFoundError: No module named 'fastapi'"
        parsed = parser.parse(error, changed_files=["app/main.py"])
        prompt = parsed.to_llm_prompt
        assert "ERROR ANALYSIS:" in prompt
        assert "CANDIDATE CAUSES:" in prompt

    def test_get_status(self):
        from smart_build.error_parser import SmartErrorParser
        parser = SmartErrorParser()
        status = parser.get_status()
        assert "error_types" in status


class TestSmartBuildEngineV2:
    """Smart Build Engine V2 testlari."""

    def test_engine_creation(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        assert engine is not None

    def test_start_session(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        session = engine.start_session("test task")
        assert session.session_id
        assert session.task == "test task"

    def test_run(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        result = engine.run("test task")
        assert result.session_id
        assert result.status in ("SUCCESS", "PARTIAL", "FAILED")

    def test_handle_error(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        parsed = engine.handle_error("ModuleNotFoundError: No module named 'x'")
        assert parsed.error_type.value == "import"

    def test_get_status(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        engine = SmartBuildEngineV2()
        status = engine.get_status()
        assert status["engine_version"] == "2.0"
        assert status["principle"] == "Weak LLM + Strong Cognitive Infrastructure"

    def test_token_budget_by_complexity(self):
        from smart_build.engine_v2 import SmartBuildEngineV2
        from smart_build.context_intelligence import TaskComplexity
        engine = SmartBuildEngineV2()
        assert engine._get_token_budget(TaskComplexity.TRIVIAL) == 0
        assert engine._get_token_budget(TaskComplexity.SIMPLE) == 1000
        assert engine._get_token_budget(TaskComplexity.MEDIUM) == 4000
        assert engine._get_token_budget(TaskComplexity.COMPLEX) == 8000
        assert engine._get_token_budget(TaskComplexity.AMBIGUOUS) == 12000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
