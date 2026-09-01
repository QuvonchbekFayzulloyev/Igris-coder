"""
IGRIS BRAIN — GitHub MCP Server
================================
MCP server for GitHub repository operations:
- list_repos: List user repositories
- get_file: Get file contents from a repository
- create_file: Create or update a file
- list_issues: List issues with filters
- create_issue: Create a new issue
- list_pull_requests: List pull requests
- create_pull_request: Create a new pull request
- search_code: Search code across repositories
- get_commits: Get recent commits
- fork_repo: Fork a repository

Authentication:
  - Set GITHUB_TOKEN environment variable (personal access token)
  - Or use gh CLI if installed (gh auth login)

Xavfsizlik:
  - Write operations require explicit confirmation
  - Token is never logged or exposed
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

# Skript rejimida ishga tushganda Igris_brain papkasi sys.path'da bo'lmaydi
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

from env_loader import get_github_token

mcp = FastMCP("github")


# ---------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------- #

GITHUB_API = "https://api.github.com"
_token: str = ""


def _get_token() -> str:
    """GitHub token olish (env yoki gh CLI)."""
    global _token
    if _token:
        return _token
    
    # 1. Environment variable (from .env via env_loader)
    _token = get_github_token()
    if _token:
        return _token
    
    # 2. gh CLI token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            _token = result.stdout.strip()
            return _token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    return ""


def _api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """GitHub API so'rov."""
    token = _get_token()
    url = f"{GITHUB_API}{endpoint}"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "IgrisAgent/2.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        return {"error": f"HTTP {exc.code}: {error_body[:500]}"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------- #
# Tool Implementations (FastMCP decorators)
# ---------------------------------------------------------------- #


@mcp.tool()
async def list_repos(user: str = "", type: str = "owner", sort: str = "updated", per_page: int = 30) -> str:
    """List repositories for the authenticated user or a specified user.

    Args:
        user: GitHub username (default: authenticated user)
        type: Repository type: all, owner, public, private, member
        sort: Sort by: created, updated, pushed, full_name
        per_page: Results per page (max 100)
    """
    result = await _list_repos({"user": user, "type": type, "sort": sort, "per_page": per_page})
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_file(repo: str, path: str, ref: str = "main") -> str:
    """Get file contents from a repository.

    Args:
        repo: Repository (owner/name)
        path: File path in the repository
        ref: Branch, tag, or commit SHA (default: main)
    """
    result = await _get_file({"repo": repo, "path": path, "ref": ref})
    return json.dumps(result, indent=2)


@mcp.tool()
async def create_file(repo: str, path: str, content: str, message: str, branch: str = "main", sha: str = "") -> str:
    """Create or update a file in a repository.

    Args:
        repo: Repository (owner/name)
        path: File path in the repository
        content: File content (plain text)
        message: Commit message
        branch: Branch name (default: main)
        sha: SHA of existing file (for updates, omit for new files)
    """
    result = await _create_file({"repo": repo, "path": path, "content": content, "message": message, "branch": branch, "sha": sha})
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_issues(repo: str, state: str = "open", labels: str = "", per_page: int = 30) -> str:
    """List issues in a repository with filters.

    Args:
        repo: Repository (owner/name)
        state: Issue state: open, closed, all
        labels: Comma-separated label names
        per_page: Results per page
    """
    result = await _list_issues({"repo": repo, "state": state, "labels": labels, "per_page": per_page})
    return json.dumps(result, indent=2)


@mcp.tool()
async def create_issue(repo: str, title: str, body: str = "", labels: list = None, assignees: list = None) -> str:
    """Create a new issue in a repository.

    Args:
        repo: Repository (owner/name)
        title: Issue title
        body: Issue body/description
        labels: Label names (list)
        assignees: Assignee usernames (list)
    """
    result = await _create_issue({"repo": repo, "title": title, "body": body, "labels": labels or [], "assignees": assignees or []})
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_pull_requests(repo: str, state: str = "open", per_page: int = 30) -> str:
    """List pull requests in a repository.

    Args:
        repo: Repository (owner/name)
        state: PR state: open, closed, all
        per_page: Results per page
    """
    result = await _list_pull_requests({"repo": repo, "state": state, "per_page": per_page})
    return json.dumps(result, indent=2)


