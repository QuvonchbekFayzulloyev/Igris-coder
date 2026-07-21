"""
igris.core.research.quality_reviewer
---------------------------------------
Stage 11: Review architecture for missing pieces.

A separate review pass catches things the synthesis might have missed:
- Missing logging/monitoring
- Missing testing strategy
- Missing database migrations
- Missing CI/CD
- Missing security hardening
- Missing error handling
- Missing documentation
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import ArchitectureRecommendation, QualityIssue

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

REVIEWER_SYSTEM = """You are a quality review agent. Given an architecture
recommendation, identify what's MISSING.

Focus on:
1. Logging and monitoring (no observability = blind in production)
2. Testing strategy (no tests = guaranteed regressions)
3. Database migrations (schema changes without migration = data loss)
4. CI/CD pipeline (no automation = manual deployment errors)
5. Security (no hardening = easy attack surface)
6. Error handling (no graceful degradation = cascading failures)
7. Documentation (no docs = knowledge loss)
8. Rate limiting (no limits = abuse)
9. Backup strategy (no backups = data loss)
10. Performance monitoring (no metrics = can't optimize)

For each issue, provide:
- category: the missing area
- severity: critical | warning | info
- description: what's missing and why it matters
- suggestion: concrete fix

Return a JSON array of issue objects. No markdown fences."""

_BASELINE_CHECKS = [
    ("logging", "critical", "Application logging for debugging and audit trails"),
    ("monitoring", "warning", "Health checks and metrics collection"),
    ("testing", "critical", "Unit, integration, and e2e test strategy"),
    ("migrations", "critical", "Database schema migration tooling"),
    ("ci_cd", "warning", "Automated build, test, and deployment pipeline"),
    ("security", "critical", "Authentication, authorization, and input validation"),
    ("error_handling", "critical", "Graceful error handling and user feedback"),
    ("documentation", "warning", "API docs and architecture decision records"),
    ("rate_limiting", "warning", "API rate limiting to prevent abuse"),
    ("backup", "warning", "Data backup and recovery strategy"),
    ("performance", "info", "Performance monitoring and profiling"),
]


def _heuristic_review(recommendations: list[ArchitectureRecommendation]) -> list[QualityIssue]:
    """Check for missing pieces using heuristics when LLM is unavailable."""
    issues = []
    components = {r.component.lower() for r in recommendations}

    has_testing = any("test" in c for c in components)
    has_logging = any("log" in c for c in components)
    has_monitoring = any("monitor" in c for c in components)
    has_security = any("auth" in c or "security" in c for c in components)
    has_migration = any("migration" in c or "orm" in c for c in components)
    has_ci_cd = any("ci" in c or "deploy" in c for c in components)

    if not has_testing:
        issues.append(QualityIssue("testing", "critical",
            "No testing strategy identified",
            "Add Jest/Vitest for unit tests, Playwright for e2e, and a testing policy"))
    if not has_logging:
        issues.append(QualityIssue("logging", "critical",
            "No logging solution identified",
            "Add structured logging (Pino/Winston for Node, structlog for Python)"))
    if not has_monitoring:
        issues.append(QualityIssue("monitoring", "warning",
            "No monitoring/observability identified",
            "Add health checks, metrics endpoint, and optionally Prometheus/Grafana"))
    if not has_security:
        issues.append(QualityIssue("security", "critical",
            "No security measures identified",
            "Add authentication, CSRF protection, input validation, and rate limiting"))
    if not has_migration:
        issues.append(QualityIssue("migrations", "critical",
            "No database migration strategy identified",
            "Add Prisma Migrate, Alembic, or equivalent migration tool"))
    if not has_ci_cd:
        issues.append(QualityIssue("ci_cd", "warning",
            "No CI/CD pipeline identified",
            "Add GitHub Actions or GitLab CI for automated testing and deployment"))

    return issues


async def review_quality(
    llm: OpenAICompatibleClient,
    recommendations: list[ArchitectureRecommendation],
    original_request: str,
) -> list[QualityIssue]:
    """Review the architecture for missing pieces."""
    arch_summary = "\n".join(
        f"- {r.component}: {r.choice} ({r.confidence:.0%})"
        for r in recommendations
    )

    prompt = (
        f"Original request: {original_request}\n\n"
        f"Architecture components:\n{arch_summary}\n\n"
        f"Identify what's MISSING from this architecture."
    )

    messages = [
        {"role": "system", "content": REVIEWER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        issues_data = json.loads(raw)

        issues = []
        for item in issues_data:
            issues.append(QualityIssue(
                category=item.get("category", "unknown"),
                severity=item.get("severity", "warning"),
                description=item.get("description", ""),
                suggestion=item.get("suggestion", ""),
            ))
        return issues

    except (json.JSONDecodeError, Exception):
        return _heuristic_review(recommendations)
