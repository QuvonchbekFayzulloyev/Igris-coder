"""
IGRIS BRAIN — Skills System
===========================
Agent qobiliyati yetmaydigan taskda ishlatadigan ko'nikmalar (SKILL.md).

Har bir skill — katalogdagi `SKILL.md` fayli:
    skills/<skill-name>/SKILL.md
        - YAML frontmatter: name, description
        - Body: bajarish ko'rsatmalari (LLM prompt'iga beriladi)
        - scripts/: yordamchi skriptlar (ixtiyoriy)

SkillManager: skill'larni topadi (bir necha root), ro'yxatlaydi va
matnini qaytaradi. Executor `use_skill` tool'i orqali ishlatadi.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_SKILL_ROOTS = [
    # modulning o'zi Igris_brain/skills/ — skill kataloglari shu yerda
    os.path.dirname(os.path.abspath(__file__)),
    # Igris_Interface/SKils — mavjud interfeys skill'lari
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Igris_Interface", "SKils")),
]


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: str
    scripts_dir: str = ""

    def full_text(self) -> str:
        """Skill'ning to'liq matni — LLM'ga beriladigan ko'rsatma."""
        parts = [f"# Skill: {self.name}", ""]
        if self.description:
            parts.append(f"**Description:** {self.description}")
            parts.append("")
        parts.append(self.body.strip())
        parts.append("")
        if self.scripts_dir:
            parts.append(
                f"**Helper scripts** in `{self.scripts_dir}` — run via `python <script> ...` "
                "with the workspace root as cwd."
            )
        return "\n".join(parts)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML frontmatter parser (name, description)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end]
    body = text[end + 4 :]
    meta: dict = {}
    current_key: Optional[str] = None
    for raw in fm.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            current_key = m.group(1)
            val = m.group(2).strip()
            # YAML block-scalar belgilarini (>, |, >-, |- va h.k.) olib tashlash
            if val in ("|>", ">", "|-", "|", ">-", "|+", ">+"):
                val = ""
            meta[current_key] = val
        elif current_key and (line.startswith("-") or not re.match(r"^[a-zA-Z_-]+:", line)):
            # ko'p qatorli qiymat (>- blok) — keyingi qatorlarni yig'amiz
            prev = meta.get(current_key, "")
            meta[current_key] = (prev + " " + line).strip()
    return meta, body


class SkillManager:
    """Bir necha root'dan skill'larni topadi va ularni LLM uchun tayyorlaydi."""

    def __init__(self, roots: Optional[list[str]] = None):
        self.roots = [os.path.abspath(r) for r in (roots or DEFAULT_SKILL_ROOTS)]
        self._skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        self._skills = {}
        for root in self.roots:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
                if "SKILL.md" not in filenames:
                    continue
                skill = self._load_skill(dirpath)
                if skill:
                    self._skills[skill.name] = skill

    def _load_skill(self, dirpath: str) -> Optional[Skill]:
        try:
            with open(os.path.join(dirpath, "SKILL.md"), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return None
        meta, body = _parse_frontmatter(text)
        name = (meta.get("name") or os.path.basename(dirpath)).strip()
        if not name:
            return None
        scripts = os.path.join(dirpath, "scripts")
        return Skill(
            name=name,
            description=meta.get("description", "").strip(),
            body=body.strip(),
            path=dirpath,
            scripts_dir=scripts if os.path.isdir(scripts) else "",
        )

    def list(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def names(self) -> list[str]:
        return [s.name for s in self.list()]

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def describe_all(self) -> str:
        """LLM'ga ko'rsatiladigan qisqa ro'yxat."""
        if not self._skills:
            return "(no skills installed)"
        lines = ["Available skills:"]
        for s in self.list():
            desc = (s.description or "").replace("\n", " ").strip()
            lines.append(f"- `{s.name}` — {desc[:220]}")
        return "\n".join(lines)


DEFAULT_MANAGER = SkillManager()

__all__ = ["Skill", "SkillManager", "DEFAULT_MANAGER", "DEFAULT_SKILL_ROOTS"]
