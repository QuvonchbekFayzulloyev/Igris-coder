import os
import sys


_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from server.server import _execution_succeeded


def test_only_successful_terminal_status_is_api_success():
    assert _execution_succeeded({"status": "ok"}) is True
    assert _execution_succeeded({"status": "verified"}) is True
    assert _execution_succeeded({"status": "partial"}) is False
    assert _execution_succeeded({"status": "failed"}) is False
    assert _execution_succeeded({"status": "cancelled", "cancelled": True}) is False
    assert _execution_succeeded({"status": "ok", "errors": ["tool failed"]}) is False