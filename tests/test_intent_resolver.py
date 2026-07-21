"""
Regression tests for igris.core.intent_resolver.

The specific case this file exists for: "list files in this directory"
was heuristically classified as `ambiguous` (no keywords matched at all)
and triggered a clarifying question instead of running terminal/list_dir.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config
from igris.core.intent_resolver import IntentResolver


THRESHOLD = 0.55


@pytest.fixture
def resolver():
    config = Config.load(project_root=Path("/tmp"))
    return IntentResolver(config, llm=None)  # heuristic-only, no Ollama needed


@pytest.mark.parametrize("text", [
    "list files in this directory",
    "show me the files here",
    "display the contents of README.md",
    "print the current git status",
    "cat main.py",
    "ko'rsat fayllarni",
    "papkadagi fayllar ro'yxati",
    "build an ecommerce site with frontend and backend",
])
def test_common_read_only_requests_do_not_trigger_clarification(resolver, text):
    intent = asyncio.run(resolver.classify(text))
    assert intent.confidence >= THRESHOLD, (
        f"'{text}' scored {intent.confidence} (category={intent.category}) "
        f"and would incorrectly trigger a clarifying question"
    )


def test_list_files_specifically_classified_as_command(resolver):
    intent = asyncio.run(resolver.classify("list files in this directory"))
    assert intent.category == "command"
    assert intent.confidence >= THRESHOLD


def test_agentic_architecture_request_routes_to_task_mode(resolver):
    intent = asyncio.run(resolver.classify("agentic MCP calling uchun system prompt qo'sh"))
    assert intent.category == "code_task"
    assert intent.confidence >= THRESHOLD


def test_memory_and_sandbox_requests_route_to_task_mode(resolver):
    intent = asyncio.run(resolver.classify("memory va sandbox MCP uchun collector qo'sh"))
    assert intent.category == "code_task"
    assert intent.confidence >= THRESHOLD


def test_genuinely_vague_input_still_asks(resolver):
    intent = asyncio.run(resolver.classify("hmm"))
    assert intent.confidence < THRESHOLD


def test_three_way_ambiguous_input_lands_in_assume_and_proceed_band(resolver):
    """
    Matches review, bug_fix, and research each with one keyword -- genuinely
    mixed-signal, but not as evidence-free as 'hmm'. Should land between
    hard_block_confidence_threshold (0.35) and clarify_confidence_threshold
    (0.55): confident enough to proceed on a stated assumption, not so
    confident it proceeds silently.
    """
    intent = asyncio.run(resolver.classify("review this and explain the error"))
    assert 0.35 <= intent.confidence < THRESHOLD


def test_assumption_note_names_the_assumed_category(resolver):
    intent = asyncio.run(resolver.classify("review this and explain the error"))
    note = resolver.build_assumption_note("review this and explain the error", intent)
    assert intent.category in note
    assert "say so" in note.lower() or "not what you meant" in note.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
