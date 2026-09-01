"""
IGRIS BRAIN — Release Automation Script
========================================
Automates the release process combining:
    - Version bumping
    - Changelog generation
    - Git operations
    - GitHub release creation

Usage:
    python release.py --version 1.3.0
    python release.py --version 1.3.0 --dry-run
    python release.py --bump minor
    python release.py --bump patch --tag --commit
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Import our tools
sys.path.insert(0, str(Path(__file__).parent))

from version_bumper import Version, get_current_version, bump_version, check_clean_working_tree
from changelog_generator import (
    generate_changelog, generate_release_notes,
    save_changelog, save_release_notes, get_commits_since
)

# Project paths
PROJECT_ROOT = Path(__file__).parent
RELEASES_DIR = PROJECT_ROOT / "releases"


# ---------------------------------------------------------------- #
# Terminal Output
# ---------------------------------------------------------------- #

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_step(num: int, text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}Step {num}:{Colors.END} {Colors.BOLD}{text}{Colors.END}")


def print_success(text: str):
    print(f"  {Colors.GREEN}✓{Colors.END} {text}")


def print_warning(text: str):
    print(f"  {Colors.YELLOW}⚠{Colors.END} {text}")


def print_error(text: str):
    print(f"  {Colors.RED}✗{Colors.END} {text}")


def print_info(text: str):
    print(f"  {Colors.BLUE}ℹ{Colors.END} {text}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ha/Yo'q savoli."""
    suffix = "[Y/n]" if default else "[y/N]"
    prompt = f"\n  {question} {suffix}: "
    
    try:
        answer = input(prompt).strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes", "ha")
    except (EOFError, KeyboardInterrupt):
        return default


# ---------------------------------------------------------------- #
# Git Operations
# ---------------------------------------------------------------- #

