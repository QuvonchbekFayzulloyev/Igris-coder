"""
IGRIS BRAIN — Version Bumper
=============================
Semantic versioning (semver) management tool.

Features:
    - Bump major, minor, patch versions
    - Pre-release versions (alpha, beta, rc)
    - Update multiple files automatically
    - Create git tags
    - Create release commits
    - Dry-run mode
    - Version validation

Usage:
    python version_bumper.py bump major
    python version_bumper.py bump minor
    python version_bumper.py bump patch
    python version_bumper.py bump pre --pre-release alpha
    python version_bumper.py current
    python version_bumper.py validate 1.2.3

Semantic Versioning:
    MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
    
    MAJOR: Incompatible API changes
    MINOR: New functionality (backwards compatible)
    PATCH: Backwards compatible bug fixes
    PRERELEASE: alpha, beta, rc
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

# Files to update with version
VERSION_FILES = [
    ("version.json", "json"),
    ("config.yaml", "yaml"),
    ("setup.py", "python"),
    ("pyproject.toml", "toml"),
    ("package.json", "json"),
]

# Current version (fallback)
DEFAULT_VERSION = "1.2.0"


# ---------------------------------------------------------------- #
# Version Parsing
# ---------------------------------------------------------------- #

class Version:
    """Semantic version representation."""
    
    def __init__(self, major: int = 1, minor: int = 0, patch: int = 0,
                 pre_release: str = "", build: str = ""):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.pre_release = pre_release
        self.build = build
    
    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """Version string ni parse qilish."""
        # Remove 'v' prefix
        version_str = version_str.lstrip("vV")
        
        # Split build metadata
        if "+" in version_str:
            version_str, cls.build = version_str.split("+", 1)
        
        # Split pre-release
        pre_release = ""
        if "-" in version_str:
            version_str, pre_release = version_str.split("-", 1)
        
        # Parse major.minor.patch
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        
        return cls(major, minor, patch, pre_release)
    
    def __str__(self) -> str:
        """Version string ga aylantirish."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre_release:
            base += f"-{self.pre_release}"
        if self.build:
            base += f"+{self.build}"
        return base
    
    def __eq__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch, self.pre_release) == \
               (other.major, other.minor, other.patch, other.pre_release)
    
    def __lt__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch) < \
               (other.major, other.minor, other.patch)
    
    def __gt__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch) > \
               (other.major, other.minor, other.patch)
    
    def bump_major(self) -> 'Version':
        """Major version ni ko'tarish."""
        return Version(self.major + 1, 0, 0)
    
    def bump_minor(self) -> 'Version':
        """Minor version ni ko'tarish."""
        return Version(self.major, self.minor + 1, 0)
    
    def bump_patch(self) -> 'Version':
        """Patch version ni ko'tarish."""
        return Version(self.major, self.minor, self.patch + 1)
    
    def bump_pre_release(self, pre_type: str = "alpha") -> 'Version':
        """Pre-release version ni ko'tarish."""
        if self.pre_release:
            # Extract current pre-release number
            match = re.match(r"([a-zA-Z]+)(\d*)", self.pre_release)
            if match:
                current_type = match.group(1)
                current_num = int(match.group(2)) if match.group(2) else 0
                
                if current_type == pre_type:
                    # Same type, increment number
                    new_pre = f"{pre_type}{current_num + 1}"
                else:
                    # Different type, reset to 1
                    new_pre = f"{pre_type}1"
            else:
                new_pre = f"{pre_type}1"
        else:
            new_pre = f"{pre_type}1"
        
        return Version(self.major, self.minor, self.patch, new_pre)
    
    def to_dict(self) -> dict:
        """Dictionary formatga aylantirish."""
        return {
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "pre_release": self.pre_release,
            "build": self.build,
            "string": str(self),
        }


# ---------------------------------------------------------------- #
# Version File Operations
# ---------------------------------------------------------------- #

