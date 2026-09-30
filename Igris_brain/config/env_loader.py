"""
IGRIS BRAIN — Environment Variable Loader
==========================================
Centralized .env file loader for all MCP servers and components.

Usage:
    from env_loader import load_env, get_env

    # Load .env file
    load_env()

    # Get environment variable with default
    database_url = get_env("DATABASE_URL", "postgresql://localhost:5432/igris")

Features:
    - Loads .env file from project root
    - Supports comments and empty lines
    - Preserves existing environment variables
    - Handles quoted values
    - Type conversion helpers
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


# Project root (Igris_brain directory)
_PROJECT_ROOT = Path(__file__).parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def load_env(env_file: Optional[str] = None, override: bool = False) -> dict:
    """Load environment variables from .env file.

    Args:
        env_file: Path to .env file (default: .env in project root)
        override: If True, override existing env vars (default: False)

    Returns:
        Dictionary of loaded variables
    """
    file_path = Path(env_file) if env_file else _ENV_FILE

    if not file_path.exists():
        return {}

    loaded = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Remove quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            # Skip if already set (unless override)
            if not override and os.environ.get(key):
                continue

            os.environ[key] = value
            loaded[key] = value

    return loaded


def get_env(key: str, default: Any = None, cast: type = None) -> Any:
    """Get environment variable with type conversion.

    Args:
        key: Environment variable name
        default: Default value if not set
        cast: Type to cast to (int, float, bool, str)

    Returns:
        Environment variable value or default
    """
    value = os.environ.get(key)

    if value is None:
        return default

    if cast is None:
        return value

    try:
        if cast is bool:
            return value.lower() in ("true", "1", "yes", "on")
        return cast(value)
    except (ValueError, TypeError):
        return default


def get_database_url() -> str:
    """Get database URL (PostgreSQL/MySQL)."""
    return get_env("DATABASE_URL", "postgresql://localhost:5432/igris")


def get_mongodb_url() -> str:
    """Get MongoDB URL."""
    return get_env("MONGODB_URL", "mongodb://localhost:27017/igris")


def get_redis_url() -> str:
    """Get Redis URL."""
    return get_env("REDIS_URL", "redis://localhost:6379/0")


def get_github_token() -> str:
    """Get GitHub token."""
    return get_env("GITHUB_TOKEN", "")


def get_ws_secret() -> str:
    """Get WebSocket secret."""
    return get_env("WS_SECRET", "")


def get_llm_config() -> dict:
    """Get LLM configuration."""
    return {
        "model": get_env("IGRIS_MODEL", "qwen3:8b"),
        "base_url": get_env("IGRIS_LLM_URL", "http://localhost:11434"),
        "temperature": get_env("IGRIS_TEMPERATURE", 0.2, float),
        "max_tokens": get_env("IGRIS_MAX_TOKENS", 8192, int),
    }


def get_memory_config() -> dict:
    """Get memory configuration."""
    return {
        "enabled": get_env("IGRIS_MEMORY_ENABLED", True, bool),
        "path": get_env("IGRIS_MEMORY_PATH", "../Igris_Memory/brain_data"),
    }


def get_chrome_config() -> dict:
    """Get Chrome/browser configuration."""
    return {
        "headless": get_env("WAB_HEADLESS", False, bool),
        "channel": get_env("WAB_BROWSER_CHANNEL", "chrome"),
        "cdp_enabled": get_env("WAB_CDP_ENABLED", True, bool),
        "cdp_url": get_env("WAB_CDP_URL", "http://127.0.0.1:9222"),
        "cdp_port": get_env("WAB_CDP_PORT", 9222, int),
        "user_data": get_env("WAB_CHROME_USER_DATA", ""),
        "profile": get_env("WAB_CHROME_PROFILE", "Profile 1"),
    }


# Auto-load on import
load_env()


__all__ = [
    "load_env",
    "get_env",
    "get_database_url",
    "get_mongodb_url",
    "get_redis_url",
    "get_github_token",
    "get_ws_secret",
    "get_llm_config",
    "get_memory_config",
    "get_chrome_config",
]
