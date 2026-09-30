import os
import sys
from types import SimpleNamespace

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)

from agent.layered_agent import LayeredAgent, RepromptEngine


class _AvailableLlm:
    def is_available(self):
        return True

    def complete(self, system, prompt):
        return (
            '{"role":"assistant","task":"answer","purpose":"help",'
            '"capabilities_needed":[],"complexity":"simple",'
            '"clarification_needed":null,"language":"uz","subject":""}'
        )


def test_reprompt_engine_uses_available_llm():
    analysis = RepromptEngine(_AvailableLlm()).analyze("salom")

    assert analysis.task == "answer"
    assert analysis.complexity == "simple"


def test_plain_chat_does_not_schedule_file_tools_without_capabilities():
    analysis = RepromptEngine().analyze("salom")
    plan = LayeredAgent().layer_constructor.construct(analysis)

    assert analysis.capabilities_needed == []
    assert all(not layer.sub_steps for layer in plan.layers)


def test_unavailable_tool_produces_failed_final_result():
    fake_agent = SimpleNamespace(_registry={}, _mcp=None, memory=None)
    events = list(LayeredAgent(agent=fake_agent).run_layered("rasm chiz"))
    final = next(event for event in events if event.get("type") == "final_result")

    assert final["status"] == "failed"
    assert final["failed_layers"]