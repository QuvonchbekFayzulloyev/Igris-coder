"""
igris.core.research.research_planner
--------------------------------------
Stage 1: Decompose a user's high-level request into concrete research areas.

The LLM does the decomposition (it's good at understanding intent), but
each area is validated against a checklist of common software architecture
concerns to ensure nothing is missed.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import ResearchArea

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

PLANNER_SYSTEM = """You are a research planning agent. Your job is to decompose
a high-level software project request into specific, researchable areas.

For each area, provide:
- name: short identifier (e.g. "frontend_framework", "database", "auth")
- description: what specifically needs to be researched
- priority: 1 (critical) to 5 (nice-to-have)
- sub_areas: specific sub-topics to investigate

Always include these baseline areas unless the user explicitly excludes them:
- architecture_pattern (overall project structure)
- frontend_framework (UI library/framework choice)
- backend_framework (server-side framework)
- database (data storage)
- authentication (user management)
- security (hardening, OWASP)
- testing (unit, integration, e2e)
- deployment (hosting, CI/CD)
- monitoring (logging, observability)
- performance (caching, optimization)

Return a JSON array of areas. No markdown fences. Just the JSON array."""

AREA_CHECKLIST = [
    "architecture_pattern",
    "frontend_framework",
    "backend_framework",
    "database",
    "authentication",
    "security",
    "testing",
    "deployment",
    "monitoring",
    "performance",
    "api_design",
    "caching",
    "logging",
    "error_handling",
    "accessibility",
    "i18n",
    "state_management",
    "real_time",
    "file_storage",
    "email",
    "queue",
    "search",
]


async def plan_research(llm: OpenAICompatibleClient, user_request: str) -> list[ResearchArea]:
    """
    Use the LLM to decompose the request into research areas,
    then fill in any gaps from the baseline checklist.
    """
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": f"Project request: {user_request}"},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        areas_data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        areas_data = _fallback_areas(user_request)

    areas = []
    seen_names = set()
    for item in areas_data:
        name = item.get("name", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        areas.append(ResearchArea(
            name=name,
            description=item.get("description", ""),
            priority=item.get("priority", 3),
            sub_areas=item.get("sub_areas", []),
        ))

    existing_names = {a.name for a in areas}
    for checklist_name in AREA_CHECKLIST:
        if checklist_name not in existing_names:
            areas.append(ResearchArea(
                name=checklist_name,
                description=f"Research {checklist_name.replace('_', ' ')} options and best practices",
                priority=4,
                sub_areas=[],
            ))

    areas.sort(key=lambda a: a.priority)
    return areas


def _fallback_areas(user_request: str) -> list[dict]:
    """Heuristic decomposition when LLM output is unparseable."""
    return [
        {"name": "architecture_pattern", "description": "Overall project architecture", "priority": 1, "sub_areas": []},
        {"name": "frontend_framework", "description": "UI framework choice", "priority": 1, "sub_areas": []},
        {"name": "backend_framework", "description": "Server framework choice", "priority": 1, "sub_areas": []},
        {"name": "database", "description": "Database choice", "priority": 1, "sub_areas": []},
        {"name": "authentication", "description": "Auth system", "priority": 2, "sub_areas": []},
        {"name": "security", "description": "Security hardening", "priority": 2, "sub_areas": []},
        {"name": "testing", "description": "Testing strategy", "priority": 2, "sub_areas": []},
        {"name": "deployment", "description": "Deployment and CI/CD", "priority": 3, "sub_areas": []},
        {"name": "monitoring", "description": "Observability", "priority": 3, "sub_areas": []},
        {"name": "performance", "description": "Performance optimization", "priority": 3, "sub_areas": []},
    ]
