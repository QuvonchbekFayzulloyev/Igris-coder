"""
igris.config
------------
Loads and resolves configuration from a `.igris/` project folder, the same
role `.claude/` plays for Claude Code. Falls back to built-in defaults so
`igris` works out of the box with zero config.

Resolution order (highest priority first):
  1. CLI flags (passed in explicitly)
  2. Environment variables (IGRIS_*)
  3. .igris/config.yaml in the current project
  4. ~/.igris/config.yaml (user-global)
  5. Built-in defaults below
"""
from __future__ import annotations

import os
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "gateway": {
        # which provider build_llm() instantiates: ollama | lmstudio | openrouter
        "provider": "ollama",
    },
    "ollama": {
        "host": "http://localhost:11434",
        "model": "qwen3",  # native tool-calling support, established local default
        "keep_alive": "10m",
        "temperature": 0.4,
        "timeout_seconds": 120,
        # recovers tool calls from models (e.g. qwen2.5-coder) that print
        # {"name":..., "arguments":...} as plain text instead of using
        # Ollama's real tool_calls field. Not needed with qwen3.
        "enable_json_tool_call_fallback": True,
    },
    "lmstudio": {
        "host": "http://localhost:1234/v1",  # LM Studio's local server, OpenAI-compatible
        "model": "local-model",  # whatever LM Studio has loaded
        "temperature": 0.4,
        "timeout_seconds": 120,
        "enable_json_tool_call_fallback": True,
    },
    "openrouter": {
        "host": "https://openrouter.ai/api/v1",
        "model": "openrouter/auto",
        "api_key": "",  # prefer OPENROUTER_API_KEY env var over storing it here
        "temperature": 0.4,
        "timeout_seconds": 120,
        "enable_json_tool_call_fallback": True,
        # cost estimation is opt-in and honest: 0.0 means "not configured",
        # not "free" -- OpenRouter pricing varies by model and changes
        # over time, so igris never guesses it. Set these to your chosen
        # model's published per-1k-token rates if you want cost shown.
        "price_per_1k_prompt_tokens": 0.0,
        "price_per_1k_completion_tokens": 0.0,
    },
    "loop": {
        # bounded mini-loop controls -- see core/reprompt_loop.py
        "max_review_iterations": 2,
        # below this, igris still asks (genuinely too ambiguous to guess)
        "clarify_confidence_threshold": 0.55,
        # below clarify_confidence_threshold but AT OR ABOVE this, igris
        # proceeds on a stated assumption instead of asking -- see the
        # autonomous-verification-loop skill. Below this floor it's a hard
        # block: too uncertain to guess safely even with a stated caveat.
        "hard_block_confidence_threshold": 0.35,
        "max_tool_iterations": 12,
        "enable_self_review": True,
        "trace": False,  # if True, prints every loop stage (debugging)
    },
    "skills": {
        "dir": ".igris/skills",
        "max_active_skills": 3,
    },
    "mcp": {
        "config_file": ".igris/mcp.json",
    },
    "memory": {
        "dir": ".igris/memory",
        "session_log": "session.jsonl",
        "checkpoints_file": "checkpoints.json",
    },
    "knowledge": {
        "dir": ".igris/knowledge",
    },
    "coder_memory": {
        "dir": ".igris/coder_memory",
        "max_context_results": 5,
    },
    "embeddings": {
        "host": "",  # empty = reuse ollama.host
        "model": "nomic-embed-text",  # ~274MB, ~137M params, well under 8GB VRAM, CPU-friendly
        "keep_alive": "10m",
        # Retrieval is enrichment, not a reason to block an agent turn for a
        # minute when the local embedding server is unavailable.
        "timeout_seconds": 10,
    },
    "platform": {
        # Windows-first, never-WSL-by-default philosophy is a first-class
        # config value, not a hardcoded assumption -- see skills/windows-first-guard.md
        "prefer_native_windows": True,
        "shell": "powershell",  # powershell | cmd | bash
    },
    "research": {
        "enabled": True,
        "max_queries_per_area": 25,
        "max_repos": 50,
        "min_confidence": 0.4,
    },
}