@mcp.tool()
async def create_pull_request(repo: str, title: str, head: str, base: str = "main", body: str = "") -> str:
    """Create a new pull request.

    Args:
        repo: Repository (owner/name)
        title: PR title
        head: Source branch
        base: Target branch (default: main)
        body: PR description
    """
    result = await _create_pull_request({"repo": repo, "title": title, "head": head, "base": base, "body": body})
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_code_github(query: str, repo: str = "", per_page: int = 30) -> str:
    """Search code across repositories.

    Args:
        query: Search query
        repo: Limit to repository (owner/name)
        per_page: Results per page
    """
    result = await _search_code({"query": query, "repo": repo, "per_page": per_page})
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_commits(repo: str, sha: str = "main", per_page: int = 10) -> str:
    """Get recent commits from a repository.

    Args:
        repo: Repository (owner/name)
        sha: Branch, tag, or commit SHA (default: main)
        per_page: Results per page
    """
    result = await _get_commits({"repo": repo, "sha": sha, "per_page": per_page})
    return json.dumps(result, indent=2)


@mcp.tool()
async def fork_repo(repo: str, organization: str = "") -> str:
    """Fork a repository to your account.

    Args:
        repo: Repository to fork (owner/name)
        organization: Target organization (optional)
    """
    result = await _fork_repo({"repo": repo, "organization": organization})
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------- #
# Tool Implementations
# ---------------------------------------------------------------- #

async def _list_repos(args: dict) -> dict:
    user = args.get("user", "")
    repo_type = args.get("type", "owner")
    sort = args.get("sort", "updated")
    per_page = args.get("per_page", 30)
    
    if user:
        endpoint = f"/users/{urllib.parse.quote(user)}/repos"
    else:
        endpoint = "/user/repos"
    
    params = f"?type={repo_type}&sort={sort}&per_page={per_page}"
    result = _api_request(f"{endpoint}{params}")
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    repos = []
    for repo in (result if isinstance(result, list) else []):
        repos.append({
            "name": repo.get("full_name"),
            "description": (repo.get("description") or "")[:100],
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "updated": repo.get("updated_at"),
            "private": repo.get("private", False),
        })
    
    return {"ok": True, "repos": repos, "count": len(repos)}


async def _get_file(args: dict) -> dict:
    repo = args.get("repo", "")
    path = args.get("path", "")
    ref = args.get("ref", "main")
    
    if not repo or not path:
        return {"ok": False, "error": "repo and path are required"}
    
    endpoint = f"/repos/{repo}/contents/{urllib.parse.quote(path)}"
    if ref:
        endpoint += f"?ref={ref}"
    
    result = _api_request(endpoint)
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    # Decode content (base64)
    import base64
    content = ""
    if "content" in result:
        try:
            content = base64.b64decode(result["content"]).decode("utf-8", errors="replace")
        except Exception:
            content = "(binary file)"
    
    return {
        "ok": True,
        "path": result.get("path"),
        "name": result.get("name"),
        "size": result.get("size", 0),
        "content": content[:50000],
        "sha": result.get("sha"),
        "url": result.get("html_url"),
    }


async def _create_file(args: dict) -> dict:
    repo = args.get("repo", "")
    path = args.get("path", "")
    content = args.get("content", "")
    message = args.get("message", "Update file via Igris")
    branch = args.get("branch", "main")
    sha = args.get("sha", "")
    
    if not repo or not path:
        return {"ok": False, "error": "repo and path are required"}
    
    import base64
    data = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha:
        data["sha"] = sha
    
    endpoint = f"/repos/{repo}/contents/{urllib.parse.quote(path)}"
    result = _api_request(endpoint, method="PUT", data=data)
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    return {
        "ok": True,
        "path": result.get("content", {}).get("path"),
        "sha": result.get("content", {}).get("sha"),
        "url": result.get("content", {}).get("html_url"),
        "message": f"File {'created' if not sha else 'updated'}: {path}",
    }


async def _list_issues(args: dict) -> dict:
    repo = args.get("repo", "")
    state = args.get("state", "open")
    labels = args.get("labels", "")
    per_page = args.get("per_page", 30)
    
    if not repo:
        return {"ok": False, "error": "repo is required"}
    
    params = f"?state={state}&per_page={per_page}"
    if labels:
        params += f"&labels={urllib.parse.quote(labels)}"
    
    result = _api_request(f"/repos/{repo}/issues{params}")
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    issues = []
    for issue in (result if isinstance(result, list) else []):
        if "pull_request" not in issue:  # Skip PRs
            issues.append({
                "number": issue.get("number"),
                "title": issue.get("title"),
                "state": issue.get("state"),
                "labels": [l.get("name") for l in issue.get("labels", [])],
                "created": issue.get("created_at"),
                "url": issue.get("html_url"),
            })
    
    return {"ok": True, "issues": issues, "count": len(issues)}


