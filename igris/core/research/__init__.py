"""
igris.core.research
--------------------
Research Pipeline: multi-source, evidence-based architecture planning.

Instead of asking the LLM to "know everything", this pipeline:
1. Decomposes the task into research areas
2. Generates targeted queries per area
3. Collects evidence from multiple sources (GitHub, docs, SO, Reddit, etc.)
4. Extracts claims from evidence
5. Cross-validates claims against 3+ independent sources
6. Resolves conflicts via weighted voting
7. Builds a knowledge graph with typed relationships
8. Mines patterns from real GitHub repositories
9. Synthesizes architecture from requirements + knowledge + patterns
10. Reviews quality and scores confidence for every recommendation

The 4-8B model handles classification, extraction, comparison, and
synthesis. The pipeline handles orchestration, storage, and verification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    OFFICIAL_DOCS = "official_docs"
    GITHUB = "github"
    STACKOVERFLOW = "stackoverflow"
    REDDIT = "reddit"
    MEDIUM = "medium"
    BLOG = "blog"
    YOUTUBE = "youtube"
    RFC = "rfc"
    PAPER = "paper"
    NPM = "npm"
    PYPI = "pypi"
    FIGMA = "figma"
    DRIBBBLE = "dribbble"
    BEHANCE = "behance"
    UNSPLASH = "unsplash"
    ICONFinder = "iconfinder"
    FLAT_ICON = "flaticon"
    THREE_D_CDN = "3d_cdn"
    SKETCHFAB = "sketchfab"


class AssetType(str, Enum):
    """Visual asset types the pipeline can discover."""
    LOGO = "logo"
    ICON = "icon"
    ILLUSTRATION = "illustration"
    MOCKUP = "mockup"
    SCREENSHOT = "screenshot"
    THREED_MODEL = "3d_model"
    UI_KIT = "ui_kit"
    COMPONENT_LIBRARY = "component_library"
    COLOR_PALETTE = "color_palette"
    FONT = "font"
    ANIMATION = "animation"
    PHOTO = "photo"
    BACKGROUND = "background"
    PATTERN = "pattern"
    DIAGRAM = "diagram"


SOURCE_WEIGHTS: dict[SourceType, float] = {
    SourceType.OFFICIAL_DOCS: 1.0,
    SourceType.GITHUB: 0.9,
    SourceType.NPM: 0.85,
    SourceType.PYPI: 0.85,
    SourceType.STACKOVERFLOW: 0.8,
    SourceType.RFC: 0.95,
    SourceType.PAPER: 0.85,
    SourceType.FIGMA: 0.9,
    SourceType.REDDIT: 0.6,
    SourceType.MEDIUM: 0.5,
    SourceType.DRIBBBLE: 0.7,
    SourceType.BEHANCE: 0.7,
    SourceType.UNSPLASH: 0.8,
    SourceType.ICONFinder: 0.75,
    SourceType.FLAT_ICON: 0.7,
    SourceType.THREE_D_CDN: 0.8,
    SourceType.SKETCHFAB: 0.85,
    SourceType.YOUTUBE: 0.4,
    SourceType.BLOG: 0.3,
}


@dataclass
class VisualAsset:
    """A discovered visual asset (logo, icon, 3D model, etc.)."""
    name: str
    asset_type: AssetType
    source_url: str
    source_type: SourceType
    download_url: str = ""
    preview_url: str = ""
    license: str = ""
    format: str = ""  # svg, png, glb, fbx, etc.
    width: int = 0
    height: int = 0
    file_size: int = 0
    tags: list[str] = field(default_factory=list)
    description: str = ""
    confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)  # other similar asset URLs
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchArea:
    name: str
    description: str
    priority: int = 1  # 1 = highest
    sub_areas: list[str] = field(default_factory=list)


@dataclass
class GeneratedQuery:
    text: str
    area: str
    source_hints: list[SourceType] = field(default_factory=list)


@dataclass
class CollectedSource:
    url: str
    source_type: SourceType
    title: str
    raw_content: str
    fetched_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    source_url: str
    source_type: SourceType
    source_weight: float
    category: str  # architecture, best_practice, warning, performance, code_snippet, etc.
    content: str
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Claim:
    text: str
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    sources_verified: int = 0
    is_conflict: bool = False
    conflict_with: list[str] = field(default_factory=list)


@dataclass
class CrossValidatedClaim:
    claim: str
    confidence: float
    supporting_sources: list[str] = field(default_factory=list)
    contradicting_sources: list[str] = field(default_factory=list)
    source_types_verified: list[SourceType] = field(default_factory=list)
    resolution: str = ""  # how conflicts were resolved


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str  # technology, concept, pattern, requirement, constraint
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str  # depends_on, alternative, recommended, deprecated, faster, slower, compatible
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pattern:
    name: str
    frequency: float  # 0.0 - 1.0
    examples: list[str] = field(default_factory=list)
    description: str = ""
    category: str = ""  # folder_structure, dependency, architecture, testing, etc.


@dataclass
class ArchitectureRecommendation:
    component: str
    choice: str
    confidence: float
    alternatives: list[tuple[str, float]] = field(default_factory=list)  # (alt, alt_confidence)
    reasoning: str = ""
    evidence_count: int = 0
    sources: list[str] = field(default_factory=list)


@dataclass
class QualityIssue:
    category: str  # missing_logging, missing_testing, missing_migration, etc.
    severity: str  # critical, warning, info
    description: str
    suggestion: str


@dataclass
class ResearchResult:
    """Complete output of the research pipeline."""
    original_request: str
    areas: list[ResearchArea] = field(default_factory=list)
    queries_generated: int = 0
    sources_collected: int = 0
    evidence_extracted: int = 0
    claims_extracted: int = 0
    claims_validated: int = 0
    claims_rejected: int = 0
    knowledge_nodes: int = 0
    knowledge_edges: int = 0
    patterns_found: int = 0
    visual_assets_found: int = 0
    recommendations: list[ArchitectureRecommendation] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    visual_assets: list[VisualAsset] = field(default_factory=list)
    knowledge_graph: dict[str, Any] = field(default_factory=dict)
    patterns: list[Pattern] = field(default_factory=list)
    full_architecture: str = ""
    confidence_summary: dict[str, float] = field(default_factory=dict)
    trace: list[tuple[str, str]] = field(default_factory=list)
