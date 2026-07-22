"""Browser Operator MCP server — persistent browser operating system.

Architecture:
  BrowserRuntime (persistent Chrome)
    ├── TabManager       — one tab per provider, persistent
    ├── SessionManager   — cookies, login health, expiration tracking
    ├── ProviderState    — detailed state machine per provider tab
    ├── DOMIntelligence  — accessibility tree + multi-strategy element detection
    ├── ChatManager      — conversation create/continue/retry
    ├── DownloadManager  — file download handling
    ├── ArtifactManager  — code/files/images extraction from responses
    └── RecoveryManager  — error recovery, retry, provider switching

Pipeline: Observe → Plan → Act → Verify → Reflect → Return
State machine: per-provider, full lifecycle tracking
Safety: code-enforced rules (no auth, no delete, no expose)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from igris.core.browser_runtime import (
    BrowserRuntime,
    ChatState,
    ProviderTab,
    SessionState,
    SUPPORTED_SITES,
    get_runtime,
)


mcp = FastMCP("browser_operator")
ROOT = Path(__file__).resolve().parents[2]
PROFILES_ROOT = ROOT / ".igris" / "browser-profiles"


# ---------------------------------------------------------------------------
# Provider Capability Registry — delegated to provider_router.py
# ---------------------------------------------------------------------------

from igris.core.provider_router import (
    PROVIDER_CAPABILITIES,
    CAPABILITY_PROVIDERS,
    query_to_capability,
    get_healthy_providers,
    select,
    select_multi,
    mark_failure,
    mark_success,
    clear_health,
    get_decision_path,
    format_decision,
    get_health_summary,
)


# ---------------------------------------------------------------------------
# Provider Router — match query type to best provider
# ---------------------------------------------------------------------------

@mcp.tool()
def browser_route(query: str) -> str:
    """Route a query to the most appropriate AI provider.

    Uses the static Provider Capability Registry — no AI calls, no "can you do this?".
    Only queries the registry. Cached health is checked so rate_limited providers
    are skipped until they recover.

    Returns first 2 healthy providers for the given capability.
    """
    capability = query_to_capability(query)
    providers = get_healthy_providers(capability)
    if not providers:
        providers = CAPABILITY_PROVIDERS.get(capability, [])[:2]
    top2 = select_multi(capability, 2) or providers[:2]
    needs_profile = [p for p in top2 if SUPPORTED_SITES.get(p, {}).get("needs_login")]
    return json.dumps({
        "ok": True,
        "route": {
            "providers": top2,
            "capability": capability,
            "reason": capability,
            "needs_profile": needs_profile,
            "no_login": [p for p in top2 if p not in needs_profile],
            "all_matching": providers,
        }
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 0. Capability Registry — inspect and manage
# ---------------------------------------------------------------------------

@mcp.tool()
def browser_capabilities(site: str = "") -> str:
    """Return the static provider capability registry and cached health.

    Never queries AI. Pure registry lookup. Use this to understand
    which providers can do what, without asking them.
    """
    from igris.core.provider_router import get_capabilities
    if site:
        caps = get_capabilities(site)
        if "error" in caps:
            return json.dumps({"ok": False, "error": caps["error"]})
        return json.dumps({"ok": True, "provider": site, **caps}, ensure_ascii=False)
    registry = get_capabilities()
    return json.dumps({"ok": True, "registry": registry, "capability_map": {k: v for k, v in CAPABILITY_PROVIDERS.items()}}, ensure_ascii=False)


@mcp.tool()
def browser_decision_trace(query: str = "") -> str:
    """Show the full decision trace for a query: how the system chooses which provider.

    Returns capability mapping, candidate providers, health status,
    winner, and fallback chain. Never asks the AI.
    """
    from igris.core.provider_router import get_decision_path
    trace = get_decision_path(query or "")
    return json.dumps({"ok": True, "trace": trace}, ensure_ascii=False)


@mcp.tool()
def browser_clear_health(provider: str = "") -> str:
    """Clear cached health for one or all providers.

    After this, they become 'available' again until the next
    rate_limited or down detection.
    """
    clear_health(provider if provider else None)
    return json.dumps({"ok": True, "cleared": provider or "all"})


# ---------------------------------------------------------------------------
# 1. Check / Status
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_check() -> str:
    """Check Chrome availability and supported providers. Idempotent."""
    try:
        rt = await get_runtime()
        await rt.ensure_browser()
        return json.dumps({
            "ok": True,
            "browser": "chrome",
            "persistent": True,
            "supported_sites": list(SUPPORTED_SITES.keys()),
            "no_login_sites": [k for k, v in SUPPORTED_SITES.items() if not v["needs_login"]],
            "login_required_sites": [k for k, v in SUPPORTED_SITES.items() if v["needs_login"]],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 2. State — check provider session + chat state
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_state(site: str = "chatgpt", profile: str = "") -> str:
    """Check provider session and chat state. Never authenticates.

    Returns: session state (logged_in, login_required, rate_limited, etc.)
    and chat state (idle, generating, finished, error, etc.).
    """
    if site not in SUPPORTED_SITES:
        return json.dumps({"ok": False, "error": f"Unsupported. Options: {list(SUPPORTED_SITES.keys())}"})
    try:
        rt = await get_runtime()
        await rt.ensure_browser(profile)
        tab = await rt.navigate(site)
        session = await rt.detect_session(site)
        chat = await rt.detect_chat_state(site)
        tab.last_verified = time.time()
        return json.dumps({
            "ok": True,
            "site": site,
            "session": session.value,
            "chat_state": chat.value,
            "url": tab.url,
            "title": tab.title,
            "message_count": tab.message_count,
            "error_count": tab.error_count,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 3. Browser Memory — state history per provider
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_memory(site: str = "") -> str:
    """Return tracked browser state per provider.

    Args:
        site: Filter by provider name. Empty returns all.
    """
    rt = await get_runtime()
    if site:
        tab = rt._tabs.get(site)
        data = {site: {"session": tab.session.value, "chat": tab.chat.value, "url": tab.url, "title": tab.title, "message_count": tab.message_count, "error_count": tab.error_count, "last_activity": tab.last_activity}} if tab else {}
    else:
        data = {}
        for name, tab in rt._tabs.items():
            data[name] = {"session": tab.session.value, "chat": tab.chat.value, "url": tab.url, "title": tab.title, "message_count": tab.message_count, "error_count": tab.error_count, "last_activity": tab.last_activity}
    return json.dumps({"ok": True, "memory": data}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. Query — send prompt, wait, extract response
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_query(
    prompt: str,
    site: str = "",
    profile: str = "",
    timeout_seconds: int = 180,
) -> str:
    """Send a prompt to an AI web interface and return the response.

    Uses capability-based provider selection — no "can you do this?" queries.
    If site is empty, auto-selects the best healthy provider for the prompt.
    If the chosen provider is rate_limited, falls back to the next healthy one.

    Browser is persistent — stays open across calls. Each provider
    gets its own tab. Tabs are reused for follow-up queries.

    Rules enforced in code:
    - If login required: returns login_required, does NOT authenticate
    - If rate limited: returns rate_limited, suggest alternatives
    - If browser closed: reconnects automatically

    Args:
        prompt: The question or task.
        site: Provider name (chatgpt, claude, kimi, perplexity, deepseek, gemini, grok).
              Empty string = auto-select best provider for the prompt's capability.
        profile: Chrome user-data-dir path for multi-account sessions.
        timeout_seconds: Max wait for response.
    """
    if not prompt.strip():
        return json.dumps({"ok": False, "error": "prompt is empty"})

    # Auto-select provider if not specified
    if not site:
        capability = query_to_capability(prompt)
        providers = get_healthy_providers(capability)
        if not providers:
            providers = CAPABILITY_PROVIDERS.get(capability, ["perplexity"])
        site = providers[0]
        return await browser_query(prompt=prompt, site=site, profile=profile, timeout_seconds=timeout_seconds)

    if site not in SUPPORTED_SITES:
        return json.dumps({"ok": False, "error": f"Unsupported. Options: {list(SUPPORTED_SITES.keys())}"})

    try:
        rt = await get_runtime()
        await rt.ensure_browser(profile)

        # Navigate first
        await rt.navigate(site)

        # Check session — if login required, return early
        if not rt._tabs.get(site, ProviderTab(site)).login_checked:
            await rt.detect_session(site)
        tab = rt._tabs.get(site)
        if tab and tab.session in (SessionState.LOGIN_REQUIRED, SessionState.LOGIN_PAGE, SessionState.BLOCKED):
            return json.dumps({"ok": False, "error": "login_required", "detail": f"{site} requires login. Use --profile with a valid Chrome user-data-dir."})

        # Execute query
        result = await rt.query(site, prompt, timeout_seconds)

        # Track provider health
        if result.get("ok"):
            mark_success(site)
        elif result.get("error") == "rate_limited":
            mark_failure(site, "rate_limited")
            capability = query_to_capability(prompt)
            fallbacks = get_healthy_providers(capability)
            if fallbacks:
                result["fallback_suggestion"] = fallbacks[0]
                result["fallback_message"] = f"{site} is rate limited. Try {fallbacks[0]} instead."

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 5. Multi-Provider Research — parallel queries + merge
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_research(query: str, sites: str = "", profile: str = "", timeout_seconds: int = 240) -> str:
    """Query multiple providers in parallel and merge results.

    Uses capability-based provider selection. If sites is empty, auto-selects
    healthy providers matching the query's capability. Each provider runs in
    its own persistent tab.

    Args:
        query: Research question.
        sites: Comma-separated providers (perplexity, chatgpt, claude, etc. + local_llm).
               Empty string = auto-select best providers for the query.
        profile: Chrome user-data-dir.
        timeout_seconds: Max total time.
    """
    rt = await get_runtime()
    await rt.ensure_browser(profile)

    # Auto-select providers if not specified
    if not sites:
        capability = query_to_capability(query)
        providers = get_healthy_providers(capability)
        if not providers:
            providers = CAPABILITY_PROVIDERS.get(capability, ["perplexity"])[:2]
        provider_list = providers[:3]
        sites = ",".join(provider_list)
    else:
        provider_list = [s.strip().lower() for s in sites.split(",") if s.strip()]

    async def _query_one(provider: str) -> dict:
        if provider == "local_llm":
            return await _query_local_llm(query)
        if provider not in SUPPORTED_SITES:
            return {"provider": provider, "ok": False, "error": "unsupported"}
        try:
            await rt.navigate(provider)
            result = await rt.query(provider, query, timeout_seconds // max(len(provider_list), 1))
            return {"provider": provider, "ok": result.get("ok", False), "response": result.get("response", ""), "response_length": result.get("response_length", 0), "error": result.get("error", "")}
        except Exception as e:
            return {"provider": provider, "ok": False, "error": str(e)}

    gathered = await asyncio.gather(*[_query_one(p) for p in provider_list])

    responses = []
    for r in gathered:
        if r.get("ok"):
            responses.append({"provider": r["provider"], "ok": True, "response_preview": (r.get("response") or "")[:2000], "response_length": r.get("response_length", 0)})
        else:
            responses.append({"provider": r["provider"], "ok": False, "error": r.get("error", "unknown")})

    return json.dumps({"ok": True, "query": query[:200], "responses": responses, "provider_count": len(responses)}, ensure_ascii=False)


async def _query_local_llm(query: str) -> dict:
    try:
        import httpx
        cfg_path = ROOT / ".igris" / "config.json"
        base_url = "http://127.0.0.1:11434"
        model = "qwen3:4b"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            base_url = cfg.get("model", {}).get("base_url", base_url)
            model = cfg.get("model", {}).get("name", model)
        resp = httpx.post(f"{base_url}/api/chat", json={"model": model, "messages": [{"role": "user", "content": f"Answer concisely: {query}"}], "stream": False}, timeout=60)
        content = resp.json().get("message", {}).get("content", "")
        return {"provider": "local_llm", "ok": True, "response": content[:50000], "response_length": len(content)}
    except Exception as e:
        return {"provider": "local_llm", "ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 6. Recovery — retry with state check, switch provider
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_recover(site: str = "chatgpt", profile: str = "", action: str = "check") -> str:
    """Attempt recovery from a failed browser state.

    Actions:
    - check: inspect current state
    - retry: check state and suggest retry if possible
    - switch: suggest alternative providers
    """
    rt = await get_runtime()
    await rt.ensure_browser(profile)

    if site in rt._tabs:
        await rt.detect_session(site)
        await rt.detect_chat_state(site)
        tab = rt._tabs[site]

        if tab.session == SessionState.RATE_LIMITED or tab.chat == ChatState.RATE_LIMITED:
            mark_failure(site, "rate_limited")
            # Use capability registry for smarter alternative selection
            q = tab.url or ""
            capability = query_to_capability(q) if q else "research"
            alternatives = get_healthy_providers(capability)
            if not alternatives:
                alternatives = [s for s in SUPPORTED_SITES if s != site]
            return json.dumps({"ok": True, "action": "switch", "detail": f"{site} is rate limited", "alternatives": alternatives[:3]}, ensure_ascii=False)

        if tab.session in (SessionState.LOGIN_REQUIRED, SessionState.LOGIN_PAGE):
            return json.dumps({"ok": True, "action": "login_needed", "detail": f"{site} requires login. Provide a Chrome profile."}, ensure_ascii=False)

        if tab.chat == ChatState.ERROR:
            tab.consecutive_errors += 1
            if tab.consecutive_errors >= 3:
                mark_failure(site, "down")
                q = tab.url or ""
                capability = query_to_capability(q) if q else "research"
                alternatives = get_healthy_providers(capability)
                if not alternatives:
                    alternatives = [s for s in SUPPORTED_SITES if s != site]
                return json.dumps({"ok": True, "action": "switch", "detail": f"{site} has {tab.consecutive_errors} consecutive errors", "alternatives": alternatives[:3]}, ensure_ascii=False)
            return json.dumps({"ok": True, "action": "retry", "detail": f"{site} has an error. Retrying may help."}, ensure_ascii=False)

        return json.dumps({"ok": True, "action": "ok", "detail": f"{site} state looks healthy"})

    # No state yet — navigate and check
    try:
        await rt.navigate(site)
        await rt.detect_session(site)
        tab = rt._tabs.get(site)
        return json.dumps({"ok": True, "action": "checked", "session": tab.session.value if tab else "unknown"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 7. Browser Manager — close/reopen tabs
# ---------------------------------------------------------------------------

@mcp.tool()
async def browser_action(action: str = "status", site: str = "", profile: str = "") -> str:
    """Manage browser tabs and sessions.

    Actions:
    - status: show all tabs and their states
    - close_tab: close a specific provider's tab
    - close_all: close all AI provider tabs
    - refresh: reload a provider's page
    - new_conversation: navigate to new chat page

    Args:
        action: Operation to perform.
        site: Provider name (required for close_tab, refresh, new_conversation).
        profile: Chrome user-data-dir.
    """
    rt = await get_runtime()
    await rt.ensure_browser(profile)

    if action == "status":
        tabs_info = {}
        for name, tab in rt._tabs.items():
            tabs_info[name] = {"session": tab.session.value, "chat": tab.chat.value, "url": tab.url, "msg_count": tab.message_count, "errors": tab.error_count}
        return json.dumps({"ok": True, "action": "status", "tabs": tabs_info, "tab_count": len(rt._tabs)}, ensure_ascii=False)

    if action == "close_tab" and site:
        if site in rt._pages:
            try:
                await rt._pages[site].close()
            except Exception:
                pass
            del rt._pages[site]
        rt._tabs.pop(site, None)
        return json.dumps({"ok": True, "action": "close_tab", "site": site}, ensure_ascii=False)

    if action == "close_all":
        for site_name in list(rt._pages.keys()):
            try:
                await rt._pages[site_name].close()
            except Exception:
                pass
        rt._pages.clear()
        rt._tabs.clear()
        return json.dumps({"ok": True, "action": "close_all"}, ensure_ascii=False)

    if action == "refresh" and site:
        if site in rt._pages:
            try:
                await rt._pages[site].reload(timeout=30000)
            except Exception:
                pass
        return json.dumps({"ok": True, "action": "refresh", "site": site}, ensure_ascii=False)

    return json.dumps({"ok": False, "error": f"Unknown action or missing site: action={action}, site={site}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Lifecycle — ensure browser closes on server shutdown
# ---------------------------------------------------------------------------

import atexit

@atexit.register
def _cleanup():
    try:
        import asyncio
        rt = asyncio.run(get_runtime())
        if rt._browser is not None:
            asyncio.run(rt.close())
    except Exception:
        pass


if __name__ == "__main__":
    mcp.run()