PROJECT_DIR_NAME = ".igris"


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _env_overrides() -> dict:
    """Map IGRIS_* environment variables onto the config tree."""
    overrides: dict[str, Any] = {}
    mapping = {
        "IGRIS_OLLAMA_HOST": ("ollama", "host"),
        "IGRIS_OLLAMA_MODEL": ("ollama", "model"),
        "IGRIS_SHELL": ("platform", "shell"),
    }
    for env_key, (section, key) in mapping.items():
        val = os.environ.get(env_key)
        if val is not None:
            overrides.setdefault(section, {})[key] = val
    return overrides


@dataclass
class Config:
    data: dict = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    project_root: Path = field(default_factory=Path.cwd)

    @property
    def igris_dir(self) -> Path:
        return self.project_root / PROJECT_DIR_NAME

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def path_for(self, dotted_key_of_relative_path: str) -> Path:
        """Resolve a config value that stores a path relative to project_root."""
        rel = self.get(dotted_key_of_relative_path)
        return self.project_root / rel

    @classmethod
    def load(cls, project_root: str | Path | None = None) -> "Config":
        root = Path(project_root) if project_root else Path.cwd()
        merged = copy.deepcopy(DEFAULTS)

        user_global = _load_yaml(Path.home() / PROJECT_DIR_NAME / "config.yaml")
        merged = _deep_merge(merged, user_global)

        project_cfg = _load_yaml(root / PROJECT_DIR_NAME / "config.yaml")
        merged = _deep_merge(merged, project_cfg)

        merged = _deep_merge(merged, _env_overrides())

        return cls(data=merged, project_root=root)

    def ensure_project_scaffold(self) -> list[str]:
        """Create .igris/ with defaults if missing. Returns list of created paths."""
        created = []
        templates_dir = Path(__file__).parent / "templates"
        skills_src = Path(__file__).parent / "skills"

        igris_dir = self.igris_dir
        for sub in ("skills", "memory"):
            p = igris_dir / sub
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
                created.append(str(p))

        cfg_path = igris_dir / "config.yaml"
        if not cfg_path.exists():
            cfg_path.write_text((templates_dir / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            created.append(str(cfg_path))

        mcp_path = igris_dir / "mcp.json"
        if not mcp_path.exists():
            mcp_path.write_text((templates_dir / "mcp.json").read_text(encoding="utf-8"), encoding="utf-8")
            created.append(str(mcp_path))
        else:
            # Add new built-in MCP servers without touching a user's existing
            # server settings or custom integrations. This lets established
            # projects receive safe memory/sandbox/browser capabilities too.
            try:
                current_mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
                template_mcp = json.loads((templates_dir / "mcp.json").read_text(encoding="utf-8"))
                current_servers = current_mcp.setdefault("servers", {})
                template_servers = template_mcp.get("servers", {})
                missing = {
                    name: spec for name, spec in template_servers.items()
                    if name not in current_servers
                }
                if missing:
                    current_servers.update(missing)
                    mcp_path.write_text(json.dumps(current_mcp, indent=2, ensure_ascii=False), encoding="utf-8")
            except (OSError, json.JSONDecodeError, AttributeError):
                # A hand-maintained but malformed mcp.json must not be
                # overwritten automatically; MCPManager will report its own
                # actionable configuration error when the project runs.
                pass

        for skill_file in skills_src.glob("*.md"):
            dest = igris_dir / "skills" / skill_file.name
            if not dest.exists():
                dest.write_text(skill_file.read_text(encoding="utf-8"), encoding="utf-8")
                created.append(str(dest))

        return created

    def save_overrides(self, updates: dict) -> None:
        """
        Deep-merge `updates` into .igris/config.yaml on disk (creating it
        from defaults first if missing) and into self.data, so the change
        is both persisted and immediately visible to the running process.
        This is what the desktop Settings panel writes through to --
        provider/model/host/api_key edits survive a restart.
        """
        if not self.igris_dir.exists():
            self.ensure_project_scaffold()

        cfg_path = self.igris_dir / "config.yaml"
        on_disk = _load_yaml(cfg_path)
        merged_on_disk = _deep_merge(on_disk, updates)
        cfg_path.write_text(
            yaml.safe_dump(merged_on_disk, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        self.data = _deep_merge(self.data, updates)
