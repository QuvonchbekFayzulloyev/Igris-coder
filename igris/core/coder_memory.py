"""Persistent, reusable Coder Knowledge Memory.

Session history answers “what was just said?”; this module answers “what
reusable project or engineering artefact do we already know and trust?”
Artefacts keep their original payload on disk, while a compact JSON manifest
and several metadata indexes make retrieval deterministic even when an
embedding service is unavailable.

The store deliberately does not ingest every chat response. Callers must
provide a category, source, and quality signal, which keeps the memory useful
as a long-lived engineering library rather than a transcript dump.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


MEMORY_CATEGORIES = frozenset({
    "project", "architecture", "folder_structure", "boilerplate", "code_pattern",
    "algorithm", "data_structure", "api_pattern", "design_pattern", "system_design",
    "ui_pattern", "ux_pattern", "component", "branding", "icon", "asset", "prompt",
    "tool", "mcp", "framework", "library", "language", "config", "error", "debug",
    "testing", "security", "performance", "database", "devops", "deployment",
    "documentation", "decision", "lesson",
})

SOURCE_TRUST = {
    "official": 0.95,
    "internal": 0.90,
    "project": 0.90,
    "web_verified": 0.85,
    "github": 0.65,
    "manual": 0.70,
    "llm": 0.35,
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.#/-]{1,}", re.IGNORECASE)
_SAFE_NAME_RE = re.compile(r"[^a-z0-9_-]+")
_IGNORED_DIRS = {
    ".git", ".igris", ".pytest_cache", "__pycache__", "node_modules", ".venv",
    "venv", "dist", "build", "target", ".next", ".turbo",
}
_COLLECTABLE_CONFIGS = {
    "pyproject.toml", "package.json", "package-lock.json", "tsconfig.json",
    "vite.config.ts", "vite.config.js", "requirements.txt", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", ".github/workflows",
}


def _now() -> float:
    return time.time()


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value)}


def _normalise_tags(tags: list[str] | str) -> list[str]:
    values = tags.split(",") if isinstance(tags, str) else tags
    return sorted({value.strip().lower() for value in values if value and value.strip()})


def _clamp_score(value: float, field_name: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number between 0 and 1") from exc
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return round(score, 3)


def _extension_for(format_name: str, language: str) -> str:
    normalised = format_name.strip().lower()
    if normalised in {"markdown", "md"}:
        return "md"
    if normalised == "json":
        return "json"
    if normalised in {"yaml", "yml"}:
        return "yaml"
    if normalised == "svg":
        return "svg"
    language_extensions = {
        "python": "py", "typescript": "ts", "javascript": "js", "tsx": "tsx",
        "jsx": "jsx", "rust": "rs", "go": "go", "java": "java", "sql": "sql",
    }
    return language_extensions.get(language.strip().lower(), "txt")


@dataclass
class MemoryArtifact:
    """Metadata shared by every durable artefact in Coder Knowledge Memory."""

    id: str
    title: str
    category: str
    subcategory: str = ""
    tags: list[str] = field(default_factory=list)
    language: str = ""
    framework: str = ""
    source: str = "manual"
    author: str = ""
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    version: str = ""
    license: str = ""
    quality_score: float = 0.5
    trust_score: float = 0.5
    reuse_score: float = 0.5
    embedding_id: str = ""
    related_items: list[str] = field(default_factory=list)
    source_uri: str = ""
    format: str = "markdown"
    content_path: str = ""
    content_hash: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "MemoryArtifact":
        allowed = {field_name for field_name in cls.__dataclass_fields__}
        payload = {key: value for key, value in raw.items() if key in allowed}
        payload.setdefault("tags", [])
        payload.setdefault("related_items", [])
        payload.setdefault("details", {})
        return cls(**payload)


@dataclass
class MemorySearchHit:
    score: float
    artifact: MemoryArtifact
    excerpt: str


class CoderMemoryStore:
    """Filesystem-backed artefact library with deterministic metadata indexes."""

    def __init__(self, config):
        self.root = config.path_for("coder_memory.dir")
        self.artifacts_dir = self.root / "artifacts"
        self.manifest_path = self.root / "manifest.json"
        self.index_path = self.root / "indexes.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self) -> list[MemoryArtifact]:
        if not self.manifest_path.exists():
            return []
        try:
            raw_entries = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw_entries, list):
            return []
        entries = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            try:
                entries.append(MemoryArtifact.from_raw(raw))
            except (TypeError, ValueError):
                continue
        return entries

    def _write_json(self, path: Path, data: Any) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(path)

    def _save_manifest(self, entries: list[MemoryArtifact]) -> None:
        self._write_json(self.manifest_path, [asdict(entry) for entry in entries])
        self._write_json(self.index_path, self._build_indexes(entries))

    def _build_indexes(self, entries: list[MemoryArtifact]) -> dict[str, dict[str, list[str]]]:
        indexes: dict[str, dict[str, list[str]]] = {
            "category": {}, "tag": {}, "language": {}, "framework": {},
            "source": {}, "project": {}, "architecture": {}, "component": {},
        }

        def add(index_name: str, value: str, artifact_id: str) -> None:
            value = value.strip().lower()
            if value:
                indexes[index_name].setdefault(value, []).append(artifact_id)

        project_id = self.root.parent.name
        for entry in entries:
            add("category", entry.category, entry.id)
            add("language", entry.language, entry.id)
            add("framework", entry.framework, entry.id)
            add("source", entry.source, entry.id)
            add("project", project_id, entry.id)
            for tag in entry.tags:
                add("tag", tag, entry.id)
                if tag in {"clean", "hexagonal", "layered", "cqrs", "event-driven", "microservices"}:
                    add("architecture", tag, entry.id)
            if entry.category in {"component", "ui_pattern", "ux_pattern"}:
                add("component", entry.subcategory or entry.title, entry.id)
        return indexes

    def list(self, category: str = "") -> list[MemoryArtifact]:
        entries = self._load_manifest()
        if category:
            return [entry for entry in entries if entry.category == category.strip().lower()]
        return entries

    def get(self, artifact_id: str) -> MemoryArtifact | None:
        return next((entry for entry in self._load_manifest() if entry.id == artifact_id), None)

    def read_content(self, artifact: MemoryArtifact, max_chars: int = 20_000) -> str:
        path = self.root / artifact.content_path
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
        return content[:max_chars]

    def ingest(
        self,
        *,
        title: str,
        category: str,
        content: str,
        subcategory: str = "",
        tags: list[str] | str = (),
        language: str = "",
        framework: str = "",
        source: str = "manual",
        author: str = "",
        version: str = "",
        license_name: str = "",
        quality_score: float = 0.5,
        trust_score: float | None = None,
        reuse_score: float = 0.5,
        embedding_id: str = "",
        related_items: list[str] | str = (),
        source_uri: str = "",
        format_name: str = "markdown",
        details: dict[str, Any] | None = None,
    ) -> tuple[MemoryArtifact, str]:
        title = title.strip()
        category = category.strip().lower()
        content = content.strip()
        source = source.strip().lower() or "manual"
        if not title:
            raise ValueError("title must not be empty")
        if category not in MEMORY_CATEGORIES:
            allowed = ", ".join(sorted(MEMORY_CATEGORIES))
            raise ValueError(f"category must be one of: {allowed}")
        if not content:
            raise ValueError("content must not be empty")
        if len(content) > 1_000_000:
            raise ValueError("content exceeds the 1,000,000 character artefact limit")

        tag_values = _normalise_tags(tags)
        related_values = _normalise_tags(related_items)
        quality = _clamp_score(quality_score, "quality_score")
        trust = _clamp_score(SOURCE_TRUST.get(source, 0.5) if trust_score is None else trust_score, "trust_score")
        reuse = _clamp_score(reuse_score, "reuse_score")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        entries = self._load_manifest()
        existing = next((entry for entry in entries if source_uri and entry.source_uri == source_uri), None)
        if existing is None:
            existing = next(
                (entry for entry in entries if not source_uri and entry.category == category and entry.title == title
                 and entry.content_hash == content_hash),
                None,
            )

        now = _now()
        artifact_id = existing.id if existing else f"mem-{uuid.uuid4().hex[:12]}"
        extension = _extension_for(format_name, language)
        content_path = Path("artifacts") / artifact_id / f"content.{extension}"
        status = "updated" if existing else "added"
        inferred_version = version.strip() or (existing.version if existing and existing.content_hash == content_hash else f"sha256:{content_hash[:12]}")
        artifact = MemoryArtifact(
            id=artifact_id,
            title=title,
            category=category,
            subcategory=subcategory.strip(),
            tags=tag_values,
            language=language.strip(),
            framework=framework.strip(),
            source=source,
            author=author.strip(),
            created_at=existing.created_at if existing else now,
            updated_at=now,
            version=inferred_version,
            license=license_name.strip(),
            quality_score=quality,
            trust_score=trust,
            reuse_score=reuse,
            embedding_id=embedding_id.strip(),
            related_items=related_values,
            source_uri=source_uri.strip(),
            format=format_name.strip().lower() or "markdown",
            content_path=str(content_path).replace("\\", "/"),
            content_hash=content_hash,
            details=details or {},
        )
        payload_path = self.root / content_path
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_text(content, encoding="utf-8")
        if existing:
            entries = [artifact if entry.id == artifact.id else entry for entry in entries]
        else:
            entries.append(artifact)
        self._save_manifest(entries)
        return artifact, status

    def search(
        self,
        query: str,
        *,
        category: str = "",
        language: str = "",
        framework: str = "",
        tags: list[str] | str = (),
        source: str = "",
        top_k: int = 5,
    ) -> list[MemorySearchHit]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        tag_filter = set(_normalise_tags(tags))
        category = category.strip().lower()
        language = language.strip().lower()
        framework = framework.strip().lower()
        source = source.strip().lower()
        hits: list[MemorySearchHit] = []
        for artifact in self._load_manifest():
            if category and artifact.category != category:
                continue
            if language and artifact.language.lower() != language:
                continue
            if framework and artifact.framework.lower() != framework:
                continue
            if source and artifact.source != source:
                continue
            if tag_filter and not tag_filter.issubset(set(artifact.tags)):
                continue

            title_tokens = _tokens(artifact.title)
            tag_tokens = set(artifact.tags)
            metadata_tokens = _tokens(" ".join([
                artifact.category, artifact.subcategory, artifact.language, artifact.framework, artifact.source,
            ]))
            content = self.read_content(artifact, max_chars=12_000)
            content_tokens = _tokens(content)
            score = (
                5.0 * len(query_tokens & title_tokens)
                + 4.0 * len(query_tokens & tag_tokens)
                + 2.0 * len(query_tokens & metadata_tokens)
                + 1.0 * len(query_tokens & content_tokens)
                + artifact.quality_score + artifact.trust_score + artifact.reuse_score
            )
            if score <= artifact.quality_score + artifact.trust_score + artifact.reuse_score:
                continue
            excerpt = " ".join(content.split())[:700]
            hits.append(MemorySearchHit(score=round(score, 3), artifact=artifact, excerpt=excerpt))
        hits.sort(key=lambda hit: (hit.score, hit.artifact.trust_score, hit.artifact.updated_at), reverse=True)
        return hits[:max(1, min(int(top_k), 20))]


class ProjectMemoryCollector:
    """Collect stable, project-owned artefacts without fabricating content with an LLM."""

    def __init__(self, config, store: CoderMemoryStore | None = None):
        self.config = config
        self.root = config.project_root.resolve()
        self.store = store or CoderMemoryStore(config)

    def _read_text(self, path: Path, max_chars: int = 120_000) -> str:
        try:
            if path.stat().st_size > max_chars * 4:
                return ""
            return path.read_text(encoding="utf-8")[:max_chars]
        except (OSError, UnicodeDecodeError):
            return ""

    def _tree(self, max_entries: int) -> str:
        lines = [f"{self.root.name}/"]
        emitted = 0
        for current, dirs, files in os.walk(self.root):
            dirs[:] = sorted(directory for directory in dirs if directory not in _IGNORED_DIRS)
            current_path = Path(current)
            depth = len(current_path.relative_to(self.root).parts)
            for name in [*dirs, *sorted(files)]:
                if emitted >= max_entries:
                    lines.append("... (tree truncated)")
                    return "\n".join(lines)
                path = current_path / name
                if path.is_dir() and name in _IGNORED_DIRS:
                    continue
                suffix = "/" if path.is_dir() else ""
                lines.append(f"{'  ' * (depth + 1)}{name}{suffix}")
                emitted += 1
        return "\n".join(lines)

    def _classify_path(self, relative: Path) -> tuple[str, str, list[str], str, str]:
        lowered = str(relative).replace("\\", "/").lower()
        name = relative.name.lower()
        if "adr" in lowered:
            return "decision", "adr", ["architecture", "decision"], "markdown", ""
        if "architecture" in lowered or "design" in lowered:
            return "architecture", "project-design", ["architecture"], "markdown", ""
        if name in _COLLECTABLE_CONFIGS or name.endswith((".toml", ".yaml", ".yml")):
            language = "json" if name.endswith(".json") else ""
            return "config", "project-config", ["configuration"], "json" if name.endswith(".json") else "text", language
        return "documentation", "project-doc", ["documentation"], "markdown", ""

    def collect(self, max_files: int = 80, max_tree_entries: int = 300) -> dict[str, Any]:
        candidates: list[Path] = []
        for root_file in ("README.md", "AGENTS.md", "pyproject.toml", "requirements.txt", "package.json", "tsconfig.json"):
            path = self.root / root_file
            if path.exists() and path.is_file():
                candidates.append(path)
        docs_root = self.root / "docs"
        if docs_root.exists():
            for path in sorted(docs_root.rglob("*.md")):
                if len(candidates) >= max_files:
                    break
                candidates.append(path)

        counts = {"added": 0, "updated": 0, "skipped": 0, "artifacts": []}
        tree_content = self._tree(max_tree_entries)
        tree_artifact, status = self.store.ingest(
            title=f"{self.root.name} folder structure",
            category="folder_structure",
            subcategory="project-tree",
            content=tree_content,
            tags=["project", "folder-tree"],
            source="project",
            source_uri="project://folder-tree",
            format_name="text",
            quality_score=0.8,
            reuse_score=0.7,
            details={"root": self.root.name, "generated": True},
        )
        counts[status] += 1
        counts["artifacts"].append(tree_artifact.id)

        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            content = self._read_text(path)
            if not content:
                counts["skipped"] += 1
                continue
            relative = path.relative_to(self.root)
            category, subcategory, tags, format_name, language = self._classify_path(relative)
            if relative.name.lower() == "readme.md":
                category, subcategory = "project", "overview"
                tags.append("overview")
            artifact, status = self.store.ingest(
                title=f"{self.root.name}: {relative.as_posix()}",
                category=category,
                subcategory=subcategory,
                content=content,
                tags=tags,
                language=language,
                source="project",
                source_uri=f"project://{relative.as_posix()}",
                format_name=format_name,
                quality_score=0.8,
                reuse_score=0.75,
                details={"project_path": relative.as_posix()},
            )
            counts[status] += 1
            counts["artifacts"].append(artifact.id)
        return counts


def discard_sandbox_path(path: Path, sandbox_root: Path) -> None:
    """Delete only a resolved child of the sandbox root; shared safety helper."""
    resolved_path = path.resolve()
    resolved_root = sandbox_root.resolve()
    if resolved_root not in resolved_path.parents:
        raise ValueError("refused to delete a path outside the sandbox root")
    shutil.rmtree(resolved_path)