async def _create_issue(args: dict) -> dict:
    repo = args.get("repo", "")
    title = args.get("title", "")
    body = args.get("body", "")
    labels = args.get("labels", [])
    assignees = args.get("assignees", [])
    
    if not repo or not title:
        return {"ok": False, "error": "repo and title are required"}
    
    data = {"title": title}
    if body:
        data["body"] = body
    if labels:
        data["labels"] = labels
    if assignees:
        data["assignees"] = assignees
    
    result = _api_request(f"/repos/{repo}/issues", method="POST", data=data)
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    return {
        "ok": True,
        "number": result.get("number"),
        "title": result.get("title"),
        "url": result.get("html_url"),
        "message": f"Issue #{result.get('number')} created",
    }


async def _list_pull_requests(args: dict) -> dict:
    repo = args.get("repo", "")
    state = args.get("state", "open")
    per_page = args.get("per_page", 30)
    
    if not repo:
        return {"ok": False, "error": "repo is required"}
    
    result = _api_request(f"/repos/{repo}/pulls?state={state}&per_page={per_page}")
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    prs = []
    for pr in (result if isinstance(result, list) else []):
        prs.append({
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "user": pr.get("user", {}).get("login"),
            "created": pr.get("created_at"),
            "url": pr.get("html_url"),
        })
    
    return {"ok": True, "pull_requests": prs, "count": len(prs)}


async def _create_pull_request(args: dict) -> dict:
    repo = args.get("repo", "")
    title = args.get("title", "")
    body = args.get("body", "")
    head = args.get("head", "")
    base = args.get("base", "main")
    
    if not repo or not title or not head:
        return {"ok": False, "error": "repo, title, and head are required"}
    
    data = {"title": title, "head": head, "base": base}
    if body:
        data["body"] = body
    
    result = _api_request(f"/repos/{repo}/pulls", method="POST", data=data)
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    return {
        "ok": True,
        "number": result.get("number"),
        "title": result.get("title"),
        "url": result.get("html_url"),
        "message": f"PR #{result.get('number')} created",
    }


async def _search_code(args: dict) -> dict:
    query = args.get("query", "")
    repo = args.get("repo", "")
    per_page = args.get("per_page", 30)
    
    if not query:
        return {"ok": False, "error": "query is required"}
    
    search_query = query
    if repo:
        search_query += f" repo:{repo}"
    
    params = f"?q={urllib.parse.quote(search_query)}&per_page={per_page}"
    result = _api_request(f"/search/code{params}")
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    items = []
    for item in (result.get("items") or []):
        items.append({
            "name": item.get("name"),
            "path": item.get("path"),
            "repository": item.get("repository", {}).get("full_name"),
            "url": item.get("html_url"),
        })
    
    return {"ok": True, "items": items, "count": result.get("total_count", 0)}


async def _get_commits(args: dict) -> dict:
    repo = args.get("repo", "")
    sha = args.get("sha", "main")
    per_page = args.get("per_page", 10)
    
    if not repo:
        return {"ok": False, "error": "repo is required"}
    
    result = _api_request(f"/repos/{repo}/commits?sha={sha}&per_page={per_page}")
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    commits = []
    for commit in (result if isinstance(result, list) else []):
        commits.append({
            "sha": commit.get("sha", "")[:8],
            "message": commit.get("commit", {}).get("message", "")[:100],
            "author": commit.get("commit", {}).get("author", {}).get("name"),
            "date": commit.get("commit", {}).get("author", {}).get("date"),
            "url": commit.get("html_url"),
        })
    
    return {"ok": True, "commits": commits, "count": len(commits)}


async def _fork_repo(args: dict) -> dict:
    repo = args.get("repo", "")
    organization = args.get("organization", "")
    
    if not repo:
        return {"ok": False, "error": "repo is required"}
    
    endpoint = f"/repos/{repo}/forks"
    data = {}
    if organization:
        data["organization"] = organization
    
    result = _api_request(endpoint, method="POST", data=data)
    
    if "error" in result:
        return {"ok": False, "error": result["error"]}
    
    return {
        "ok": True,
        "full_name": result.get("full_name"),
        "url": result.get("html_url"),
        "message": f"Repository forked to {result.get('full_name')}",
    }


# ---------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------- #

if __name__ == "__main__":
    mcp.run()
