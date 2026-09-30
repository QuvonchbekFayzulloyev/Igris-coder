"""
IGRIS BRAIN — Changelog Generator
==================================
Generates changelogs from git commit messages.

Features:
    - Parse conventional commits (feat:, fix:, docs:, etc.)
    - Categorize changes automatically
    - Generate markdown changelog
    - Link to GitHub issues/PRs
    - Support multiple formats (markdown, JSON, text)
    - Filter by date range or version

Usage:
    from changelog_generator import generate_changelog, get_commits_since
    
    # Generate changelog
    changelog = generate_changelog()
    
    # Get commits since last release
    commits = get_commits_since("v1.1.0")

Conventional Commits Format:
    feat: add new feature
    fix: bug fix
    docs: documentation update
    style: code style changes
    refactor: code refactoring
    test: add tests
    chore: maintenance tasks
    perf: performance improvements
    ci: CI/CD changes
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
RELEASES_DIR = PROJECT_ROOT / "releases"


# ---------------------------------------------------------------- #
# Commit Categories
# ---------------------------------------------------------------- #

CATEGORIES = {
    "feat": {
        "title": "🚀 Features",
        "description": "New features and capabilities",
        "emoji": "✨",
    },
    "fix": {
        "title": "🐛 Bug Fixes",
        "description": "Bug fixes and corrections",
        "emoji": "🐛",
    },
    "docs": {
        "title": "📚 Documentation",
        "description": "Documentation changes",
        "emoji": "📝",
    },
    "style": {
        "title": "💄 Style",
        "description": "Code style changes (formatting, missing semi-colons, etc)",
        "emoji": "💄",
    },
    "refactor": {
        "title": "♻️ Refactoring",
        "description": "Code refactoring without functional changes",
        "emoji": "♻️",
    },
    "perf": {
        "title": "⚡ Performance",
        "description": "Performance improvements",
        "emoji": "⚡",
    },
    "test": {
        "title": "✅ Tests",
        "description": "Adding or updating tests",
        "emoji": "✅",
    },
    "chore": {
        "title": "🔧 Maintenance",
        "description": "Maintenance tasks and dependencies",
        "emoji": "🔧",
    },
    "ci": {
        "title": "👷 CI/CD",
        "description": "Continuous integration and deployment",
        "emoji": "👷",
    },
    "build": {
        "title": "📦 Build",
        "description": "Build system changes",
        "emoji": "📦",
    },
    "other": {
        "title": "📝 Other Changes",
        "description": "Other changes",
        "emoji": "📝",
    },
}

# Breaking change indicators
BREAKING_KEYWORDS = ["BREAKING CHANGE", "breaking:", "!:", "major:"]

# Issue/PR link patterns
ISSUE_PATTERN = re.compile(r"#(\d+)")


# ---------------------------------------------------------------- #
# Git Operations
# ---------------------------------------------------------------- #

def _run_git(args: list, cwd: str = None) -> tuple[bool, str]:
    """Git buyrug'ini bajarish."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def get_commits(since: str = None, until: str = None, author: str = None) -> list:
    """Git commit'larni olish.
    
    Args:
        since: Start reference (tag, commit, date)
        until: End reference (tag, commit, date)
        author: Filter by author
        
    Returns:
        List of commit dicts
    """
    args = ["log", "--pretty=format:%H|%s|%an|%ae|%ai|%b", "--no-merges"]
    
    if since:
        args.append(f"{since}..HEAD" if since else "")
    if until:
        args.append(f"HEAD..{until}")
    if author:
        args.extend(["--author", author])
    
    # Remove empty strings
    args = [a for a in args if a]
    
    ok, output = _run_git(args)
    if not ok or not output:
        return []
    
    commits = []
    for line in output.split("\n"):
        if not line.strip():
            continue
        
        parts = line.split("|", 5)
        if len(parts) < 5:
            continue
        
        commit_hash = parts[0]
        subject = parts[1]
        author_name = parts[2]
        author_email = parts[3]
        date_str = parts[4]
        body = parts[5] if len(parts) > 5 else ""
        
        # Parse commit
        parsed = parse_commit(subject, body)
        parsed["hash"] = commit_hash[:8]
        parsed["full_hash"] = commit_hash
        parsed["author"] = author_name
        parsed["email"] = author_email
        parsed["date"] = date_str[:10] if date_str else ""
        parsed["subject"] = subject
        parsed["body"] = body.strip()
        
        commits.append(parsed)
    
    return commits


