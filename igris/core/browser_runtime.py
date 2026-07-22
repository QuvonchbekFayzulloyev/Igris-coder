"""Shared browser runtime for AI web-site queries.

Extracted from browser_operator_server.py so both the browser-operator and
multi-ai-research MCP servers can use it without maintaining a dead MJS runner.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


SUPPORTED_SITES = {
    "chatgpt":    {"url": "https://chatgpt.com",          "needs_login": True,  "label": "ChatGPT"},
    "claude":     {"url": "https://claude.ai",            "needs_login": True,  "label": "Claude"},
    "kimi":       {"url": "https://kimi.moonshot.cn",     "needs_login": True,  "label": "Kimi"},
    "perplexity": {"url": "https://www.perplexity.ai",    "needs_login": False, "label": "Perplexity"},
    "deepseek":   {"url": "https://chat.deepseek.com",    "needs_login": False, "label": "DeepSeek"},
    "gemini":     {"url": "https://gemini.google.com",    "needs_login": True,  "label": "Gemini"},
    "grok":       {"url": "https://grok.com",             "needs_login": True,  "label": "Grok"},
}


class SessionState(Enum):
    UNKNOWN = "unknown"
    HOMEPAGE = "homepage"
    LOGIN_REQUIRED = "login_required"
    LOGIN_PAGE = "login_page"
    LOGGED_IN = "logged_in"
    RATE_LIMITED = "rate_limited"
    TEMP_ERROR = "temp_error"
    SESSION_EXPIRED = "session_expired"
    BLOCKED = "blocked"


class ChatState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    GENERATING = "generating"
    TOOL_CALLING = "tool_calling"
    CANVAS = "canvas"
    IMAGE_GENERATING = "image_generating"
    FILE_UPLOADING = "file_uploading"
    FINISHED = "finished"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    INCOMPLETE = "incomplete"


@dataclass
class ProviderTab:
    provider: str
    tab_index: int = -1
    session: SessionState = SessionState.UNKNOWN
    chat: ChatState = ChatState.IDLE
    url: str = ""
    title: str = ""
    conversation_id: str = ""
    message_count: int = 0
    last_activity: float = 0.0
    error_count: int = 0
    consecutive_errors: int = 0
    login_checked: bool = False
    last_verified: float = 0.0


_DETECTORS: dict[str, dict[str, list[str]]] = {
    "chatgpt": {
        "logged_in": ["nav", 'a[href*="/g/"]', '[data-testid="conversation-turn"]'],
        "login_required": ['button:has-text("Log in")', 'a[href*="login"]'],
        "input": ["#prompt-textarea", "textarea", '[contenteditable="true"]', 'div[role="textbox"]'],
        "submit": ['button[data-testid*="send"]', 'button[aria-label*="Send"]', 'button:has-text("Send")'],
        "generating": ['.result-streaming', '.typing', '[aria-label*="Stop"]', '[data-testid="stop-button"]'],
        "response": ['[data-message-author-role="assistant"]', 'article', '.markdown', '.prose'],
        "error": ['[role="alert"]', '.error', 'text=rate limited', 'text=too many'],
    },
    "claude": {
        "logged_in": ['nav', '.conversations-list', 'a[href*="/new"]'],
        "login_required": ['button:has-text("Log in")', 'button:has-text("Continue")'],
        "input": ['div[contenteditable="true"]', '[role="textbox"]'],
        "submit": ['button[aria-label*="Send"]', 'button:has-text("Send")'],
        "generating": ['.typing-indicator', '.streaming', '[aria-label*="Stop"]'],
        "response": ['.font-claude-message', '.message', 'article'],
        "error": ['[role="alert"]', 'text=rate limit'],
    },
    "kimi": {
        "logged_in": ['nav', '.chat-list', '.conversation'],
        "login_required": ['button:has-text("登录")', '.login-btn'],
        "input": ["textarea", '#chat-input', '[contenteditable="true"]'],
        "submit": ['button[type="submit"]', 'button:has-text("发送")', '.send-btn'],
        "generating": ['.typing', '.loading-dots', '.generating'],
        "response": ['.message-item', '.chat-message', '.response-content'],
        "error": ['[role="alert"]', '.error-message'],
    },
    "perplexity": {
        "logged_in": ['nav', 'a[href*="/library"]'],
        "login_required": ['button:has-text("Log in")', 'button:has-text("Sign up")'],
        "input": ['textarea[placeholder*="Ask"]', 'input[type="text"]', 'div[contenteditable="true"]'],
        "submit": ['button[aria-label*="Submit"]', 'button[type="submit"]'],
        "generating": ['.streaming', '.typing', '.loading'],
        "response": ['.prose', '.markdown', '[data-testid="answer"]', '.result'],
        "error": ['[role="alert"]', '.error'],
    },
    "deepseek": {
        "logged_in": ['nav', '.conversation-list'],
        "login_required": ['button:has-text("Log in")', 'button:has-text("Sign up")'],
        "input": ["textarea", '#chat-input', '[contenteditable="true"]'],
        "submit": ['button[type="submit"]', 'button:has-text("Send")'],
        "generating": ['.typing', '.streaming'],
        "response": ['.ds-markdown', '.message', 'article'],
        "error": ['[role="alert"]', '.error'],
    },
    "gemini": {
        "logged_in": ['nav', '.conversation-list'],
        "login_required": ['button:has-text("Sign in")', 'a[href*="accounts.google.com"]'],
        "input": ['div[contenteditable="true"]', '[role="textbox"]', "textarea"],
        "submit": ['button[aria-label*="Send"]', 'button:has-text("Send")'],
        "generating": ['.thinking', '.streaming', '.loading'],
        "response": ['.message-content', '.response', '.markdown'],
        "error": ['[role="alert"]', '.error'],
    },
    "grok": {
        "logged_in": ['nav', '.chat-list'],
        "login_required": ['button:has-text("Log in")', 'button:has-text("Sign up")'],
        "input": ['textarea', '[contenteditable="true"]', '[role="textbox"]'],
        "submit": ['button[type="submit"]', 'button:has-text("Send")'],
        "generating": ['.typing', '.streaming', '.generating'],
        "response": ['.message', '.response', '.markdown', 'article'],
        "error": ['[role="alert"]', '.error'],
    },
}


class BrowserRuntime:
    """Persistent Chrome instance — lives for the lifetime of the MCP server."""

    def __init__(self):
        self._browser = None
        self._context = None
        self._playwright = None
        self._tabs: dict[str, ProviderTab] = {}
        self._pages: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._stealth_js = (
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
            "Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });"
        )

    async def ensure_browser(self, profile: str = "") -> None:
        if self._browser is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. "
                "Run: pip install playwright && python -m playwright install chromium"
            )
        self._playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        user_data_dir = None
        if profile:
            p = Path(profile).resolve()
            p.mkdir(parents=True, exist_ok=True)
            user_data_dir = str(p)
        if user_data_dir:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",
                headless=False,
                args=launch_args,
                no_viewport=True,
            )
            self._browser = self._context.browser
        else:
            self._browser = await self._playwright.chromium.launch(
                channel="chrome",
                headless=False,
                args=launch_args,
            )
            self._context = await self._browser.new_context()
            await self._context.add_init_script(self._stealth_js)

    async def get_or_create_tab(self, provider: str) -> tuple[Any, ProviderTab]:
        await self.ensure_browser()
        if provider in self._pages:
            page = self._pages[provider]
            try:
                await page.evaluate("1")
                return page, self._tabs.get(provider, ProviderTab(provider=provider))
            except Exception:
                pass
        tab = self._tabs.get(provider, ProviderTab(provider=provider))
        page = await self._context.new_page()
        await page.add_init_script(self._stealth_js)
        self._pages[provider] = page
        self._tabs[provider] = tab
        return page, tab

    async def navigate(self, provider: str, url: str | None = None) -> ProviderTab:
        page, tab = await self.get_or_create_tab(provider)
        target = url or SUPPORTED_SITES.get(provider, {}).get("url", "")
        if target:
            await page.goto(target, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            tab.url = page.url
            tab.title = await page.title()
            tab.last_activity = time.time()
        return tab

    async def detect_session(self, provider: str) -> SessionState:
        page, tab = await self.get_or_create_tab(provider)
        detect = _DETECTORS.get(provider, {})
        url_lower = page.url.lower()
        if any(w in url_lower for w in ["login", "signin", "auth", "authorize"]):
            tab.session = SessionState.LOGIN_PAGE
        elif any(w in url_lower for w in ["error", "blocked", "denied", "captcha"]):
            tab.session = SessionState.BLOCKED
        elif any(w in url_lower for w in ["rate-limit", "too-many", "429"]):
            tab.session = SessionState.RATE_LIMITED
        if tab.session == SessionState.UNKNOWN:
            logged_in = await self._find_any(page, detect.get("logged_in", []))
            login_req = await self._find_any(page, detect.get("login_required", []))
            if logged_in:
                tab.session = SessionState.LOGGED_IN
            elif login_req:
                tab.session = SessionState.LOGIN_REQUIRED
            else:
                tab.session = SessionState.UNKNOWN
        tab.last_verified = time.time()
        tab.login_checked = True
        return tab.session

    async def detect_chat_state(self, provider: str) -> ChatState:
        page, tab = await self.get_or_create_tab(provider)
        detect = _DETECTORS.get(provider, {})
        generating = await self._find_any(page, detect.get("generating", []))
        error_el = await self._find_any(page, detect.get("error", []))
        input_el = await self._find_any(page, detect.get("input", []))
        if error_el:
            text = await error_el.text_content() or ""
            if re.search(r"rate\s*limit|too\s*many|try\s*again|429|busy|unavailable", text, re.I):
                tab.chat = ChatState.RATE_LIMITED
            else:
                tab.chat = ChatState.ERROR
        elif generating:
            tab.chat = ChatState.GENERATING
        elif input_el:
            tab.chat = ChatState.IDLE
        else:
            tab.chat = ChatState.INCOMPLETE
        return tab.chat

    async def query(self, provider: str, prompt: str, timeout: int = 180) -> dict:
        page, tab = await self.get_or_create_tab(provider)
        detect = _DETECTORS.get(provider, {})
        if not tab.login_checked or time.time() - tab.last_verified > 120:
            await self.detect_session(provider)
        if tab.session in (SessionState.LOGIN_REQUIRED, SessionState.LOGIN_PAGE, SessionState.BLOCKED):
            return {"ok": False, "error": tab.session.value, "detail": f"{provider} is not logged in"}
        await self.detect_chat_state(provider)
        if tab.chat == ChatState.RATE_LIMITED:
            return {"ok": False, "error": "rate_limited", "detail": f"{provider} is rate limited"}
        input_el = await self._find_any(page, detect.get("input", []))
        if not input_el:
            return {"ok": False, "error": "input_not_found", "detail": "Could not locate input field"}
        try:
            await input_el.click()
            await page.wait_for_timeout(500)
            await input_el.fill("")
            await page.wait_for_timeout(200)
            await input_el.type(prompt, delay=20)
        except Exception as e:
            return {"ok": False, "error": "input_failed", "detail": str(e)}
        submit_btn = await self._find_any(page, detect.get("submit", []))
        if submit_btn:
            try:
                await submit_btn.click()
            except Exception:
                await page.keyboard.press("Enter")
        else:
            await page.keyboard.press("Enter")
        tab.chat = ChatState.GENERATING
        tab.last_activity = time.time()
        response_text = await self._wait_for_response(page, provider, timeout)
        tab.last_activity = time.time()
        tab.message_count += 1
        if response_text:
            tab.chat = ChatState.FINISHED
            return {"ok": True, "site": provider, "response": response_text[:50000], "response_length": len(response_text), "url": page.url, "title": await page.title()}
        tab.chat = ChatState.INCOMPLETE
        tab.error_count += 1
        return {"ok": False, "error": "empty_response", "detail": "Response was empty or extraction failed"}

    async def _wait_for_response(self, page, provider: str, timeout: int) -> str:
        detect = _DETECTORS.get(provider, {})
        response_sel = detect.get("response", [])
        generating_sel = detect.get("generating", [])
        start = time.time()
        max_wait = max(10, min(timeout, 180))
        last_text = ""
        stable_checks = 0
        last_len = 0
        while time.time() - start < max_wait:
            gen_el = await self._find_any(page, generating_sel)
            is_generating = gen_el is not None
            text = ""
            raw_texts = []
            for sel in response_sel:
                try:
                    els = await page.query_selector_all(sel)
                    for el in els:
                        t = (await el.text_content()) or ""
                        if t.strip():
                            raw_texts.append(t.strip())
                except Exception:
                    pass
            if raw_texts:
                text = "\n".join(raw_texts)
            if not is_generating and text:
                current_len = len(text)
                if current_len == last_len:
                    stable_checks += 1
                else:
                    stable_checks = 0
                    last_len = current_len
                if stable_checks >= 3:
                    return text
                if current_len > 100 and time.time() - start > 5:
                    return text
            elif is_generating and text:
                last_text = text
                last_len = len(text)
                stable_checks = 0
            await asyncio.sleep(1)
        return last_text or text

    async def _find_any(self, page, selectors: list[str]) -> Any:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    return el
            except Exception:
                pass
        return None

    async def close(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass


_runtime: BrowserRuntime | None = None


async def get_runtime() -> BrowserRuntime:
    global _runtime
    if _runtime is None:
        _runtime = BrowserRuntime()
    return _runtime
