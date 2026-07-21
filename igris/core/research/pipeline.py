"""
igris.core.research.pipeline
------------------------------
The complete research pipeline orchestrator.

Runs all 12 stages in sequence, with bounded concurrency where possible.
The pipeline is designed to work with 4-8B models: each stage uses
structured prompts and has heuristic fallbacks.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Awaitable

from . import (
    ResearchResult, ResearchArea, GeneratedQuery, CollectedSource,
    Evidence, Claim, CrossValidatedClaim, Pattern, ArchitectureRecommendation,
    QualityIssue, SourceType, VisualAsset,
)
from .research_planner import plan_research
from .query_generator import generate_all_queries
from .collector import collect_all
from .evidence_extractor import extract_all
from .claim_extractor import extract_claims
from .cross_validator import validate_all
from .conflict_resolver import resolve_conflicts, apply_weight_adjustments
from .knowledge_graph import build_graph_from_claims, add_visual_assets_to_graph
from .pattern_miner import mine_patterns
from .visual_asset_collector import collect_visual_assets
from .design_synthesizer import synthesize_architecture
from .quality_reviewer import review_quality
from .confidence_scorer import (
    score_recommendations, score_alternatives, get_confidence_summary,
    reject_low_confidence,
)

from igris.core.providers.openai_compatible import OpenAICompatibleClient


class ResearchPipeline:
    """
    Full research pipeline: from user request to architecture recommendation.

    Usage:
        pipeline = ResearchPipeline(llm_client)
        result = await pipeline.run("Build a CRM with React and FastAPI")
    """

    def __init__(
        self,
        llm: OpenAICompatibleClient,
        max_queries_per_area: int = 3,
        max_repos_for_patterns: int = 10,
        min_claim_confidence: float = 0.4,
        max_areas: int = 5,
        on_stage: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        self.llm = llm
        self.max_queries_per_area = max_queries_per_area
        self.max_repos_for_patterns = max_repos_for_patterns
        self.min_claim_confidence = min_claim_confidence
        self.max_areas = max_areas
        self._on_stage = on_stage

    async def _trace(self, result: ResearchResult, stage: str, detail: str) -> None:
        result.trace.append((stage, detail))
        if self._on_stage:
            await self._on_stage(stage, detail)

    async def run(
        self,
        user_request: str,
        constraints: list[str] | None = None,
    ) -> ResearchResult:
        """Execute the full research pipeline."""
        result = ResearchResult(original_request=user_request)
        t0 = time.time()

        # Stage 1: Research Planning
        await self._trace(result, "planner", "decomposing request into research areas")
        areas = await plan_research(self.llm, user_request)
        areas = areas[:self.max_areas]
        result.areas = areas
        await self._trace(result, "planner", f"found {len(areas)} research areas (limited to {self.max_areas})")

        # Stage 2: Query Generation
        await self._trace(result, "query_gen", "generating search queries")
        queries = await generate_all_queries(self.llm, areas, self.max_queries_per_area)
        result.queries_generated = len(queries)
        await self._trace(result, "query_gen", f"generated {len(queries)} queries")

        # Stage 3: Multi-Source Collection
        await self._trace(result, "collector", "fetching from multiple sources")
        sources = await collect_all(queries)
        result.sources_collected = len(sources)
        await self._trace(result, "collector", f"collected {len(sources)} sources")

        # Stage 4: Evidence Extraction (sample best sources)
        await self._trace(result, "evidence", "extracting structured evidence")
        scored_sources = sorted(sources, key=lambda s: len(s.raw_content), reverse=True)
        evidence = await extract_all(self.llm, scored_sources[:15])
        result.evidence_extracted = len(evidence)
        await self._trace(result, "evidence", f"extracted {len(evidence)} evidence items from {min(len(sources), 15)} sources")

        # Stage 5: Claim Extraction
        await self._trace(result, "claims", "extracting verifiable claims")
        claims = await extract_claims(self.llm, evidence)
        result.claims_extracted = len(claims)
        await self._trace(result, "claims", f"extracted {len(claims)} claims")

        # Stage 6: Cross-Validation
        await self._trace(result, "validation", "cross-validating claims")
        validated, rejected = await validate_all(
            self.llm, claims, evidence, self.min_claim_confidence
        )
        result.claims_validated = len(validated)
        result.claims_rejected = len(rejected)
        await self._trace(result, "validation",
            f"validated {len(validated)}, rejected {len(rejected)}")

        # Stage 7: Conflict Resolution
        await self._trace(result, "conflicts", "resolving conflicting claims")
        validated = await resolve_conflicts(self.llm, validated)
        validated = apply_weight_adjustments(validated)
        await self._trace(result, "conflicts", "conflicts resolved")

        # Stage 8: Knowledge Graph
        await self._trace(result, "graph", "building knowledge graph")
        graph = build_graph_from_claims(validated)
        result.knowledge_nodes = len(graph.nodes)
        result.knowledge_edges = len(graph.edges)
        result.knowledge_graph = graph.to_dict()
        await self._trace(result, "graph",
            f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Stage 9: Pattern Mining (GitHub)
        await self._trace(result, "patterns", "mining patterns from GitHub")
        patterns = await mine_patterns("react production app", self.max_repos_for_patterns)
        result.patterns_found = len(patterns)
        result.patterns = [
            Pattern(name=p.name, frequency=p.frequency, description=p.description, category=p.category)
            for p in patterns
        ]
        await self._trace(result, "patterns", f"found {len(patterns)} patterns")

        # Stage 9.5: Visual Asset Collection (logos, icons, mockups, 3D)
        await self._trace(result, "visual", "collecting visual assets (logos, icons, mockups, 3D)")
        visual_assets = await collect_visual_assets(self.llm, user_request, areas)
        result.visual_assets_found = len(visual_assets)
        result.visual_assets = visual_assets
        add_visual_assets_to_graph(graph, visual_assets)
        result.knowledge_graph = graph.to_dict()
        await self._trace(result, "visual",
            f"found {len(visual_assets)} visual assets")

        # Stage 10: Design Synthesis
        await self._trace(result, "synthesis", "synthesizing architecture with visual assets")
        recommendations, full_arch, visual_recs = await synthesize_architecture(
            self.llm, user_request, areas, validated, graph, patterns, constraints, visual_assets
        )
        result.recommendations = recommendations
        result.full_architecture = full_arch
        await self._trace(result, "synthesis",
            f"generated {len(recommendations)} recommendations, {len(visual_recs)} visual asset recs")

        # Stage 11: Quality Review
        await self._trace(result, "review", "reviewing for missing pieces")
        quality_issues = await review_quality(self.llm, recommendations, user_request)
        result.quality_issues = quality_issues
        await self._trace(result, "review", f"found {len(quality_issues)} issues")

        # Stage 12: Confidence Scoring
        await self._trace(result, "confidence", "scoring confidence")
        recommendations = score_recommendations(recommendations, validated, quality_issues)
        for rec in recommendations:
            score_alternatives(rec, validated)
        result.recommendations = recommendations
        result.confidence_summary = get_confidence_summary(recommendations)

        accepted, _ = reject_low_confidence(recommendations)
        result.recommendations = accepted

        elapsed = time.time() - t0
        await self._trace(result, "done", f"pipeline completed in {elapsed:.1f}s")

        return result


async def run_research(
    llm: OpenAICompatibleClient,
    user_request: str,
    constraints: list[str] | None = None,
    on_stage: Callable[[str, str], Awaitable[None]] | None = None,
) -> ResearchResult:
    """Convenience function to run the full pipeline."""
    pipeline = ResearchPipeline(llm, on_stage=on_stage)
    return await pipeline.run(user_request, constraints)