def get_tags() -> list:
    """Git teglarini olish."""
    ok, output = _run_git(["tag", "--sort=-v:refname"])
    if not ok:
        return []
    return [t.strip() for t in output.split("\n") if t.strip()]


def get_latest_tag() -> Optional[str]:
    """Eng so'nggi tegni olish."""
    tags = get_tags()
    return tags[0] if tags else None


def get_commits_since(tag: str = None) -> list:
    """Tegdan keyingi commit'larni olish."""
    if not tag:
        tag = get_latest_tag()
    
    if tag:
        return get_commits(since=tag)
    else:
        # No tags, get all commits
        return get_commits()


# ---------------------------------------------------------------- #
# Commit Parsing
# ---------------------------------------------------------------- #

def parse_commit(subject: str, body: str = "") -> dict:
    """Commit xabarini parse qilish (conventional commits).
    
    Formats:
        feat: add login feature
        feat(scope): add login feature
        fix!: fix breaking change
        feat: add feature (#123)
    """
    result = {
        "type": "other",
        "scope": None,
        "description": subject,
        "is_breaking": False,
        "issues": [],
        "pull_requests": [],
    }
    
    # Check for breaking changes
    for keyword in BREAKING_KEYWORDS:
        if keyword.lower() in subject.lower() or keyword.lower() in body.lower():
            result["is_breaking"] = True
            break
    
    # Parse conventional commit format
    # Pattern: type(scope)!: description
    match = re.match(
        r"^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$",
        subject,
        re.IGNORECASE,
    )
    
    if match:
        commit_type = match.group(1).lower()
        scope = match.group(2)
        breaking = match.group(3)
        description = match.group(4)
        
        if commit_type in CATEGORIES:
            result["type"] = commit_type
        else:
            result["type"] = "other"
        
        result["scope"] = scope
        result["description"] = description
        result["is_breaking"] = bool(breaking)
    
    # Extract issue references
    all_text = f"{subject} {body}"
    issues = ISSUE_PATTERN.findall(all_text)
    result["issues"] = [int(i) for i in issues]
    
    # Extract PR references
    pr_pattern = re.compile(r"(?:pull request|pr)[#\s]+(\d+)", re.IGNORECASE)
    prs = pr_pattern.findall(all_text)
    result["pull_requests"] = [int(p) for p in prs]
    
    return result


# ---------------------------------------------------------------- #
# Changelog Generation
# ---------------------------------------------------------------- #

