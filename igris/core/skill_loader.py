"""
igris.core.skill_loader
--------------------------
Loads skill files from .igris/skills/*.md using the same convention as
the existing Claude Code skill library this project pairs with:

    ---
    name: intent-resolver
    description: ...
    pipeline_stage: Planning
    triggers: [ambiguous, clarify, intent]
    defers_to: [clarification-guard]
    used_by: [reprompt-loop]
    ---
    ## Scope
    ...
    ## Procedure
    ...
    ## Anti-patterns
    ...

Routing is keyword-based (matches `triggers` + intent category against the
user's text) rather than an LLM call, so skill selection stays fast and
deterministic -- consistent with treating skills as a static, auditable
pipeline rather than something the model freely improvises.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    pipeline_stage: str
    triggers: list[str] = field(default_factory=list)
    defers_to: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    body: str = ""
    source_path: Path | None = None

    def procedure_block(self) -> str:
        """Extract just the ## Procedure section to keep injected context lean."""
        match = re.search(r"##\s*Procedure\s*\n(.*?)(\n##\s|\Z)", self.body, re.DOTALL)
        return match.group(1).strip() if match else self.body.strip()

    def to_prompt_block(self) -> str:
        return f"### Skill: {self.name} (stage: {self.pipeline_stage})\n{self.procedure_block()}"


def _parse_skill_file(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    fm_raw, body = match.groups()
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        return None

    return Skill(
        name=fm.get("name", path.stem),
        description=fm.get("description", ""),
        pipeline_stage=fm.get("pipeline_stage", "Unspecified"),
        triggers=fm.get("triggers", []) or [],
        defers_to=fm.get("defers_to", []) or [],
        used_by=fm.get("used_by", []) or [],
        body=body,
        source_path=path,
    )


class SkillLoader:
    def __init__(self, config):
        self.config = config
        self.skills_dir = config.path_for("skills.dir")
        self.max_active = config.get("skills.max_active_skills", 3)
        self._skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        self._skills = {}
        if not self.skills_dir.exists():
            return
        for path in sorted(self.skills_dir.glob("*.md")):
            skill = _parse_skill_file(path)
            if skill:
                self._skills[skill.name] = skill

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def select(self, intent, text: str) -> list[Skill]:
        """
        Keyword-match triggers against intent.category and the raw text,
        expand through `defers_to` one level (a skill that defers to another
        pulls it in too, mirroring the bidirectional pipeline links), then
        cap at max_active_skills.
        """
        lowered = text.lower()
        scored: list[tuple[int, Skill]] = []

        for skill in self._skills.values():
            score = 0
            if intent.category in skill.triggers:
                score += 2
            for trig in skill.triggers:
                if trig.lower() in lowered:
                    score += 1
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda t: t[0], reverse=True)
        selected = [s for _, s in scored[: self.max_active]]

        # pull in one level of defers_to dependencies not already selected
        names_selected = {s.name for s in selected}
        extra = []
        for skill in selected:
            for dep_name in skill.defers_to:
                if dep_name not in names_selected and dep_name in self._skills:
                    extra.append(self._skills[dep_name])
                    names_selected.add(dep_name)

        return selected + extra

    def prompt_block_for(self, skills: list[Skill]) -> str:
        if not skills:
            return "(no skills matched this task)"
        return "\n\n".join(s.to_prompt_block() for s in skills)
