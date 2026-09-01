"""
CODER AGENT MEMORY — JSON Schemas
All L1 (18 runtime) and L2 (24 persistent) memory type schemas.

1.5B optimizatsiya:
- Har bir entry 500 token dan oshmasligi
- summary field majburiy
- Minimal field, flat structure
"""

import uuid
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ============================================================
# L1 RUNTIME MEMORY SCHEMAS (18 types)
# ============================================================

def make_short_turn(
    session_id: str,
    turn_number: int,
    user_message: str,
    assistant_message: str,
    tool_calls: Optional[list[dict]] = None,
    file_changes: Optional[list[dict]] = None,
    decisions: Optional[list[str]] = None,
    thinking_summary: str = "",
    summary: str = "",
) -> dict:
    """01. Short-turn memory — oxirgi 1-5 tur chat/tool call"""
    return {
        "id": _gen_id("short-turn"),
        "type": "short-turn",
        "session_id": session_id,
        "turn_number": turn_number,
        "data": {
            "user_message": user_message[:500],
            "assistant_message": assistant_message[:500],
            "tool_calls": (tool_calls or [])[:5],
            "file_changes": (file_changes or [])[:10],
            "decisions": decisions or [],
            "thinking_summary": thinking_summary[:200],
        },
        "timestamp": _now_iso(),
        "ttl_seconds": 300,
        "summary": summary[:200] or user_message[:200],
    }