def generate_changelog(
    commits: list = None,
    version: str = None,
    start_date: str = None,
    end_date: str = None,
    include_links: bool = True,
    github_repo: str = None,
) -> str:
    """Changelog yaratish.
    
    Args:
        commits: List of commits (default: since latest tag)
        version: Version number for header
        start_date: Filter commits after this date
        end_date: Filter commits before this date
        include_links: Include GitHub links
        github_repo: GitHub repo for links (owner/repo)
        
    Returns:
        Markdown changelog
    """
    # Get commits if not provided
    if commits is None:
        commits = get_commits_since()
    
    # Filter by date
    if start_date:
        commits = [c for c in commits if c.get("date", "") >= start_date]
    if end_date:
        commits = [c for c in commits if c.get("date", "") <= end_date]
    
    if not commits:
        return "No changes to report."
    
    # Group by type
    grouped = {}
    for commit in commits:
        commit_type = commit.get("type", "other")
        if commit_type not in grouped:
            grouped[commit_type] = []
        grouped[commit_type].append(commit)
    
    # Generate markdown
    lines = []
    
    # Header
    if version:
        lines.append(f"## [{version}]")
    else:
        lines.append(f"## [{datetime.now().strftime('%Y-%m-%d')}]")
    
    # Date range
    dates = [c.get("date") for c in commits if c.get("date")]
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        if min_date == max_date:
            lines.append(f"*Released on {min_date}*")
        else:
            lines.append(f"*Changes from {min_date} to {max_date}*")
    
    lines.append("")
    
    # Breaking changes first
    breaking = [c for c in commits if c.get("is_breaking")]
    if breaking:
        lines.append("### ⚠️ BREAKING CHANGES")
        lines.append("")
        for commit in breaking:
            desc = commit.get("description", "")
            scope = commit.get("scope")
            hash_str = commit.get("hash", "")
            
            scope_text = f"**{scope}:** " if scope else ""
            lines.append(f"- {scope_text}{desc} ({hash_str})")
        lines.append("")
    
    # Categories in order
    category_order = [
        "feat", "fix", "perf", "refactor", "docs", 
        "test", "style", "ci", "build", "chore", "other"
    ]
    
    for commit_type in category_order:
        if commit_type not in grouped:
            continue
        
        category = CATEGORIES.get(commit_type, CATEGORIES["other"])
        commits_list = grouped[commit_type]
        
        lines.append(f"### {category['title']}")
        lines.append("")
        
        for commit in commits_list:
            desc = commit.get("description", "")
            scope = commit.get("scope")
            hash_str = commit.get("hash", "")
            issues = commit.get("issues", [])
            
            # Format scope
            scope_text = f"**{scope}:** " if scope else ""
            
            # Format issue links
            issue_text = ""
            if include_issues and issues and github_repo:
                issue_links = [f"[#{i}](https://github.com/{github_repo}/issues/{i})" for i in issues]
                issue_text = f" ({', '.join(issue_links)})"
            elif issues:
                issue_text = f" (#{', '.join(map(str, issues))})"
            
            lines.append(f"- {scope_text}{desc}{issue_text} ({hash_str})")
        
        lines.append("")
    
    # Summary
    lines.append("---")
    lines.append("")
    lines.append(f"*{len(commits)} commits from {len(set(c.get('author') for c in commits if c.get('author')))} contributors*")
    
    return "\n".join(lines)


def generate_release_notes(
    version: str,
    commits: list = None,
    github_repo: str = None,
) -> str:
    """Reliz uchun qisqa xabarnoma yaratish."""
    if commits is None:
        commits = get_commits_since()
    
    features = [c for c in commits if c.get("type") == "feat"]
    fixes = [c for c in commits if c.get("type") == "fix"]
    breaking = [c for c in commits if c.get("is_breaking")]
    
    lines = []
    lines.append(f"# Release {version}")
    lines.append("")
    
    # Summary
    lines.append(f"## Summary")
    lines.append("")
    lines.append(f"- **{len(features)}** new features")
    lines.append(f"- **{len(fixes)}** bug fixes")
    if breaking:
        lines.append(f"- **{len(breaking)}** breaking changes")
    lines.append("")
    
    # Key features
    if features:
        lines.append("## 🚀 Highlights")
        lines.append("")
        for commit in features[:5]:
            desc = commit.get("description", "")
            lines.append(f"- {desc}")
        if len(features) > 5:
            lines.append(f"- ...and {len(features) - 5} more features")
        lines.append("")
    
    # Breaking changes
    if breaking:
        lines.append("## ⚠️ Breaking Changes")
        lines.append("")
        lines.append("**Please review these changes carefully:**")
        lines.append("")
        for commit in breaking:
            desc = commit.get("description", "")
            lines.append(f"- {desc}")
        lines.append("")
    
    # Full changelog link
    lines.append("## 📝 Full Changelog")
    lines.append("")
    lines.append("See [CHANGELOG.md](CHANGELOG.md) for complete details.")
    
    return "\n".join(lines)


# ---------------------------------------------------------------- #
# File Operations
# ---------------------------------------------------------------- #

def save_changelog(content: str, filepath: str = None):
    """Changelog ni faylga saqlash."""
    path = Path(filepath) if filepath else CHANGELOG_FILE
    
    # Read existing changelog
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    
    # Prepend new changelog
    if existing:
        # Find first ## header
        header_match = re.search(r"^## ", existing, re.MULTILINE)
        if header_match:
            new_content = content + "\n\n" + existing[header_match.start():]
        else:
            new_content = content + "\n\n" + existing
    else:
        new_content = "# Changelog\n\n" + content
    
    # Write file
    path.write_text(new_content, encoding="utf-8")
    print(f"[changelog] Saved to {path}")


