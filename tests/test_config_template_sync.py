"""
Regression guard: config.py's DEFAULTS dict and templates/config.yaml
(what actually gets written into a new project's .igris/config.yaml)
must expose exactly the same set of keys. If someone adds a new config
option to one and forgets the other, a new project either silently
lacks a documented, editable setting, or Config.load() silently falls
back to a default the user can't see or override in their own file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.config import DEFAULTS


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    keys = set()
    for k, v in d.items():
        full = f"{prefix}{k}"
        if isinstance(v, dict):
            keys |= _flatten_keys(v, full + ".")
        else:
            keys.add(full)
    return keys


def test_defaults_and_template_expose_the_same_keys():
    defaults_keys = _flatten_keys(DEFAULTS)
    template_path = Path(__file__).parent.parent / "igris" / "templates" / "config.yaml"
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    template_keys = _flatten_keys(template)

    missing_from_template = defaults_keys - template_keys
    missing_from_defaults = template_keys - defaults_keys

    assert not missing_from_template, f"in DEFAULTS but not templates/config.yaml: {sorted(missing_from_template)}"
    assert not missing_from_defaults, f"in templates/config.yaml but not DEFAULTS: {sorted(missing_from_defaults)}"
