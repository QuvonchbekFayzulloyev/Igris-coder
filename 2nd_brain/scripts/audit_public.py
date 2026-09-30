#!/usr/bin/env python3
"""IGRIS 2nd Brain Public Audit — validate Wiki for external sharing."""

import json
import re
import sys
from pathlib import Path
from typing import List


def audit(root: str = ".") -> bool:
    wiki_dir = Path(root) / "Wiki"
    errors = 0
    warnings = 0

    print("=== Public Audit ===")

    # Check all Wiki notes
    for md_path in wiki_dir.rglob("*.md"):
        if md_path.name == "index.md":
            continue
        content = md_path.read_text(encoding="utf-8")
        rel = str(md_path.relative_to(Path(root)))

        # Check for internal-only content
        internal_patterns = [
            (r"(?i)password|secret|api.?key|token", "contains sensitive data"),
            (r"(?i)localhost|127\.0\.0\.1", "contains localhost reference"),
            (r"(?i)TODO|FIXME|HACK", "contains unfinished item"),
        ]
        for pattern, msg in internal_patterns:
            if re.search(pattern, content):
                print(f"  [WARN] {rel}: {msg}")
                warnings += 1

        # Check frontmatter
        if not content.startswith("---"):
            print(f"  [ERROR] {rel}: missing frontmatter")
            errors += 1

    # Check catalog
    catalog_path = wiki_dir / "catalog.jsonl"
    if catalog_path.exists():
        entries = []
        with open(catalog_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        print(f"  Catalog: {len(entries)} entries")
    else:
        print("  [WARN] No catalog.jsonl found")
        warnings += 1

    print(f"\nResult: {errors} errors, {warnings} warnings")
    return errors == 0


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    ok = audit(root)
    sys.exit(0 if ok else 1)