def save_release_notes(version: str, content: str, directory: str = None):
    """Reliz xabarnomasini saqlash."""
    dir_path = Path(directory) if directory else RELEASES_DIR
    dir_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"release-{version}.md"
    filepath = dir_path / filename
    
    filepath.write_text(content, encoding="utf-8")
    print(f"[changelog] Release notes saved to {filepath}")


def load_existing_changelog() -> str:
    """Mavjud changelog ni yuklash."""
    if CHANGELOG_FILE.exists():
        return CHANGELOG_FILE.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------- #
# JSON Export
# ---------------------------------------------------------------- #

def export_changelog_json(
    commits: list = None,
    filepath: str = None,
) -> dict:
    """Changelog ni JSON formatda eksport qilish."""
    if commits is None:
        commits = get_commits_since()
    
    # Group by type
    grouped = {}
    for commit in commits:
        commit_type = commit.get("type", "other")
        if commit_type not in grouped:
            grouped[commit_type] = []
        grouped[commit_type].append({
            "hash": commit.get("hash"),
            "description": commit.get("description"),
            "scope": commit.get("scope"),
            "author": commit.get("author"),
            "date": commit.get("date"),
            "is_breaking": commit.get("is_breaking"),
            "issues": commit.get("issues", []),
        })
    
    data = {
        "generated_at": datetime.now().isoformat(),
        "total_commits": len(commits),
        "contributors": list(set(c.get("author") for c in commits if c.get("author"))),
        "categories": grouped,
    }
    
    if filepath:
        path = Path(filepath)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[changelog] JSON exported to {path}")
    
    return data


# ---------------------------------------------------------------- #
# CLI Interface
# ---------------------------------------------------------------- #

def main():
    """CLI uchun asosiy funksiya."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IGRIS Changelog Generator")
    parser.add_argument("command", choices=["generate", "release", "export", "tags"],
                       help="Command to run")
    parser.add_argument("--version", help="Version number")
    parser.add_argument("--since", help="Start reference (tag/commit/date)")
    parser.add_argument("--until", help="End reference (tag/commit/date)")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--format", choices=["markdown", "json", "text"],
                       default="markdown", help="Output format")
    parser.add_argument("--repo", help="GitHub repo (owner/repo)")
    parser.add_argument("--no-links", action="store_true",
                       help="Disable GitHub links")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        commits = get_commits(since=args.since, until=args.until)
        changelog = generate_changelog(
            commits=commits,
            version=args.version,
            include_links=not args.no_links,
            github_repo=args.repo,
        )
        
        if args.output:
            save_changelog(changelog, args.output)
        else:
            print(changelog)
    
    elif args.command == "release":
        if not args.version:
            print("[changelog] Version required for release command")
            sys.exit(1)
        
        commits = get_commits(since=args.since, until=args.until)
        
        # Generate changelog
        changelog = generate_changelog(
            commits=commits,
            version=args.version,
            github_repo=args.repo,
        )
        
        # Generate release notes
        release_notes = generate_release_notes(
            version=args.version,
            commits=commits,
            github_repo=args.repo,
        )
        
        # Save both
        save_changelog(changelog, args.output)
        save_release_notes(args.version, release_notes)
        
        print(f"\n[changelog] Release {args.version} prepared!")
        print(f"  - Changelog updated")
        print(f"  - Release notes saved")
    
    elif args.command == "export":
        commits = get_commits(since=args.since, until=args.until)
        data = export_changelog_json(
            commits=commits,
            filepath=args.output,
        )
        
        if not args.output:
            print(json.dumps(data, indent=2))
    
    elif args.command == "tags":
        tags = get_tags()
        if not tags:
            print("[changelog] No tags found")
        else:
            print("\n[changelog] Available tags:")
            for tag in tags[:20]:
                print(f"  {tag}")


if __name__ == "__main__":
    main()
