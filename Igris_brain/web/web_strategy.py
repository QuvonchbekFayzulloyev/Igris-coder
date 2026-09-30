"""
IGRIS BRAIN — WebStrategy — S5 modullashtirish
==============================================
problems_to_fix.md :: S5 (qism) — igris_agent god-file'dan ajratilgan.
Protokol P04: veb so'rov darvozasi, strategiya (delegate/browser/full),
fokuslangan web tool to'plamlari va qaror qoidalari matni.

Bu modul DETERMINISTIK va holatsiz (LLM chaqirmaydi, tarmoqqa chiqmaydi).
IgrisAgent metodlari shu yerdagi funksiyalarga DELEGATSIYA qiladi; agent'ning
o'z API'si (nomlar, imzolar, testlar) o'zgarmaydi.

Eksport:
  WEB_INTENT_RE / WEB_GATE_RE / WEB_AI_NAME_RE / WEB_RESEARCH_RE /
  WEB_BROWSER_RE                    — aniqlash regexlari
  WEB_TECH_HINTS / WEB_URL_MARKERS  — sayt platforma aniqlash
  needs_web(message)                -> bool      (darvoza)
  web_strategy(message)             -> ''|delegate|browser|full
  detect_web_tech(message)          -> display nomi yoki ''
  delegate_tool_keys() / browser_basic_keys() — strategiya kalit to'plamlari
  web_decision_rules(strategy)      -> system-prompt matni
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------- #
WEB_INTENT_RE = re.compile(
    r"https?://|www\.|"
    # Aniq brauzer/sayt amallari — qo'shimchali shakllar ham ('brauzerda',
    # 'googledan') — lekin 'sahifa'/'ochuvch' kabi so'zlar o'zi yetarli.
    r"\b(?:brauzer|browser|sahifa|ochuvch|googl|yuklab|download)\w*|"
    # "internetdan qidir", "saytni och" kabi — sayt/so'z + amal fe'li birga.
    # sayt/site/websit/url qo'shimcha qabul qiladi ('saytni', 'saytini'),
    # 'link' QAT'IY (\b) — 'linked list' soxta pozitiv bo'lmasligi uchun.
    # Guruh QAVSLAR ICHIDA — lookahead butun guruhga tegishli bo'lishi kerak
    # (aks holda faqat oxirgi alternativaga yopishib qoladi).
    # Fe'llar qo'shimchali ham mos keladi ('ochib', 'qidirib') — \w* qo'shimcha.
    r"(?:\b(?:sayt|site|websit|url|internet|online)\w*|\blink\b)"
    r"(?=[^\n]*\b(?:och|open|qidir|search|ol|read|look|bor|visit)\w*\b)|"
    # qidiruv amali o'zi yetarli (internetdan qidirish = web ehtiyoji).
    # 'search' uchun keyingi ob'ekt talab qilinadi — 'binary search' kabi
    # kod mavzulari soxta pozitiv bo'lmasligi uchun.
    r"\bqidir\w*\b|\bsearch\b(?=\s+(?:for|the|on|online|google|web))",
    re.IGNORECASE,
)

# Darvoza uchun yana qanday so'zlar WEB ehtiyojini bildiradi? Tadqiqot
# fe'llari (qo'shimchali shakllar ham — 'tadqiqot') + web AI nomlari
# (delegatsiya tool'lari kerak). Eslatma: bu WEB_RESEARCH_RE ning ATALGAN
# QISM-TO'PLAMI — darvozaga umumbilim fe'llari (o'rgan/bilmoqchiman) kirmaydi,
# aks holda oddiy bilim savollari web tool'larini ochib qo'yardi.
WEB_GATE_RE = re.compile(
    r"\b(?:tadqiq\w*|research\w*|googl\w*|izla\w*|"
    r"internetdan\s*top\w*|onlinedan\s*top\w*)\b",
    re.IGNORECASE,
)

# \w* qo'shimcha — 'chatgptdan', 'gemindan' kabi egalik/yo'nalish qo'shimchalari
# ham mos keladi (\b oxiri so'z chegarasida).
WEB_AI_NAME_RE = re.compile(
    r"\b(?:chatgpt|gemini|claude(?:\s*ai)?|deepseek|perplexity|grok|bard)\w*\b",
    re.IGNORECASE,
)

# Qidiruv/tadqiqot/bilim fe'llari — web AI'ga topshiriladi. Faqat darvoza
# (WEB_GATE_RE) o'tgandan so'ng ishlatiladi — o'zi darvoza EMAS.
WEB_RESEARCH_RE = re.compile(
    r"\b(?:tadqiq\w*|research\w*|qidir\w*|izla\w*|o'?rgan\w*|googl\w*|"
    r"bilmoqchiman|bilishni\s*istayman|maslahat\s*ber|tavsiya\s*ber|"
    r"aniqlab\s*ber|topib\s*ber|nima\s*deydi|qanday\s*deydi)\b",
    re.IGNORECASE,
)

# Brauzer amallari — real sahifa interaktivligi kerak. Fe'llar qo'shimchali
# ham mos keladi ('ochib') — \w* qo'shimcha. 'ol\w*' 'olib'ni tutadi;
# 'saytni olma' kabi noyob soxta pozitivlar tavakkal — sayt kontekstida
# kamdan-kam uchraydi.
WEB_BROWSER_RE = re.compile(
    r"\b(?:brauzer|browser|sahifa|ochuvch|yuklab|download)\w*|"
    r"(?:\b(?:sayt|site|websit|url|internet)\w*|\blink\b)"
    r"(?=[^\n]*\b(?:och|open|ol|read|look|bor|visit|go)\w*\b)",
    re.IGNORECASE,
)

# Sayt texnologiyalari — `_detect_web_tech` so'rov matnidan sayt turini
# aniqlaydi ("wordpress saytini tekshir" -> WordPress).
WEB_TECH_HINTS: tuple = (
    ("wordpress", "WordPress"),
    ("shopify", "Shopify"),
    ("wix", "Wix"),
    ("squarespace", "Squarespace"),
    ("webflow", "Webflow"),
    ("joomla", "Joomla"),
    ("drupal", "Drupal"),
    ("tilda", "Tilda"),
    ("bitrix", "Bitrix"),
    ("opencart", "OpenCart"),
    ("prestashop", "PrestaShop"),
    ("magento", "Magento"),
    ("blogger", "Blogger"),
    ("medium", "Medium"),
    ("notion", "Notion"),
    ("netlify", "Netlify"),
    ("vercel", "Vercel"),
    ("ghost", "Ghost"),
)

# URL markerlari — domen ichida ham aniqlanadi (myshopify.com va h.k.)
WEB_URL_MARKERS: tuple = (
    ("myshopify.com", "Shopify"),
    ("wixsite.com", "Wix"),
    ("squarespace.com", "Squarespace"),
    ("webflow.io", "Webflow"),
    ("wordpress.com", "WordPress"),
    ("blogger.com", "Blogger"),
    ("medium.com", "Medium"),
    ("notion.site", "Notion"),
    ("github.io", "GitHub Pages"),
    ("ghost.io", "Ghost"),
)

# Subagent (delegate) yo'lida web AI tool'lari — ask_web_ai + tadqiqot boshqaruvi.
WEB_DELEGATE_KEYS: frozenset = frozenset({
    "web_ai_bridge__ask_web_ai",
    "web_ai_bridge__web_ai_start_research",
    "web_ai_bridge__web_ai_check_research",
    "web_ai_bridge__web_ai_get_conversation",
    "web_ai_bridge__web_ai_new_chat",
    "web_ai_bridge__web_ai_stop_generating",
})

# Delegate strategiyasida zaxira sifatida ruxsat etilgan MINIMAL brauzer
# amallari: web AI login talab qilsa yoki aniq URL o'qish kerak bo'lsa —
# model qo'lda qolmaydi.
WEB_BROWSER_BASIC_KEYS: frozenset = frozenset({
    "web_ai_bridge__browser_navigate",
    "web_ai_bridge__browser_get_text",
    "web_ai_bridge__browser_screenshot",
    "web_ai_bridge__browser_check_link",
    "web_ai_bridge__browser_wait_for",
    "web_ai_bridge__browser_dismiss_overlays",
    "web_ai_bridge__browser_info",
    "web_ai_bridge__browser_ai_task",
})

# Browser INTERAKTIV amallari — delegate strategiyasida noto'g'ri ishlatish
# (kuzatuv verdicti 'misuse-browser').
WEB_INTERACTION_KEYS: frozenset = frozenset({
    "web_ai_bridge__browser_click",
    "web_ai_bridge__browser_type",
    "web_ai_bridge__browser_select_option",
    "web_ai_bridge__browser_press_key",
    "web_ai_bridge__browser_hover",
    "web_ai_bridge__browser_scroll",
    "web_ai_bridge__browser_upload_file",
})


def detect_web_tech(message: str) -> str:
    """Web so'rovidan SAYT texnologiyasini aniqlaydi (LLMsiz).

    WordPress/Shopify/Wix... kabi platforma nomi yoki URL domen markeri
    (myshopify.com -> Shopify). Qaytaradi: display nomi yoki ''.
    """
    low = (message or "").lower()
    for marker, name in WEB_URL_MARKERS:
        if marker in low:
            return name
    for pat, name in WEB_TECH_HINTS:
        if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
            return name
    return ""


def needs_web(message: str) -> bool:
    """So'rovda veb/brauzer ehtiyoji bormi? (URL, sayt ochish, qidirish,
    yoki web AI'ga murojaat — chatgpt/gemini/deepseek...)

    Qoida: URL/manzil BOR, brauzer/sayt amali aniq ifodalangan yoki web
    AI/tadqiqot so'ralgan bo'lsa. "web", "link", "site", "search" o'zi
    bilan ishlamaydi — qo'shni fe'l talab qilinadi (soxta pozitiv kamayadi).
    """
    msg = message or ""
    if WEB_INTENT_RE.search(msg):
        return True
    # Web AI nomi (chatgptdan so'ra...) yoki tadqiqot fe'li — delegatsiya
    # tool'lari kerak, aks holda model ularni hech qachon ocholmaydi.
    if WEB_AI_NAME_RE.search(msg) or WEB_GATE_RE.search(msg):
        return True
    # SAYT TEXNOLOGIYASI + amal fe'li: "shopify do'konini och",
    # "wordpress saytini tekshir" — platforma nomi brauzer amali bilan
    # birga kelsa veb so'rov (so'z o'zi yetarli emas: "wordpress nima"
    # bilim savoli, brauzer talab qilmaydi).
    if detect_web_tech(msg):
        if re.search(
            r"\b(?:och|open|qidir|search|ol|read|tekshir|check|ko'rsat|show|bor|visit|yuklab|download|qur|build|yarat|create|yasash)\w*",
            msg, re.IGNORECASE,
        ):
            return True
    return False


def web_strategy(message: str) -> str:
    """Veb so'rov strategiyasi: '' | 'delegate' | 'browser' | 'full'.

    Qoida: URL yoki aniq brauzer amali -> browser. Bilim/qidiruv so'rovi
    -> delegate (web AI subagent). Ikkalasi ham -> full.
    """
    msg = message or ""
    if not needs_web(msg):
        return ""
    has_url = bool(re.search(r"https?://|www\.", msg, re.IGNORECASE))
    browser = bool(WEB_BROWSER_RE.search(msg))
    research = bool(WEB_AI_NAME_RE.search(msg) or WEB_RESEARCH_RE.search(msg))
    if has_url and research:
        return "full"
    if has_url or browser:
        return "browser"
    if research:
        return "delegate"
    return "browser"


def delegate_tool_keys() -> frozenset:
    """'delegate' strategiyasiga ruxsat etilgan web tool kalitlari."""
    return WEB_DELEGATE_KEYS | WEB_BROWSER_BASIC_KEYS


def browser_basic_keys() -> frozenset:
    """'browser' strategiyasida delegate oilasi CHEGARLANADI — qolganlari."""
    return WEB_BROWSER_BASIC_KEYS


def web_decision_rules(strategy: str) -> str:
    """Web so'rovida system prompt'ga qo'shiladigan QAROR QOIDALARI.

    Eng arzon vosita birinchi: to'g'ridan-to'g'ri javob > web_fetch >
    ask_web_ai (web AI subagent) > browser. Bilim savollarida browser'ni
    qo'lda boshqarish o'rniga helper AI'ga topshirish tavsiya etiladi.
    """
    if strategy == "delegate":
        hint = (
            "This is a research/knowledge request: DELEGATE it to a web AI "
            "(chatgpt/gemini/claude_web/deepseek) with ask_web_ai(provider, prompt) "
            "or web_ai_start_research for long work — the web AI is your helper "
            "and does the browsing for you."
        )
    elif strategy == "browser":
        hint = (
            "This needs a real page: open it with browser_navigate, read with "
            "browser_get_text/browser_screenshot, interact only if required "
            "(forms/logins). Do not chain unnecessary steps."
        )
    else:
        hint = ""
    return (
        "WEB REQUEST POLICY — use the CHEAPEST tool that answers the question:\n"
        "1. Answer directly from your own knowledge — no tools.\n"
        "2. web_fetch(url) reads static page text over HTTP (docs/articles) — no browser.\n"
        "3. ask_web_ai(provider, prompt) delegates to a web AI (chatgpt/gemini/"
        "claude_web/deepseek) as a SUBAGENT for research and knowledge questions; "
        "web_ai_start_research + web_ai_check_research for long analysis.\n"
        "4. Browser tools (navigate/get_text/screenshot/click/...) ONLY for "
        "interactive pages: accounts, forms, logins, JS-heavy apps, exact live state.\n"
        + ((hint + "\n") if hint else "")
        + WEB_TOOLS_GUIDE
    )


# web-ai-bridge GUIDE.md dan to'liq tool qo'llanmasi — model har bir
# browser/web-AI tool'ini QACHON ishlatishni aniq bilsin. Faqat web so'rovida
# system prompt'ga qo'shiladi (web_decision_rules / _tools_hint orqali).
# Nomlar toolset'da `web_ai_bridge__` prefiksi bilan keladi.
WEB_TOOLS_GUIDE = (
    "WEB-TOOLS QUICK GUIDE (tool names are prefixed web_ai_bridge__, e.g. "
    "web_ai_bridge__browser_navigate):\n"
    "- Open a URL and see what's there: browser_navigate\n"
    "- Check what a link even is without leaving your tab: browser_check_link\n"
    "- Look at the page yourself: browser_screenshot\n"
    "- Read the page's text (ads/clutter stripped): browser_get_text\n"
    "- Click something: browser_click\n"
    "- Fill in a field: browser_type\n"
    "- Choose a dropdown option: browser_select_option\n"
    "- Attach a local file: browser_upload_file\n"
    "- Press a shortcut (Escape, Ctrl+A, ...): browser_press_key\n"
    "- Scroll / reveal something off-screen: browser_scroll\n"
    "- Wait for something to actually load: browser_wait_for\n"
    "- Work with more than one tab: browser_list_tabs / browser_new_tab / "
    "browser_switch_tab / browser_close_tab\n"
    "- See what's been downloaded: browser_list_downloads\n"
    "- Confirm which browser is actually running: browser_info\n"
    "- Clear a cookie banner / popup that's in the way: browser_dismiss_overlays\n"
    "- Run a WHOLE adaptive task (browser-use-style: picks elements by "
    "text/label from the live page, so UI redesigns don't break it): "
    "browser_ai_task\n"
    "- Ask ChatGPT / Gemini / Claude.ai / DeepSeek something (normal length): "
    "ask_web_ai\n"
    "- Ask something that could take a while (deep research): "
    "web_ai_start_research, then poll web_ai_check_research\n"
    "- Start that provider's conversation over: web_ai_new_chat\n"
    "- Interrupt a reply that's generating: web_ai_stop_generating\n"
    "- Read the full on-screen conversation: web_ai_get_conversation\n"
    "\n"
    "BUTTON SAFETY TIERS:\n"
    "1. Automatic (routine/reversible): navigation, tabs, dropdowns, scrolling, "
    "ordinary form fields, provider New Chat / Stop buttons.\n"
    "2. Automatic after checking clutter: cookie banners via "
    "browser_dismiss_overlays (clicks Accept; generic popups get "
    "Close/Dismiss/No thanks).\n"
    "3. NEVER without explicit user confirmation (browser_click with "
    "confirm:true): Buy Now, Place Order, Confirm Payment, Pay Now, Proceed "
    "to Checkout, Delete My Account, Deactivate/Remove Account, Cancel "
    "Subscription. Add to Cart and plain navigation are fine.\n"
    "\n"
    "LOGIN: ask_web_ai needs the user to be logged in to the provider in the "
    "visible Chrome window once - if it fails with a login error, tell the "
    "user to log in and try again.\n"
    "\n"
    "DEEP RESEARCH: submit with web_ai_start_research, then do useful work of "
    "your own and poll web_ai_check_research periodically (still working = "
    "normal, check later; complete = reply text; hard failure = report it). "
    "Never block-wait for a long reply.\n"
    "\n"
    "READING BROWSER RESULTS (how to interpret what the tools report):\n"
    "- Navigations are classified by real HTTP status + Content-Type - page / "
    "image / media / text / file - never guessed from the URL's extension.\n"
    "- Failed navigations are reported in plain language (DNS failure, "
    "connection refused, timeout, TLS error, too many redirects) - do not "
    "invent a reason.\n"
    "- If the 'failure' was actually a file download, the file is saved - "
    "check browser_list_downloads instead of treating it as an error.\n"
    "- A page is reported as BLOCKED (CAPTCHA/bot-check) or OBSTRUCTED (cookie "
    "banner/popup) - never both. If blocked, do not keep retrying; if "
    "obstructed, clear it once with browser_dismiss_overlays.\n"
    "- Text you send to a third-party AI (browser_type, ask_web_ai) is scanned "
    "for secrets (API keys, tokens, passwords, SSNs, card numbers). A hit "
    "escalates to a confirmation prompt - tell the user what was found and "
    "wait for their go-ahead.\n"
    "- If ask_web_ai reports slow or degraded replies (or the provider says "
    "the conversation is getting long), start a fresh chat with "
    "web_ai_new_chat and fold the essential context into the new prompt.\n"
)

# Har bir web_ai_bridge tool'iga schema-darajadagi QISQA ko'rsatma — model
# tool tanlash paytida ham (system prompt'ga tayanmasdan) qachon ishlatishni
# ko'radi. `_web_tools()` ularni description'ga qo'shadi. Kalitlari bridge
# server'ining tool nomlari bilan mos (test: drift YO'Q).
WEB_TOOL_HINTS: dict = {
    "web_ai_bridge__ask_web_ai": (
        "PREFER this for research/knowledge questions ('what does X say', "
        "qidirib ber, tadqiqot): it DELEGATES to a web AI subagent "
        "(chatgpt/gemini/claude_web/deepseek) that does the browsing for you. "
        "For long jobs use web_ai_start_research instead. Requires the user to "
        "be logged in to the provider in the visible Chrome window (first use) - "
        "if it fails with a login error, ask the user to log in."),
    "web_ai_bridge__web_ai_start_research": (
        "For deep research that takes a while: submit and return immediately, "
        "then do your own useful work and poll web_ai_check_research. "
        "Never block-wait for a long reply."),
    "web_ai_bridge__web_ai_check_research": (
        "Poll a research job started with web_ai_start_research: still working "
        "(normal, check later) / complete (reply text) / hard failure (report it)."),
    "web_ai_bridge__web_ai_new_chat": (
        "Start a fresh conversation with the provider - use when ask_web_ai "
        "replies get slow or the provider says the conversation is getting long; "
        "fold the essential context into your next prompt."),
    "web_ai_bridge__web_ai_stop_generating": "Interrupt a reply that is still generating.",
    "web_ai_bridge__web_ai_get_conversation": (
        "Read the full on-screen conversation with a provider - use before "
        "starting a new chat to carry forward what matters."),
    "web_ai_bridge__browser_navigate": (
        "Open a URL. The result is classified by real HTTP status + Content-Type "
        "(page/image/media/text/file), never guessed from the URL extension, and "
        "reported as BLOCKED (CAPTCHA) or OBSTRUCTED (cookie banner) - never both."),
    "web_ai_bridge__browser_check_link": (
        "Verify a link in a throwaway tab without leaving your current work - use "
        "when the user hands you a link and wants to know what it is first."),
    "web_ai_bridge__browser_screenshot": (
        "Look at the page yourself - especially when selector-based tools fail or "
        "a login/CAPTCHA might be showing."),
    "web_ai_bridge__browser_get_text": (
        "Read the page's text (ads/clutter stripped). Pass clean:false only if "
        "you need the raw unfiltered text."),
    "web_ai_bridge__browser_click": (
        "NEVER click irreversible actions (Buy Now, Place Order, Confirm Payment, "
        "Pay Now, Proceed to Checkout, Delete My Account, Cancel Subscription) "
        "without explicit user confirmation - retry with confirm:true only after "
        "the user agrees. Add to Cart and plain navigation are fine."),
    "web_ai_bridge__browser_type": (
        "Fill in a field. Text about to be sent is scanned for secrets (API keys, "
        "tokens, passwords) before it leaves."),
    "web_ai_bridge__browser_select_option": "Choose an option in a dropdown by visible label or value.",
    "web_ai_bridge__browser_upload_file": "Attach a local file to a file input, like a human file picker.",
    "web_ai_bridge__browser_press_key": "Press a keyboard key or shortcut (Escape, Ctrl+A, Tab...).",
    "web_ai_bridge__browser_scroll": "Scroll the page or reveal an element that is off-screen.",
    "web_ai_bridge__browser_wait_for": "Wait for something to actually load instead of guessing a delay.",
    "web_ai_bridge__browser_list_tabs": (
        "List open tabs - use when a site opens something in a new tab or you are "
        "working two things in parallel."),
    "web_ai_bridge__browser_new_tab": "Open a new tab and make it active, like Ctrl+T.",
    "web_ai_bridge__browser_switch_tab": "Make a different open tab the active one.",
    "web_ai_bridge__browser_close_tab": "Close a tab (omit index to close the active one).",
    "web_ai_bridge__browser_list_downloads": (
        "Files are saved automatically when a link triggers a download - check "
        "this instead of treating the download as an error."),
    "web_ai_bridge__browser_info": (
        "Confirm which browser is actually running (real Chrome via CDP vs "
        "bundled Chromium)."),
    "web_ai_bridge__browser_dismiss_overlays": (
        "Clear a cookie-consent banner (clicks Accept) or close generic popups "
        "(Close/Dismiss/No thanks). Call when a page's real content seems blocked "
        "or a navigation flags an obstruction."),
    "web_ai_bridge__browser_hover": "Hover over an element to open hover menus/tooltips.",
    "web_ai_bridge__browser_go_back": "Go back one page in the active tab's history.",
    "web_ai_bridge__browser_go_forward": "Go forward one page in the active tab's history.",
    "web_ai_bridge__browser_close": "Close the entire browser (all tabs) and end the session.",
    "web_ai_bridge__browser_ai_task": (
        "Adaptive agent for WHOLE multi-step tasks on unknown/unstable pages: "
        "it re-reads the live page each step and picks elements by text/label, "
        "so UI redesigns don't break it. Irreversible clicks (payment, "
        "purchase, deletion) are refused and reported. For precise single "
        "clicks/fills prefer the plain browser_* tools."),
}
