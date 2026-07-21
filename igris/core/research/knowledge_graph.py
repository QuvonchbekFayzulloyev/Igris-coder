"""
igris.core.research.knowledge_graph
--------------------------------------
Stage 8: Build a knowledge graph from validated claims.

Nodes: technologies, concepts, patterns, requirements
Edges: relationships (depends_on, alternative, recommended, deprecated, etc.)

The graph is stored as a simple dict (JSON-serializable) but can be
exported to NetworkX for advanced analysis.
"""
from __future__ import annotations

import json
from typing import Any

from . import CrossValidatedClaim, GraphNode, GraphEdge

# Relationship types
RELATIONSHIPS = {
    "depends_on": "requires",
    "alternative": "can replace",
    "recommended": "better than",
    "deprecated": "replaced by",
    "faster": "performs better than",
    "slower": "performs worse than",
    "compatible": "works with",
    "includes": "contains",
    "implements": "realizes",
    "extends": "builds on",
}


class KnowledgeGraph:
    """In-memory knowledge graph with JSON serialization."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
        else:
            existing = self.nodes[node.id]
            for k, v in node.properties.items():
                if k not in existing.properties:
                    existing.properties[k] = v

    def add_edge(self, edge: GraphEdge) -> None:
        for existing in self.edges:
            if (existing.source == edge.source and
                existing.target == edge.target and
                existing.relationship == edge.relationship):
                existing.weight = max(existing.weight, edge.weight)
                return
        self.edges.append(edge)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self.nodes.get(node_id)

    def get_neighbors(self, node_id: str, relationship: str | None = None) -> list[str]:
        neighbors = []
        for edge in self.edges:
            if edge.source == node_id:
                if relationship is None or edge.relationship == relationship:
                    neighbors.append(edge.target)
            elif edge.target == node_id:
                if relationship is None or edge.relationship == relationship:
                    neighbors.append(edge.source)
        return neighbors

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": n.id, "label": n.label, "type": n.node_type, "properties": n.properties}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "relationship": e.relationship,
                 "weight": e.weight, "metadata": e.metadata}
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeGraph":
        graph = cls()
        for n in data.get("nodes", []):
            graph.add_node(GraphNode(
                id=n["id"], label=n["label"], node_type=n["type"],
                properties=n.get("properties", {}),
            ))
        for e in data.get("edges", []):
            graph.add_edge(GraphEdge(
                source=e["source"], target=e["target"],
                relationship=e["relationship"], weight=e.get("weight", 1.0),
                metadata=e.get("metadata", {}),
            ))
        return graph

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        node_map = {}
        for i, node in enumerate(self.nodes.values()):
            nid = f"N{i}"
            node_map[node.id] = nid
            label = node.label.replace('"', "'")
            if node.node_type == "technology":
                lines.append(f"    {nid}[\"{label}\"]")
            elif node.node_type == "requirement":
                lines.append(f"    {nid}{{\"{label}\"}}")
            else:
                lines.append(f"    {nid}(\"{label}\")")

        for edge in self.edges:
            src = node_map.get(edge.source)
            tgt = node_map.get(edge.target)
            if src and tgt:
                label = edge.relationship.replace("_", " ")
                lines.append(f"    {src} -->|\"{label}\"| {tgt}")

        return "\n".join(lines)


def _make_id(text: str) -> str:
    return text.lower().replace(" ", "_").replace("-", "_")[:50]


def build_graph_from_claims(
    validated_claims: list[CrossValidatedClaim],
) -> KnowledgeGraph:
    """Build a knowledge graph from cross-validated claims."""
    graph = KnowledgeGraph()

    for vc in validated_claims:
        words = vc.claim.split()
        technologies = _extract_technologies(vc.claim)

        for tech in technologies:
            graph.add_node(GraphNode(
                id=_make_id(tech),
                label=tech,
                node_type="technology",
                properties={"confidence": vc.confidence},
            ))

        relationships = _infer_relationships(vc.claim)
        for src, rel, tgt in relationships:
            src_id = _make_id(src)
            tgt_id = _make_id(tgt)
            graph.add_node(GraphNode(id=src_id, label=src, node_type="technology"))
            graph.add_node(GraphNode(id=tgt_id, label=tgt, node_type="technology"))
            graph.add_edge(GraphEdge(
                source=src_id, target=tgt_id,
                relationship=rel, weight=vc.confidence,
            ))

    return graph


def _extract_technologies(text: str) -> list[str]:
    """Extract technology names from claim text."""
    known_techs = [
        "React", "Vue", "Svelte", "Angular", "Next.js", "Nuxt", "Remix",
        "Node.js", "Express", "Fastify", "NestJS", "Django", "Flask", "FastAPI",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite",
        "Docker", "Kubernetes", "Vercel", "Netlify", "AWS", "Azure",
        "TypeScript", "JavaScript", "Python", "Go", "Rust",
        "Redux", "Zustand", "Jotai", "TanStack Query", "SWR",
        "Tailwind", "CSS", "SASS",
        "Jest", "Vitest", "Playwright", "Cypress",
        "GraphQL", "REST", "tRPC",
        "Prisma", "Drizzle", "TypeORM",
        "WebSocket", "Socket.io", "SSE",
        "RabbitMQ", "Kafka", "Bull",
        "Nginx", "Apache",
        "Linux", "Ubuntu", "Debian",
        "Git", "GitHub", "GitLab",
        "VS Code", "IntelliJ",
        "Webpack", "Vite", "esbuild", "Rollup",
        "ESLint", "Prettier",
    ]
    found = []
    text_lower = text.lower()
    for tech in known_techs:
        if tech.lower() in text_lower:
            found.append(tech)
    return found[:5]


def _infer_relationships(text: str) -> list[tuple[str, str, str]]:
    """Infer relationships from claim text."""
    relationships = []
    text_lower = text.lower()

    rel_patterns = [
        (["replaces", "better than", "instead of"], "alternative"),
        (["recommended", "prefer", "use"], "recommended"),
        (["deprecated", "replaced by", "superseded by"], "deprecated"),
        (["faster than", "quicker than", "more performant"], "faster"),
        (["slower than", "heavier than"], "slower"),
        (["depends on", "requires", "needs"], "depends_on"),
        (["compatible with", "works with", "integrates with"], "compatible"),
        (["extends", "builds on", "based on"], "extends"),
    ]

    techs = _extract_technologies(text)
    for keyword_list, rel_type in rel_patterns:
        for kw in keyword_list:
            if kw in text_lower:
                if len(techs) >= 2:
                    relationships.append((techs[0], rel_type, techs[1]))
                break

    return relationships


def add_visual_assets_to_graph(
    graph: KnowledgeGraph,
    visual_assets: list,
) -> None:
    """Add visual assets as nodes and connect them to relevant technologies."""
    from . import VisualAsset, AssetType

    for asset in visual_assets:
        node_id = _make_id(f"asset_{asset.name}")
        graph.add_node(GraphNode(
            id=node_id,
            label=asset.name,
            node_type="visual_asset",
            properties={
                "asset_type": asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type),
                "source_url": asset.source_url,
                "download_url": asset.download_url,
                "format": asset.format,
                "confidence": asset.confidence,
                "license": asset.license,
            },
        ))

        for tag in asset.tags[:3]:
            if not isinstance(tag, str):
                continue
            tech_id = _make_id(tag)
            if tech_id in graph.nodes:
                graph.add_edge(GraphEdge(
                    source=tech_id,
                    target=node_id,
                    relationship="has_visual",
                    weight=asset.confidence,
                ))