def get_current_version() -> Version:
    """Joriy versiyani olish."""
    # Try version.json first
    version_file = PROJECT_ROOT / "version.json"
    if version_file.exists():
        try:
            with open(version_file, "r") as f:
                data = json.load(f)
                version_str = data.get("version", DEFAULT_VERSION)
                return Version.parse(version_str)
        except Exception:
            pass
    
    # Try config.yaml
    config_file = PROJECT_ROOT / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, "r") as f:
                data = yaml.safe_load(f)
                version_str = data.get("version", DEFAULT_VERSION)
                return Version.parse(version_str)
        except Exception:
            pass
    
    # Try package.json
    package_file = PROJECT_ROOT / "package.json"
    if package_file.exists():
        try:
            with open(package_file, "r") as f:
                data = json.load(f)
                version_str = data.get("version", DEFAULT_VERSION)
                return Version.parse(version_str)
        except Exception:
            pass
    
    # Fallback
    return Version.parse(DEFAULT_VERSION)


def update_version_files(new_version: Version, dry_run: bool = False) -> list:
    """Barcha versiya fayllarini yangilash."""
    updated = []
    
    # version.json
    version_file = PROJECT_ROOT / "version.json"
    if version_file.exists():
        try:
            with open(version_file, "r") as f:
                data = json.load(f)
            
            data["version"] = str(new_version)
            data["updated_at"] = datetime.now().isoformat()
            
            if not dry_run:
                with open(version_file, "w") as f:
                    json.dump(data, f, indent=2)
            
            updated.append("version.json")
        except Exception as exc:
            print(f"[version] Error updating version.json: {exc}")
    
    # config.yaml
    config_file = PROJECT_ROOT / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, "r") as f:
                content = f.read()
            
            # Replace version in YAML
            content = re.sub(
                r'version:\s*["\']?[\d.]+["\']?',
                f'version: "{new_version}"',
                content,
            )
            
            if not dry_run:
                with open(config_file, "w") as f:
                    f.write(content)
            
            updated.append("config.yaml")
        except Exception as exc:
            print(f"[version] Error updating config.yaml: {exc}")
    
    # package.json (if exists)
    package_file = PROJECT_ROOT / "package.json"
    if package_file.exists():
        try:
            with open(package_file, "r") as f:
                data = json.load(f)
            
            data["version"] = str(new_version)
            
            if not dry_run:
                with open(package_file, "w") as f:
                    json.dump(data, f, indent=2)
            
            updated.append("package.json")
        except Exception as exc:
            print(f"[version] Error updating package.json: {exc}")
    
    # igris_agent.py (if exists)
    agent_file = PROJECT_ROOT / "igris_agent.py"
    if agent_file.exists():
        try:
            content = agent_file.read_text(encoding="utf-8")
            
            # Update version string
            content = re.sub(
                r'VERSION\s*=\s*["\'][\d.]+["\']',
                f'VERSION = "{new_version}"',
                content,
            )
            
            if not dry_run:
                agent_file.write_text(content, encoding="utf-8")
            
            updated.append("igris_agent.py")
        except Exception as exc:
            print(f"[version] Error updating igris_agent.py: {exc}")
    
    return updated


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


def create_git_tag(version: Version, message: str = None) -> bool:
    """Git teg yaratish."""
    tag_name = f"v{version}"
    tag_message = message or f"Release {version}"
    
    ok, output = _run_git(["tag", "-a", tag_name, "-m", tag_message])
    if ok:
        print(f"[version] Created tag: {tag_name}")
        return True
    else:
        print(f"[version] Failed to create tag: {output}")
        return False


def create_release_commit(version: Version, files: list, message: str = None) -> bool:
    """Release commit yaratish."""
    # Stage files
    for file in files:
        file_path = Path(file)
        if file_path.exists():
            _run_git(["add", str(file_path)])
    
    # Create commit
    commit_message = message or f"chore(release): v{version}\n\nBump version to {version}"
    ok, output = _run_git(["commit", "-m", commit_message])
    
    if ok:
        print(f"[version] Created commit for v{version}")
        return True
    else:
        print(f"[version] Commit failed: {output}")
        return False


def check_clean_working_tree() -> bool:
    """Toza ishchi daraxtini tekshirish."""
    ok, output = _run_git(["status", "--porcelain"])
    return ok and not output


def get_last_commit() -> str:
    """Oxirgi commit ni olish."""
    ok, output = _run_git(["log", "-1", "--pretty=format:%h %s"])
    return output if ok else ""


# ---------------------------------------------------------------- #
# Version Validation
# ---------------------------------------------------------------- #

