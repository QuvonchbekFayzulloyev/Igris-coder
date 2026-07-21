"""
igris.workspace
-----------------
Resolves the on-disk layout for the "one install, many projects" workflow:
igris-cli itself contains a projects/ folder, and every task runs scoped
to exactly one project directory inside it -- so filesystem/terminal/git
tools are always sandboxed to projects/<name>/, no matter what directory
you happened to launch `igris` from.

    igris-cli/
      igris/              <- the tool's own code, never touched by tasks
      projects/
        my-app/
          .igris/          <- config.yaml, mcp.json, skills/, memory/
          ...project files the agent creates/edits live here...
        another-app/
          ...
      .active_project      <- plain text file: name of the selected project

Commands:
    igris new <name>       create projects/<name>/, scaffold it, make it active
    igris use <name>       switch the active project
    igris projects         list projects, marking the active one
    igris [--project X] -p "..."   run a task against the active (or given) project
"""
from __future__ import annotations

from pathlib import Path


def workspace_root() -> Path:
    """The igris-cli install directory itself (parent of the igris/ package)."""
    return Path(__file__).resolve().parent.parent


def projects_dir() -> Path:
    d = workspace_root() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _active_project_file() -> Path:
    return workspace_root() / ".active_project"


def list_projects() -> list[str]:
    return sorted(p.name for p in projects_dir().iterdir() if p.is_dir())


def get_active_project() -> str | None:
    f = _active_project_file()
    if not f.exists():
        return None
    name = f.read_text(encoding="utf-8").strip()
    return name or None


def set_active_project(name: str) -> None:
    _active_project_file().write_text(name, encoding="utf-8")


def project_path(name: str) -> Path:
    return projects_dir() / name


def project_exists(name: str) -> bool:
    return project_path(name).is_dir()


class NoProjectSelected(Exception):
    """Raised when a task is requested but there's no unambiguous project to run it in."""


def resolve_project_root(explicit_name: str | None = None) -> Path:
    """
    Decide which project a task should run against, in order:
      1. explicit_name (e.g. --project flag) -- also persists it as active
      2. the persisted active project, if still valid
      3. if exactly one project exists under projects/, auto-select it
      4. otherwise, raise NoProjectSelected with next-step guidance
    """
    if explicit_name:
        if not project_exists(explicit_name):
            raise NoProjectSelected(
                f"Project '{explicit_name}' does not exist. Create it with: igris new {explicit_name}"
            )
        set_active_project(explicit_name)
        return project_path(explicit_name)

    active = get_active_project()
    if active:
        if not project_exists(active):
            raise NoProjectSelected(
                f"Active project '{active}' no longer exists under projects/. "
                f"Run `igris projects` to see what's available, or `igris use <name>`."
            )
        return project_path(active)

    existing = list_projects()
    if len(existing) == 1:
        set_active_project(existing[0])
        return project_path(existing[0])
    if not existing:
        raise NoProjectSelected("No projects yet. Create one with: igris new <project-name>")
    raise NoProjectSelected(
        f"Multiple projects exist ({', '.join(existing)}) and none is active. "
        f"Pick one with: igris use <name>  (or pass --project <name> for a one-off run)"
    )


def create_project(name: str) -> Path:
    path = project_path(name)
    path.mkdir(parents=True, exist_ok=True)
    return path
