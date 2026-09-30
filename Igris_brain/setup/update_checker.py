"""
IGRIS BRAIN — Auto-Update Checker
==================================
Checks for new versions of IGRIS and notifies the user.

Features:
    - Check GitHub releases for updates
    - Compare semantic versions
    - Show changelog
    - Backup before update
    - Download and install updates
    - Auto-check on startup (optional)

Usage:
    from update_checker import check_for_updates, get_current_version
    
    # Check for updates
    update_info = check_for_updates()
    if update_info:
        print(f"New version available: {update_info['version']}")
        
    # Get current version
    version = get_current_version()
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent
VERSION_FILE = PROJECT_ROOT / "version.json"
UPDATE_LOG = PROJECT_ROOT / "logs" / "updates.log"

# GitHub repository (update this with your repo)
GITHUB_REPO = "your-org/igris"  # Change to your repo
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"

# Current version
CURRENT_VERSION = "1.2.0"
CURRENT_VERSION_FILE = PROJECT_ROOT / "version.json"


# ---------------------------------------------------------------- #
# Version Management
# ---------------------------------------------------------------- #

def get_current_version() -> str:
    """Joriy versiyani olish."""
    if CURRENT_VERSION_FILE.exists():
        try:
            with open(CURRENT_VERSION_FILE, "r") as f:
                data = json.load(f)
                return data.get("version", CURRENT_VERSION)
        except Exception:
            pass
    return CURRENT_VERSION


def save_version(version: str, changelog: str = ""):
    """Versiyani saqlash."""
    data = {
        "version": version,
        "updated_at": datetime.now().isoformat(),
        "changelog": changelog,
    }
    with open(CURRENT_VERSION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def parse_version(version_str: str) -> tuple:
    """Semantic version ni parse qilish."""
    # Remove 'v' prefix if present
    version_str = version_str.lstrip("vV")
    
    try:
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def compare_versions(current: str, latest: str) -> int:
    """Versiyalarni solishtirish.
    
    Returns:
        1 if latest > current
        0 if equal
        -1 if latest < current
    """
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)
    
    if latest_tuple > current_tuple:
        return 1
    elif latest_tuple < current_tuple:
        return -1
    return 0


# ---------------------------------------------------------------- #
# GitHub API
# ---------------------------------------------------------------- #

def _github_request(endpoint: str) -> dict:
    """GitHub API so'rov."""
    url = f"{GITHUB_API}{endpoint}"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "IgrisAgent-UpdateChecker/1.0",
    }
    
    # Add token if available
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"error": str(exc)}


def get_latest_release() -> Optional[dict]:
    """GitHub'dan eng so'nggi relizni olish."""
    result = _github_request("/releases/latest")
    
    if "error" in result:
        return None
    
    return {
        "version": result.get("tag_name", "").lstrip("vV"),
        "name": result.get("name", ""),
        "body": result.get("body", ""),
        "published_at": result.get("published_at", ""),
        "html_url": result.get("html_url", ""),
        "assets": [
            {
                "name": asset.get("name"),
                "size": asset.get("size"),
                "download_url": asset.get("browser_download_url"),
            }
            for asset in result.get("assets", [])
        ],
    }


def get_all_releases(limit: int = 10) -> list:
    """Barcha relizlarni olish."""
    result = _github_request(f"/releases?per_page={limit}")
    
    if "error" in result or not isinstance(result, list):
        return []
    
    return [
        {
            "version": release.get("tag_name", "").lstrip("vV"),
            "name": release.get("name", ""),
            "published_at": release.get("published_at", ""),
        }
        for release in result
    ]


# ---------------------------------------------------------------- #
# Update Check
# ---------------------------------------------------------------- #

