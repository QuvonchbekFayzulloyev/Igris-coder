# igris/mcp_servers (backend.mcp_servers)

The data-access/integration layer: the only code in igris that touches
the filesystem, a subprocess shell, git, or (via the knowledge server)
an embedding model directly. Everything here is a real MCP server using
the official `mcp` Python SDK's `FastMCP`, spawned over stdio by
`core/mcp_manager.py`.

## Purpose

Give the model real capabilities without giving the reprompt loop itself
any of that responsibility -- `core/` decides *when* to call a tool,
these files decide *how* the tool actually does its job safely.

## Boundary

- **Every server here is spawned with `cwd` pinned to the resolved
  project root** by `MCPManager` (`StdioServerParameters(cwd=...)`) --
  never relies on inherited cwd from wherever `igris` was launched.
- **Destructive operations require an explicit `confirm=true` parameter
  enforced in code**, not just documented in the tool's docstring (see
  `filesystem_server.py`'s `delete_path`) -- per `agent-safety-
  boundaries`, a description saying "be careful" is not a safety
  boundary.
- **Tool functions never let an unhandled exception reach the MCP
  transport layer.** A failure (bad path, connection refused, timeout)
  must come back as a clear `"ERROR: ..."` string the model can read and
  self-correct from -- per `tool-call-reliability`. This was a real bug,
  not a hypothetical: `knowledge_server.py`'s first version crashed the
  whole tool call on a connection failure instead of returning a clean
  error; see `tests/test_knowledge_server.py`'s regression tests.

## Key files

| File | Tools | Role |
|---|---|---|
| `filesystem_server.py` | read/write/list/search/move/delete | path-traversal-guarded, scoped to the project root |
| `terminal_server.py` | run_command, which, env_info | PowerShell-first (`shell="auto"`); WSL only if explicitly requested, never automatic |
| `git_server.py` | status/diff/log/commit/branch | thin wrapper over the `git` CLI |
| `knowledge_server.py` | knowledge_search, knowledge_add, knowledge_list_modules | the hierarchical project knowledge base, see `../core/knowledge_base.py` |
| `memory_server.py` | memory_collect_project, memory_ingest/search/get, memory_record_lesson | source-backed reusable Coder Knowledge Memory with metadata indexes |
| `sandbox_server.py` | sandbox_create/run_profile/report/discard | isolated source-copy verification with allow-listed profiles; not a hostile-code VM |
| `browser_server.py` | browser_check, browser_user_journey | local Playwright click/fill/assert/screenshot tests; external URLs require explicit opt-in |

## Testing

Two tiers, deliberately: `tests/test_knowledge_server.py` (and similar)
call the `@mcp.tool()`-decorated functions directly (FastMCP leaves them
plain callables) with a mocked embedder -- fast, no subprocess. `tests/
smoke_mcp.py` and `tests/smoke_knowledge_server.py` spawn the *real*
subprocess servers via `MCPManager` and exercise every tool through the
actual MCP protocol -- this is what caught the unhandled-exception bug
above; a mocked-transport test wouldn't have, since the bug was in how
FastMCP's own exception handling surfaced a raw error rather than in the
tool's business logic.

## How this compares

Using MCP specifically (rather than a bespoke function-calling registry)
is a bet that the same servers stay reusable outside igris -- any
MCP-aware client can spawn `filesystem_server.py` on its own. The
narrow-tools-over-one-general-shell design (a `run_command` tool instead
of unrestricted arbitrary execution with no structure) follows the same
least-privilege reasoning `agent-safety-boundaries` lays out generally.