def make_session(
    status: str = "active",
    total_turns: int = 0,
    total_tool_calls: int = 0,
    total_tokens_used: int = 0,
    files_read: Optional[list[str]] = None,
    files_modified: Optional[list[str]] = None,
    errors_encountered: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """02. Session memory — butun sessiya tarixi"""
    return {
        "id": _gen_id("session"),
        "type": "session",
        "status": status,
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "total_turns": total_turns,
        "total_tool_calls": total_tool_calls,
        "total_tokens_used": total_tokens_used,
        "files_read": files_read or [],
        "files_modified": files_modified or [],
        "errors_encountered": errors_encountered or [],
        "summary": summary[:500],
    }


def make_active_context(
    current_task: str,
    priority: str = "medium",
    focus_area: Optional[dict] = None,
    dependencies: Optional[list[dict]] = None,
    blockers: Optional[list[dict]] = None,
    recent_goals: Optional[list[str]] = None,
    environment_state: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """03. Active context — hozirgi task, fayl, qator, fokus"""
    return {
        "id": _gen_id("active-ctx"),
        "type": "active-context",
        "current_task": current_task[:300],
        "priority": priority,
        "focus_area": focus_area or {},
        "dependencies": dependencies or [],
        "blockers": blockers or [],
        "recent_goals": recent_goals or [],
        "environment_state": environment_state or {},
        "timestamp": _now_iso(),
        "summary": summary[:200] or current_task[:200],
    }


def make_working_memory(
    reasoning_chain: Optional[list[dict]] = None,
    current_hypothesis: str = "",
    pending_questions: Optional[list[str]] = None,
    confidence_score: float = 0.5,
    summary: str = "",
) -> dict:
    """04. Working memory — agentning ichki reasoning statei"""
    return {
        "id": _gen_id("working"),
        "type": "working-memory",
        "reasoning_chain": (reasoning_chain or [])[:10],
        "current_hypothesis": current_hypothesis[:300],
        "pending_questions": pending_questions or [],
        "confidence_score": confidence_score,
        "timestamp": _now_iso(),
        "summary": summary[:200] or current_hypothesis[:200],
    }


def make_task_memory(
    title: str,
    description: str = "",
    acceptance_criteria: Optional[list[str]] = None,
    constraints: Optional[list[str]] = None,
    progress_status: str = "pending",
    progress_percentage: int = 0,
    summary: str = "",
) -> dict:
    """05. Task memory — task malumotlari, input, expected output"""
    return {
        "id": _gen_id("task"),
        "type": "task-memory",
        "title": title[:300],
        "description": description[:500],
        "acceptance_criteria": acceptance_criteria or [],
        "constraints": constraints or [],
        "progress": {"status": progress_status, "percentage": progress_percentage},
        "timestamp": _now_iso(),
        "summary": summary[:200] or title[:200],
    }


def make_execution_memory(
    tool_calls_history: Optional[list[dict]] = None,
    execution_pattern: str = "",
    summary: str = "",
) -> dict:
    """06. Execution memory — bajarilgan tool call natijalari"""
    return {
        "id": _gen_id("exec"),
        "type": "execution-memory",
        "tool_calls_history": (tool_calls_history or [])[:20],
        "execution_pattern": execution_pattern[:200],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_observation_memory(
    observations: Optional[list[dict]] = None,
    code_insights: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """07. Observation memory — kod/tizimdan olingan kuzatishlar"""
    return {
        "id": _gen_id("obs"),
        "type": "observation-memory",
        "observations": (observations or [])[:10],
        "code_insights": code_insights or [],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_planning_memory(
    goal: str = "",
    steps: Optional[list[dict]] = None,
    alternatives: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """08. Planning memory — reja, sub-task lar, progress"""
    return {
        "id": _gen_id("plan"),
        "type": "planning-memory",
        "plan": {
            "goal": goal[:300],
            "steps": (steps or [])[:15],
        },
        "alternatives": alternatives or [],
        "timestamp": _now_iso(),
        "summary": summary[:200] or goal[:200],
    }


def make_attention_memory(
    current_focus: Optional[dict] = None,
    attention_stack: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """09. Attention memory — hozirgi etibordagi entity/file lar"""
    return {
        "id": _gen_id("attention"),
        "type": "attention-memory",
        "current_focus": current_focus or {},
        "attention_stack": (attention_stack or [])[:10],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_scratchpad(
    notes: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """10. Scratchpad — vaqtinchalik hisob-kitob, draft"""
    return {
        "id": _gen_id("scratch"),
        "type": "scratchpad",
        "notes": (notes or [])[:20],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_temporary_knowledge(
    items: Optional[list[dict]] = None,
    total_size_bytes: int = 0,
    summary: str = "",
) -> dict:
    """11. Temporary knowledge — 1 marta oqilgan fayl/tushuncha"""
    return {
        "id": _gen_id("temp-know"),
        "type": "temporary-knowledge",
        "items": (items or [])[:30],
        "total_size_bytes": total_size_bytes,
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_runtime_cache(
    entries: Optional[list[dict]] = None,
    hit_rate: float = 0.0,
    summary: str = "",
) -> dict:
    """12. Runtime cache — tool output cache (git log, ls)"""
    return {
        "id": _gen_id("cache"),
        "type": "runtime-cache",
        "entries": (entries or [])[:50],
        "hit_rate": hit_rate,
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_prompt_buffer(
    current_prompt: Optional[dict] = None,
    history: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """13. Prompt buffer — tuzilgan prompt lar, template lar"""
    return {
        "id": _gen_id("prompt"),
        "type": "prompt-buffer",
        "current_prompt": current_prompt or {},
        "history": (history or [])[:10],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_decision_log(
    decisions: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """14. Decision log — qabul qilingan qarorlar va sabab"""
    return {
        "id": _gen_id("decision"),
        "type": "decision-log",
        "decisions": (decisions or [])[:15],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_reflection_memory(
    self_review_notes: Optional[list[str]] = None,
    improvement_suggestions: Optional[list[str]] = None,
    performance_self_assessment: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """15. Reflection memory — self-reflection natijalari"""
    return {
        "id": _gen_id("reflection"),
        "type": "reflection-memory",
        "self_review_notes": self_review_notes or [],
        "improvement_suggestions": improvement_suggestions or [],
        "performance_self_assessment": performance_self_assessment or {},
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_rollback_points(
    checkpoints: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """16. Rollback points — checkpoint lar, state snapshot"""
    return {
        "id": _gen_id("rollback"),
        "type": "rollback-points",
        "checkpoints": (checkpoints or [])[:10],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


def make_streaming_buffer(
    content: str = "",
    chunks: Optional[list[dict]] = None,
    status: str = "streaming",
    summary: str = "",
) -> dict:
    """17. Streaming buffer — streaming output buffer"""
    return {
        "id": _gen_id("stream"),
        "type": "streaming-buffer",
        "content": content[:2000],
        "chunks": (chunks or [])[:100],
        "status": status,
        "timestamp": _now_iso(),
        "summary": summary[:200] or content[:200],
    }


def make_context_compressor(
    original_size_tokens: int = 0,
    compressed_size_tokens: int = 0,
    compression_ratio: float = 0.0,
    compressed_sections: Optional[list[dict]] = None,
    compression_rules: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """18. Context compressor — siqilgan context (token budget)"""
    return {
        "id": _gen_id("compressor"),
        "type": "context-compressor",
        "original_size_tokens": original_size_tokens,
        "compressed_size_tokens": compressed_size_tokens,
        "compression_ratio": compression_ratio,
        "compressed_sections": compressed_sections or [],
        "compression_rules": compression_rules or [],
        "timestamp": _now_iso(),
        "summary": summary[:200],
    }


# L1 Runtime type registry
L1_TYPES = {
    "short-turn": {"file": "01-short-turn.jsonl", "make": make_short_turn, "max_kb": 10},
    "session": {"file": "02-session.jsonl", "make": make_session, "max_kb": 512},
    "active-context": {"file": "03-active-context.jsonl", "make": make_active_context, "max_kb": 2},
    "working-memory": {"file": "04-working.jsonl", "make": make_working_memory, "max_kb": 8},
    "task-memory": {"file": "05-task.jsonl", "make": make_task_memory, "max_kb": 4},
    "execution-memory": {"file": "06-execution.jsonl", "make": make_execution_memory, "max_kb": 16},
    "observation-memory": {"file": "07-observation.jsonl", "make": make_observation_memory, "max_kb": 8},
    "planning-memory": {"file": "08-planning.jsonl", "make": make_planning_memory, "max_kb": 4},
    "attention-memory": {"file": "09-attention.jsonl", "make": make_attention_memory, "max_kb": 1},
    "scratchpad": {"file": "10-scratchpad.jsonl", "make": make_scratchpad, "max_kb": 2},
    "temporary-knowledge": {"file": "11-temp-knowledge.jsonl", "make": make_temporary_knowledge, "max_kb": 32},
    "runtime-cache": {"file": "12-cache.jsonl", "make": make_runtime_cache, "max_kb": 64},
    "prompt-buffer": {"file": "13-prompt-buffer.jsonl", "make": make_prompt_buffer, "max_kb": 4},
    "decision-log": {"file": "14-decision-log.jsonl", "make": make_decision_log, "max_kb": 2},
    "reflection-memory": {"file": "15-reflection.jsonl", "make": make_reflection_memory, "max_kb": 2},
    "rollback-points": {"file": "16-rollback.jsonl", "make": make_rollback_points, "max_kb": 8},
    "streaming-buffer": {"file": "17-streaming.jsonl", "make": make_streaming_buffer, "max_kb": 1},
    "context-compressor": {"file": "18-compressor.jsonl", "make": make_context_compressor, "max_kb": 2},
}


# ============================================================
# L2 PERSISTENT MEMORY SCHEMAS (24 types)
# ============================================================

def make_long_term(
    categories: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """01. Long-term memory — umumiy bilimlar, kontekst"""
    return {
        "id": _gen_id("lt"),
        "type": "long-term",
        "categories": categories or {
            "general_knowledge": [],
            "domain_facts": [],
            "best_practices": [],
        },
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_experience(
    sessions: Optional[list[dict]] = None,
    success_rate: float = 0.0,
    summary: str = "",
) -> dict:
    """02. Experience memory — tajribalar, natijalar"""
    return {
        "id": _gen_id("exp"),
        "type": "experience",
        "sessions": (sessions or [])[:50],
        "success_rate": success_rate,
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_knowledge(
    domains: Optional[dict] = None,
    glossary: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """03. Knowledge memory — domain bilimlari, faktlar"""
    return {
        "id": _gen_id("know"),
        "type": "knowledge",
        "domains": domains or {},
        "glossary": glossary or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_project_memory(
    project: Optional[dict] = None,
    status: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """04. Project memory — loyiha metamalumotlari"""
    return {
        "id": _gen_id("proj"),
        "type": "project-memory",
        "project": project or {},
        "status": status or {"phase": "active_development", "health": "good"},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_skill_memory(
    skills: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """05. Skill memory — agent skill lari, qobiliyatlar"""
    return {
        "id": _gen_id("skill"),
        "type": "skill-memory",
        "skills": skills or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_pattern_memory(
    patterns: Optional[dict] = None,
    anti_patterns: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """06. Pattern memory — kod pattern lari, idiomalar"""
    return {
        "id": _gen_id("pattern"),
        "type": "pattern-memory",
        "patterns": patterns or {},
        "anti_patterns": anti_patterns or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_solution_memory(
    solutions: Optional[list[dict]] = None,
    solution_stats: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """07. Solution memory — muammo->yechim mapping"""
    return {
        "id": _gen_id("soln"),
        "type": "solution-memory",
        "solutions": (solutions or [])[:100],
        "solution_stats": solution_stats or {"total": 0, "by_domain": {}},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_research_memory(
    topics: Optional[dict] = None,
    papers: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """08. Research memory — tadqiqot natijalari"""
    return {
        "id": _gen_id("research"),
        "type": "research-memory",
        "topics": topics or {},
        "papers": papers or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_documentation_memory(
    api_docs: Optional[dict] = None,
    library_docs: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """09. Documentation memory — doc lar, API reference"""
    return {
        "id": _gen_id("docs"),
        "type": "documentation-memory",
        "api_docs": api_docs or {},
        "library_docs": library_docs or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_example_memory(
    snippets: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """10. Example memory — kod misollari, snippet lar"""
    return {
        "id": _gen_id("example"),
        "type": "example-memory",
        "snippets": (snippets or [])[:50],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_error_memory(
    errors: Optional[list[dict]] = None,
    error_patterns: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """11. Error memory — xatolar, fix lar, workaround"""
    return {
        "id": _gen_id("err"),
        "type": "error-memory",
        "errors": (errors or [])[:100],
        "error_patterns": error_patterns or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_verification_memory(
    test_results: Optional[list[dict]] = None,
    quality_gates: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """12. Verification memory — test natijalari, validation"""
    return {
        "id": _gen_id("verify"),
        "type": "verification-memory",
        "test_results": (test_results or [])[:50],
        "quality_gates": quality_gates or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_workflow_memory(
    workflows: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """13. Workflow memory — build/deploy/test workflow lar"""
    return {
        "id": _gen_id("wf"),
        "type": "workflow-memory",
        "workflows": workflows or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_archive(
    projects: Optional[dict] = None,
    archive_stats: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """14. Archive — eski, kam ishlatiladigan"""
    return {
        "id": _gen_id("arch"),
        "type": "archive",
        "projects": projects or {},
        "archive_stats": archive_stats or {"total_projects": 0, "total_sessions": 0, "total_size_mb": 0},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_fact_memory(
    verified_facts: Optional[list[dict]] = None,
    assumptions: Optional[list[dict]] = None,
    contradictions: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """15. Fact memory — aniq faktlar, haqiqatlar"""
    return {
        "id": _gen_id("fact"),
        "type": "fact-memory",
        "verified_facts": verified_facts or [],
        "assumptions": assumptions or [],
        "contradictions": contradictions or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_rule_memory(
    coding_rules: Optional[list[dict]] = None,
    naming_conventions: Optional[list[dict]] = None,
    security_rules: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """16. Rule memory — qoidalar, konvensiyalar"""
    return {
        "id": _gen_id("rule"),
        "type": "rule-memory",
        "coding_rules": coding_rules or [],
        "naming_conventions": naming_conventions or [],
        "security_rules": security_rules or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_code_map_memory(
    directory_structure: Optional[dict] = None,
    dependency_map: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """17. Code map memory — kod strukturasi, dependency graph"""
    return {
        "id": _gen_id("codemap"),
        "type": "code-map-memory",
        "directory_structure": directory_structure or {},
        "dependency_map": dependency_map or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_user_model_memory(
    preferences: Optional[dict] = None,
    skill_level: Optional[dict] = None,
    personalization_rules: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """18. User model memory — user profili, odatlari"""
    return {
        "id": _gen_id("usermodel"),
        "type": "user-model-memory",
        "preferences": preferences or {},
        "skill_level": skill_level or {},
        "personalization_rules": personalization_rules or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_test_memory(
    test_cases: Optional[list[dict]] = None,
    fixtures: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """19. Test memory — test case lar, fixture lar"""
    return {
        "id": _gen_id("test"),
        "type": "test-memory",
        "test_cases": (test_cases or [])[:100],
        "fixtures": fixtures or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_deployment_memory(
    environments: Optional[dict] = None,
    deployment_checklist: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """20. Deployment memory — deploy config lar, env"""
    return {
        "id": _gen_id("deploy"),
        "type": "deployment-memory",
        "environments": environments or {},
        "deployment_checklist": deployment_checklist or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_performance_memory(
    benchmarks: Optional[dict] = None,
    profiles: Optional[dict] = None,
    optimizations_applied: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """21. Performance memory — performance profiling"""
    return {
        "id": _gen_id("perf"),
        "type": "performance-memory",
        "benchmarks": benchmarks or {},
        "profiles": profiles or {},
        "optimizations_applied": optimizations_applied or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_security_memory(
    audit_logs: Optional[list[dict]] = None,
    vulnerabilities: Optional[list[dict]] = None,
    security_policies: Optional[list[str]] = None,
    access_control: Optional[dict] = None,
    summary: str = "",
) -> dict:
    """22. Security memory — security qoidalar, audit"""
    return {
        "id": _gen_id("sec"),
        "type": "security-memory",
        "audit_logs": (audit_logs or [])[:50],
        "vulnerabilities": vulnerabilities or [],
        "security_policies": security_policies or [],
        "access_control": access_control or {},
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_dependency_memory(
    dependency_tree: Optional[dict] = None,
    vulnerabilities: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """23. Dependency memory — dependency tree, version"""
    return {
        "id": _gen_id("dep"),
        "type": "dependency-memory",
        "dependency_tree": dependency_tree or {},
        "vulnerabilities": vulnerabilities or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


def make_integration_memory(
    apis: Optional[dict] = None,
    tokens: Optional[dict] = None,
    health_checks: Optional[list[dict]] = None,
    summary: str = "",
) -> dict:
    """24. Integration memory — API integration lar, token lar"""
    return {
        "id": _gen_id("int"),
        "type": "integration-memory",
        "apis": apis or {},
        "tokens": tokens or {},
        "health_checks": health_checks or [],
        "updated_at": _now_iso(),
        "summary": summary[:500],
    }


# L2 Persistent type registry
L2_TYPES = {
    "long-term": {"file": "01-long-term.jsonl", "make": make_long_term},
    "experience": {"file": "02-experience.jsonl", "make": make_experience},
    "knowledge": {"file": "03-knowledge.jsonl", "make": make_knowledge},
    "project-memory": {"file": "04-project.jsonl", "make": make_project_memory},
    "skill-memory": {"file": "05-skill.jsonl", "make": make_skill_memory},
    "pattern-memory": {"file": "06-pattern.jsonl", "make": make_pattern_memory},
    "solution-memory": {"file": "07-solution.jsonl", "make": make_solution_memory},
    "research-memory": {"file": "08-research.jsonl", "make": make_research_memory},
    "documentation-memory": {"file": "09-docs.jsonl", "make": make_documentation_memory},
    "example-memory": {"file": "10-example.jsonl", "make": make_example_memory},
    "error-memory": {"file": "11-error.jsonl", "make": make_error_memory},
    "verification-memory": {"file": "12-verify.jsonl", "make": make_verification_memory},
    "workflow-memory": {"file": "13-workflow.jsonl", "make": make_workflow_memory},
    "archive": {"file": "14-archive.jsonl", "make": make_archive},
    "fact-memory": {"file": "15-fact.jsonl", "make": make_fact_memory},
    "rule-memory": {"file": "16-rule.jsonl", "make": make_rule_memory},
    "code-map-memory": {"file": "17-codemap.jsonl", "make": make_code_map_memory},
    "user-model-memory": {"file": "18-usermodel.jsonl", "make": make_user_model_memory},
    "test-memory": {"file": "19-test.jsonl", "make": make_test_memory},
    "deployment-memory": {"file": "20-deploy.jsonl", "make": make_deployment_memory},
    "performance-memory": {"file": "21-perf.jsonl", "make": make_performance_memory},
    "security-memory": {"file": "22-security.jsonl", "make": make_security_memory},
    "dependency-memory": {"file": "23-dep.jsonl", "make": make_dependency_memory},
    "integration-memory": {"file": "24-integration.jsonl", "make": make_integration_memory},
}
