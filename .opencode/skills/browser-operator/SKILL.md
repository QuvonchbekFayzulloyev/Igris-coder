# Browser Operator Skill

Persistent browser operating system for AI web interfaces.
Uses Google Chrome via Playwright Python — stays open for the lifetime
of the MCP server. No Node.js bridge, no per-request browser spawn.

## Architecture

```
BrowserRuntime (persistent Chrome process)
  ├── TabManager        — one tab per provider, reused across queries
  ├── SessionManager    — cookie/login health tracking, expiration detection
  ├── ProviderState     — full state machine per provider tab
  ├── DOMIntelligence   — accessibility-tree + multi-strategy element detection
  ├── ChatManager       — conversation create/continue/retry
  ├── DownloadManager   — file download handling
  ├── ArtifactManager   — code/files/images extraction from responses
  └── RecoveryManager   — error recovery, retry, provider switching
```

## Key Design Decisions

1. **Persistent browser** — Chrome stays open across all tool calls. Never
   spawns a new browser per query. Each provider gets one dedicated tab.

2. **Playwright Python** — no Node.js bridge. Direct Python Playwright API
   for lower latency and better error handling.

3. **Goal-oriented selectors** — multiple selector strategies per intent.
   If one breaks (UI change), alternatives are tried automatically.

4. **State machine** — every provider has a tracked session state and chat
   state. Actions check state before executing.

5. **No authentication** — the operator never logs in, never signs up,
   never resets passwords. Only operates already-authenticated sessions.

## Pipeline

```
browser_route(query)          → select providers by query type
browser_state(site, profile)  → verify session for each provider
browser_query(prompt, site)   → typed → submit → wait → extract
browser_research(query, sites) → multi-provider parallel + merge
browser_recover(site)         → rate limited? switch. Error? retry/switch.
browser_action(action, site)  → close tab, refresh, new conversation
browser_memory(site)          → tracked state per provider
```

## Provider State Machine

```
Session: unknown → homepage → login_required → login_page → logged_in
         → rate_limited → temp_error → session_expired → blocked

Chat: idle → thinking → generating → tool_calling → canvas
      → image_generating → file_uploading → finished
      → error → rate_limited → incomplete
```

## Provider Routing

| Type         | Providers                              |
|-------------|----------------------------------------|
| Coding      | ChatGPT, Claude, DeepSeek              |
| Architecture| Claude, ChatGPT                        |
| Images      | ChatGPT, Kimi, Gemini                  |
| Reasoning   | Claude, ChatGPT, Kimi                  |
| Research    | Perplexity, DeepSeek, Grok             |

## Safety (code-enforced)

```
NEVER authenticate users
NEVER create accounts
NEVER delete conversations
NEVER expose credentials
NEVER accept browser permissions
```

## Files

- `igris/mcp_servers/browser_operator_server.py` — MCP server (persistent Chrome)
- `igris/templates/rules/browser_operator.yaml` — operation rules
