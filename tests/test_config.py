"""
Tests for igris.config.Config.save_overrides -- persists settings changes
(provider, model, host, api_key, ...) to .igris/config.yaml on disk, which
is what the desktop Settings panel writes through to via
POST /api/settings.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import Config


def test_save_overrides_persists_to_disk(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()

    config.save_overrides({"gateway": {"provider": "lmstudio"}})

    on_disk = yaml.safe_load((tmp_path / ".igris" / "config.yaml").read_text(encoding="utf-8"))
    assert on_disk["gateway"]["provider"] == "lmstudio"


def test_save_overrides_updates_in_memory_immediately(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()

    config.save_overrides({"openrouter": {"model": "anthropic/claude-3.5-sonnet"}})

    assert config.get("openrouter.model") == "anthropic/claude-3.5-sonnet"


def test_save_overrides_does_not_clobber_unrelated_settings(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()

    config.save_overrides({"ollama": {"model": "qwen2.5-coder:7b"}})

    # unrelated keys within the same section (host, temperature, ...)
    # must survive the merge, not just the one key we changed.
    assert config.get("ollama.host") == "http://localhost:11434"
    assert config.get("ollama.model") == "qwen2.5-coder:7b"


def test_save_overrides_creates_scaffold_if_missing(tmp_path):
    config = Config.load(project_root=tmp_path)
    assert not config.igris_dir.exists()

    config.save_overrides({"gateway": {"provider": "openrouter"}})

    assert config.igris_dir.exists()
    assert config.get("gateway.provider") == "openrouter"


def test_save_overrides_persists_across_reload(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    config.save_overrides({
        "gateway": {"provider": "openrouter"},
        "openrouter": {"api_key": "sk-abc123", "model": "openrouter/auto"},
    })

    reloaded = Config.load(project_root=tmp_path)
    assert reloaded.get("gateway.provider") == "openrouter"
    assert reloaded.get("openrouter.api_key") == "sk-abc123"


def test_scaffold_merges_new_bundled_mcps_without_overwriting_custom_server(tmp_path):
    config = Config.load(project_root=tmp_path)
    config.ensure_project_scaffold()
    mcp_path = tmp_path / ".igris" / "mcp.json"
    original = json.loads(mcp_path.read_text(encoding="utf-8"))
    original["servers"] = {"custom": {"command": "custom-tool", "args": ["serve"]}}
    mcp_path.write_text(json.dumps(original), encoding="utf-8")

    config.ensure_project_scaffold()

    merged = json.loads(mcp_path.read_text(encoding="utf-8"))["servers"]
    assert merged["custom"]["command"] == "custom-tool"
    assert {"memory", "sandbox", "browser"}.issubset(merged)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