def check_for_updates(auto_check: bool = False) -> Optional[dict]:
    """Yangilanish mavjudligini tekshirish.
    
    Args:
        auto_check: Avtomatik tekshirish (True = foydalanuvchi so'ramagan)
    
    Returns:
        Update info dict or None if no update available
    """
    current_version = get_current_version()
    
    # Get latest release from GitHub
    latest = get_latest_release()
    
    if not latest:
        if not auto_check:
            print("[update] Could not check for updates (GitHub API unavailable)")
        return None
    
    latest_version = latest.get("version", "")
    
    if not latest_version:
        return None
    
    # Compare versions
    comparison = compare_versions(current_version, latest_version)
    
    if comparison <= 0:
        if not auto_check:
            print(f"[update] You are running the latest version ({current_version})")
        return None
    
    # Update available
    update_info = {
        "current_version": current_version,
        "latest_version": latest_version,
        "name": latest.get("name", ""),
        "changelog": latest.get("body", ""),
        "published_at": latest.get("published_at", ""),
        "url": latest.get("html_url", ""),
        "assets": latest.get("assets", []),
    }
    
    if not auto_check:
        print(f"\n[update] New version available!")
        print(f"  Current: {current_version}")
        print(f"  Latest:  {latest_version}")
        print(f"  Released: {latest.get('published_at', 'unknown')[:10]}")
        if latest.get("name"):
            print(f"  Name: {latest['name']}")
        print(f"\n  Changelog:")
        print(f"  {latest.get('body', 'No changelog')[:500]}")
        print(f"\n  Download: {latest.get('html_url', '')}")
    
    return update_info


# ---------------------------------------------------------------- #
# Update Backup
# ---------------------------------------------------------------- #

def create_backup() -> Optional[Path]:
    """Update dan oldin backup yaratish."""
    backup_dir = PROJECT_ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"igris_backup_{timestamp}"
    backup_path = backup_dir / backup_name
    
    try:
        # Create backup directory
        backup_path.mkdir(exist_ok=True)
        
        # Copy important files
        files_to_backup = [
            "config.yaml",
            "mcp_servers.json",
            ".env",
            "version.json",
        ]
        
        for file_name in files_to_backup:
            src = PROJECT_ROOT / file_name
            if src.exists():
                shutil.copy2(src, backup_path / file_name)
        
        # Copy MCP servers directory
        mcp_src = PROJECT_ROOT / "mcp_servers"
        if mcp_src.exists():
            shutil.copytree(mcp_src, backup_path / "mcp_servers", dirs_exist_ok=True)
        
        print(f"[update] Backup created: {backup_path}")
        return backup_path
        
    except Exception as exc:
        print(f"[update] Backup failed: {exc}")
        return None


def restore_backup(backup_path: Path) -> bool:
    """Backup'dan tiklash."""
    try:
        for item in backup_path.iterdir():
            if item.is_file():
                dest = PROJECT_ROOT / item.name
                shutil.copy2(item, dest)
            elif item.is_dir() and item.name == "mcp_servers":
                dest = PROJECT_ROOT / "mcp_servers"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
        
        print(f"[update] Backup restored from: {backup_path}")
        return True
    except Exception as exc:
        print(f"[update] Restore failed: {exc}")
        return False


# ---------------------------------------------------------------- #
# Update Download & Install
# ---------------------------------------------------------------- #

def download_update(update_info: dict) -> Optional[Path]:
    """Update faylini yuklab olish."""
    assets = update_info.get("assets", [])
    
    # Find appropriate asset
    asset = None
    for a in assets:
        name = a.get("name", "").lower()
        if name.endswith(".zip") or name.endswith(".tar.gz") or name.endswith(".7z"):
            asset = a
            break
    
    if not asset:
        # Use source code download
        asset = {
            "name": f"igris-{update_info['latest_version']}.zip",
            "download_url": f"https://github.com/{GITHUB_REPO}/archive/refs/tags/v{update_info['latest_version']}.zip",
        }
    
    download_url = asset.get("download_url")
    if not download_url:
        print("[update] No download URL found")
        return None
    
    # Download
    download_dir = PROJECT_ROOT / "downloads"
    download_dir.mkdir(exist_ok=True)
    
    filename = asset.get("name", "update.zip")
    filepath = download_dir / filename
    
    print(f"[update] Downloading {filename}...")
    
    try:
        urllib.request.urlretrieve(download_url, filepath)
        print(f"[update] Downloaded to: {filepath}")
        return filepath
    except Exception as exc:
        print(f"[update] Download failed: {exc}")
        return None


