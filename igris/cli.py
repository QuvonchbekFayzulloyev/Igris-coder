"""
igris.cli
---------
Entry point for the "one install, many projects" workflow:

    igris new <name>            create projects/<name>/ inside igris-cli, make it active
    igris use <name>            switch the active project
    igris projects              list projects, marking the active one
    igris                       interactive REPL against the active project
    igris -p "do X"             one-shot ("print") mode against the active project
    igris --project X -p "..."  one-off run against a specific project (also sets it active)
    igris --debug                trace every mini-loop stage

Every task -- filesystem edits, terminal commands, git operations -- runs
sandboxed to projects/<active>/, regardless of the directory you launched
`igris` from. See igris/workspace.py for the resolution rules.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.markdown import Markdown

from . import workspace
from .config import Config
from .memory import Memory
from .core.context_engine import ContextEngine
from .core.gateway import build_llm
from .core.intent_resolver import IntentResolver
from .core.mcp_manager import MCPManager
from .core.reprompt_loop import RepromptLoop
from .core.skill_loader import SkillLoader

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="igris", description="Local Claude-Code-style agent over Ollama")
    sub = parser.add_subparsers(dest="command")

    new_p = sub.add_parser("new", help="Create a new project under projects/ and make it active")
    new_p.add_argument("name")

    use_p = sub.add_parser("use", help="Switch the active project")
    use_p.add_argument("name")

    sub.add_parser("projects", help="List projects under projects/, marking the active one")

    seed_p = sub.add_parser("seed-knowledge", help="Embed and store igris's own knowledge-base seed content for the active project")
    # default=SUPPRESS (not None): if --project isn't given after the
    # subcommand, this must not touch args.project at all, or it would
    # silently clobber a value already parsed from `igris --project X
    # seed-knowledge` (top-level position) back to None -- confirmed by
    # testing both orderings before landing on this fix.
    seed_p.add_argument("--project", default=argparse.SUPPRESS, help="Seed this project instead of the active one")

    collect_p = sub.add_parser(
        "collect-memory",
        help="Collect stable project docs, configs, ADRs, and folder structure into reusable Coder Memory",
    )
    collect_p.add_argument("--project", default=argparse.SUPPRESS, help="Collect from this project instead of the active one")
    collect_p.add_argument("--max-files", type=int, default=80, help="Maximum documentation/config files to ingest")

    parser.add_argument("-p", "--prompt", help="One-shot prompt (non-interactive)")
    parser.add_argument("--project", help="Run against this project for this call (also sets it active)")
    parser.add_argument("--provider", choices=["ollama", "lmstudio", "openrouter"], help="Override gateway.provider")
    parser.add_argument("--model", help="Override the configured model for the active provider")
    parser.add_argument("--debug", action="store_true", help="Print every mini-loop stage")
    return parser


def _cmd_new(name: str) -> int:
    path = workspace.create_project(name)
    config = Config.load(project_root=path)
    created = config.ensure_project_scaffold()
    workspace.set_active_project(name)

    console.print(f"[green]Created project '{name}'[/green] at {path}")
    for c in created:
        console.print(f"  {c}")
    console.print(f"[dim]Active project set to '{name}'[/dim]")
    return 0


def _cmd_use(name: str) -> int:
    if not workspace.project_exists(name):
        console.print(f"[red]Project '{name}' not found.[/red] Run: igris new {name}")
        return 1
    workspace.set_active_project(name)
    console.print(f"[green]Active project set to '{name}'[/green]")
    return 0


def _cmd_projects() -> int:
    active = workspace.get_active_project()
    names = workspace.list_projects()
    if not names:
        console.print("[dim]No projects yet. Create one with: igris new <name>[/dim]")
        return 0
    for n in names:
        marker = "[bold green]*[/bold green]" if n == active else " "
        console.print(f"{marker} {n}")
    return 0


def _cmd_seed_knowledge(explicit_project: str | None) -> int:
    from .core.embeddings import EmbeddingClient
    from .core.knowledge_base import KnowledgeStore
    from .core.knowledge_seed import SEED_ENTRIES, seed_all

    try:
        project_root = workspace.resolve_project_root(explicit_project)
    except workspace.NoProjectSelected as e:
        console.print(f"[yellow]{e}[/yellow]")
        return 1

    config = Config.load(project_root=project_root)
    if not config.igris_dir.exists():
        config.ensure_project_scaffold()

    store = KnowledgeStore(config)
    embedder = EmbeddingClient(config)

    console.print(f"Seeding {len(SEED_ENTRIES)} knowledge entries via {embedder.model} at {embedder.host}...")

    def on_progress(i, total, seed, error):
        if error:
            console.print(f"  [red]\u2717[/red] [{i}/{total}] {seed.module_path or 'project'}: {error}")
        else:
            console.print(f"  [green]\u2713[/green] [{i}/{total}] {seed.module_path or 'project'}: {seed.text[:60]}...")

    succeeded, failed = asyncio.run(seed_all(store, embedder, on_progress=on_progress))

    console.print(f"\n[green]{succeeded} added[/green], [red]{failed} failed[/red] out of {len(SEED_ENTRIES)}.")
    if failed:
        console.print("[yellow]Failures usually mean Ollama isn't running or the embedding model isn't pulled:[/yellow]")
        console.print(f"  ollama pull {embedder.model}")
    return 1 if failed and not succeeded else 0


def _cmd_collect_memory(explicit_project: str | None, max_files: int) -> int:
    from .core.coder_memory import ProjectMemoryCollector

    try:
        project_root = workspace.resolve_project_root(explicit_project)
    except workspace.NoProjectSelected as e:
        console.print(f"[yellow]{e}[/yellow]")
        return 1
    config = Config.load(project_root=project_root)
    config.ensure_project_scaffold()
    try:
        result = ProjectMemoryCollector(config).collect(max_files=max(1, min(max_files, 200)))
    except (OSError, ValueError) as e:
        console.print(f"[red]Coder Memory collection failed:[/red] {e}")
        return 1
    console.print(
        f"[green]Coder Memory collected:[/green] {result['added']} added, "
        f"{result['updated']} updated, {result['skipped']} skipped."
    )
    return 0


def _build_pipeline(config: Config):
    memory = Memory(config)
    context_engine = ContextEngine(config, memory)
    llm = build_llm(config)
    intent_resolver = IntentResolver(config, llm=llm)
    skills = SkillLoader(config)
    return memory, context_engine, llm, intent_resolver, skills


async def _run_once(config: Config, prompt: str) -> None:
    memory, context_engine, llm, intent_resolver, skills = _build_pipeline(config)

    async with MCPManager(config) as mcp:
        loop = RepromptLoop(config, llm, mcp, skills, context_engine, intent_resolver, memory)
        result = await loop.run(prompt)

    if result.needs_clarification:
        console.print(f"[yellow]?[/yellow] {result.clarifying_question}")
    else:
        console.print(Markdown(result.final_response))


async def _repl(config: Config) -> None:
    memory, context_engine, llm, intent_resolver, skills = _build_pipeline(config)

    provider = config.get("gateway.provider", "ollama")
    console.print("[bold cyan]igris[/bold cyan] -- local agent (Ctrl+C to exit)")
    console.print(f"project={config.project_root.name}  provider={provider}  model={config.get(f'{provider}.model')}\n")

    async with MCPManager(config) as mcp:
        loop = RepromptLoop(config, llm, mcp, skills, context_engine, intent_resolver, memory)
        while True:
            try:
                user_input = console.input("[bold green]>[/bold green] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nbye")
                break
            if not user_input.strip():
                continue
            if user_input.strip() in ("/exit", "/quit"):
                break

            with console.status("[dim]thinking...[/dim]"):
                result = await loop.run(user_input)

            if result.needs_clarification:
                console.print(f"[yellow]?[/yellow] {result.clarifying_question}")
            else:
                console.print(Markdown(result.final_response))
                console.print()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "new":
        return _cmd_new(args.name)
    if args.command == "use":
        return _cmd_use(args.name)
    if args.command == "projects":
        return _cmd_projects()
    if args.command == "seed-knowledge":
        return _cmd_seed_knowledge(getattr(args, "project", None))
    if args.command == "collect-memory":
        return _cmd_collect_memory(getattr(args, "project", None), args.max_files)

    try:
        project_root = workspace.resolve_project_root(args.project)
    except workspace.NoProjectSelected as e:
        console.print(f"[yellow]{e}[/yellow]")
        return 1

    config = Config.load(project_root=project_root)
    config.ensure_project_scaffold()  # auto-heal + add missing bundled MCPs/skills safely

    if args.provider:
        config.data["gateway"]["provider"] = args.provider
    if args.model:
        config.data[config.get("gateway.provider", "ollama")]["model"] = args.model
    if args.debug:
        config.data["loop"]["trace"] = True

    if args.prompt:
        asyncio.run(_run_once(config, args.prompt))
    else:
        asyncio.run(_repl(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
