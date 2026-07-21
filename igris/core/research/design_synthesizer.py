"""
igris.core.research.design_synthesizer
-----------------------------------------
Stage 10: Synthesize architecture from requirements + knowledge + patterns.

Combines:
- User requirements (from the original request)
- Validated claims (from cross-validation)
- Knowledge graph (relationships between technologies)
- Patterns (from GitHub mining)
- Constraints (4-6GB GPU, local-first, lightweight)

Produces a concrete architecture recommendation.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import (
    ArchitectureRecommendation, Claim, CrossValidatedClaim,
    Pattern, ResearchArea,
)
from .knowledge_graph import KnowledgeGraph

if TYPE_CHECKING:
    from igris.core.providers.openai_compatible import OpenAICompatibleClient

SYNTHESIZER_SYSTEM = """You are an architecture synthesis agent. Given:
1. User requirements
2. Cross-validated claims (verified by multiple sources)
3. Knowledge graph (technology relationships)
4. Patterns (from real GitHub repos)
5. Visual assets (logos, icons, UI kits, 3D models, etc.)
6. Constraints

Produce a concrete architecture recommendation.

For each component, provide:
- component: what it is (e.g. "frontend_framework")
- choice: your recommendation
- confidence: 0.0-1.0
- alternatives: list of [alternative, confidence] pairs
- reasoning: brief explanation
- evidence_count: how many sources support this

Also recommend visual assets:
- logos: app logo, brand mark
- icons: icon set/library to use
- ui_kit: design system or UI kit
- colors: primary/secondary color palette
- fonts: heading + body font pairing
- illustrations: illustration style/source
- mockups: dashboard/page mockup references
- 3d: 3D elements if appropriate

