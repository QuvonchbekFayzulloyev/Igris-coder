"""
igris.core.knowledge_seed
----------------------------
Seed content for igris's own hierarchical knowledge base: real,
project-specific rules, descriptions, and code templates -- not generic
boilerplate. Every entry states something specific enough to be wrong if
the project changes, which is what makes it useful as grounding context
during the reprompt loop (see context_engine.py's gather()).

Sources are honest about provenance:
    manual        -- a fact about THIS project's actual design decisions,
                      known directly from building it, not general recall
    web_verified   -- checked against a real, current external source
                      during this seed's authoring (see the entry itself
                      for what was verified and when)
    llm            -- general software-engineering convention recalled
                      from training, not project-specific and not
                      independently re-checked

Run `igris seed-knowledge` to embed and store all of these against the
active project (requires a running Ollama with the embeddings model
pulled -- see embeddings.py).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SeedEntry:
    module_path: str
    kind: str  # rule | description | template
    source: str  # manual | web_verified | llm
    tags: list[str]
    text: str


SEED_ENTRIES: list[SeedEntry] = [
    # ---------------------------------------------------------------- project
    SeedEntry("", "description", "manual", ["architecture"],
        "igris is a local Claude-Code-style agent: a Python backend "
        "(FastAPI + MCP tool-calling) with an optional Tauri+React desktop "
        "UI, organized as one CLI install containing a projects/ folder -- "
        "each project gets its own .igris/ config, not a separate "
        "top-level install per project."),
    SeedEntry("", "rule", "manual", ["windows", "shell"],
        "Windows-first policy: default shell is PowerShell, WSL is never "
        "chosen automatically by any tool (terminal_server.py's "
        "shell='auto') -- only used if explicitly requested."),
    SeedEntry("", "description", "manual", ["reprompt-loop"],
        "The reprompt loop (RepromptLoop) always runs before any raw user "
        "message reaches the LLM: snapshot -> intent classify -> clarify/"
        "assume gate -> complexity analysis -> loop template selection -> "
        "skill routing -> context gather -> spec synthesis -> execute -> "
        "self-review. The model never sees the raw request alone."),
    SeedEntry("", "rule", "manual", ["intent", "human-in-the-loop"],
        "Intent confidence has two thresholds: below "
        "hard_block_confidence_threshold (0.35) igris asks a clarifying "
        "question; between that and clarify_confidence_threshold (0.55) "
        "igris proceeds but states its assumption explicitly; at or above "
        "0.55 it proceeds silently."),
    SeedEntry("", "rule", "manual", ["gateway", "providers"],
        "gateway.provider in .igris/config.yaml selects the active LLM "
        "backend: ollama (default, local), lmstudio (local, OpenAI-"
        "compatible), or openrouter (hosted, needs an API key). All three "
        "implement the same chat()/run_with_tools() interface returning a "
        "shared ChatResult."),
    SeedEntry("", "description", "web_verified", ["embeddings", "ollama"],
        "Ollama's local embedding model nomic-embed-text is ~274MB, "
        "~137M parameters, loads into VRAM in about a second, and runs "
        "even CPU-only -- comfortably under 8GB VRAM. The current batch-"
        "capable endpoint is POST /api/embed (input: string|list of "
        "strings, returns embeddings: list of vectors); the older POST "
        "/api/embeddings (prompt: string, returns embedding: one vector) "
        "is still supported but singular-input only."),

    # ---------------------------------------------------------------- backend
    SeedEntry("backend", "rule", "manual", ["providers", "interface"],
        "Every LLM provider (OllamaClient, OpenAICompatibleClient) must "
        "implement async chat(messages, tools) and async run_with_tools"
        "(system_prompt, user_prompt, mcp_manager, max_iterations, "
        "on_tool_call) returning a shared ChatResult (content, tool_calls, "
        "prompt_tokens, completion_tokens, used_fallback_parsing, "
        "tool_iterations)."),
    SeedEntry("backend", "rule", "manual", ["tool-calling", "fallback"],
        "Models that don't populate a real tool_calls field (e.g. "
        "qwen2.5-coder printing {\"name\":...,\"arguments\":...} as plain "
        "text) are recovered via _extract_fallback_tool_calls in "
        "llm_common.py -- every provider's run_with_tools loop must check "
        "for this fallback before treating a response as final content."),
    SeedEntry("backend", "rule", "manual", ["cost", "honesty"],
        "Cost estimation is opt-in and honest: local providers always "
        "report $0.00; OpenRouter cost is computed only from explicitly "
        "configured openrouter.price_per_1k_*_tokens rates, never a "
        "hardcoded price table (see igris/core/cost.py)."),
    SeedEntry("backend", "description", "manual", ["testing"],
        "Backend testing convention: pytest, async tests via "
        "asyncio.run(), MockLLM (tests/mock_llm.py) stands in for any "
        "provider by implementing the same chat()/run_with_tools() "
        "interface. Real MCP servers are spawned as real subprocesses in "
        "integration tests (via MCPManager), not mocked, when testing MCP "
        "tool behavior itself."),

    # ----------------------------------------------------------- backend.core
    SeedEntry("backend.core", "description", "manual", ["loop-generator"],
        "loop_generator.py maps intent category + complexity tier to a "
        "stage-sequence template (e.g. bug_fix -> Observe/Locate/"
        "Hypothesis/Patch/Test); for complexity=multi_agent it instead "
        "produces independent per-subsystem branches run concurrently via "
        "execution_graph.py's ExecutionGraph (asyncio.gather per "
        "topological layer)."),
    SeedEntry("backend.core", "description", "manual", ["task-analyzer"],
        "task_analyzer.py classifies complexity as simple/medium/complex/"
        "multi_agent using heuristics: connector count, file-mention "
        "count, architecture-language detection, and (for multi_agent) "
        "two or more named independent subsystems (frontend/backend/"
        "database/testing/deployment)."),
    SeedEntry("backend.core", "description", "manual", ["spec", "reprompt"],
        "TaskSpec (spec.py) is the actual 'reprompt': it bundles the raw "
        "request with category-specific acceptance criteria, global "
        "constraints (Windows-first, English code/docs), the loop "
        "generator's stage guidance, gathered context (git status, file "
        "reads, knowledge base results), and skill guidance -- this whole "
        "structure is what the model sees, never the raw message alone."),
    SeedEntry("backend.core", "rule", "manual", ["self-review"],
        "Self-review (RepromptLoop._self_review) is a single LLM-as-judge "
        "call per attempt: forces a PASS/FAIL first line plus one "
        "feedback sentence, bounded by loop.max_review_iterations so it "
        "can never retry forever."),
    SeedEntry("backend.core", "template", "manual", ["loop-generator", "stage-template"],
        "Adding a new stage template to loop_generator.py: add an entry "
        "to STAGE_TEMPLATES keyed by the intent category, e.g. "
        "STAGE_TEMPLATES['research'] = ['Collect', 'Analyze', 'Compare', "
        "'Reason', 'Find Gap']. For a category that should fan out into "
        "parallel subsystem branches, add its keyword patterns to "
        "task_analyzer.py's SUBSYSTEM_KEYWORDS instead, and a matching "
        "entry in loop_generator.py's SUBSYSTEM_TEMPLATES."),

    # --------------------------------------------------- backend.mcp_servers
    SeedEntry("backend.mcp_servers", "rule", "manual", ["mcp", "cwd"],
        "All MCP servers use the official mcp Python SDK's FastMCP class, "
        "spawned by MCPManager over stdio with cwd pinned to the resolved "
        "project root (StdioServerParameters(cwd=...)) -- never relying "
        "on inherited cwd from wherever `igris` itself was launched."),
    SeedEntry("backend.mcp_servers", "rule", "manual", ["filesystem", "safety"],
        "filesystem_server.py resolves every path against ROOT and "
        "refuses anything outside it (path traversal guard); delete_path "
        "requires an explicit confirm=true parameter enforced in code, "
        "not just documented, per agent-safety-boundaries."),
    SeedEntry("backend.mcp_servers", "rule", "manual", ["terminal", "windows"],
        "terminal_server.py's shell='auto' resolves to PowerShell/pwsh on "
        "Windows and bash only on non-Windows hosts or when WSL is "
        "explicitly requested -- WSL is never the automatic default."),
    SeedEntry("backend.mcp_servers", "rule", "manual", ["reliability", "errors"],
        "Tool functions must never let an unhandled exception propagate "
        "to the MCP transport layer -- wrap failure-prone calls (e.g. "
        "embedding requests) and return a clear 'ERROR: ...' string the "
        "model can read and self-correct from, per tool-call-reliability."),
    SeedEntry("backend.mcp_servers", "template", "manual", ["mcp", "fastmcp"],
        "Minimal FastMCP tool pattern used throughout this project:\n"
        "@mcp.tool()\n"
        "async def my_tool(arg: str, confirm: bool = False) -> str:\n"
        '    """One-line description the model reads to decide when to call this."""\n'
        "    if is_destructive and not confirm:\n"
        '        return "REFUSED: pass confirm=true to proceed."\n'
        "    try:\n"
        "        result = await do_the_thing(arg)\n"
        '        return f"OK: {result}"\n'
        "    except ExpectedFailureType as e:\n"
        '        return f"ERROR: {e}"'),

    # ----------------------------------------------------- backend.providers
    SeedEntry("backend.providers", "description", "manual", ["openai-compatible"],
        "OpenAICompatibleClient (providers/openai_compatible.py) is "
        "shared by both LM Studio and OpenRouter since they speak the "
        "same protocol; the only differences are base_url, whether an "
        "api_key/auth header is required, and default model."),
    SeedEntry("backend.providers", "rule", "manual", ["tool-calls", "protocol"],
        "Tool-call responses in the OpenAI protocol must echo back "
        "tool_calls[i].id as tool_call_id on the following 'tool' role "
        "message -- Ollama's protocol doesn't require this, OpenAI's "
        "does. Missing this breaks multi-turn tool calling silently on "
        "OpenRouter/LM Studio."),
    SeedEntry("backend.providers", "rule", "manual", ["gateway"],
        "gateway.py's build_llm(config) is the only place that should "
        "ever choose a provider class -- everything downstream "
        "(RepromptLoop, server.py, cli.py) depends only on the shared "
        "chat()/run_with_tools() interface, never imports a specific "
        "provider directly."),

    # -------------------------------------------------------- backend.server
    SeedEntry("backend.server", "description", "manual", ["fastapi", "websocket"],
        "server.py is the FastAPI+WebSocket bridge for the desktop UI: "
        "REST endpoints for state (projects/skills/mcp-tools/settings), "
        "one streaming WebSocket (/ws/chat) that emits one JSON stage "
        "event per RepromptLoop pipeline stage via an on_stage callback, "
        "then a final event with the response plus prompt_tokens/"
        "completion_tokens/cost_usd."),
    SeedEntry("backend.server", "rule", "manual", ["csp", "cors", "tauri"],
        "CORS in server.py is scoped to known dev/Tauri origins "
        "(localhost:5173, tauri://localhost, http://tauri.localhost) -- "
        "tauri.conf.json's security.csp connect-src must list the exact "
        "same backend host:port or the frontend's fetch/WebSocket calls "
        "will be silently blocked by the webview, not the server."),

    # --------------------------------------------------------------- frontend
    SeedEntry("frontend", "description", "manual", ["design-tokens"],
        "Design tokens (desktop/tailwind.config.js): bg #FFFFFF, blue "
        "#1D5FD6 (interactive accent), green #1FA463 / green-dark #0B4D33 "
        "(state/methodology), Segoe UI for UI text (Windows-first, no web "
        "font fetch needed), Cascadia Code for monospace/logs (ships with "
        "Windows Terminal)."),
    SeedEntry("frontend", "rule", "manual", ["api-client", "layering"],
        "Every network call (fetch or WebSocket) must go through "
        "desktop/src/lib/api.ts -- no component calls fetch/WebSocket "
        "directly. Enforced by convention, not code, so review new "
        "components for direct fetch() calls (see "
        "architecture-layer-classification's violation check)."),
    SeedEntry("frontend", "rule", "manual", ["react", "effects", "testing"],
        "Async effects that call setState must guard against post-"
        "unmount execution with a cancelled/active flag -- found via "
        "component tests raising React act() warnings, not by "
        "inspection; see App.tsx's mount-time effects and SettingsPanel's "
        "load effect."),
    SeedEntry("frontend", "description", "manual", ["testing"],
        "Frontend testing convention: Vitest + jsdom + @testing-library/"
        "react + user-event; WebSocket-driven components are tested with "
        "a hand-rolled FakeWebSocket class (static .OPEN/.CLOSED "
        "constants, .emit() helper) since jsdom has no real WebSocket "
        "implementation -- see ui-component-testing skill."),

    # ------------------------------------------------------ frontend.components
    SeedEntry("frontend.components", "rule", "manual", ["usability", "keyboard"],
        "Every interactive control needs a keyboard path and a clear "
        "disabled state with a stated reason (see Conversation.tsx's "
        "disabledReason prop) -- a disabled button with no explanation is "
        "a usability gap, not acceptable polish debt (desktop-ux-"
        "usability-audit)."),
    SeedEntry("frontend.components", "description", "manual", ["loop-tracker"],
        "The Loop panel (LoopTracker.tsx) is the product's signature UI "
        "element: it renders StageEvent[] as an ordered, live-updating "
        "timeline as the WebSocket streams them, making the reprompt "
        "loop's normally-invisible reasoning process visible."),
    SeedEntry("frontend.components", "template", "manual", ["component", "pattern"],
        "Standard component shape used throughout desktop/src/components: "
        "props interface first, then the component function, styled with "
        "Tailwind utility classes only (no inline style objects), "
        "network/state operations delegated to props (callbacks) rather "
        "than the component calling lib/api.ts itself -- keeps components "
        "unit-testable with plain prop mocks, no fetch mocking needed at "
        "that layer."),

    # ------------------------------------------------------------ frontend.lib
    SeedEntry("frontend.lib", "rule", "manual", ["api-client", "websocket"],
        "api.ts's openChatSocket() wraps the raw WebSocket and exposes "
        "only send()/close()/raw -- callers drive it via onEvent "
        "callbacks dispatching on a discriminated union WsEvent (stage | "
        "final | error), never by inspecting raw.readyState directly "
        "outside api.ts itself."),
]


async def seed_all(store, embedder, on_progress=None) -> tuple[int, int]:
    """
    Embeds and stores every entry in SEED_ENTRIES. Returns (succeeded,
    failed) counts. on_progress, if given, is called as
    on_progress(index, total, entry, error_or_None) after each attempt --
    used by `igris seed-knowledge` to print progress without this
    function knowing anything about the CLI.
    """
    from .knowledge_base import KnowledgeEntry
    import time
    import uuid

    succeeded = 0
    failed = 0
    total = len(SEED_ENTRIES)

    for i, seed in enumerate(SEED_ENTRIES, start=1):
        error = None
        try:
            vector = await embedder.embed_one(seed.text)
            if not vector:
                raise RuntimeError("embedding model returned no vector")
            store.add(KnowledgeEntry(
                id=str(uuid.uuid4())[:8],
                text=seed.text,
                module_path=seed.module_path,
                kind=seed.kind,
                source=seed.source,
                tags=seed.tags,
                embedding=vector,
                created_at=time.time(),
            ))
            succeeded += 1
        except Exception as e:  # noqa: BLE001 -- report every failure, don't let one entry abort the batch
            failed += 1
            error = str(e)

        if on_progress:
            on_progress(i, total, seed, error)

    return succeeded, failed