def validate_version(version_str: str) -> tuple[bool, str]:
    """Version ni tekshirish.
    
    Returns:
        (is_valid, message)
    """
    # Semver regex pattern
    pattern = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    
    if re.match(pattern, version_str):
        return True, "Valid semantic version"
    else:
        return False, "Invalid semantic version format. Use: MAJOR.MINOR.PATCH"


# ---------------------------------------------------------------- #
# Version Bumping
# ---------------------------------------------------------------- #

def bump_version(bump_type: str, pre_release: str = None, 
                 dry_run: bool = False, tag: bool = False,
                 commit: bool = False, message: str = None) -> Version:
    """Versiyani ko'tarish.
    
    Args:
        bump_type: major, minor, patch, or pre
        pre_release: Pre-release type (alpha, beta, rc)
        dry_run: Show what would be done without doing it
        tag: Create git tag
        commit: Create release commit
        message: Custom commit/tag message
        
    Returns:
        New version
    """
    # Get current version
    current = get_current_version()
    print(f"\n[version] Current version: {current}")
    
    # Calculate new version
    if bump_type == "major":
        new_version = current.bump_major()
    elif bump_type == "minor":
        new_version = current.bump_minor()
    elif bump_type == "patch":
        new_version = current.bump_patch()
    elif bump_type == "pre":
        if not pre_release:
            pre_release = "alpha"
        new_version = current.bump_pre_release(pre_release)
    else:
        print(f"[version] Unknown bump type: {bump_type}")
        sys.exit(1)
    
    print(f"[version] New version: {new_version}")
    
    if dry_run:
        print("\n[dry-run] Would update:")
        for file, _ in VERSION_FILES:
            file_path = PROJECT_ROOT / file
            if file_path.exists():
                print(f"  - {file}")
        
        if tag:
            print(f"  - Create tag: v{new_version}")
        if commit:
            print(f"  - Create commit: chore(release): v{new_version}")
        
        return new_version
    
    # Update files
    updated_files = update_version_files(new_version, dry_run=False)
    if updated_files:
        print(f"\n[version] Updated files:")
        for f in updated_files:
            print(f"  - {f}")
    
    # Create commit
    if commit:
        commit_files = updated_files.copy()
        commit_files.append("version.json")
        create_release_commit(new_version, list(set(commit_files)), message)
    
    # Create tag
    if tag:
        create_git_tag(new_version, message)
    
    # Summary
    print(f"\n[version] Version bumped: {current} -> {new_version}")
    
    return new_version


# ---------------------------------------------------------------- #
# CLI Interface
# ---------------------------------------------------------------- #

def main():
    """CLI uchun asosiy funksiya."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IGRIS Version Bumper")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # bump command
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument("type", choices=["major", "minor", "patch", "pre"],
                            help="Bump type")
    bump_parser.add_argument("--pre-release", choices=["alpha", "beta", "rc"],
                            help="Pre-release type")
    bump_parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be done")
    bump_parser.add_argument("--tag", action="store_true",
                            help="Create git tag")
    bump_parser.add_argument("--commit", action="store_true",
                            help="Create release commit")
    bump_parser.add_argument("--message", "-m",
                            help="Custom commit/tag message")
    
    # current command
    subparsers.add_parser("current", help="Show current version")
    
    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate version")
    validate_parser.add_argument("version", help="Version to validate")
    
    # list command
    subparsers.add_parser("files", help="List version files")
    
    args = parser.parse_args()
    
    if args.command == "bump":
        bump_version(
            bump_type=args.type,
            pre_release=args.pre_release,
            dry_run=args.dry_run,
            tag=args.tag,
            commit=args.commit,
            message=args.message,
        )
    
    elif args.command == "current":
        version = get_current_version()
        print(f"Current version: {version}")
    
    elif args.command == "validate":
        is_valid, message = validate_version(args.version)
        if is_valid:
            print(f"[OK] {message}")
            v = Version.parse(args.version)
            print(f"  Major: {v.major}")
            print(f"  Minor: {v.minor}")
            print(f"  Patch: {v.patch}")
            if v.pre_release:
                print(f"  Pre-release: {v.pre_release}")
        else:
            print(f"[ERROR] {message}")
    
    elif args.command == "files":
        print("\nVersion files:")
        for file, file_type in VERSION_FILES:
            file_path = PROJECT_ROOT / file
            exists = file_path.exists()
            status = "exists" if exists else "not found"
            print(f"  [{status}] {file} ({file_type})")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
