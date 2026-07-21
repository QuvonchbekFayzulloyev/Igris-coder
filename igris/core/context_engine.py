"""
igris.core.context_engine
---------------------------
Stage 1 and Stage 5 of the mini-loop: gather *just enough* context, twice.

`snapshot()` is cheap and synchronous -- cwd, a shallow file listing, recent
turns from memory. It runs after the clarify gate and before the request is
dispatched to chat or task execution, so it stays deliberately light.

`gather()` runs after intent + skill routing and is allowed to use MCP
tools (git status, targeted file reads) to pull in whatever the resolved
intent actually needs, instead of stuffing the whole repo into the prompt.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContextSnapshot:
    cwd: str
    top_level_entries: list[str]
    recent_turns_summary: str

    def summary(self) -> str:
        return (
            f"cwd={self.cwd}\n"
            f"top_level=({', '.join(self.top_level_entries[:15])})\n"
            f"recent_turns={self.recent_turns_summary or '(none)'}"
        )

    def to_prompt_block(self) -> str:
        """Render the small, bounded context shared by chat and task prompts."""
        parts = [
            f"Working directory: {self.cwd}",
            f"Top-level workspace entries: {', '.join(self.top_level_entries[:15]) or '(none)'}",
        ]
        if self.recent_turns_summary:
            parts += ["Recent conversation:", self.recent_turns_summary]
        return "\n".join(parts)


@dataclass
class GatheredContext:
    pieces: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        return ", ".join(f"{k} ({len(v)} chars)" for k, v in self.pieces.items()) or "(nothing gathered)"

    def to_prompt_block(self) -> str:
        if not self.pieces:
            return "(no additional context gathered for this task)"
        blocks = []
        for name, content in self.pieces.items():
            blocks.append(f"### {name}\n{content.strip()}")
        return "\n\n".join(blocks)


class ContextEngine:
    def __init__(self, config, memory):
        self.config = config
        self.memory = memory
        self.root = config.project_root

    def snapshot(self) -> ContextSnapshot:
        try:
            entries = sorted(
                e.name + ("/" if e.is_dir() else "")
                for e in self.root.iterdir()
                if not e.name.startswith(".") or e.name == ".igris"
            )
        except OSError:
            entries = []

        recent = self.memory.recent_turns(limit=4)
        recent_summary = " | ".join(f"{t['role']}: {t['content'][:60]}" for t in recent)

        return ContextSnapshot(
            cwd=str(self.root),
            top_level_entries=entries,
            recent_turns_summary=recent_summary,
        )

    async def gather(self, intent, user_input: str, snapshot: ContextSnapshot, mcp_manager) -> GatheredContext:
        """Pull in intent-specific context. Bounded and cheap -- not a full repo dump."""
        gathered = GatheredContext()

        if mcp_manager is None:
            return gathered

        if intent.category in ("code_task", "bug_fix", "review"):
            try:
                status = await mcp_manager.call("git__git_status", {})
                if status and not status.startswith("ERROR"):
                    gathered.pieces["git_status"] = status
            except Exception:
                pass

            # consult the hierarchical project knowledge base (rules/
            # descriptions/templates) for this kind of task -- silently
            # skipped if the knowledge MCP server isn't registered or the
            # embedding model isn't reachable, since this is enrichment,
            # not a hard requirement for the loop to proceed.
            try:
                knowledge = await mcp_manager.call("knowledge__knowledge_search", {"query": user_input, "top_k": 4})
                if knowledge and not knowledge.startswith("ERROR") and not knowledge.startswith("(no knowledge"):
                    gathered.pieces["project_knowledge"] = knowledge
            except Exception:
                pass

        # Coder Memory is source-backed and survives across sessions. It is
        # intentionally queried separately from vector knowledge: metadata
        # retrieval still works when Ollama's embedding model is unavailable.
        if intent.category in ("code_task", "bug_fix", "review", "research", "command"):
            try:
                top_k = self.config.get("coder_memory.max_context_results", 5)
                memory = await mcp_manager.call("memory__memory_search", {"query": user_input, "top_k": top_k})
                if memory and not memory.startswith("ERROR") and not memory.startswith("(no Coder Memory"):
                    gathered.pieces["coder_memory"] = memory
            except Exception:
                pass

        if intent.mentioned_paths:
            for rel_path in intent.mentioned_paths[:5]:
                try:
                    content = await mcp_manager.call("filesystem__read_file", {"path": rel_path})
                    if content and not content.startswith("ERROR"):
                        gathered.pieces[f"file:{rel_path}"] = content[:8000]
                except Exception:
                    pass

        return gathered
