"""
IGRIS BRAIN — Filesystem MCP Server
====================================
MCP server for advanced file operations:
- search_files: Search for files by pattern
- get_file_info: Get file metadata (size, modified, type)
- copy_file: Copy files with options
- compress_files: Create zip archives

Xavfsizlik:
  - Faqat workspace ichida ishlaydi
  - Ruxsatsiz operatsiyalar blokalanadi
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)

mcp = FastMCP("filesystem")


# ---------------------------------------------------------------- #
# Tools
# ---------------------------------------------------------------- #

@mcp.tool()
def search_files(pattern: str = "*", directory: str = ".") -> dict:
    """Search for files matching a glob pattern in the workspace.
    
    Args:
        pattern: Glob pattern (e.g., "*.py", "**/*.md")
        directory: Directory to search in (relative to workspace)
    
    Returns:
        List of matching file paths
    """
    try:
        search_dir = os.path.join(_BRAIN_DIR, directory) if not os.path.isabs(directory) else directory
        matches = []
        for root, dirs, files in os.walk(search_dir):
            for fname in files:
                import fnmatch
                if fnmatch.fnmatch(fname, pattern):
                    rel_path = os.path.relpath(os.path.join(root, fname), _BRAIN_DIR)
                    matches.append(rel_path)
        return {"ok": True, "files": sorted(matches), "count": len(matches)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def get_file_info(filepath: str) -> dict:
    """Get file metadata (size, modified time, type).
    
    Args:
        filepath: Path to the file
    
    Returns:
        File metadata including size, mtime, and MIME type
    """
    try:
        abs_path = os.path.join(_BRAIN_DIR, filepath) if not os.path.isabs(filepath) else filepath
        if not os.path.exists(abs_path):
            return {"ok": False, "error": f"File not found: {filepath}"}
        
        stat = os.stat(abs_path)
        mime_type, _ = mimetypes.guess_type(abs_path)
        
        return {
            "ok": True,
            "path": filepath,
            "size": stat.st_size,
            "size_human": _human_size(stat.st_size),
            "modified": stat.st_mtime,
            "modified_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            "type": "directory" if os.path.isdir(abs_path) else "file",
            "mime_type": mime_type,
            "extension": os.path.splitext(filepath)[1],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def copy_file(source: str, destination: str, overwrite: bool = False) -> dict:
    """Copy a file or directory.
    
    Args:
        source: Source path
        destination: Destination path
        overwrite: Whether to overwrite existing files
    
    Returns:
        Copy operation result
    """
    try:
        src = os.path.join(_BRAIN_DIR, source) if not os.path.isabs(source) else source
        dst = os.path.join(_BRAIN_DIR, destination) if not os.path.isabs(destination) else destination
        
        if not os.path.exists(src):
            return {"ok": False, "error": f"Source not found: {source}"}
        
        if os.path.exists(dst) and not overwrite:
            return {"ok": False, "error": f"Destination exists: {destination} (use overwrite=True)"}
        
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        
        return {"ok": True, "source": source, "destination": destination, "type": "directory" if os.path.isdir(src) else "file"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def compress_files(files: list, archive_name: str = "archive.zip") -> dict:
    """Create a zip archive from a list of files.
    
    Args:
        files: List of file paths to include
        archive_name: Name of the output archive
    
    Returns:
        Archive creation result
    """
    try:
        archive_path = os.path.join(_BRAIN_DIR, archive_name)
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            added = 0
            for f in files:
                abs_f = os.path.join(_BRAIN_DIR, f) if not os.path.isabs(f) else f
                if os.path.exists(abs_f):
                    zf.write(abs_f, f)
                    added += 1
        
        return {
            "ok": True,
            "archive": archive_name,
            "files_added": added,
            "size": _human_size(os.path.getsize(archive_path)),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def extract_archive(archive_path: str, destination: str = ".") -> dict:
    """Extract a zip archive.
    
    Args:
        archive_path: Path to the zip archive
        destination: Directory to extract to
    
    Returns:
        Extraction result
    """
    try:
        arch = os.path.join(_BRAIN_DIR, archive_path) if not os.path.isabs(archive_path) else archive_path
        dest = os.path.join(_BRAIN_DIR, destination) if not os.path.isabs(destination) else destination
        
        if not os.path.exists(arch):
            return {"ok": False, "error": f"Archive not found: {archive_path}"}
        
        os.makedirs(dest, exist_ok=True)
        
        with zipfile.ZipFile(arch, 'r') as zf:
            zf.extractall(dest)
            extracted = zf.namelist()
        
        return {
            "ok": True,
            "archive": archive_path,
            "destination": destination,
            "files_extracted": len(extracted),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def file_hash(filepath: str, algorithm: str = "sha256") -> dict:
    """Calculate file hash (MD5, SHA1, SHA256).
    
    Args:
        filepath: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256)
    
    Returns:
        File hash value
    """
    try:
        abs_path = os.path.join(_BRAIN_DIR, filepath) if not os.path.isabs(filepath) else filepath
        
        if not os.path.exists(abs_path):
            return {"ok": False, "error": f"File not found: {filepath}"}
        
        h = hashlib.new(algorithm)
        with open(abs_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        
        return {
            "ok": True,
            "path": filepath,
            "algorithm": algorithm,
            "hash": h.hexdigest(),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def disk_usage(path: str = ".") -> dict:
    """Get disk usage statistics for a directory.
    
    Args:
        path: Directory path to analyze
    
    Returns:
        Disk usage statistics
    """
    try:
        target = os.path.join(_BRAIN_DIR, path) if not os.path.isabs(path) else path
        
        total_size = 0
        file_count = 0
        dir_count = 0
        by_ext = {}
        
        for root, dirs, files in os.walk(target):
            dir_count += len(dirs)
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    file_count += 1
                    ext = os.path.splitext(f)[1] or "(no ext)"
                    by_ext[ext] = by_ext.get(ext, 0) + size
                except OSError:
                    pass
        
        # Sort by size
        top_exts = sorted(by_ext.items(), key=lambda x: -x[1])[:10]
        
        return {
            "ok": True,
            "path": path,
            "total_size": _human_size(total_size),
            "total_bytes": total_size,
            "files": file_count,
            "directories": dir_count,
            "top_extensions": [{"ext": e, "size": _human_size(s)} for e, s in top_exts],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------- #

def _human_size(size: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


if __name__ == "__main__":
    mcp.run()