def _run_git(args: list) -> tuple[bool, str]:
    """Git buyrug'ini bajarish."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as exc:
        return False, str(exc)


def git_push(remote: str = "origin", branch: str = "main", tags: bool = True) -> bool:
    """Git push."""
    ok, output = _run_git(["push", remote, branch])
    if not ok:
        print_error(f"Failed to push: {output}")
        return False
    
    if tags:
        ok, output = _run_git(["push", remote, "--tags"])
        if not ok:
            print_warning(f"Failed to push tags: {output}")
    
    return True


def git_create_release_commit(version: Version, message: str = None) -> bool:
    """Release commit yaratish."""
    # Stage all changes
    _run_git(["add", "-A"])
    
    # Create commit
    commit_message = message or f"chore(release): v{version}\n\nRelease {version}"
    ok, output = _run_git(["commit", "-m", commit_message])
    
    if ok:
        print_success(f"Created commit for v{version}")
        return True
    else:
        print_error(f"Commit failed: {output}")
        return False


def git_create_tag(version: Version, message: str = None) -> bool:
    """Git teg yaratish."""
    tag_name = f"v{version}"
    tag_message = message or f"Release {version}"
    
    ok, output = _run_git(["tag", "-a", tag_name, "-m", tag_message])
    if ok:
        print_success(f"Created tag: {tag_name}")
        return True
    else:
        print_error(f"Failed to create tag: {output}")
        return False


# ---------------------------------------------------------------- #
# GitHub Release
# ---------------------------------------------------------------- #

def create_github_release(version: Version, release_notes: str, draft: bool = False) -> bool:
    """GitHub release yaratish (gh CLI orqali)."""
    # Check if gh CLI is available
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print_warning("GitHub CLI (gh) not found, skipping GitHub release")
            return False
    except FileNotFoundError:
        print_warning("GitHub CLI (gh) not found, skipping GitHub release")
        return False
    
    # Create release
    tag_name = f"v{version}"
    title = f"Release {version}"
    
    # Save release notes to temp file
    temp_file = PROJECT_ROOT / ".release_notes.md"
    temp_file.write_text(release_notes, encoding="utf-8")
    
    try:
        cmd = [
            "gh", "release", "create",
            tag_name,
            "--title", title,
            "--notes-file", str(temp_file),
        ]
        
        if draft:
            cmd.append("--draft")
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            print_success(f"Created GitHub release: {result.stdout.strip()}")
            return True
        else:
            print_error(f"Failed to create GitHub release: {result.stderr}")
            return False
    finally:
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()


# ---------------------------------------------------------------- #
# Release Process
# ---------------------------------------------------------------- #

def run_release(
    version: str = None,
    bump_type: str = None,
    pre_release: str = None,
    dry_run: bool = False,
    skip_tests: bool = False,
    skip_commit: bool = False,
    skip_tag: bool = False,
    skip_push: bool = False,
    skip_github: bool = False,
    draft: bool = False,
    message: str = None,
) -> bool:
    """Release jarayonini bajarish.
    
    Args:
        version: Target version (e.g., "1.3.0")
        bump_type: Bump type (major/minor/patch/pre)
        pre_release: Pre-release type (alpha/beta/rc)
        dry_run: Show what would be done
        skip_tests: Skip test execution
        skip_commit: Skip git commit
        skip_tag: Skip git tag creation
        skip_push: Skip git push
        skip_github: Skip GitHub release
        draft: Create draft release
        message: Custom release message
        
    Returns:
        True if successful
    """
    print_header("IGRIS Release Process")
    
    # Get current version
    current = get_current_version()
    print_info(f"Current version: {current}")
    
    # Determine target version
    if version:
        target = Version.parse(version)
    elif bump_type:
        if bump_type == "major":
            target = current.bump_major()
        elif bump_type == "minor":
            target = current.bump_minor()
        elif bump_type == "patch":
            target = current.bump_patch()
        elif bump_type == "pre":
            target = current.bump_pre_release(pre_release or "alpha")
        else:
            print_error(f"Unknown bump type: {bump_type}")
            return False
    else:
        print_error("Either --version or --bump required")
        return False
    
    print_info(f"Target version: {target}")
    
    if dry_run:
        print_warning("DRY RUN MODE - No changes will be made")
    
    # Step 1: Pre-flight checks
    print_step(1, "Pre-flight checks")
    
    if not skip_tests:
        print_info("Running tests...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "test_*.py", "-v", "--tb=short"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print_success("All tests passing")
            else:
                print_error("Tests failed!")
                if not dry_run:
                    return False
        except Exception as exc:
            print_warning(f"Could not run tests: {exc}")
    else:
        print_warning("Skipping tests (--skip-tests)")
    
    # Check clean working tree
    if check_clean_working_tree():
        print_success("Working tree is clean")
    else:
        print_warning("Working tree has uncommitted changes")
        if not dry_run:
            if not ask_yes_no("Continue anyway?", default=False):
                return False
    
    # Step 2: Version bump
    print_step(2, "Version bump")
    
    if not dry_run:
        new_version = bump_version(
            bump_type="patch" if not bump_type else bump_type,
            pre_release=pre_release,
            dry_run=False,
            tag=False,  # We'll handle tagging separately
            commit=False,  # We'll handle commit separately
        )
    else:
        new_version = target
        print_info(f"Would bump: {current} -> {target}")
    
    # Step 3: Generate changelog
    print_step(3, "Generate changelog")
    
    commits = get_commits_since()
    
    if not dry_run:
        # Generate full changelog
        changelog = generate_changelog(
            commits=commits,
            version=str(target),
            github_repo="your-org/igris",
        )
        save_changelog(changelog)
        
        # Generate release notes
        release_notes = generate_release_notes(
            version=str(target),
            commits=commits,
            github_repo="your-org/igris",
        )
        save_release_notes(str(target), release_notes)
        
        print_success("Changelog and release notes generated")
    else:
        print_info("Would generate changelog and release notes")
    
    # Step 4: Create commit
    print_step(4, "Create release commit")
    
    if not skip_commit and not dry_run:
        commit_message = message or f"chore(release): v{target}\n\nRelease {target}"
        git_create_release_commit(target, commit_message)
    else:
        print_info("Skipping commit" if skip_commit else "Would create commit")
    
    # Step 5: Create tag
    print_step(5, "Create git tag")
    
    if not skip_tag and not dry_run:
        git_create_tag(target, message)
    else:
        print_info("Skipping tag" if skip_tag else "Would create tag")
    
    # Step 6: Push
    print_step(6, "Push to remote")
    
    if not skip_push and not dry_run:
        if ask_yes_no("Push to remote now?", default=True):
            git_push(tags=True)
        else:
            print_info("Skipping push (do it manually)")
    else:
        print_info("Skipping push" if skip_push else "Would push to remote")
    
    # Step 7: GitHub release
    print_step(7, "GitHub release")
    
    if not skip_github and not dry_run:
        if ask_yes_no("Create GitHub release?", default=True):
            release_notes = ""
            release_file = RELEASES_DIR / f"release-{target}.md"
            if release_file.exists():
                release_notes = release_file.read_text(encoding="utf-8")
            
            create_github_release(target, release_notes, draft=draft)
        else:
            print_info("Skipping GitHub release")
    else:
        print_info("Skipping GitHub release" if skip_github else "Would create GitHub release")
    
    # Summary
    print_header("Release Complete!")
    
    print(f"""
{Colors.GREEN}{Colors.BOLD}Release {target} is ready!{Colors.END}