Return a JSON object with:
- architecture_name: short name
- components: list of component recommendations
- visual_assets: list of {type, name, source, url, reasoning}
- overall_confidence: average confidence
- constraints_satisfied: which constraints are met
- constraints_violated: which constraints can't be met
No markdown fences."""


async def synthesize_architecture(
    llm: OpenAICompatibleClient,
    original_request: str,
    areas: list[ResearchArea],
    validated_claims: list[CrossValidatedClaim],
    graph: KnowledgeGraph,
    patterns: list[Pattern],
    constraints: list[str] | None = None,
    visual_assets: list | None = None,
) -> tuple[list[ArchitectureRecommendation], str, list[dict]]:
    """
    Synthesize a concrete architecture from all research artifacts.
    Returns (recommendations, full_architecture_text).
    """
    constraints = constraints or [
        "4-6GB GPU (local LLM inference)",
        "Lightweight and local-first",
        "Can run on a single developer machine",
        "Minimal cloud dependencies",
        "Fast startup and low memory usage",
    ]

    claims_summary = "\n".join(
        f"- [{vc.confidence:.0%}] {vc.claim}" for vc in validated_claims[:30]
    )

    graph_summary = ""
    if graph.nodes:
        graph_summary = f"Knowledge graph: {len(graph.nodes)} technologies, {len(graph.edges)} relationships\n"
        for edge in graph.edges[:15]:
            src = graph.nodes.get(edge.source, None)
            tgt = graph.nodes.get(edge.target, None)
            if src and tgt:
                graph_summary += f"  {src.label} --{edge.relationship}--> {tgt.label}\n"

    patterns_summary = ""
    for p in patterns[:10]:
        patterns_summary += f"- {p.name}: {p.frequency:.0%} adoption\n"

    visual_summary = ""
    if visual_assets:
        visual_summary = "Discovered visual assets:\n"
        for va in visual_assets[:15]:
            visual_summary += f"- [{va.asset_type.value if hasattr(va.asset_type, 'value') else va.asset_type}] {va.name}: {va.source_url} ({va.confidence:.0%})\n"

    prompt = (
        f"Original request: {original_request}\n\n"
        f"Research areas: {', '.join(a.name for a in areas[:10])}\n\n"
        f"Validated claims:\n{claims_summary}\n\n"
        f"{graph_summary}\n"
        f"Patterns from GitHub:\n{patterns_summary}\n\n"
        f"{visual_summary}\n"
        f"Constraints:\n" + "\n".join(f"- {c}" for c in constraints) + "\n\n"
        f"Synthesize a concrete architecture recommendation including visual assets."
    )

    messages = [
        {"role": "system", "content": SYNTHESIZER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        result = await llm.chat(messages=messages)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)

        recommendations = []
        for comp in data.get("components", []):
            alts = comp.get("alternatives", [])
            if isinstance(alts, list):
                alts = [(a[0], a[1]) if isinstance(a, list) and len(a) >= 2 else (str(a), 0.5) for a in alts]
            else:
                alts = []

            recommendations.append(ArchitectureRecommendation(
                component=comp.get("component", ""),
                choice=comp.get("choice", ""),
                confidence=min(1.0, max(0.0, comp.get("confidence", 0.5))),
                alternatives=alts,
                reasoning=comp.get("reasoning", ""),
                evidence_count=comp.get("evidence_count", 0),
            ))

        full_text = _render_architecture(data, recommendations)
        visual_recs = data.get("visual_assets", [])
        return recommendations, full_text, visual_recs

    except (json.JSONDecodeError, Exception) as e:
        return _fallback_synthesis(validated_claims, patterns, visual_assets)


def _render_architecture(data: dict, recommendations: list[ArchitectureRecommendation]) -> str:
    """Render the architecture as readable text."""
    lines = [
        f"# {data.get('architecture_name', 'Recommended Architecture')}",
        "",
        "## Components",
        "",
    ]

    for r in recommendations:
        lines.append(f"### {r.component.replace('_', ' ').title()}")
        lines.append(f"**Recommendation:** {r.choice} (confidence: {r.confidence:.0%})")
        if r.alternatives:
            lines.append("**Alternatives:**")
            for alt, conf in r.alternatives:
                lines.append(f"  - {alt} ({conf:.0%})")
        if r.reasoning:
            lines.append(f"**Reasoning:** {r.reasoning}")
        lines.append(f"**Evidence:** {r.evidence_count} sources")
        lines.append("")

    visual_assets = data.get("visual_assets", [])
    if visual_assets:
        lines.append("## Visual Assets")
        lines.append("")
        for va in visual_assets:
            va_type = va.get("type", "asset")
            va_name = va.get("name", "")
            va_url = va.get("url", "")
            va_reasoning = va.get("reasoning", "")
            lines.append(f"- **{va_type}**: {va_name}")
            if va_url:
                lines.append(f"  URL: {va_url}")
            if va_reasoning:
                lines.append(f"  {va_reasoning}")
        lines.append("")

    constraints_met = data.get("constraints_satisfied", [])
    constraints_violated = data.get("constraints_violated", [])
    if constraints_met:
        lines.append("## Constraints Satisfied")
        for c in constraints_met:
            lines.append(f"- {c}")
        lines.append("")

    if constraints_violated:
        lines.append("## Constraints Violated")
        for c in constraints_violated:
            lines.append(f"- {c}")

    return "\n".join(lines)


def _fallback_synthesis(
    claims: list[CrossValidatedClaim],
    patterns: list[Pattern],
    visual_assets: list | None = None,
) -> tuple[list[ArchitectureRecommendation], str, list[dict]]:
    """Fallback synthesis when LLM fails."""
    recommendations = []
    seen_components = set()

    for vc in claims:
        if vc.confidence < 0.6:
            continue
        techs = _extract_techs_from_claim(vc.claim)
        for tech in techs:
            component = _guess_component(tech)
            if component and component not in seen_components:
                seen_components.add(component)
                recommendations.append(ArchitectureRecommendation(
                    component=component,
                    choice=tech,
                    confidence=vc.confidence,
                    reasoning=vc.claim,
                    evidence_count=len(vc.supporting_sources),
                ))

    lines = ["# Recommended Architecture (Fallback)", ""]
    for r in recommendations:
        lines.append(f"- **{r.component}**: {r.choice} ({r.confidence:.0%})")

    visual_recs = []
    if visual_assets:
        lines.append("")
        lines.append("## Visual Assets")
        for va in visual_assets[:10]:
            lines.append(f"- [{va.asset_type.value}] {va.name}: {va.source_url}")
            visual_recs.append({
                "type": va.asset_type.value,
                "name": va.name,
                "url": va.source_url,
                "reasoning": va.description,
            })

    return recommendations, "\n".join(lines), visual_recs


def _extract_techs_from_claim(text: str) -> list[str]:
    known = [
        "React", "Vue", "Svelte", "Next.js", "Nuxt", "Remix",
        "Node.js", "Express", "Fastify", "NestJS", "Django", "FastAPI",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite",
        "Docker", "Kubernetes", "Vercel",
        "TypeScript", "Python",
        "Redux", "Zustand", "TanStack Query",
        "Tailwind", "Prisma", "Drizzle",
    ]
    return [t for t in known if t.lower() in text.lower()]


def _guess_component(tech: str) -> str | None:
    frontend = {"React", "Vue", "Svelte", "Next.js", "Nuxt", "Remix", "Angular"}
    backend = {"Node.js", "Express", "Fastify", "NestJS", "Django", "Flask", "FastAPI", "Go", "Rust"}
    database = {"PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Prisma", "Drizzle"}
    state = {"Redux", "Zustand", "Jotai", "TanStack Query", "SWR"}
    css = {"Tailwind", "CSS", "SASS"}
    infra = {"Docker", "Kubernetes", "Vercel", "Netlify", "AWS"}

    if tech in frontend:
        return "frontend_framework"
    if tech in backend:
        return "backend_framework"
    if tech in database:
        return "database"
    if tech in state:
        return "state_management"
    if tech in css:
        return "css_solution"
    if tech in infra:
        return "deployment"
    return None
