"""Chat Stream Aggregator — tests."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestChatStream:
    """ChatStream testlari."""

    def test_create_stream(self):
        from smart_build.chat_stream import ChatStream
        stream = ChatStream(task="test task")
        assert stream.task == "test task"
        assert stream.actions == []

    def test_add_action(self):
        from smart_build.chat_stream import ChatStream, StreamGroup
        stream = ChatStream(task="test task")
        action = stream.add_action(StreamGroup.INVESTIGATE, "Investigating")
        assert action.group == StreamGroup.INVESTIGATE
        assert len(stream.actions) == 1

    def test_get_current(self):
        from smart_build.chat_stream import ChatStream, StreamGroup, StreamStatus
        stream = ChatStream(task="test task")
        action = stream.add_action(StreamGroup.INVESTIGATE, "Investigating")
        action.start()
        assert stream.get_current() == action

    def test_complete_stream(self):
        from smart_build.chat_stream import ChatStream
        stream = ChatStream(task="test task")
        stream.complete(success=True)
        assert stream.final_status == "completed"

    def test_to_summary(self):
        from smart_build.chat_stream import ChatStream, StreamGroup
        stream = ChatStream(task="test task")
        action = stream.add_action(StreamGroup.EXECUTE, "Editing")
        action.start()
        action.complete()
        stream.complete()
        summary = stream.to_summary()
        assert summary["task"] == "test task"
        assert summary["total_actions"] == 1


class TestSemanticAction:
    """SemanticAction testlari."""

    def test_to_compact(self):
        from smart_build.chat_stream import SemanticAction, StreamGroup, StreamStatus
        action = SemanticAction(
            action_id="a1",
            group=StreamGroup.EXECUTE,
            label="Editing",
            status=StreamStatus.COMPLETED,
            duration_seconds=5.0,
        )
        compact = action.to_compact()
        assert compact["group"] == "execute"
        assert "✓" in compact["label"]

    def test_to_expanded(self):
        from smart_build.chat_stream import SemanticAction, StreamGroup
        action = SemanticAction(
            action_id="a1",
            group=StreamGroup.TEST,
            label="Testing",
            files_changed=[{"path": "test.py", "type": "M"}],
        )
        expanded = action.to_expanded()
        assert expanded["files"][0]["path"] == "test.py"

    def test_to_trace(self):
        from smart_build.chat_stream import SemanticAction, StreamGroup, MicroAction
        action = SemanticAction(
            action_id="a1",
            group=StreamGroup.INVESTIGATE,
            label="Investigating",
        )
        action.add_micro(MicroAction(action_type="read", description="read file.py"))
        trace = action.to_trace()
        assert len(trace["micro_actions"]) == 1

    def test_to_evidence(self):
        from smart_build.chat_stream import SemanticAction, StreamGroup
        action = SemanticAction(
            action_id="a1",
            group=StreamGroup.VERIFY,
            label="Verifying",
            raw_output="test output",
            evidence=[{"type": "test", "passed": True, "details": "all passed"}],
        )
        evidence = action.to_evidence()
        assert evidence["raw_output"] == "test output"
        assert len(evidence["evidence"]) == 1


class TestChatStreamAggregator:
    """ChatStreamAggregator testlari."""

    def test_create_aggregator(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        assert agg is not None

    def test_start_stream(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        stream = agg.start_stream("test task")
        assert stream.task == "test task"

    def test_add_tool_call(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        agg.start_stream("test task")
        result = agg.add_tool_call("read_file", {"path": "test.py"})
        assert result is not None
        assert result["group"] == "investigate"

    def test_aggregate_same_group(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        agg.start_stream("test task")
        agg.add_tool_call("read_file", {"path": "a.py"})
        result = agg.add_tool_call("read_file", {"path": "b.py"})
        assert result is not None
        assert "2 operations" in result.get("label", "")

    def test_complete_action(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        agg.start_stream("test task")
        agg.add_tool_call("write_file", {"path": "test.py"})
        result = agg.complete_action(success=True)
        assert result is not None
        assert result["status"] == "completed"

    def test_complete_stream(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        agg.start_stream("test task")
        agg.complete_stream(success=True)
        assert agg.get_stream() is None

    def test_get_all_streams(self):
        from smart_build.chat_stream import ChatStreamAggregator
        agg = ChatStreamAggregator()
        agg.start_stream("task 1")
        agg.complete_stream()
        agg.start_stream("task 2")
        agg.complete_stream()
        streams = agg.get_all_streams()
        assert len(streams) == 2


class TestToolGroupMapping:
    """Tool → Group mapping testlari."""

    def test_investigate_tools(self):
        from smart_build.chat_stream import ChatStreamAggregator, StreamGroup
        agg = ChatStreamAggregator()
        agg.start_stream("test")
        for tool in ["read_file", "search_code", "grep", "glob", "list_files"]:
            result = agg.add_tool_call(tool, {})
            assert result["group"] == StreamGroup.INVESTIGATE.value

    def test_execute_tools(self):
        from smart_build.chat_stream import ChatStreamAggregator, StreamGroup
        agg = ChatStreamAggregator()
        agg.start_stream("test")
        for tool in ["write_file", "edit_file", "run_command", "python_exec"]:
            result = agg.add_tool_call(tool, {})
            assert result["group"] == StreamGroup.EXECUTE.value

    def test_test_tools(self):
        from smart_build.chat_stream import ChatStreamAggregator, StreamGroup
        agg = ChatStreamAggregator()
        agg.start_stream("test")
        result = agg.add_tool_call("smart_build_check", {})
        assert result["group"] == StreamGroup.TEST.value

    def test_verify_tools(self):
        from smart_build.chat_stream import ChatStreamAggregator, StreamGroup
        agg = ChatStreamAggregator()
        agg.start_stream("test")
        result = agg.add_tool_call("vision_verify", {})
        assert result["group"] == StreamGroup.VERIFY.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
