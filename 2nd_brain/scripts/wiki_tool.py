#!/usr/bin/env python3
"""IGRIS 2nd Brain Wiki Tool — Deterministic CLI (Python stdlib only).

Commands:
  doctor          Health check
  build           Generate catalog.jsonl, index.md
  lint            Validate frontmatter and links
  source-scan     List Raw sources, update manifest
  source-lint     Validate source frontmatter
  source-delta    Show uncovered sources
  source-coverage Coverage report
  search-catalog  Full-text search
  log             Append to Wiki/log.md
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class WikiTool:
    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.raw_dir = self.root / "Raw" / "Sources"
        self.wiki_dir = self.root / "Wiki"
        self.schema_dir = self.root / "Schema"
        self.catalog_path = self.wiki_dir / "catalog.jsonl"
        self.manifest_path = self.schema_dir / "source-manifest.jsonl"
        self.index_path = self.wiki_dir / "index.md"
        self.log_path = self.wiki_dir / "Logs" / "log.md"

    def doctor(self) -> bool:
        print("=== Wiki Doctor ===")
        ok = True
        checks = [
            ("Raw/Sources", self.raw_dir.exists()),
            ("Wiki", self.wiki_dir.exists()),
            ("Schema", self.schema_dir.exists()),
            ("Wiki/Topics", (self.wiki_dir / "Topics").exists()),
            ("Wiki/Concepts", (self.wiki_dir / "Concepts").exists()),
            ("Wiki/Entities", (self.wiki_dir / "Entities").exists()),
            ("Wiki/Projects", (self.wiki_dir / "Projects").exists()),
            ("Wiki/Logs", (self.wiki_dir / "Logs").exists()),
        ]
        for name, exists in checks:
            status = "OK" if exists else "MISSING"
            if not exists:
                ok = False
            print(f"  [{status}] {name}")

        # Check Python version
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(f"  [OK] Python {py_ver}")

        # Check catalog
        if self.catalog_path.exists():
            count = sum(1 for _ in open(self.catalog_path, encoding="utf-8"))
            print(f"  [OK] catalog.jsonl ({count} entries)")
        else:
            print("  [WARN] catalog.jsonl not found (run 'build')")

        # Check manifest
        if self.manifest_path.exists():
            count = sum(1 for _ in open(self.manifest_path, encoding="utf-8"))
            print(f"  [OK] source-manifest.jsonl ({count} entries)")
        else:
            print("  [WARN] source-manifest.jsonl not found (run 'source-scan')")

        print(f"\nResult: {'HEALTHY' if ok else 'ISSUES FOUND'}")
        return ok

    def build(self):
        print("=== Building Wiki ===")
        entries = []
        for md_path in self.wiki_dir.rglob("*.md"):
            if md_path.name == "index.md":
                continue
            rel = md_path.relative_to(self.wiki_dir)
            content = md_path.read_text(encoding="utf-8")
            title = self._extract_frontmatter_field(content, "Title") or md_path.stem
            tags = self._extract_frontmatter_list(content, "tags")
            entry = {
                "path": str(rel),
                "title": title,
                "tags": tags,
                "size": len(content),
                "modified": datetime.fromtimestamp(md_path.stat().st_mtime).isoformat(),
            }
            entries.append(entry)

        # Write catalog
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"  catalog.jsonl: {len(entries)} entries")

        # Write index
        lines = ["# IGRIS 2nd Brain Wiki Index\n"]
        lines.append(f"Generated: {datetime.now().isoformat()}\n")
        lines.append(f"Total notes: {len(entries)}\n\n")
        by_tag = {}
        for e in entries:
            for tag in e["tags"]:
                by_tag.setdefault(tag, []).append(e)
        for tag, items in sorted(by_tag.items()):
            lines.append(f"## {tag}\n")
            for item in items:
                lines.append(f"- [[{item['title']}]] ({item['path']})")
            lines.append("")

        self.index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  index.md: {len(lines)} lines")
        print("Build complete.")

    def lint(self) -> bool:
        print("=== Linting Wiki ===")
        errors = 0
        warnings = 0

        for md_path in self.wiki_dir.rglob("*.md"):
            if md_path.name == "index.md":
                continue
            content = md_path.read_text(encoding="utf-8")
            rel = str(md_path.relative_to(self.root))

            # Check frontmatter
            if not content.startswith("---"):
                print(f"  [ERROR] {rel}: missing frontmatter")
                errors += 1
                continue

            # Check required fields
            for field in ["Title", "Created"]:
                if not self._extract_frontmatter_field(content, field):
                    print(f"  [ERROR] {rel}: missing '{field}'")
                    errors += 1
            if not self._extract_frontmatter_list(content, "tags"):
                print(f"  [ERROR] {rel}: missing 'tags'")
                errors += 1

            # Check wiki-links
            links = re.findall(r"\[\[([^\]]+)\]\]", content)
            for link in links:
                link_name = link.split("|")[0]
                if not self._wiki_link_exists(link_name):
                    print(f"  [WARN] {rel}: broken link [[{link_name}]]")
                    warnings += 1

        print(f"\nResult: {errors} errors, {warnings} warnings")
        return errors == 0

    def source_scan(self, update: bool = False):
        print("=== Scanning Raw Sources ===")
        sources = []
        for md_path in self.raw_dir.rglob("*.md"):
            rel = str(md_path.relative_to(self.root))
            content = md_path.read_text(encoding="utf-8")
            title = self._extract_frontmatter_field(content, "Title") or md_path.stem
            processed = self._extract_frontmatter_field(content, "Processed") == "true"
            sources.append({
                "source": rel,
                "title": title,
                "processed": processed,
            })

        print(f"  Found {len(sources)} sources")
        for s in sources:
            status = "PROCESSED" if s["processed"] else "UNPROCESSED"
            print(f"  [{status}] {s['source']} — {s['title']}")

        if update:
            manifest = []
            for s in sources:
                manifest.append({
                    "source": s["source"],
                    "status": "covered" if s["processed"] else "uncovered",
                    "notes": [],
                    "last_checked": datetime.now().strftime("%Y-%m-%d"),
                })
            self.schema_dir.mkdir(parents=True, exist_ok=True)
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                for m in manifest:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
            print(f"  Manifest updated: {len(manifest)} entries")

    def source_lint(self) -> bool:
        print("=== Linting Sources ===")
        errors = 0
        for md_path in self.raw_dir.rglob("*.md"):
            content = md_path.read_text(encoding="utf-8")
            rel = str(md_path.relative_to(self.root))

            if not content.startswith("---"):
                print(f"  [ERROR] {rel}: missing frontmatter")
                errors += 1
                continue

            for field in ["Title", "Author", "Created", "tags"]:
                if not self._extract_frontmatter_field(content, field):
                    print(f"  [ERROR] {rel}: missing '{field}'")
                    errors += 1

        print(f"\nResult: {errors} errors")
        return errors == 0

    def source_delta(self):
        print("=== Uncovered Sources ===")
        if not self.manifest_path.exists():
            print("  No manifest found. Run 'source-scan --update' first.")
            return

        manifest = self._read_jsonl(self.manifest_path)
        uncovered = [m for m in manifest if m.get("status") == "uncovered"]
        print(f"  {len(uncovered)} uncovered sources")
        for m in uncovered:
            print(f"  - {m['source']}")

    def source_coverage(self):
        print("=== Source Coverage ===")
        if not self.manifest_path.exists():
            print("  No manifest found.")
            return

        manifest = self._read_jsonl(self.manifest_path)
        total = len(manifest)
        covered = sum(1 for m in manifest if m.get("status") == "covered")
        pct = (covered / total * 100) if total else 0
        print(f"  Total: {total}")
        print(f"  Covered: {covered}")
        print(f"  Coverage: {pct:.1f}%")

    def search_catalog(self, query: str):
        print(f"=== Search: '{query}' ===")
        if not self.catalog_path.exists():
            print("  No catalog found. Run 'build' first.")
            return

        results = []
        for entry in self._read_jsonl(self.catalog_path):
            score = 0
            query_lower = query.lower()
            if query_lower in entry.get("title", "").lower():
                score += 10
            for tag in entry.get("tags", []):
                if query_lower in tag.lower():
                    score += 5
            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: -x[0])
        print(f"  Found {len(results)} matches")
        for score, entry in results[:10]:
            print(f"  [{score}] {entry['title']} ({entry['path']})")

    def log(self, title: str, details: str):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = f"\n## {title}\n\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{details}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"  Logged: {title}")

    def _extract_frontmatter_field(self, content: str, field: str) -> Optional[str]:
        match = re.search(rf"^{field}:\s*\"?([^\"]+)\"?\s*$", content, re.MULTILINE)
        if match:
            return match.group(1).strip('"')
        return None

    def _extract_frontmatter_list(self, content: str, field: str) -> List[str]:
        match = re.search(rf"^{field}:\s*\[(.*?)\]", content, re.MULTILINE)
        if match:
            items = match.group(1)
            return [s.strip().strip('"') for s in items.split(",") if s.strip()]
        return []

    def _wiki_link_exists(self, name: str) -> bool:
        for md_path in self.wiki_dir.rglob("*.md"):
            if md_path.stem == name:
                return True
        return False

    def _read_jsonl(self, path: Path) -> List[dict]:
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries


def main():
    parser = argparse.ArgumentParser(description="IGRIS 2nd Brain Wiki Tool")
    parser.add_argument("command", choices=[
        "doctor", "build", "lint", "source-scan", "source-lint",
        "source-delta", "source-coverage", "search-catalog", "log"
    ])
    parser.add_argument("--root", default=".", help="Wiki root directory")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--title", help="Log title")
    parser.add_argument("--details", help="Log details")
    parser.add_argument("--update", action="store_true", help="Update manifest")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    tool = WikiTool(args.root)

    commands = {
        "doctor": lambda: tool.doctor(),
        "build": lambda: tool.build(),
        "lint": lambda: tool.lint(),
        "source-scan": lambda: tool.source_scan(args.update),
        "source-lint": lambda: tool.source_lint(),
        "source-delta": lambda: tool.source_delta(),
        "source-coverage": lambda: tool.source_coverage(),
        "search-catalog": lambda: tool.search_catalog(args.query or ""),
        "log": lambda: tool.log(args.title or "Untitled", args.details or ""),
    }

    result = commands[args.command]()
    if result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