def extract_update(download_path: Path) -> Optional[Path]:
    """Update faylini ochish."""
    extract_dir = PROJECT_ROOT / "temp_update"
    extract_dir.mkdir(exist_ok=True)
    
    try:
        if download_path.suffix == ".zip":
            import zipfile
            with zipfile.ZipFile(download_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        elif download_path.name.endswith(".tar.gz"):
            import tarfile
            with tarfile.open(download_path, "r:gz") as tar_ref:
                tar_ref.extractall(extract_dir)
        else:
            print(f"[update] Unsupported format: {download_path.suffix}")
            return None
        
        print(f"[update] Extracted to: {extract_dir}")
        return extract_dir
    except Exception as exc:
        print(f"[update] Extraction failed: {exc}")
        return None


def install_update(extract_path: Path, update_info: dict) -> bool:
    """Update ni o'rnatish."""
    try:
        # Find the actual update files
        update_files = []
        for item in extract_path.rglob("*"):
            if item.is_file():
                # Skip non-Igris files
                if item.name.startswith(".") or item.name in ("__pycache__", "node_modules"):
                    continue
                update_files.append(item)
        
        if not update_files:
            print("[update] No update files found")
            return False
        
        # Create backup first
        backup_path = create_backup()
        
        # Copy update files
        for src_file in update_files:
            # Calculate relative path
            try:
                rel_path = src_file.relative_to(extract_path)
            except ValueError:
                continue
            
            # Skip first directory (GitHub archives have a root folder)
            parts = list(rel_path.parts)
            if len(parts) > 1:
                parts = parts[1:]
            
            if not parts:
                continue
            
            dest_file = PROJECT_ROOT.joinpath(*parts)
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src_file, dest_file)
        
        # Update version file
        save_version(
            update_info["latest_version"],
            update_info.get("changelog", "")
        )
        
        print(f"[update] Updated to version {update_info['latest_version']}")
        return True
        
    except Exception as exc:
        print(f"[update] Installation failed: {exc}")
        return False


def cleanup_temp():
    """Vaqtinchalik fayllarni tozalash."""
    temp_dirs = ["temp_update", "downloads"]
    for dir_name in temp_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
            except Exception:
                pass


# ---------------------------------------------------------------- #
# Update Log
# ---------------------------------------------------------------- #

def log_update(version: str, action: str, success: bool):
    """Update logini yozish."""
    UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "version": version,
        "action": action,
        "success": success,
    }
    
    with open(UPDATE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_update_history(limit: int = 10) -> list:
    """Update tarixini olish."""
    if not UPDATE_LOG.exists():
        return []
    
    history = []
    try:
        with open(UPDATE_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        history.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    
    return history[-limit:]


# ---------------------------------------------------------------- #
# Auto-Check on Startup
# ---------------------------------------------------------------- #

def auto_check_on_startup():
    """Igris ishga tushganda avtomatik tekshirish."""
    # Check if auto-check is enabled
    auto_check = os.environ.get("IGRIS_AUTO_UPDATE_CHECK", "true").lower() == "true"
    
    if not auto_check:
        return
    
    # Check when last checked
    last_check_file = PROJECT_ROOT / ".last_update_check"
    check_interval = 24 * 60 * 60  # 24 hours
    
    if last_check_file.exists():
        try:
            last_check = float(last_check_file.read_text().strip())
            if time.time() - last_check < check_interval:
                return  # Checked recently
        except Exception:
            pass
    
    # Perform check
    try:
        check_for_updates(auto_check=True)
        last_check_file.write_text(str(time.time()))
    except Exception:
        pass  # Silent fail for auto-check


# ---------------------------------------------------------------- #
# CLI Interface
# ---------------------------------------------------------------- #

def main():
    """CLI uchun asosiy funksiya."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IGRIS Update Checker")
    parser.add_argument("command", choices=["check", "history", "backup", "version"],
                       help="Command to run")
    parser.add_argument("--auto", action="store_true",
                       help="Auto-update mode")
    parser.add_argument("--download", action="store_true",
                       help="Download update")
    parser.add_argument("--install", action="store_true",
                       help="Install update")
    
    args = parser.parse_args()
    
    if args.command == "check":
        update_info = check_for_updates(auto_check=args.auto)
        if update_info and args.download:
            download_path = download_update(update_info)
            if download_path and args.install:
                extract_path = extract_update(download_path)
                if extract_path:
                    install_update(extract_path, update_info)
                    cleanup_temp()
    
    elif args.command == "history":
        history = get_update_history()
        if not history:
            print("[update] No update history found")
        else:
            print("\n[update] Update History:")
            for entry in history:
                status = "OK" if entry.get("success") else "FAILED"
                print(f"  [{status}] {entry['timestamp'][:10]} - {entry['action']} v{entry['version']}")
    
    elif args.command == "backup":
        backup_path = create_backup()
        if backup_path:
            print(f"[update] Backup created: {backup_path}")
    
    elif args.command == "version":
        version = get_current_version()
        print(f"[update] Current version: {version}")


if __name__ == "__main__":
    main()
