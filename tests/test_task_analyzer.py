"""
Tests for igris.core.task_analyzer -- pure heuristic, no LLM needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.task_analyzer import analyze


def test_short_request_is_simple():
    result = analyze("list files in this directory")
    assert result.tier == "simple"


def test_multi_step_request_is_medium():
    result = analyze("read config.py and then update the timeout value")
    assert result.tier in ("medium", "complex")  # 2 files-ish + connector is at least medium


def test_architecture_language_is_complex():
    result = analyze("design the full-stack architecture for this service from scratch")
    assert result.tier == "complex"


def test_multiple_subsystems_is_multi_agent():
    result = analyze("build an ecommerce site with frontend, backend, and a database schema")
    assert result.tier == "multi_agent"
    assert "frontend" in result.subsystems
    assert "backend" in result.subsystems
    assert "database" in result.subsystems


def test_single_subsystem_mention_is_not_multi_agent():
    result = analyze("add a new API endpoint for user login")
    assert result.tier != "multi_agent"


def test_long_request_with_many_files_is_complex():
    text = (
        "refactor auth.py and then update session.py, also fix tests in "
        "test_auth.py, and after that update the config.yaml and finally "
        "check main.py for any leftover imports that reference the old module"
    )
    result = analyze(text)
    assert result.tier == "complex"
