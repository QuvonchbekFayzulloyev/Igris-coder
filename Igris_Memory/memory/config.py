"""
CODER AGENT MEMORY — L3 Configuration (Sozlamalar)
14 tur config fayllar: user, agent, mcp, model, etc.

Storage: JSON files (static, doimiy)
Load: Session start
"""

import json
import os
from typing import Any, Optional


# Default config schemas
DEFAULT_USER_CONFIG = {
    "id": "user-config-001",
    "type": "config-user",
    "profile": {"name": "user", "role": "developer", "experience_years": 5},
    "settings": {"theme": "dark", "verbose_level": 2, "temperature": 0.2},
    "limits": {"max_files_per_session": 50, "max_tool_calls_per_task": 100},
}

DEFAULT_AGENT_CONFIG = {
    "id": "agent-config-001",
    "type": "config-agent",
    "identity": {"name": "Coder Agent", "version": "2.1.0"},
    "behavior": {
        "style": "step_by_step",
        "error_handling": "explicit",
        "communication": "concise",
    },
    "constraints": {
        "max_context_tokens": 4096,
        "max_memory_results": 5,
        "use_cache": True,
    },
}

DEFAULT_MCP_CONFIG = {
    "id": "mcp-config-001",
    "type": "config-mcp",
    "servers": {
        "filesystem": {
            "command": "node",
            "args": ["mcp-servers/filesystem.js"],
            "read_only": False,
        }
    },
    "tools": {
        "read": {"server": "filesystem", "timeout_ms": 5000},
        "write": {"server": "filesystem", "timeout_ms": 5000, "confirm": True},
        "bash": {
            "server": "filesystem",
            "timeout_ms": 30000,
            "deny_patterns": ["rm -rf", "sudo"],
        },
    },
}

DEFAULT_MODEL_CONFIG = {
    "id": "model-config-001",
    "type": "config-model",
    "providers": {
        "local-1.5b": {
            "type": "local",
            "model": "qwen2.5-1.5b-instruct",
            "parameters": {"temperature": 0.2, "max_tokens": 4096},
        },
    },
    "routing": {
        "strategy": "cost_based",
        "rules": [
            {"query_type": "simple", "model": "local-1.5b"},
            {"query_type": "complex", "model": "local-1.5b"},
        ],
    },
}

CONFIG_MAP = {
    "user": {"file": "user.json", "default": DEFAULT_USER_CONFIG},
    "agent": {"file": "agent.json", "default": DEFAULT_AGENT_CONFIG},
    "mcp": {"file": "mcp.json", "default": DEFAULT_MCP_CONFIG},
    "model": {"file": "model.json", "default": DEFAULT_MODEL_CONFIG},
}


class ConfigManager:
    """
    L3 Configuration Manager.
    
    Handles loading, saving, and accessing config files.
    All configs are JSON-based for simplicity.
    """

    def __init__(self, config_dir: str = "memory/config"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        """Load all config files, creating defaults if missing."""
        for name, meta in CONFIG_MAP.items():
            path = os.path.join(self.config_dir, meta["file"])
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self._cache[name] = json.load(f)
                except Exception:
                    self._cache[name] = meta["default"].copy()
            else:
                self._cache[name] = meta["default"].copy()
                self._save(name)

    def _save(self, name: str):
        """Save a config to disk."""
        if name not in CONFIG_MAP:
            return
        path = os.path.join(self.config_dir, CONFIG_MAP[name]["file"])
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._cache[name], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============================================================
    # PUBLIC API
    # ============================================================

    def get(self, name: str, key: str = "", default: Any = None) -> Any:
        """
        Get a config value.
        
        Args:
            name: Config name (user, agent, mcp, model)
            key: Optional dot-notation key (e.g. "profile.name")
            default: Default value if key not found
        
        Returns:
            Config value or default
        """
        config = self._cache.get(name, {})
        if not key:
            return config

        # Support dot-notation: "profile.name"
        parts = key.split(".")
        current = config
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, default)
            else:
                return default
        return current

    def set(self, name: str, key: str, value: Any):
        """
        Set a config value.
        
        Args:
            name: Config name (user, agent, mcp, model)
            key: Dot-notation key (e.g. "settings.temperature")
            value: New value
        """
        if name not in self._cache:
            self._cache[name] = {}

        config = self._cache[name]
        parts = key.split(".")
        for part in parts[:-1]:
            if part not in config or not isinstance(config[part], dict):
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value
        self._save(name)

    def update(self, name: str, updates: dict):
        """Merge updates into a config."""
        if name in self._cache:
            self._deep_merge(self._cache[name], updates)
            self._save(name)

    def _deep_merge(self, base: dict, updates: dict):
        """Deep merge updates into base dict."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get_all(self, name: str) -> dict:
        """Get entire config for a name."""
        return self._cache.get(name, {}).copy()

    def reset(self, name: str):
        """Reset a config to defaults."""
        if name in CONFIG_MAP:
            self._cache[name] = CONFIG_MAP[name]["default"].copy()
            self._save(name)

    def list_configs(self) -> list[str]:
        """List all available config names."""
        return list(CONFIG_MAP.keys())

    def get_agent_constraints(self) -> dict:
        """Get agent constraints for memory optimization."""
        agent = self._cache.get("agent", {})
        return agent.get("constraints", {
            "max_context_tokens": 4096,
            "max_memory_results": 5,
            "use_cache": True,
        })

    def get_model_config(self) -> dict:
        """Get current model configuration."""
        return self._cache.get("model", DEFAULT_MODEL_CONFIG)

    def to_context_string(self) -> str:
        """
        Serialize configs to a compact string for LLM context.
        1.5B optimization: minimal tokens.
        """
        parts = []
        agent = self._cache.get("agent", {})
        identity = agent.get("identity", {})
        if identity:
            parts.append(f"Agent: {identity.get('name', 'Agent')} v{identity.get('version', '1.0')}")

        constraints = agent.get("constraints", {})
        if constraints:
            parts.append(f"Context limit: {constraints.get('max_context_tokens', 4096)} tokens")

        user = self._cache.get("user", {})
        profile = user.get("profile", {})
        if profile:
            parts.append(f"User: {profile.get('role', 'developer')}")

        return " | ".join(parts)
