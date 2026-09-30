"""
IGRIS BRAIN — executor package
===============================
ReAct loop (Plan→Act→Observe→Correct), pipeline safety,
checkpoint integrity.

Import example:
    from executor.executor import AgentExecutor
    from executor.pipeline_safety import PipelineSafety
"""

__all__ = [
    "executor",
    "pipeline_safety",
    "checkpoint_integrity",
]