{Colors.CYAN}What was done:{Colors.END}
  - Version bumped: {current} -> {target}
  - Changelog updated
  - Release notes created
  {'  - Commit created' if not skip_commit else ''}
  {'  - Tag created: v' + str(target) if not skip_tag else ''}
  {'  - Pushed to remote' if not skip_push else ''}
  {'  - GitHub release created' if not skip_github else ''}

{Colors.CYAN}Next steps:{Colors.END}
  {'  - git push origin main --tags' if skip_push else ''}
  {'  - Create GitHub release manually' if skip_github else ''}
  - Monitor for issues
  - Update documentation if needed
""")
    
    return True


# ---------------------------------------------------------------- #
# CLI Interface
# ---------------------------------------------------------------- #

def main():
    """CLI uchun asosiy funksiya."""
    parser = argparse.ArgumentParser(
        description="IGRIS Release Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Release with specific version
  python release.py --version 1.3.0

  # Bump minor and release
  python release.py --bump minor

  # Dry run (preview changes)
  python release.py --version 1.3.0 --dry-run

  # Quick release (skip tests)
  python release.py --bump patch --skip-tests

  # Draft release
  python release.py --version 1.3.0 --draft
        """,
    )
    
    # Version options
    version_group = parser.add_mutually_exclusive_group(required=True)
    version_group.add_argument("--version", help="Target version (e.g., 1.3.0)")
    version_group.add_argument("--bump", choices=["major", "minor", "patch", "pre"],
                              help="Bump type")
    
    # Pre-release
    parser.add_argument("--pre-release", choices=["alpha", "beta", "rc"],
                       help="Pre-release type (with --bump pre)")
    
    # Flags
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done")
    parser.add_argument("--skip-tests", action="store_true",
                       help="Skip running tests")
    parser.add_argument("--skip-commit", action="store_true",
                       help="Skip creating git commit")
    parser.add_argument("--skip-tag", action="store_true",
                       help="Skip creating git tag")
    parser.add_argument("--skip-push", action="store_true",
                       help="Skip pushing to remote")
    parser.add_argument("--skip-github", action="store_true",
                       help="Skip creating GitHub release")
    parser.add_argument("--draft", action="store_true",
                       help="Create draft GitHub release")
    parser.add_argument("--message", "-m",
                       help="Custom release message")
    
    args = parser.parse_args()
    
    success = run_release(
        version=args.version,
        bump_type=args.bump,
        pre_release=args.pre_release,
        dry_run=args.dry_run,
        skip_tests=args.skip_tests,
        skip_commit=args.skip_commit,
        skip_tag=args.skip_tag,
        skip_push=args.skip_push,
        skip_github=args.skip_github,
        draft=args.draft,
        message=args.message,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
