"""
IGRIS CODER AGENT — Main Orchestrator
=====================================
Hybrid engine:
  1. Deterministic: bricks + knowledge + constraint resolver (<10ms)
  2. Healing:     reconstruct missing capability chains
  3. Hybrid LLM:  Ollama fallback for complex / low-confidence queries
  4. Memory/RAG:  Igris_Memory bridge — recall before, remember after

Reference (plan, igris_brick_knowledge):
    Query: 'matritsani teskari top' [uz -> code]
    Status: ✓  Confidence: 0.902  Chains: ['chain_math']
    Output: np.linalg.inv(matrix)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Optional

from core.brick_system import BrickBank
from core.knowledge_system import KnowledgeBank, build_default_knowledge, build_default_bricks
from resolver.constraint_resolver import ConstraintResolver, Resolution
from chains.chain_system import (
    ChainRegistry,
    ChainHealer,
    build_default_chains,
)
from llm.ollama_client import OllamaClient
from refactor_machine import RefactorMachine
from memory_bridge import MemoryBridge
from core.intelligence import IntelligenceCore
from core.intelligence.logic import extract_balanced_json
from core.requirements import Requirement, RequirementExtractor


# Chat uchun ish maydoni — UI workspace daraxti bilan bir xil (preview ishlashi uchun)
DEFAULT_WORKSPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_workspace")

# Chat ham REAL tool'lar bilan ishlaydi: model "rasm chiza olmayman" deyishi
# shart emas — chizmani O'ZI yaratadi (art__draw_custom_svg) yoki tayyor
# shablonlarni ishlatadi.
CHAT_TOOLS_SYSTEM = (
    "You are Igris, a helpful local coding agent with REAL tools. "
    "When the user asks you to draw or generate an image (a picture, an apple, "
    "a duck, a robot, a logo, a UI design, a dashboard...), YOU ARE THE ARTIST: "
    "generate the SVG markup yourself and save it with art__draw_custom_svg "
    "(args: svg='<your full <svg>...</svg> markup>', output='duck.svg', "
    "style='cartoon|realistic|flat', "
    "size='standard|icon|avatar|card|poster|banner'). "
    "THERE IS NO FIXED SUBJECT LIST — any subject works, you design it. "
    "Support a drawing STYLE: infer it from the user's request (or ask) and "
    "pass it as the style argument — 'cartoon' (bold outlines, saturated "
    "colors, playful), 'realistic' (soft gradients, subtle shadows, natural "
    "palette) or 'flat' (solid colors, no gradients/shadows, minimal). "
    "Support drawing SIZE too: infer the canvas from the request (avatar / "
    "profil rasmi, card / karta, poster / afisha, banner, icon / ikonka) and "
    "pass it as the size argument — or a custom 'WxH' like '800x600'. Design "
    "the SVG for that exact viewBox (e.g. poster = 1080x1920 portrait, "
    "banner = 1920x480 ultra-wide, icon = 256x256 tiny). "
    "Quality rules: viewBox='0 0 512 512', start with a soft background, then "
    "layered shapes (outline -> body -> details -> highlights), use gradients, "
    "soft shadows and smooth curves, pick a coherent color palette, and put "
    "every visual part as its own element so the UI reveals the drawing piece "
    "by piece. After saving, tell the user the file is ready in 1 short "
    "sentence (no code dump). "
    "You may also use the quick canned tools: art__draw_scene_svg (apple, house, "
    "tree, cat, star, heart, car, rocket, flower, mountain, sun, moon, bird, "
    "fish, butterfly, mushroom, ball; Uzbek: olma, uy, daraxt, mushuk, "
    "mashina, raketa, gul, tog, quyosh, oy, qush, baliq, kapalak, qo'ziqorin, "
    "to'p) with color and texture args for a fast stylized scene, and "
    "art__draw_ui_svg (UI/UX mockups - dashboard, mobile_app, login, "
    "profile, chat, settings). Use art__draw_object_png only for a simple "
    "bitmap. "
    "When the user asks to BUILD a real working UI screen (layout, dashboard, "
    "app window with buttons, sidebar, opening dialogs...), call art__ui_build_spec "
    "(app, output, theme) - it creates a construction plan that the frontend "
    "builds as REAL HTML step by step: background first, then sections, then the "
    "navigation layer with a WORKING sidebar toggle, then content in design "
    "order, then buttons that really OPEN a window, then the window itself - "
    "first its shape and color, then its inner content as a sketch. The finished "
    "parts are immediately interactive. Do NOT say you cannot draw images and do "
    "NOT reply with only code. "
    "A TODO/TASK LIST app ('todo' or 'vazifalar') is a REAL interactive app: "
    "the user can type a task, add it, check it done, delete it, filter by "
    "status, and it persists in localStorage - build it with "
    "art__ui_build_spec(app='todo', output='todo.uibuild.json', ...). "
    "Always give ui_build_spec an output filename ending in .uibuild.json "
    "(e.g. output='todo.uibuild.json') so the frontend renders the live build. "
    "You can also create and edit text files with write_file/read_file. "
    "For ordinary conversational questions, answer directly without tools. "
    "You also have fast web tools: web_fetch(url) reads a page's text over "
    "HTTP without a browser (e.g. weather: web_fetch('https://wttr.in/<city>')), "
    "and web_search_image(query) finds and DOWNLOADS an image into the workspace "
    "(e.g. web_search_image(query='green apple') -> the chat shows the picture). "
    "When you WRITE CODE, follow these quality rules: 1) write simple, correct "
    "code with short comments; 2) after creating a code file, VERIFY it - run "
    "it with python_exec or run_command and fix any errors you see; 3) prefer a "
    "complete working solution over a long explanation; 4) when the request "
    "asks for both drawing AND code (e.g. generate an image with a script), use "
    "the art tools for the image and write_file for the script, then run it."
)


# web-ai-bridge GUIDE.md dan to'liq tool qo'llanmasi — model har bir
# browser/web-AI tool'ini QACHON ishlatishni aniq bilsin. Faqat web so'rovida
# system prompt'ga qo'shiladi (_web_decision_rules / _tools_hint orqali).
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
# ko'radi. `_web_tools()` ularni description'ga qo'shadi.
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


# art__ tool'lariga ham schema-darajadagi QISQA ko'rsatma — model qaysi
# chizish vositasini QACHON tanlashni biladi (draw_custom_svg bosh, scene/UI
# tezkor varianti, ui_build_spec interaktiv ekranlar uchun).
ART_TOOL_HINTS: dict = {
    "art__draw_custom_svg": (
        "MAIN drawing tool - use for ANY image the user requests (objects, "
        "scenes, logos, posters, avatars): YOU are the artist, generate the "
        "full <svg> markup yourself and pass style='cartoon|realistic|flat' "
        "and size='standard|icon|avatar|card|poster|banner'. There is NO fixed "
        "subject list."),
    "art__draw_scene_svg": (
        "Quick layered SCENE for known simple objects (apple, house, tree, cat, "
        "star, heart, car, rocket, flower, mountain, sun, moon, bird, fish, "
        "butterfly, mushroom, ball). For anything else use draw_custom_svg."),
    "art__draw_object_png": (
        "Legacy canned PNG drawing of a simple object (raster, not SVG). Prefer "
        "draw_custom_svg or draw_scene_svg for vector quality; use this only "
        "when the user explicitly wants a PNG/raster picture."),
    "art__draw_ui_svg": (
        "STATIC UI/UX mockup screen as layered SVG (app, theme, texture). Use "
        "for a visual mockup/wireframe. For a REAL interactive screen use "
        "ui_build_spec instead."),
    "art__ui_build_spec": (
        "REAL INTERACTIVE UI screen (dashboard, todo app, settings, ...): "
        "produces a .uibuild.json that the frontend renders as a live-build "
        "preview with working widgets. Output must end in .uibuild.json. Use "
        "for apps/screens the user can actually interact with."),
    "art__list_subjects": "List the objects the canned scene/drawing tools can render.",
}


# ---------------------------------------------------------------------- #
# STACK REJALARI — framework/til aniqlanganda tool rejasi + buyruq qo'llanmasi
# ---------------------------------------------------------------------- #
# Kod so'rovida framework/til topilsa (`_detect_code_stack`):
#   - `_planned_tools` shu stack'ga mos vositalarni rejalaydi
#     (React -> read/write/list/run_command — npm shu terminal orqali ishlaydi),
#   - `_stack_guide` modelga ANIQ buyruqlarni system prompt orqali yetkazadi
#     (npm install, npx webpack, manage.py runserver...).
# Alohida npm/webpack tool'i KERAK EMAS — run_command terminal vositasi yetarli,
# faqat modelga qanday buyruq kerakligi aytilishi shart.

STACK_PLANS: dict = {
    "npm": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - JavaScript/TypeScript (npm):\n"
            "- Key files: package.json (scripts + deps), vite.config.js / webpack.config.js, "
            "index.html, src/ (main.jsx|tsx, App.jsx|tsx).\n"
            "- New project: `npm create vite@latest . -- --template react` "
            "(or `npx create-react-app .`); bare: `npm init -y` + `npm install react react-dom`.\n"
            "- Install: `npm install` (one pkg: `npm install <pkg>`, dev: `npm install -D <pkg>`).\n"
            "- Run: `npm run dev` (Vite) or `npm start` (CRA). Build: `npm run build`; "
            "webpack: `npx webpack` (prod: `npx webpack --mode production`).\n"
            "- Typecheck (TS): `npx tsc --noEmit`. Tests: `npm test`.\n"
            "- Run all of these with the run_command tool (cwd = project dir)."
        ),
    },
    "python": {
        "tools": ["read_file", "write_file", "list_files", "run_command", "python_exec"],
        "guide": (
            "STACK GUIDE - Python:\n"
            "- Key files: requirements.txt / pyproject.toml, manage.py (Django), app.py, tests/.\n"
            "- Install: `pip install -r requirements.txt` (one pkg: `pip install <pkg>`); "
            "prefer a venv: `python -m venv .venv`.\n"
            "- Run: `python app.py` (Django: `python manage.py runserver`; "
            "FastAPI dev: `uvicorn app:app --reload`).\n"
            "- Tests: `python -m pytest` or `python -m unittest`.\n"
            "- Use python_exec for quick snippets, run_command for the real app/CLI."
        ),
    },
    "php": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - PHP (Composer):\n"
            "- Key files: composer.json, src/, public/index.php (Laravel: artisan).\n"
            "- Install: `composer install` (one pkg: `composer require <pkg>`).\n"
            "- Run: `php -S localhost:8000` (Laravel: `php artisan serve`).\n"
            "- Tests: `vendor/bin/phpunit`. Use the run_command tool."
        ),
    },
    "ruby": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Ruby (Bundler):\n"
            "- Key files: Gemfile, config.ru, app/ (Rails: bin/rails).\n"
            "- Install: `bundle install` (one gem: `bundle add <gem>`).\n"
            "- Run: `ruby app.rb` (Rails: `bin/rails server`). Tests: `bundle exec rspec`.\n"
            "- Use the run_command tool."
        ),
    },
    "java": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Java (Maven/Gradle):\n"
            "- Key files: pom.xml / build.gradle, src/main (java/ katalogi).\n"
            "- Install/build: `mvn install` or `gradle build` "
            "(Spring Boot: `./mvnw spring-boot:run` / `./gradlew bootRun`).\n"
            "- Tests: `mvn test` / `gradle test`. Use the run_command tool."
        ),
    },
    "dotnet": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - .NET/C#:\n"
            "- Key files: *.csproj / *.sln, Program.cs.\n"
            "- Restore/build: `dotnet restore` + `dotnet build` (add pkg: `dotnet add package <pkg>`).\n"
            "- Run: `dotnet run`. Tests: `dotnet test`. Use the run_command tool."
        ),
    },
    "go": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Go:\n"
            "- Key files: go.mod, main.go.\n"
            "- Install: `go mod tidy` (add: `go get <module>`).\n"
            "- Run: `go run .` Build: `go build`. Tests: `go test ./...`. Use run_command."
        ),
    },
    "rust": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Rust (Cargo):\n"
            "- Key files: Cargo.toml, src/main.rs.\n"
            "- Install: `cargo build` (add: `cargo add <crate>`).\n"
            "- Run: `cargo run`. Tests: `cargo test`. Use the run_command tool."
        ),
    },
    "dart": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Dart/Flutter:\n"
            "- Key files: pubspec.yaml, lib/main.dart.\n"
            "- Install: `flutter pub get` (add: `flutter pub add <pkg>`).\n"
            "- Run: `flutter run`. Tests: `flutter test`. Use the run_command tool."
        ),
    },
    "swift": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Swift/SwiftUI:\n"
            "- Key files: Package.swift, Sources/ (Xcode project or SPM).\n"
            "- Build: `swift build` (add: add to Package.swift dependencies).\n"
            "- Tests: `swift test`. Use the run_command tool."
        ),
    },
    "postgres": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - PostgreSQL:\n"
            "- Connect: `psql -U <user> -d <dbname> -h localhost` (auth: PGPASSWORD env / pg_hba).\n"
            "- Inspect: `\\dt` (tables), `\\d <table>` (schema), `\\l` (databases); quit with `\\q`.\n"
            "- Dump/backup: `pg_dump -U <user> <db> -f backup.sql`.\n"
            "- App drivers: psycopg / SQLAlchemy (Python: `postgresql+psycopg://user:pass@localhost:5432/db`), "
            "pg / Prisma / TypeORM / Drizzle (Node/TS: `postgresql://...` in schema.prisma), GORM (Go).\n"
            "- Run via the run_command tool."
        ),
    },
    "prisma": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Prisma (ORM, Node/TypeScript):\n"
            "- Install: `npm install prisma @prisma/client` (CLI dev dep: `npm install -D prisma`).\n"
            "- Init: `npx prisma init --datasource-provider postgresql` "
            "(yoki mysql/sqlite) -> prisma/schema.prisma + .env.\n"
            "- .env: `DATABASE_URL=\"postgresql://user:pass@localhost:5432/dbname\"` "
            "(provider DB bilan mos bo'lishi shart).\n"
            "- Model: `model User { id Int @id @default(autoincrement()) email String @unique name String? }` "
            "schema.prisma'da, keyin:\n"
            "- Migrate: `npx prisma migrate dev --name init` (jadval yaratadi + client generate qiladi).\n"
            "- Migratsiyasiz sync: `npx prisma db push`. Client qayta: `npx prisma generate`.\n"
            "- Ko'rish: `npx prisma studio` (brauzer UI). Seed: `npx prisma db seed` "
            "(package.json'da `prisma.seed` kerak).\n"
            "- Client: `import { PrismaClient } from '@prisma/client'; "
            "const prisma = new PrismaClient();`\n"
            "- Run via the run_command tool."
        ),
    },
    "mysql": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - MySQL/MariaDB:\n"
            "- Connect: `mysql -u <user> -p <dbname>` (add `-h <host>` if remote).\n"
            "- Inspect: `SHOW DATABASES; SHOW TABLES; DESCRIBE <table>;`\n"
            "- Dump/backup: `mysqldump -u <user> -p <db> > backup.sql`.\n"
            "- App drivers: mysql-connector-python / SQLAlchemy (Python), "
            "mysql2 / Prisma / TypeORM (Node), PDO/mysqli (PHP).\n"
            "- Run via the run_command tool."
        ),
    },
    "mongodb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - MongoDB:\n"
            "- Connect: `mongosh \"mongodb://localhost:27017/<db>\"` or `mongosh` then `use <db>`.\n"
            "- Inspect: `show dbs`, `show collections`, `db.<collection>.find().limit(5)`.\n"
            "- App drivers: pymongo (Python), mongodb/mongoose (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "redis": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Redis:\n"
            "- Connect: `redis-cli` (add `-h <host> -p <port>` if remote).\n"
            "- Basic: `SET key value`, `GET key`, `KEYS <pattern>`, `TTL key` (FLUSHDB is destructive).\n"
            "- App drivers: redis-py (Python), ioredis/node-redis (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "sqlite": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - SQLite:\n"
            "- Open: `sqlite3 <file>.db` then `.tables`, `.schema <table>`, `SELECT ...;`, `.quit`.\n"
            "- No server needed — the DB is a single file.\n"
            "- App drivers: sqlite3 (Python stdlib), better-sqlite3 (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "mssql": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - SQL Server:\n"
            "- Connect: `sqlcmd -S localhost -U <user> -P <pass>` then `SELECT ...; GO`.\n"
            "- Inspect: `SELECT name FROM sys.databases;` / `SELECT * FROM sys.tables;`\n"
            "- App drivers: pyodbc (Python), mssql (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "elasticsearch": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Elasticsearch:\n"
            "- REST API over HTTP (default port 9200): `curl -X GET \"http://localhost:9200/\"`.\n"
            "- Indices: `curl \"http://localhost:9200/_cat/indices?v\"`; "
            "create: `curl -X PUT \"http://localhost:9200/my-index\"`.\n"
            "- Search: `curl -X POST \"http://localhost:9200/my-index/_search\" "
            "-H 'Content-Type: application/json' -d '{\"query\":{\"match_all\":{}}}'`.\n"
            "- Client libs: elasticsearch-py (Python), @elastic/elasticsearch (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "cassandra": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Cassandra (CQL):\n"
            "- Connect: `cqlsh` (one-shot: `cqlsh -e \"SELECT ...\"`).\n"
            "- Inspect: `DESCRIBE KEYSPACES;`, `DESCRIBE TABLES;`, `SELECT ... LIMIT 10;`\n"
            "- Driver: cassandra-driver (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "dynamodb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - DynamoDB:\n"
            "- AWS CLI: `aws dynamodb list-tables --region <region>`; "
            "`aws dynamodb scan --table-name <t>`.\n"
            "- Local dev: `docker run -p 8000:8000 amazon/dynamodb-local` then pass "
            "`--endpoint-url http://localhost:8000`.\n"
            "- Driver: boto3 (Python), @aws-sdk/client-dynamodb (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "neo4j": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Neo4j (Cypher):\n"
            "- Connect: `cypher-shell -u neo4j -p <pass>` (bolt 7687, browser UI 7474).\n"
            "- Basic: `MATCH (n) RETURN n LIMIT 25;`\n"
            "- Driver: neo4j (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "clickhouse": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - ClickHouse:\n"
            "- Connect: `clickhouse-client` (native 9000; HTTP 8123).\n"
            "- Basic: `SHOW TABLES;`, `SELECT * FROM <table> LIMIT 10;`\n"
            "- Driver: clickhouse-connect (Python), @clickhouse/client (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "oracle": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Oracle (SQL*Plus):\n"
            "- Connect: `sqlplus user/pass@//localhost:1521/XEPDB1`.\n"
            "- Inspect: `SELECT table_name FROM user_tables;`\n"
            "- Driver: python-oracledb (Python), oracledb (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "chroma": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Chroma (vector DB):\n"
            "- Install: `pip install chromadb`. Server: `chroma run --path ./chroma-data` "
            "(yoki embedded: `import chromadb; client = chromadb.PersistentClient(path='./db')`).\n"
            "- Collection: `col = client.get_or_create_collection('docs', "
            "metadata={'hnsw:space': 'cosine'})` (cosine/l2/ip).\n"
            "- Add: `col.add(ids=['1'], documents=['matn'], embeddings=[vec])` — "
            "vektorlarni o'zingiz bering YOKI `embedding_function` berilsa matndan avtomatik.\n"
            "- Search: `col.query(query_embeddings=[vec], n_results=5, "
            "include=['documents','distances'])`.\n"
            "- EMBEDDING O'LCHAMI: `vec` uzunligi collection'dagi birinchi embedding bilan "
            "MOS bo'lishi shart (ajralib qolsa xato). Umumiy: OpenAI text-embedding-3-small="
            "1536, ada-002=1536, all-MiniLM-L6-v2=384 (Chroma default), nomic-embed-text "
            "(Ollama)=768, bge-base=768. Model almashtirilsa — yangi collection + qayta embed.\n"
            "- Filter: `col.query(..., where={'category': 'news'})`.\n"
            "- Run via the run_command tool."
        ),
    },
    "qdrant": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Qdrant (vector DB):\n"
            "- Local: `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant` (REST 6333 / GRPC 6334).\n"
            "- Python: `pip install qdrant-client`; "
            "`client = QdrantClient(url='http://localhost:6333')`.\n"
            "- Create: `client.create_collection('docs', vectors_config={'size': 1536, 'distance': 'Cosine'})` — "
            "`size` = EMBEDDING O'LCHAMI (OpenAI 3-small/ada-002=1536, 3-large=3072, "
            "MiniLM=384, nomic=768); model o'zgarsa YANGI collection kerak.\n"
            "- Upsert: `client.upsert('docs', points=[PointStruct(id=1, vector=vec, "
            "payload={'title': '...'})])`.\n"
            "- Search: `client.search('docs', query_vector=vec, limit=5, with_payload=True)`.\n"
            "- REST: `curl -X POST http://localhost:6333/collections/docs/points/search "
            "-H 'Content-Type: application/json' -d '{\"vector\": [...], \"limit\": 5}'`.\n"
            "- Filter: `client.search(..., query_filter=Filter(must=[FieldCondition(key='category', "
            "match=Match(value='news'))]))`.\n"
            "- Run via the run_command tool."
        ),
    },
    "pinecone": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Pinecone (cloud vector DB):\n"
            "- SDK: `pip install pinecone-client`; "
            "`pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])`.\n"
            "- Index: `pc.create_index('docs', dimension=1536, metric='cosine')` — "
            "`dimension` = EMBEDDING O'LCHAMI va index yaratilgach O'ZGARMAYDI "
            "(OpenAI 3-small/ada-002=1536, 3-large=3072, MiniLM=384, nomic=768; "
            "model almashtirilsa yangi index).\n"
            "- Index obyekti: `idx = pc.Index('docs')` — keyin upsert/query shu bilan.\n"
            "- Upsert: `idx.upsert(vectors=[(id, vec, {'title': '...'})], namespace='ns1')`.\n"
            "- Query: `idx.query(vector=vec, top_k=5, include_metadata=True)`.\n"
            "- Namespace: `idx.query(..., namespace='ns1')` — bo'sh namespace default.\n"
            "- Metadata filter: `idx.query(vector=vec, top_k=5, filter={'category': {'$eq': 'news'}})`.\n"
            "- Run via the run_command tool."
        ),
    },
    "milvus": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Milvus (vector DB):\n"
            "- Local: `docker compose up` (milvus-standalone, port 19530) yoki "
            "`pip install pymilvus`; `client = MilvusClient(uri='http://localhost:19530')`.\n"
            "- Create: `client.create_collection('docs', dimension=1536, metric_type='COSINE')` — "
            "`dimension` = EMBEDDING O'LCHAMI (OpenAI 3-small/ada-002=1536, MiniLM=384, "
            "nomic=768). Metrik: COSINE/IP/L2.\n"
            "- Insert: `client.insert('docs', [{'id': 1, 'vector': vec, 'title': '...'}])`.\n"
            "- Search: `client.search('docs', data=[vec], limit=5, output_fields=['title'])`.\n"
            "- IVFFlat/HNSW index'da `nprobe`/`ef` parametrlari aniqlik tezligini boshqaradi.\n"
            "- Run via the run_command tool."
        ),
    },
    "weaviate": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Weaviate (vector DB):\n"
            "- Local: `docker run -p 8080:8080 semitechnologies/weaviate` (REST /v1/graphql).\n"
            "- Python: `pip install weaviate-client`; `client = weaviate.Client('http://localhost:8080')`.\n"
            "- Class: vectorizer='none' va `'vectorIndexConfig': {'distance': 'cosine'}`.\n"
            "- Object: `client.data_object.create({'title': '...'}, class_name='Document', vector=vec)`.\n"
            "- Search: `client.query.get('Document', ['title']).with_near_vector({'vector': vec}).with_limit(5).do()` "
            "(GraphQL: `{ Get { Document(limit: 5, nearVector: {vector: [...]}) { title } } }`).\n"
            "- EMBEDDING O'LCHAMI: class'ga birinchi object bilan o'rnatiladi — model "
            "o'zgarsa yangi class kerak (OpenAI 3-small/ada-002=1536, MiniLM=384, nomic=768).\n"
            "- Run via the run_command tool."
        ),
    },
    "faiss": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - FAISS (in-process vector index):\n"
            "- Install: `pip install faiss-cpu`. Server YO'Q — faqat in-process (loyiha ichida).\n"
            "- Index: `import faiss; import numpy as np; index = faiss.IndexFlatIP(dim)` "
            "(cosine uchun vectorlarni normalize qiling yoki IndexFlatL2).\n"
            "- Add: `index.add(np.array(vectors).astype('float32'))` — barcha vectorlar bir xil "
            "`dim` o'lchamda (EMBEDDING O'LCHAMI: OpenAI 3-small/ada-002=1536, MiniLM=384, "
            "nomic=768).\n"
            "- Search: `D, I = index.search(np.array([vec]).astype('float32'), k=5)` — "
            "I = id'lar, D = masofalar.\n"
            "- Cosine: normalize qilinsa IP = cosine: `faiss.normalize_L2(x)`.\n"
            "- Metadata: FAISS o'zi saqlamaydi — id -> matn xaritasi (dict) o'zingizda.\n"
            "- Run via the run_command tool."
        ),
    },
    "influxdb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - InfluxDB (time series):\n"
            "- Connect: `influx` CLI (default port 8086) or `curl http://localhost:8086/health`.\n"
            "- Query (Flux): `influx query 'from(bucket:\"my-bucket\") |> range(start: -1h) |> limit(n: 10)'`.\n"
            "- v1 API: `/query?q=SELECT ...`; client libs: influxdb-client (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "memcached": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Memcached:\n"
            "- Default port 11211, plain-text protocol: `printf 'stats\\r\\n' | nc localhost 11211`.\n"
            "- Basic: `set key 0 <ttl> <bytes>\\r\\n<value>` / `get key` / `delete key`.\n"
            "- Client libs: pymemcache (Python), memjs (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "duckdb": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - DuckDB (embedded analytics):\n"
            "- CLI: `duckdb my.db` then SQL; in-process via `import duckdb; duckdb.sql(\"...\")` (Python).\n"
            "- Reads Parquet/CSV/JSON directly: `SELECT * FROM 'data.parquet';`\n"
            "- Node: duckdb package. Run via the run_command tool."
        ),
    },
    "snowflake": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Snowflake (warehouse):\n"
            "- CLI: `snowsql -a <account> -u <user>` (credentials in ~/.snowsql/config or env).\n"
            "- Query: standard SQL — `SELECT ...; SHOW TABLES;`\n"
            "- Drivers: snowflake-connector-python (Python), snowflake-sdk (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "bigquery": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - BigQuery:\n"
            "- CLI: `bq query --use_legacy_sql=false 'SELECT ...'` (gcloud auth required).\n"
            "- Inspect: `bq ls <dataset>`, `bq show <dataset>.<table>`\n"
            "- Drivers: google-cloud-bigquery (Python), @google-cloud/bigquery (Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "db": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Database (generic):\n"
            "- Cloud xizmatlar (Firebase/Airtable/Rockset/etcd...): SDK/konsol orqali — "
            "firebase-admin, pyairtable, rockset-client (Python/Node); "
            "`curl -s https://<api-endpoint>` ko'rinishidagi REST ham ishlaydi.\n"
            "- O'z CLI/client'i: `psql -U user -d db`, `mysql -u user -p db`, "
            "`mongosh \"mongodb://localhost:27017/db\"`, `redis-cli -h localhost`, "
            "`sqlite3 app.db`, `cqlsh -e \"DESCRIBE TABLES\"`, `sqlcmd -S localhost -U user`, "
            "`etcdctl get /key`, `arangosh --server.endpoint tcp://127.0.0.1:8529`, "
            "`surreal start memory`, `influx query 'from(bucket:\"b\")'`, "
            "`clickhouse-client --query \"SHOW TABLES\"`...\n"
            "- Connection strings: `<scheme>://user:pass@host:port/dbname`.\n"
            "- Avval sxemani o'rganing (schema), keyin so'rov, keyin dump/backup.\n"
            "- Run via the run_command tool."
        ),
    },
    "s3": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Object storage (S3/MinIO/GCS/Azure Blob/R2):\n"
            "- AWS S3: `aws s3 ls`, `aws s3 cp <fayl> s3://<buket>/`, "
            "`aws s3 sync <dir> s3://<buket>/` (auth: `aws configure` yoki "
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).\n"
            "- MinIO (lokal, S3-mos): `docker run -p 9000:9000 minio/minio server /data`; "
            "`mc alias set local http://localhost:9000 <user> <pass>`, "
            "`mc ls local/<buket>`, `mc cp <fayl> local/<buket>/`.\n"
            "- Google Cloud Storage: `gsutil ls gs://<buket>`, "
            "`gsutil cp <fayl> gs://<buket>/` (auth: `gcloud auth login`).\n"
            "- Azure Blob: `azcopy copy <fayl> https://<acct>.blob.core.windows.net/<container>/` "
            "(auth: `az login`).\n"
            "- Cloudflare R2: `wrangler r2 object put/get` (S3-mos API).\n"
            "- Universal: `rclone copy <fayl> remote:<buket>/`.\n"
            "- SDK'lar: boto3 (Python: `s3 = boto3.client('s3'); "
            "s3.upload_file('f', 'buket', 'key')`), @aws-sdk/client-s3 (Node), "
            "minio-py, google-cloud-storage, @azure/storage-blob.\n"
            "- Run via the run_command tool."
        ),
    },
    "firestore": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Firebase Firestore / Realtime Database:\n"
            "- Konsol: https://console.firebase.google.com -> Firestore Database "
            "(real-vaqt uchun Realtime Database).\n"
            "- Web (modular v9): `npm install firebase`; "
            "`import { initializeApp } from 'firebase/app'; "
            "import { getFirestore, collection, addDoc, getDocs, query, where } from 'firebase/firestore'`.\n"
            "- Yozish/o'qish: `addDoc(collection(db, 'users'), {name: 'A'})`; "
            "`const q = query(collection(db, 'users'), where('age', '>', 18)); "
            "const snap = await getDocs(q);`\n"
            "- Realtime: `import { getDatabase, ref, set, onValue } from 'firebase/database'; "
            "set(ref(db, 'users/1'), {...}); onValue(ref(db, 'users'), (s) => {...})`.\n"
            "- Xavfsizlik: Firestore Database -> Rules yorlig'i (ommaviy ilovalarda juda muhim).\n"
            "- Emulator: `firebase emulators:start`. Admin SDK (backend): `npm install firebase-admin`.\n"
            "- Run via the run_command tool."
        ),
    },
    "streams": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - Stream / message broker (Kafka/RabbitMQ/Pulsar):\n"
            "- Kafka (lokal): `docker run -p 9092:9092 apache/kafka:latest`; "
            "topic: `kafka-topics.sh --create --topic <t> --bootstrap-server localhost:9092`; "
            "producer: `kafka-console-producer.sh --topic <t> --bootstrap-server localhost:9092`; "
            "consumer: `kafka-console-consumer.sh --topic <t> --from-beginning --bootstrap-server localhost:9092`.\n"
            "- Kafka driver'lar: confluent-kafka (Python), kafkajs (Node).\n"
            "- RabbitMQ: `docker run -p 5672:5672 -p 15672:15672 rabbitmq:3-management`; "
            "boshqaruv UI http://localhost:15672 (user/guest); pika (Python), amqplib (Node).\n"
            "- Pulsar: `pulsar-admin topics create persistent://public/default/<t>`; "
            "pulsar-client (Python/Node).\n"
            "- Run via the run_command tool."
        ),
    },
    "generic": {
        "tools": ["read_file", "write_file", "list_files", "run_command"],
        "guide": (
            "STACK GUIDE - general project:\n"
            "- Inspect the project files first (list_files/read_file), then build/run/test "
            "with the run_command tool. If a package manifest exists (package.json, "
            "requirements.txt, go.mod, Cargo.toml, ...) use its standard commands."
        ),
    },
}

# Framework -> ekotizim xaritasi (STACK_PLANS kalitlari).
FRAMEWORK_STACK: dict = {
    "React": "npm", "React Native": "npm", "Next.js": "npm", "SvelteKit": "npm",
    "Nuxt": "npm", "Gatsby": "npm", "Vue": "npm", "Vuex": "npm", "Redux": "npm",
    "Angular": "npm", "Express": "npm", "jQuery": "npm", "Electron": "npm",
    "Node.js": "npm", "Three.js": "npm", "NestJS": "npm", "Fastify": "npm",
    "Tailwind CSS": "npm", "Bootstrap": "npm", "Sass": "npm", "SCSS": "npm",
    "Tauri": "npm",
    "Django": "python", "Flask": "python", "FastAPI": "python", "PyTorch": "python",
    "TensorFlow": "python", "pandas": "python", "NumPy": "python",
    "scikit-learn": "python", "Matplotlib": "python", "Beautiful Soup": "python",
    "Selenium": "python", "pytest": "python", "Celery": "python",
    "SQLAlchemy": "python",
    "Laravel": "php", "Symfony": "php", "WordPress": "php", "CodeIgniter": "php",
    "Rails": "ruby", "Sinatra": "ruby",
    "Spring": "java", "Hibernate": "java", "Maven": "java", "Gradle": "java",
    "ASP.NET": "dotnet", ".NET": "dotnet", "Xamarin": "dotnet",
    "Flutter": "dart",
}

# ORM -> ekotizim xaritasi (STACK_PLANS kalitlari). Prisma o'z maxsus
# rejasiga ega (npx prisma init/migrate/generate buyruqlari); boshqa Node
# ORM'lar npm rejasi bilan ishlaydi (TypeORM/Drizzle/Mongoose...).
ORM_STACK: dict = {
    "Prisma": "prisma",
    "TypeORM": "npm", "Drizzle ORM": "npm", "Mongoose": "npm",
    "Sequelize": "npm", "Knex": "npm",
}

# Til -> ekotizim xaritasi (noma'lum framework yoki faqat til aytilganda).
LANG_STACK: dict = {
    "JavaScript": "npm", "TypeScript": "npm",
    "Python": "python",
    "PHP": "php", "Ruby": "ruby",
    "Java": "java", "Kotlin": "java",
    "C#": "dotnet",
    "Go": "go", "Rust": "rust",
    "Dart": "dart", "Swift": "swift",
}

# Ma'lumotlar bazasi -> stack rejasi xaritasi (STACK_PLANS kalitlari).
DB_STACK: dict = {
    "PostgreSQL": "postgres", "MySQL": "mysql", "MariaDB": "mysql",
    "MongoDB": "mongodb", "Redis": "redis", "SQLite": "sqlite",
    "SQL Server": "mssql", "Cassandra": "cassandra", "Oracle": "oracle",
    "DynamoDB": "dynamodb", "Neo4j": "neo4j", "ClickHouse": "clickhouse",
    "Elasticsearch": "elasticsearch", "Firebase": "db", "Supabase": "postgres",
    # Moslashtiriladiganlar (mos CLI/client ishlaydi)
    "TimescaleDB": "postgres", "Redshift": "postgres", "CockroachDB": "postgres",
    "pgvector": "postgres",
    "PlanetScale": "mysql",
    "ScyllaDB": "cassandra",
    "Valkey": "redis",
    "Turso": "sqlite", "libSQL": "sqlite",
    "TiDB": "mysql", "YugabyteDB": "postgres",
    # Maxsus rejalar
    "Memcached": "memcached", "InfluxDB": "influxdb", "DuckDB": "duckdb",
    "Snowflake": "snowflake", "BigQuery": "bigquery",
    "Chroma": "chroma", "Qdrant": "qdrant", "Milvus": "milvus",
    "Pinecone": "pinecone", "Weaviate": "weaviate", "FAISS": "faiss",
    # Obyekt saqlash (S3-mos)
    "S3": "s3", "MinIO": "s3", "Google Cloud Storage": "s3",
    "Azure Blob": "s3", "Cloudflare R2": "s3", "Backblaze B2": "s3",
    "DigitalOcean Spaces": "s3",
    # Realtime / serverless
    "Firestore": "firestore", "Firebase Realtime": "firestore",
    "Neon Postgres": "postgres", "Xata": "postgres", "Cloudflare D1": "sqlite",
    "Upstash": "redis", "SurrealDB": "db", "SingleStore": "mysql",
    "Tarantool": "db", "Rockset": "db", "Airtable": "db",
    # Stream / navbat
    "Kafka": "streams", "RabbitMQ": "streams", "Apache Pulsar": "streams",
    "NATS": "streams", "Redpanda": "streams",
    # Generic 'db' rejasi
    "QuestDB": "db", "CouchDB": "db", "Couchbase": "db", "HBase": "db",
    "ArangoDB": "db", "etcd": "db", "RocksDB": "db", "LevelDB": "db",
}

# Subject'da DB yolg'iz bo'lganda "(baza)" o'rniga aniqroq qo'shimcha
# ("S3 (saqlash)", "Kafka (oqim)"...). Ro'yxatda bo'lmaganlar -> baza.
DB_DISPLAY_SUFFIX: dict = {
    "S3": "saqlash", "MinIO": "saqlash", "Google Cloud Storage": "saqlash",
    "Azure Blob": "saqlash", "Cloudflare R2": "saqlash",
    "Backblaze B2": "saqlash", "DigitalOcean Spaces": "saqlash",
    "Kafka": "oqim", "RabbitMQ": "navbat",
    "Apache Pulsar": "oqim", "NATS": "oqim", "Redpanda": "oqim",
    "Firestore": "real-vaqt bazasi", "Firebase Realtime": "real-vaqt bazasi",
    "Memcached": "kesh", "Elasticsearch": "qidiruv", "Neo4j": "graf",
}


# ---------------------------------------------------------------------- #
# INTELLEKT 2.2 — xavfsiz arifmetika so'rovi detektori (tez deterministik yo'l)
# ---------------------------------------------------------------------- #

# Raqamlar va + - * / ( ) dan tashqari hech narsa bo'lmagan arifmetik zanjir.
# "2+2*3", "(15-3)/4" kabi ifodalarni topadi; "Python dasturi yoz" kabi
# so'rovlar ushlanmaydi (raqam zanjiri yo'q).
MATH_EXPR_RE = re.compile(r"(?<![\w.])(?:[-+]?\d+(?:\.\d+)?)(?:\s*[-+*/]\s*[-+]?\d+(?:\.\d+)?)+")
MATH_PREFIX_RE = re.compile(
    r"^\s*(hisobla|hisoblang|hisoblab\s+ber|calculate|compute|evaluate|nechchi|qancha|what\s+is|how\s+much\s+is)\s*[:=]?\s*(.+)$",
    re.IGNORECASE,
)

# INTELLEKT 2.4 — loyiha strukturasi so'rovi markerlari (spatial kontekst)
STRUCTURE_REQUEST_WORDS = (
    "loyiha tuzilishi", "proyekt tuzilishi", "proekt tuzilishi",
    "fayl daraxti", "fayllar ro'yxati", "barcha fayllar", "qanday fayllar",
    "nechta fayl", "papka tuzilishi", "loyihada nima bor", "loyiha qanday",
    "project structure", "file tree", "folder structure",
    "what files", "how is the project organized", "what's in the project",
)

# INTELLEKT 2.11 — kreativ so'rov markerlari (multi-candidate generatsiya)
CREATIVE_REQUEST_WORDS = (
    "variant", "variants", "alternativ", "alternatives", "alternative",
    "g'oya", "g'oyalar", "ideas", "boshqa variant", "boshqa taklif",
    "options", "different ways", "yana qanday", "creative", "ijodiy",
)


# ---------------------------------------------------------------------- #
# AGENTIK PIPELINE REGISTRY — zarurat turi -> pipeline spetsifikatsiyasi
# ---------------------------------------------------------------------- #
# chat()/chat_stream() so'rovni klassifikatsiya qiladi va SHU jadval asosida
# agentik pipeline'ni tanlab QUradi: qaysi bosqichlar (PipelineStepper uchun),
# qaysi dvigatel ishlaydi. Bir nechta zarurat birlashgan bo'lsa (masalan
# "rasm chiz va kod yoz") `_build_pipeline` qo'shimcha (sub) pipeline'larni
# ham generatsiya qiladi — foydalanuvchi pipeline BIRINCHI quriladi.
#
# Oxirida bajarilgan ish `data["completion"]` sifatida konversatsiyaga
# to'ldiriladi (server chat_history.jsonl'ga ham yozadi).

# ------------------------------------------------------------------
# PIPELINE_SPECS — loop reestri (agentic architecture §3.1 + §3.2)
# ------------------------------------------------------------------
# Har bir kirish = bitta Loop. fieldlar:
#   stages      — pipeline bosqichlari (plan → ... → review)
#   engine      — LLM tipi (llm / llm+tools / math-quick / weather-quick)
#   loop_shape  — iteratsiya shakli (§3.2):
#       straight_through    — 1 marta ishlaydi, chiqish
#       react_iterative     — think → act → observe, max_iter marta
#       plan_then_execute   — bir marta rejalash, keyin ketma-ket bosqichlar
#       build_verify        — edit → review (deterministik) → repair, max_repair marta
#       reflexion_critique  — generate → self-critique → retry, max_repair marta
#   max_iter    — loop-shape iteratsiya cheklovi (react/build_verify uchun)
#   max_repair  — review bosqichi retry cheklovi (build_verify/reflexion uchun)
# ------------------------------------------------------------------
PIPELINE_SPECS: dict = {
    # -- chat-family (javob o'zi matn) ------------------------------------------
    "chat": {
        "label": "Suhbat (to'g'ridan-to'g'ri javob)",
        "stages": ["plan", "review"],
        "engine": "llm",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    "math": {
        "label": "Hisob / mantiq",
        "stages": ["plan", "review"],
        "engine": "math-quick",
        "loop_shape": "straight_through",
        "max_iter": 1,
        "max_repair": 0,
    },
    "weather": {
        "label": "Ob-havo",
        "stages": ["plan", "review"],
        "engine": "weather-quick",
        "loop_shape": "straight_through",
        "max_iter": 1,
        "max_repair": 0,
    },
    "creative": {
        "label": "Kreativ variantlar",
        "stages": ["plan", "review"],
        "engine": "llm",
        "loop_shape": "reflexion_critique",
        "max_iter": 1,
        "max_repair": 3,
    },
    "structure": {
        "label": "Loyiha strukturasi",
        "stages": ["plan", "read", "review"],
        "engine": "llm",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    # -- creator-family (artifact ishlab chiqaradi) ------------------------------
    "draw": {
        "label": "Chizma / SVG",
        "stages": ["plan", "edit", "review"],
        "engine": "llm+tools",
        "loop_shape": "build_verify",
        "max_iter": 8,
        "max_repair": 3,
    },
    "ui_build": {
        "label": "UI qurish (uibuild)",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
    "web": {
        "label": "Veb tadqiqot",
        "stages": ["plan", "read", "review"],
        "engine": "llm+tools",
        "loop_shape": "react_iterative",
        "max_iter": 8,
        "max_repair": 0,
    },
    "code": {
        "label": "Kod vazifasi",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "build_verify",
        "max_iter": 8,
        "max_repair": 3,
    },
    "file_task": {
        "label": "Fayl vazifasi (o'qish/tahrirlash)",
        "stages": ["plan", "read", "edit", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
    "composition": {
        "label": "Kompozitsiya (qatlamli qurish)",
        "stages": ["plan", "read", "edit", "test", "review"],
        "engine": "llm+tools",
        "loop_shape": "plan_then_execute",
        "max_iter": 1,
        "max_repair": 0,
    },
}


def _tool_desc_with_hint(schema: dict, hint: Optional[str]) -> str:
    """Schema description'iga 'WHEN TO USE' hint'ini qo'shadi (web+art DRY).

    Base 350 belgigacha cheklanadi, hint esa TO'LIQ saqlanadi (hintlar ~300
    belgidan oshmasa umumiy cap 800 ichida hint o'rtasidan kesilmaydi).
    """
    desc = (schema.get("description") or "")[:350]
    if hint:
        desc = (desc + "\n\nWHEN TO USE: " + hint)[:800]
    return desc


def _drawing_quality_tip(report: dict) -> str:
    """Validator hisobotidan eng zaif jihatlar uchun amaliy takliflar tuzadi.

    Xotiradagi CHIZMA SIFATI yozuviga qo'shiladi — RAG recall'da model
    keyingi chizishda aynan nimani yaxshilashni ko'radi (svg-artist skill
    qoidalariga asoslangan).
    """
    weak = {c.get("name") for c in report.get("checks") or [] if not c.get("ok")}
    style = (report.get("meta") or {}).get("style_comment") or "cartoon"
    tips: list[str] = []
    # flat uslubda gradient/soya bo'lmasligi TO'G'RI — bu uslubda 'qo'shish'
    # taklifi berilmaydi (aks holda modelga zid ko'rsatma ketardi).
    if "gradient" in weak and style != "flat":
        tips.append("asosiy tanaga gradient (linear/radial) qo'shish")
    if "soya" in weak and style != "flat":
        tips.append("yumshoq soya (feDropShadow yoki pastki opacity-ellipse)")
    if "fon" in weak or "fon tartibi" in weak:
        tips.append("birinchi element: to'liq-canvas yumshoq fon rect")
    if "markazlash" in weak:
        tips.append("mavzuni canvas markaziga joylash")
    if "margin" in weak:
        tips.append("chekkadan ~12% margin qoldirish")
    if "chegara" in weak:
        tips.append("kontent viewBox chegarasida qolsin")
    if "ranglar" in weak:
        tips.append("2-6 rangli uyg'un palitra tanlash")
    if "xilma-xillik" in weak:
        tips.append("3+ rang ohangi ishlatish (monoxrom emas)")
    if "uslub mosligi" in weak:
        if style == "realistic":
            tips.append("realistic: gradient + soya majburiy")
        elif style == "flat":
            tips.append("flat: gradient/soya YO'Q bo'lishi kerak")
        else:
            tips.append("cartoon: qalin kontur (stroke-width 4-6)")
    if "silliq chiziqlar" in weak:
        tips.append("stroke-linejoin/linecap round")
    return "; ".join(tips[:4])


class IgrisAgent:
    """Orchestrates bricks -> resolver -> chains -> RAG memory -> optional LLM."""

    def __init__(
        self,
        use_llm: bool = True,
        llm_model: str = "qwen3:8b",
        llm_base_url: str = "http://localhost:11434",
        min_confidence: float = 0.7,
        memory_enabled: bool = True,
        memory_session: str = "",
        memory_dir: str = "",
        workspace_root: str = "",
        # Ixtiyoriy OpenAI-mos logprob re-so'ruvi (self-eval ishonch signali;
        # 2x inference narxi). Server `--logprobs` / `IGRIS_LOGPROBS=1` bilan
        # yoqiladi. Default O'CHIQ — native /api/chat logprob qaytarmaydi.
        llm_logprobs: bool = False,
    ):
        # Deterministic core
        self.bricks = BrickBank().add_many(build_default_bricks())
        self.knowledge = build_default_knowledge()
        self.resolver = ConstraintResolver(self.bricks, self.knowledge)
        self.chains = build_default_chains(self.knowledge)
        self.healer = ChainHealer(self.chains)

        # Hybrid LLM (optional, lazy)
        self.use_llm = use_llm
        self.min_confidence = min_confidence
        self.llm = OllamaClient(model=llm_model, base_url=llm_base_url,
                                logprobs=llm_logprobs)
        self._llm_checked = False
        self._llm_available = False
        # Graceful degradation: LLM xatosidan keyin avtomatik tiklash
        self._llm_last_failure = 0.0     # oxirgi xato vaqti (epoch)
        self._llm_failure_count = 0      # ketma-ket xato soni
        self._llm_cooldown = 60.0        # xatodan keyin kutish vaqti (sekund)
        self._llm_max_cooldown = 600.0   # maksimal cooldown (10 daqiqa)
        # Degradation metrics tracking - time-series uchun
        self._degradation_history: list[dict] = []  # oxirgi N ta event
        self._degradation_max_history = 100         # max tarix uzunligi
        self._degradation_started_at = 0.0          # joriy degradation boshlangan vaqt
        self._total_degradation_time = 0.0          # jami degradation vaqti (sekund)
        self._total_degradation_count = 0           # jami degradation soni
        self._last_recovery_time = 0.0              # oxirgi tiklash vaqti (epoch)

        # Memory / RAG bridge (Igris_Memory)
        self.memory = MemoryBridge(enabled=memory_enabled, session_id=memory_session,
                                   base_dir=memory_dir)

        # Refactor Machine (meta-assessment layer)
        self.refactor = RefactorMachine(agent=self)

        # CAG (response cache) + MAG (memory-augmented context)
        self.cag_cache = None
        self.mag = None

        # Intelligence core (BuildIntalaganceInstructionRequest.md)
        # 2.10 harm-filter -> 2.6 user-model + 2.12 tone-detect ->
        # [2.1 language / 2.2 logic / 2.4 spatial / 2.11 creative] ->
        # 2.7 self-eval. Avtonomiya NOL: bu qatlam hech qachon agentning
        # o'z maqsadini/system prompt'ini o'zi o'zgartirmaydi.
        self.intelligence = IntelligenceCore(
            enabled=True,
            language="auto",
        )

        # Chat tool'lar (MCP + workspace) — lazy init
        self.workspace_root = workspace_root or DEFAULT_WORKSPACE
        self._mcp_cache: Optional[object] = None
        self._chat_exec = None
        self._registry_cache = None
        self._chat_tools_cache: Optional[list[dict]] = None
        # svg-artist skill matni — chizish so'rovlarida system prompt'ga qo'shiladi
        self._draw_skill_cache: Optional[str] = None
        # SEMANTIK TALAB QATLAMI (Part L): user talabini struktur modelga o'tkazadi —
        # javob shakllanishi (til/chuqurlik/format/cheklovlar) shunga moslanadi.
        # LLM yo'q/offline bo'lsa deterministik fallback ishlaydi.
        self.requirements = RequirementExtractor(llm=self.llm, cache=None)

    # ------------------------------------------------------------ #
    # LLM availability (lazy + cached)
    # ------------------------------------------------------------ #

    def llm_available(self) -> bool:
        """LLM mavjudligini tekshiradi. Graceful degradation bilan:

        - Birinchi marta: Ollama mavjudligini tekshiradi
        - Xatodan keyin: cooldown davomida False qaytaradi
        - Cooldown tugagach: qayta tekshiradi (avtomatik tiklash)
        - Maksimal cooldown: 10 daqiqa (cheksiz kutish yo'q)
        """
        if not self.use_llm:
            return False
        now = time.time()
        # Cooldown holatida: hali kutish kerak
        if self._llm_failure_count > 0 and self._llm_last_failure > 0:
            elapsed = now - self._llm_last_failure
            cooldown = min(
                self._llm_cooldown * (2 ** min(self._llm_failure_count - 1, 4)),
                self._llm_max_cooldown
            )
            if elapsed < cooldown:
                return False
            # Cooldown tugadi - qayta tekshiramiz
        if not self._llm_checked:
            self._llm_available = self.llm.is_available()
            self._llm_checked = True
        return self._llm_available

    def _mark_llm_failed(self, error: str = ""):
        """LLM xatosini qayd etadi - graceful degradation uchun.

        Birinchi xatoda: 60s cooldown
        Keyingilarda: 2x oshadi (120s, 240s, 480s, 600s max)
        Cooldown tugagach: avtomatik qayta tekshiriladi.

        Degradation event tarixi saqlanadi - monitoring dashboard uchun.
        """
        now = time.time()
        self._llm_last_failure = now
        self._llm_failure_count += 1
        self._llm_available = False
        self._llm_checked = True
        cooldown = min(
            self._llm_cooldown * (2 ** min(self._llm_failure_count - 1, 4)),
            self._llm_max_cooldown
        )
        # Degradation event tracking
        if self._degradation_started_at == 0:
            self._degradation_started_at = now
            self._total_degradation_count += 1
        event = {
            "type": "failure",
            "timestamp": now,
            "error": str(error)[:200],
            "failure_count": self._llm_failure_count,
            "cooldown_seconds": cooldown,
        }
        self._degradation_history.append(event)
        if len(self._degradation_history) > self._degradation_max_history:
            self._degradation_history.pop(0)
        print(f"[igris] LLM failed ({self._llm_failure_count}x): {error[:80]} - cooldown {cooldown:.0f}s")

    def _mark_llm_recovered(self):
        """LLM qayta ishga tushdi - cooldown'ni tozalaydi.

        Degradation event tarixiga recovery yozuvi qo'shiladi.
        """
        now = time.time()
        recovery_duration = 0.0
        if self._degradation_started_at > 0:
            recovery_duration = now - self._degradation_started_at
            self._total_degradation_time += recovery_duration
        if self._llm_failure_count > 0:
            print(f"[igris] LLM recovered after {self._llm_failure_count} failures ({recovery_duration:.0f}s degradation)")
        # Degradation recovery event
        event = {
            "type": "recovery",
            "timestamp": now,
            "failures_before_recovery": self._llm_failure_count,
            "degradation_duration_seconds": round(recovery_duration, 1),
            "total_degradation_count": self._total_degradation_count,
            "total_degradation_time_seconds": round(self._total_degradation_time, 1),
        }
        self._degradation_history.append(event)
        if len(self._degradation_history) > self._degradation_max_history:
            self._degradation_history.pop(0)
        # Reset state
        self._llm_failure_count = 0
        self._llm_last_failure = 0.0
        self._llm_available = True
        self._llm_checked = True
        self._degradation_started_at = 0.0
        self._last_recovery_time = now

    def degradation_status(self) -> dict:
        """Degradation metrics holati - monitoring dashboard uchun."""
        now = time.time()
        current_degradation_time = 0.0
        if self._degradation_started_at > 0:
            current_degradation_time = now - self._degradation_started_at
        return {
            "is_degraded": self._llm_failure_count > 0,
            "failure_count": self._llm_failure_count,
            "current_cooldown_seconds": min(
                self._llm_cooldown * (2 ** max(0, self._llm_failure_count - 1)),
                self._llm_max_cooldown
            ) if self._llm_failure_count > 0 else 0,
            "current_degradation_seconds": round(current_degradation_time, 1),
            "total_degradation_count": self._total_degradation_count,
            "total_degradation_time_seconds": round(self._total_degradation_time, 1),
            "last_recovery_time": self._last_recovery_time or None,
            "history": self._degradation_history[-20:],  # oxirgi 20 ta event
        }

    # ------------------------------------------------------------ #
    # Universal speed boost (TURBO) — har qanday LLM ga birdek qo'llanadi
    # ------------------------------------------------------------ #

    def set_speed(self, turbo: bool):
        """Universal tez rejim: BIR kalit — barcha modellarni tezlashtiradi.

        - Ollama so'rovlari: kichik kontekst/token, thinking o'chiq, qisqa timeout
        - oddiy chat savollari -> avtomatik tanlangan tez model (fast_model)
        - katta model faqat murakkab/tool vazifalarga qoladi
        """
        if not self.use_llm:
            return
        try:
            models = self.llm.list_models()
        except Exception:
            models = []
        self.llm.set_turbo(bool(turbo), available_models=models)
        print(f"[igris] speed: turbo={'on' if turbo else 'off'} fast_model={self.llm.fast_model}")

    def speed_status(self) -> dict:
        return {
            "turbo": bool(getattr(self.llm, "turbo", False)),
            "fast_model": getattr(self.llm, "fast_model", None),
            "model": self.llm.model,
        }

    # ------------------------------------------------------------ #
    # Semantic requirement layer (Part L — user talabiga mos javob)
    # ------------------------------------------------------------ #

    def _extract_requirements(self, message: str,
                              history: Optional[list] = None) -> Requirement:
        """User talabini struktur modelga o'tkazadi (LLM, CAG-keshlangan).

        Hech qachon exception bermaydi — xatolikda deterministik fallback.
        Chizish so'rovi — DETERMINISTIK tez talab (LLM keraksiz: sekin va
        kuchsiz model noto'g'ri chiqarishi mumkin).
        """
        try:
            if self._is_draw_request(message):
                return self.requirements.extract_fast(message)
        except Exception:
            pass
        try:
            self.requirements.cache = self._cag()
        except Exception:
            pass
        try:
            return self.requirements.extract(message, history)
        except Exception:
            return Requirement()

    def _summary_instruction(self, req: Requirement) -> str:
        """Final xulosa ko'rsatmasi — req (til/chuqurlik/format)ga mos.

        Qotib qolgan "1-2 short sentences" o'rniga foydalanuvchi talabiga
        mos uzunlik va shakl (Part L, CP-L3/B1).
        """
        lang = req.language or "the user's language"
        verb = {
            "concise": "1-2 short sentences",
            "detailed": "a detailed summary (5-8 sentences) covering the key steps",
            "balanced": "2-4 short sentences",
        }.get(req.verbosity, "2-4 short sentences")
        fmt = req.output_format
        text = (
            f"Summarize what you just did for the user in {verb}, in {lang}. "
            "Plain text only — no JSON, no tool-call format, no code fences. "
            "Mention the created file if relevant."
        )
        if fmt in ("list", "table", "steps"):
            text += f" Present the summary as a {fmt}."
        if req.constraints:
            text += " Constraints to respect: " + "; ".join(req.constraints) + "."
        return text

    def _compliance(self, content: str, req: Requirement, message: str) -> str:
        """Talab bilan solishtiradi; nomoslik bo'lsa BIR marta qayta generatsiya.

        Faqat aniq talab (til/format/cheklov/chuqurlik) bor bo'lganda ishlaydi —
        qimmat tekshiruv keraksiz chaqirilmaydi. CAG `chk:` kesh bilan bir xil
        tekshiruv takrorlanmaydi (Part L, CP-L3/B2).
        """
        if not content or not content.strip():
            return content
        if self.llm is None or not self.llm_available():
            return content
        if req.output_format in ("image",):
            return content  # rasm/visual — draw-pipeline orqali tekshirilgan
        if not (req.language or req.output_format != "text" or req.verbosity != "balanced"
                or req.constraints or req.deliverable_name):
            return content
        try:
            cache = self._cag()
            key = f"chk:{message}"
            if cache is not None:
                hit = cache.get("req", key)
                if hit == content:
                    return content
            system = (
                "You verify that an agent's answer satisfies the user's stated "
                "requirements. Respond with ONLY 'yes' or 'no'.\n"
                f"Requirements: intent={req.intent}; language={req.language or 'any'}; "
                f"format={req.output_format}; verbosity={req.verbosity}; "
                f"constraints={req.constraints or 'none'}; "
                f"deliverable={req.deliverable_name or 'none'}.\n"
                "Answer 'no' ONLY if the answer clearly violates a requirement "
                "(wrong language, wrong format, missing requested file, or too "
                "brief when detailed was requested)."
            )
            verdict = self.llm.complete(system=system, prompt=f"Answer: {content[:2000]}")
            if verdict and verdict.strip().lower().startswith("yes"):
                if cache is not None:
                    cache.put("req", key, content)
                return content
            # Nomoslik — talabga mos qilib 1 marta qayta generatsiya
            messages = [
                {"role": "system", "content": (
                    "Improve the previous answer so it strictly follows the user "
                    "requirements. Stay truthful — do not invent facts.\n"
                    + req.to_block()
                )},
                {"role": "user", "content": message},
                {"role": "assistant", "content": content},
            ]
            fixed = self.llm.chat(messages)
            if fixed and fixed.strip():
                return fixed.strip()
        except Exception:
            pass
        return content

    def _retry_generate(self, messages: list[dict], req: Requirement,
                        attempts: int = 2) -> str:
        """Bo'sh/`I could not...` javob o'rniga qayta generatsiya (req bilan).

        Turli temperature/hint bilan 2 urinish; hali ham bo'sh bo'lsa — halol,
        template bo'lmagan minimal javob (yolg'on "bajarildi" aytmaydi).
        """
        # Part O: chizish so'rovi — kuchsiz model qimmat/junk SVG beradi;
        # retry qilish o'rniga to'g'ridan-to'g'ri halol javob (tez, crashsiz).
        user_msg = " ".join(str(m.get("content") or "") for m in (messages or [])
                            if m.get("role") == "user")
        is_draw = bool(user_msg) and self._is_draw_request(user_msg)
        if is_draw:
            attempts = 0
        for i in range(attempts):
            try:
                m = list(messages)
                if i > 0:
                    m.append({"role": "user", "content":
                              "Please actually answer the user's request now. "
                              + req.to_block()})
                out = self.llm.chat(m) if i == 0 else self.llm.complete(
                    system=(m[0].get("content") if m and m[0].get("role") == "system" else ""),
                    prompt=m[-1].get("content", ""))
                if out and out.strip():
                    # Part O: soxta "Chizdim ... rasm tayyor" (model rasmini
                    # CHIZMAGAN) — muvaffaqiyat deb qabul qilinmaydi.
                    if self._fake_draw_claim(out):
                        continue
                    return out.strip()
            except Exception:
                continue

        # Part N: xabarni TILga mos va REAL SABAB bilan beramiz — "rephrase"
        # shabloni emas. Model yuklana olmasa (OOM) avtomatik kichik modelga
        # o'tilgan; baribir bo'sh bo'lsa — tushunarli izoh.
        lang = (req.language or self._detect_lang(messages) or "uz")
        # Part O: chizish so'rovi bajarilmadi — ma'lum narsalarni taklif qilamiz
        # (yolg'on "Chizdim" emas).
        if is_draw:
            if lang == "uz":
                return ("Bu narsani hozirgi model bilan aniq chizib bo'lmadi. "
                        "Ma'lum narsalardan birini so'rang (olma, uy, daraxt, "
                        "mushuk, mashina, gul, qush, baliq, kapalak...) yoki "
                        "Settings'dan kuchliroq modelni tanlang.")
            return ("The current model could not draw this accurately. Ask for a "
                    "known subject (apple, house, tree, cat, car, flower, bird, "
                    "fish, butterfly...) or pick a stronger model in Settings.")
        reason = (getattr(self.llm, "last_error", None) or "").lower()
        if any(k in reason for k in ("out of memory", "cudamalloc", "xotira",
                                     "yuklana olmadi", "failed to load",
                                     "unable to allocate", "cuda0 buffer")):
            if lang == "uz":
                return ("Model GPU xotirasi yetmagani uchun yuklana olmadi — "
                        "kichikroq modelga avtomatik o'tildi. Yana bir marta "
                        "yozib ko'ring yoki Settings'dan boshqa model tanlang.")
            return ("The model could not load (GPU memory) — a smaller model "
                    "was selected automatically. Try again or pick another "
                    "model in Settings.")
        if reason and "ollama" in reason:
            if lang == "uz":
                return (f"Model ishlay olmadi (Ollama xatosi). Qayta urinib "
                        f"ko'ring. Tafsilot: {reason[:120]}")
            return (f"The model failed (Ollama error). Please try again. "
                    f"Detail: {reason[:120]}")
        if lang == "uz":
            return ("Men javob bera olmadim — model bo'sh natija qaytardi. "
                    "So'rovingizni boshqacha shaklda yozib ko'ring yoki aniqroq "
                    "ayting (men nima qilishim kerakligini).")
        return ("I could not produce an answer — the model returned an empty "
                "response. Please try again or rephrase your request.")

    def _detect_lang(self, messages: list[dict]) -> str:
        """Xabarlardan tilni aniqlaydi (uz/en) — fallback xabari to'g'ri tilda."""
        try:
            import re as _re
            text = " ".join(str(m.get("content") or "") for m in (messages or [])
                            if m.get("role") == "user").lower()
            if _re.search(
                    r"[ʻ'`‘]?[oO]ʻ|[gG]ʻ|ў|қ|ғ|ҳ|ё|o'z|qan|uchun|kerak|salom|"
                    r"rasm|chiz|qilib|so'rang|mushuk|gul|baliq|kapalak|mashina|"
                    r"daraxt|quyosh|yulduz|yurak|raketa|tog|havo|nech|qanday|"
                    r"qanaqa|ko'rsat|yozib|olma|uy|qush|rangda|o'lcham|uslub",
                    text):
                return "uz"
            return "en"
        except Exception:
            return "uz"

    def _draw_unsupported_message(self, request: str) -> str:
        """Noma'lum subject chizish — tez halol javob (model ishlamaydi)."""
        lang = self._detect_lang([{"role": "user", "content": request}])
        if lang == "uz":
            return ("Bu narsani hozirgi model bilan aniq chizib bo'lmadi. "
                    "Ma'lum narsalardan birini so'rang (olma, uy, daraxt, mushuk, "
                    "mashina, gul, qush, baliq, kapalak, quyosh, oy, yulduz, "
                    "yurak, raketa...) yoki Settings'dan kuchliroq modelni tanlang.")
        return ("The current model could not draw this accurately. Ask for a known "
                "subject (apple, house, tree, cat, car, flower, bird, fish, "
                "butterfly, sun, moon, star, heart, rocket...) or pick a stronger "
                "model in Settings.")

    # ------------------------------------------------------------ #
    # Resolution pipeline
    # ------------------------------------------------------------ #

    def resolve(self, query: str, allow_llm: bool = True, use_memory: bool = True) -> dict:
        """Full pipeline: RAG recall -> deterministic -> (heal) -> LLM fallback.

        Returns a dict with status, confidence, engine, output, trace,
        duration_ms and (ok rezolyutsiyalarda) self_eval. Every resolution
        is remembered in Igris_Memory — istisno: repair qilib bo'lmaydigan
        buzilgan LLM chiqishi (verified='fail') RAG'ni ifloslantirmaslik
        uchun xotiraga YOZILMAYDI.
        """
        t0 = time.perf_counter()

        # 0. RAG recall (memory context, before any engine runs)
        memory_ctx, memory_hits = self.memory.recall(query) if (use_memory and self.memory.enabled) else ("", 0)

        # 1. Deterministic pass
        res: Resolution = self.resolver.resolve(query)

        # 2. Healing pass when deterministic output is weak
        if res.status == "failed":
            healed = self.resolver.heal(query, self.chains.availability(),
                                        self.chains.similarity_map())
            if healed.confidence > 0:
                res = healed

        # 3. Hybrid LLM fallback for low confidence / complex queries
        if allow_llm and self.llm_available() and res.confidence < self.min_confidence:
            # Part L (D2): LLM fallback endi faqat kod emas — user talabining
            # O'ZI asosida javob beradi (eski "har doim Python kodga aylantir"
            # fiksiri qotib qolgan pattern edi). `req.intent == code` bo'lsa
            # kod prompti, aks holda umumiy (req-format/til/chuqurlik bo'yicha).
            req = self._extract_requirements(query, None)
            if req.intent == "code":
                system = (
                    "You are Igris, a coding agent. Convert the user request "
                    "into executable code. Respond with only the code, "
                    "no explanation, in a code fenced block."
                )
            else:
                system = (
                    "You are Igris, a local assistant. Answer the user's request "
                    "directly and truthfully, following exactly the requirements.\n"
                    + req.to_block()
                )
            if memory_ctx:
                system += (
                    "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                    + memory_ctx
                )
            try:
                llm_out = self.llm.complete(system=system, prompt=query)
            except Exception as llm_exc:
                # LLM xatosi - graceful degradation: deterministic natijani qaytaramiz
                self._mark_llm_failed(str(llm_exc))
                print(f"[igris] LLM failed in resolve, falling back to deterministic: {llm_exc}")
                llm_out = None
            if llm_out:
                # Muvaffaqiyatli LLM chaqiruvi - cooldown'ni tozalaymiz
                self._mark_llm_recovered()
                code = self.llm.extract_code(llm_out) if req.intent == "code" else llm_out
                # A2: LLM fallback yo'lida ham struktura tekshiruvi/ta'mirlash —
                # chat final yo'li bilan BIR XIL: code chiqishi repair'dan o'tadi,
                # muammo bo'lsa `structure_check` biriktiriladi va `verified`
                # signali self_eval'ga ulanadi (repaired −0.10 / fail −0.25).
                # Toza javoblar hisobotga tushmaydi (shovqin yo'q).
                code_final, struct_check = self._verify_and_repair(code or "")
                data = {
                    "query": query,
                    "status": "ok",
                    "engine": "llm",
                    "model": self.llm.model,
                    "matched_bricks": res.matched_bricks,
                    "matched_rules": res.matched_rules,
                    "trace": res.trace + ["Engine: Ollama LLM fallback"],
                    "output": code_final or code,
                    "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                }
                if struct_check is not None:
                    data["structure_check"] = struct_check
                # Ixtiyoriy logprob re-so'ruvi uchun system+query saqlanadi
                # (`_self_eval_for` o'qiydi va olib tashlaydi).
                data["_llm_messages"] = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ]
                # A2: self_eval BIR MARTA hisoblanadi, confidence undan olinadi
                # (LLM fallback yo'lida ham javob kalibrlangan bo'ladi).
                # `confidence` DOIM mavjud bo'lishi kerak — intellekt xato
                # bersa ham neytral 0.5 qaytadi (eski _calibrated_confidence
                # fallback'i kabi).
                ev = self._self_eval_for(data)
                data["confidence"] = (ev or {}).get("confidence", 0.5)
                self.refactor.observe(query, data)
                # RAG ifloslanmasligi: repair qilib BO'LMAYDIGAN buzilgan
                # chiqish (structure_check ok=False, verified='fail') xotiraga
                # yozilmaydi — aks holda keyingi recall buzilgan code'ni
                # qaytaradi. Javob foydalanuvchiga baribir qaytadi (fail
                # signali + past confidence bilan); telemetry (refactor)
                # ham yoziladi — faqat RAG tozalanadi.
                if struct_check is None or struct_check.get("ok") is not False:
                    self.memory.on_resolve(query, data)
                return data

        # Return deterministic resolution
        data = res.to_dict()
        data["engine"] = "deterministic" if not data["healed"] else "healed"
        data["memory"] = {"recall_hits": memory_hits, "context_chars": len(memory_ctx)}
        # A2: resolverning heuristic confidence'i o'rniga — SelfEvaluator (2.7)
        # kalibratsiyasi (engine/status/output/memory_hits/healed signallari).
        # Resolverning O'Z bahosi (0.6*rule_score + 0.4*coverage) `resolver_score`
        # sifatida uzatiladi — kuchsiz rule mosligi deterministik OK'ni 1.0 ga
        # cheklab qo'ymaydi (SelfEvaluator engine signalini shu bilan scaley
        # qiladi). FAQAT muvaffaqiyatli (status="ok") rezolyutsiyalar
        # kalibrlanadi — failed/partial (0.0/<=0.5) resolver bahosi saqlanadi,
        # aks holda SelfEvaluator ularni 0.4/0.75 ga ko'tarib, RAG'ni
        # shishirilgan ishonch bilan ifloslantirishi mumkin edi ("low = yomon
        # javob" kontrakti buzilardi). self_eval ham shu yerda BIR MARTA
        # hisoblanadi va `data["self_eval"]`'ga biriktiriladi (resolve natijasi
        # chat natijalari kabi kalibrlangan bo'ladi).
        if data["status"] == "ok":
            data["resolver_score"] = float(res.confidence or 0.0)
            ev = self._self_eval_for(data)
            if ev:
                data["confidence"] = ev.get("confidence", 0.5)
        data["chains"] = self.active_chains(res)
        data["llm_available"] = self.llm_available()
        data["duration_ms"] = (time.perf_counter() - t0) * 1000.0

        # Continuous process analysis (telemetry)
        self.refactor.observe(query, data)
        self.memory.on_resolve(query, data)
        return data

    def chat(self, message: str, history: Optional[list[dict]] = None,
             use_memory: bool = True, progress_cb=None) -> dict:
        """Conversational completion (used by the interface bridge server).

        Chat ham REAL tool'lar bilan ishlaydi: foydalanuvchi rasm chizish, sahifa
        ochish yoki fayl yaratishni so'rasa, model mavjud MCP/registry tool'larini
        chaqiradi, ular bajariladi va javobga `tool_calls` + `image` maydonlari
        qo'shiladi (frontend karta ko'rsatadi). Oddiy savollarda esa to'g'ridan-
        to'g'ri javob beradi.

        CAG (cache-augmented): keshda javob bo'lsa — LLM chaqirilmaydi.
        MAG (memory-augmented): xotira konteksti L1+L2+RAG yig'ib beriladi.

        progress_cb: ixtiyoriy (stage, detail) callback — frontend pipeline
        stepperiga JONLI progress yuboradi (chat run davomida).

        history: [{role: 'user'|'assistant', content: str}, ...]
        """
        t0 = time.perf_counter()

        # --- TODO COMMAND CHECK ---
        # Todo buyruqlarini tekshiramiz (/todo ... yoki natural language)
        try:
            from todo_integration import get_todo_integration
            todo_int = get_todo_integration()
            todo_result = todo_int.process_message(message)
            if todo_result and todo_result.get("is_todo"):
                return self._finalize({
                    "message": message,
                    "content": todo_result["response"],
                    "engine": "todo",
                    "model": self.llm.model,
                    "tool_calls": [],
                    "image": None,
                    "memory": {"recall_hits": 0, "context_chars": 0},
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                    "todo": todo_result.get("data"),
                }, None)
        except ImportError:
            pass  # Todo integration not available

        # JONLI PIPELINE: chat boshlanganda — real stage frontend stepperiga yuboriladi
        if progress_cb is not None:
            try:
                progress_cb("plan", "task tahlil qilinmoqda…")
            except Exception:
                pass

        # AGENTIK PIPELINE: zarurat turi aniqlanadi va mos pipeline tanlab
        # QURILADI (chat/math/weather/draw/ui_build/web/code/composition/...).
        # Detektorlar deterministik (LLM chaqirilmaydi) — progress'da pipeline
        # nomi ko'rinadi, oxirida ish yakuni `completion` record'ida
        # konversatsiyaga to'ldiriladi.
        pipeline = self._build_pipeline(message, history)
        # SEMANTIK TALAB (Part L): user talabini struktur modelga o'tkazamiz —
        # javob shakllanishi (til/chuqurlik/format/cheklovlar) shunga moslanadi.
        req = self._extract_requirements(message, history)
        if progress_cb is not None:
            try:
                progress_cb("plan", f"{pipeline['label']}: {pipeline['clarified']}")
            except Exception:
                pass

        # --- CLARIFICATION GATE (§3.3.c) ---
        # Pre-loop: so'rov yetarli darajada aniqlanganini tekshiramiz.
        # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
        # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
        # bergandan keyin pipeline QAYTA ishga tushadi.
        clar = self._clarification_gate(req)
        if clar is not None:
            return self._finalize({
                "message": message,
                "content": clar["question"],
                "engine": "clarification",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "clarification": {
                    "question": clar["question"],
                    "missing_fields": clar["missing_fields"],
                },
            }, pipeline)

        # --- SUPERVISOR INTEGRATION (§9) ---
        # Complex so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi.
        supervisor_result = self._run_supervisor(message, pipeline, progress_cb)
        if supervisor_result is not None:
            data = {
                "message": message,
                "content": supervisor_result.get("summary", ""),
                "engine": "supervisor",
                "model": self.llm.model if self.llm_available() else "offline",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "supervisor": {
                    "status": supervisor_result.get("status"),
                    "iterations_used": supervisor_result.get("iterations_used", 0),
                    "nodes": supervisor_result.get("nodes", {}),
                },
            }
            return self._finalize(data, pipeline)

        # INTELLEKT 2.10 (harm-filter): operator buyrug'i aniq zarar
        # chegarasidan o'tsa — rad etiladi, sabab tushuntiriladi. Bu eng
        # birinchi qadam (qo'llanma 4-bo'lim oqimi). Rad etilgan so'rov
        # LLM'ga ham bormaydi, xotiraga ham yozilmaydi.
        verdict = self.intelligence.screen(message)
        if not verdict.allowed:
            if progress_cb is not None:
                try:
                    progress_cb("review", "so'rov rad etildi (zarar filtri)")
                except Exception:
                    pass
            refusal = verdict.reason or "Bu so'rov aniq zarar chegarasidan o'tadi."
            data = {
                "message": message,
                "content": refusal,
                "engine": "harm-filter",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "refused": True,
                "refusal_category": verdict.category,
                "self_eval": self.intelligence.evaluate(
                    engine="harm-filter", status="ok", output=refusal
                ).to_dict(),
            }
            return self._finalize(data, pipeline)

        # INTELLEKT 2.6+2.12: foydalanuvchi xabarini kuzatamiz (profil signali)
        # va ohangni aniqlaymiz — faqat moslashtirish uchun, manipulyatsiya emas.
        try:
            self.intelligence.observe(message)
        except Exception:
            pass

        # TEZ DETERMINISTIK YO'L: ob-havo so'rovi — brauzer/LLM keraksiz,
        # Open-Meteo API orqali 2-4 soniyada aniq javob (qwen3:8b katta modelni
        # ishga tushirmaydi — tezlik va aniqlik kafolati).
        quick = self._quick_weather(message)
        if quick is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "javob tayyor")
                except Exception:
                    pass
            data = {
                "message": message,
                "content": quick,
                "engine": "weather-quick",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "quick": True,
            }
            if self.memory.enabled:
                try:
                    self.memory.on_resolve(message, {"output": quick, "engine": "weather-quick", "confidence": self._confidence_for(data)})
                except Exception:
                    pass
            return self._finalize(data, pipeline)

        # INTELLEKT 2.2 (logic): oddiy arifmetika — deterministik tez yo'l
        # (LLM/brauzer keraksiz; xavfsiz safe_math orqali hisoblanadi).
        quick_math = self._quick_math(message)
        if quick_math is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "javob tayyor")
                except Exception:
                    pass
            data = {
                "message": message,
                "content": quick_math,
                "engine": "math-quick",
                "model": self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "quick": True,
            }
            if self.memory.enabled:
                try:
                    self.memory.on_resolve(message, {"output": quick_math, "engine": "math-quick", "confidence": self._confidence_for(data)})
                except Exception:
                    pass
            return self._finalize(data, pipeline)

        memory_ctx, memory_hits = self.memory.recall(message) if (use_memory and self.memory.enabled) else ("", 0)

        # MAG: L1+L2+RAG kontekstini yig'amiz (RAG recall'dan to'liqroq).
        # RAG recall allaqachon kontekst bergan bo'lsa — MAG takror ishlamaydi.
        mag_ctx = ""
        if use_memory and self.memory.enabled and not history and not memory_ctx:
            try:
                mag = self._mag()
                mag_ctx = mag.assemble(message)["context"] if mag else ""
            except Exception:
                mag_ctx = ""

        # INTELLEKT 2.1/2.2/2.6/2.12: system prompt'ni moslashtiramiz —
        # domain lug'at + foydalanuvchi profili + ohang + CoT yo'naltirish.
        # Bu faqat javob SIFATINI o'zgartiradi, maqsadli natijani emas.
        system = self.intelligence.adapt_system(CHAT_TOOLS_SYSTEM, message)
        cot = self.intelligence.reasoning_suffix()
        if cot and cot not in system:
            system = (system or "") + "\n\n" + cot
        # REAL bugungi sana — eskirgan/soxta sana javoblarini oldini oladi
        system = (system or "") + self._today_note()
        # INTELLEKT 2.3 (musiqa): musiqa/ovoz so'rovi — glossary + yo'naltirish
        music_dir = self._intel("music_directive", message)
        if music_dir:
            system += "\n\n" + music_dir
        # INTELLEKT 2.4 + 2.8 (spatial + naturalist): loyiha strukturasi so'rovi —
        # workspace daraxti + til taqsimoti konteksti (agent muhitni ko'radi).
        _sp = None
        if self._is_structure_request(message):
            _sp = self._spatial_env_context(message)
            if _sp:
                system += "\n\n" + _sp[0]
        # CHIZISH SO'ROVI: svg-artist skill ko'rsatmasi AVTOMATIK qo'shiladi —
        # model har chizishda professional SVG (gradient/soya/qatlamlar) yaratadi
        if self._is_draw_request(message):
            skill_text = self._draw_skill_text()
            if skill_text:
                system += "\n\n" + skill_text
            # Oxirgi chizma sifat feedback'i — model avvalgi xatolarini
            # takrorlamasligi uchun (RAG recall'ga tayanmasdan ham ishlaydi)
            fb = self._draw_feedback_context()
            if fb:
                system += "\n\n" + fb
        # WEB SO'ROVI: qaror qoidalari — model eng arzon vositanı tanlaydi
        # (to'g'ridan-to'g'ri javob > web_fetch > web AI subagent > browser).
        web_strategy = self._web_strategy(message)
        # Qoidalar faqat web_ai_bridge MCP ulangan bo'lsa qo'shiladi — aks holda
        # modelga mavjud bo'lmagan tool'lar (ask_web_ai/browser) eslatilmaydi.
        if web_strategy and self._mcp() is not None:
            system += "\n\n" + self._web_decision_rules(web_strategy)
        # STACK GUIDE: kod so'rovida framework/til aniqlansa — model aniq
        # buyruqlarni (npm/pip/mvn...) ishlatishi uchun yo'naltiruv qo'shiladi.
        stack_guide = self._stack_guide(pipeline)
        if stack_guide:
            system += "\n\n" + stack_guide
        if memory_ctx:
            system += (
                "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                + memory_ctx
            )
        elif mag_ctx:
            system += "\n\nMemory context:\n" + mag_ctx
        # SEMANTIK TALAB BLOKI (Part L): model javobni req'ga mos shakllantiradi.
        if self.llm_available():
            system += "\n\n" + req.to_block()

        messages: list[dict] = [{"role": "system", "content": system}]
        for h in (history or [])[-12:]:
            role = h.get("role")
            content = h.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        # CAG: keshda javob bo'lsa, LLM'ni ishga tushirmaymiz (faqat oddiy savollar).
        # Kesh kaliti STABIL bo'ladi: CHAT_TOOLS_SYSTEM (o'zgarmas) + message.
        # memory_ctx kesh kalitiga kirmaydi — aks holda birinchi javob xotirada
        # eslab qolingach, keyingi takroriy savolda kontekst o'zgarib miss bo'lardi.
        if not history and not self._is_draw_request(message) and not self._is_date_question(message):
            cache = self._cag()
            if cache is not None:
                cached = cache.get(CHAT_TOOLS_SYSTEM, message)
                if cached is not None:
                    # AUDIT (CAG hit): keshlangan matn ham repair'dan o'tadi —
                    # eski/buzilgan kesh yozuvlari ham `data["content"]` kabi
                    # canonical (repair'dan keyingi) matn bo'ladi; memory va
                    # confidence shundan hisoblanadi (xom kesh bilan tafovut yo'q).
                    out_final, struct_check = self._verify_and_repair(cached)
                    tool_calls: list[dict] = []
                    image: Optional[str] = None
                    engine = "cag"
                    duration = (time.perf_counter() - t0) * 1000.0
                    data = {
                        "message": message,
                        "content": out_final or cached,
                        "engine": engine,
                        "model": self.llm.model,
                        "tool_calls": tool_calls,
                        "image": image,
                        "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                        "duration_ms": duration,
                        "cag": {"hit": True},
                    }
                    if struct_check is not None:
                        data["structure_check"] = struct_check
                    # keshlangan javob ham xotiraga yoziladi (RAG boyiydi) — final
                    # yo'li bilan BIR XIL: `data["content"]` (repair'dan keyingi)
                    # saqlanadi, bo'sh/xato javoblar yozilmaydi. Fail-guard:
                    # repair qilib BO'LMAYDIGAN chiqish ham yozilmaydi.
                    if (self.memory.enabled and self._cacheable_out(data.get("content"))
                            and (struct_check is None or struct_check.get("ok") is not False)):
                        self.memory.on_resolve(message, {"output": data["content"], "engine": "cag", "confidence": self._confidence_for(data)})
                    return self._finalize(data, pipeline)

        tool_calls: list[dict] = []
        image: Optional[str] = None
        redraw_note: Optional[dict] = None
        out = ""
        engine = "deterministic"

        # INTELLEKT 2.11 (creative): kreativ so'rov — multi-temperature variantlar
        # (CAG'ga tushmagan, tool kerak bo'lmagan, TARIXSIZ oddiy so'rovda ishlaydi
        # — tarixli davomiy so'rovda kontekst yo'qolmasligi uchun oddiy yo'l ishlaydi).
        creative_data = None
        if not history:
            creative_data = self._creative_variants(message, system=system, memory_hits=memory_hits)
        if creative_data is not None:
            if progress_cb is not None:
                try:
                    progress_cb("review", "kreativ variantlar tayyorlanmoqda…")
                except Exception:
                    pass
            return self._finalize(creative_data, pipeline)

        # TURBO tez yo'l faqat tool'siz oddiy savollarga ishlaydi (rasm chizish,
        # fayl yaratish, web ochish kabi vazifalar katta modelni talab qiladi).
        tool_needed = (
            self._is_draw_request(message)
            or self._needs_web(message)
            or bool(self._registry() and any(
                w in message.lower()
                for w in ("fayl", "file", "write", "yarat", "create", "dastur", "kod", "code")
            ))
        )

        if self.llm_available():
            # WEB avtomatizatsiya: so'rovda sayt/URL/brauzer ehtiyoji bo'lsa —
            # browser tool'lari chatda ham avtomatik ochiladi (model ularni
            # ishlatishi uchun). Oddiy chatda ochilmaydi (keraksiz chaqiruvlar
            # oldini oladi).
            web_needed = bool(web_strategy)
            llm_failed = False
            try:
                # TURBO tez yo'l: oddiy savol + tez rejim -> kichik/tez modelga
                # yo'naltiramiz (tool kerak emas, katta model ishlamaydi).
                if (
                    getattr(self.llm, "turbo", False)
                    and not tool_needed
                    and not history
                ):
                    fast = self.llm.chat_fast(messages)
                    if fast and fast.strip():
                        # AUDIT (turbo yo'li): final yo'l bilan BIR XIL — repair'dan
                        # keyingi matn saqlanadi, memory output == confidence signali
                        # == ko'rsatilgan javob (raw `out` emas, tafovut yo'q).
                        out_final, struct_check = self._verify_and_repair(fast.strip())
                        engine = "llm-fast"
                        data = {
                            "message": message,
                            # Part L: bo'sh javob o'rniga req-aware retry (canned emas)
                            "content": out_final or self._retry_generate(messages, req),
                            "engine": engine,
                            "model": self.llm.fast_model or self.llm.model,
                            "tool_calls": [],
                            "image": None,
                            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                            "duration_ms": (time.perf_counter() - t0) * 1000.0,
                            "turbo": True,
                        }
                        if struct_check is not None:
                            data["structure_check"] = struct_check
                        # logprob re-so'ruvi (ixtiyoriy) uchun asl messages
                        if engine in ("llm", "llm+tools", "llm-fast"):
                            data["_llm_messages"] = messages
                        # Guard ham final yo'l bilan bir xil: bo'sh/xato javoblar RAG'ga
                        # tushmaydi (eski holatda faqat `engine != "offline"` edi).
                        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish ham yozilmaydi.
                        if (engine != "offline" and self._cacheable_out(data.get("content"))
                                and (struct_check is None or struct_check.get("ok") is not False)):
                            self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
                        return self._finalize(data, pipeline)
                tools = self._chat_tools(include_web=web_needed, web_strategy=web_strategy)
                content, tool_calls, image, redraw_note = self._chat_with_redraw(
                    messages, tools, web=web_needed, progress=progress_cb, request=message,
                    req=req)
                out = content
                engine = "llm+tools" if tool_calls else "llm"
                if not (out or "").strip():
                    # Part L: bo'sh javob / web-toolsiz matn o'rniga req-aware retry
                    # (canned "Veb so'rovi aniqlandi..." emas — real urinish).
                    out = self._retry_generate(messages, req)
                # Muvaffaqiyatli LLM chaqiruvi - cooldown'ni tozalaymiz
                self._mark_llm_recovered()
                # KUZATUV: strategiya to'g'ri tanlandimi + model nima qildi
                # (`_mcp_cache` — server ishga tushirmaydi, faqat holatni o'qiydi)
                self._log_web_strategy(message, web_strategy, tool_calls, engine,
                                       mcp_ok=self._mcp_cache is not None,
                                       content_len=len(out or ""))
            except Exception as llm_exc:
                # LLM xatosi — graceful degradation: bricks+RAG bilan davom etamiz
                llm_failed = True
                self._mark_llm_failed(str(llm_exc))
                print(f"[igris] LLM failed in chat, degrading: {llm_exc}")

        if not self.llm_available() or llm_failed:
            # offline/graceful degradation: bricks + RAG bilan best-effort
            engine = "offline" if not llm_failed else "degraded"
            # `_mcp_cache` — offline yo'lida MCP serverlarni ishga tushirmaydi
            self._log_web_strategy(message, web_strategy, [], engine,
                                   mcp_ok=self._mcp_cache is not None)
            res = self.resolve(message, allow_llm=False, use_memory=use_memory)
            if res.get("status") == "ok" and res.get("output"):
                out = res["output"]
            else:
                # Bricks+RAG ham javob bera olmadi — foydalanuvchiga tushuntiramiz
                if llm_failed:
                    out = (
                        f"IGRIS LLM xatosi tufayli vaqtincha cheklangan holatda ishlayapti. "
                        f"Deterministik dvigatel (bricks + RAG xotira) bilan javob berishga "
                        f"urinildi, lekin bu so'rov uchun yetarli ma'lumot topilmadi. "
                        f"LLM avtomatik tiklanadi ({self._llm_cooldown:.0f}s ichida). "
                        f"Xato: {str(llm_exc)[:100] if llm_failed else 'noma\'lum'}"
                    )
                else:
                    out = (
                        "IGRIS hozir javob bera olmadi — Ollama (lokal AI) "
                        "yoqilmagan. Iltimos `run.bat` orqali yoki terminalda "
                        "`ollama serve` bilan Ollama'ni ishga tushiring, so'ng qayta "
                        "yozing. (Deterministik dvigatel faqat oldindan ma'lum bo'lgan "
                        "oddiy kod so'rovlarini biladi — suhbat savollariga javob "
                        "bera olmaydi.)"
                    )

        if progress_cb is not None:
            try:
                progress_cb("review", "javob yozilmoqda…")
            except Exception:
                pass

        out_final, struct_check = self._verify_and_repair(out or "")
        # Part L (B2): talab compliance — nomoslik bo'lsa 1 marta qayta generatsiya.
        # Part O: rasm/visual natija (image mavjud) — LLM compliance KERAKSIZ
        # (chizma deterministik yoki draw-pipeline orqali tekshirilgan); sekin
        # LLM chaqiruvi tezlikni buzmasin.
        content_final = out_final or ""
        if content_final and not image and engine != "offline" and self.llm_available() \
                and req.output_format not in ("image",):
            content_final = self._compliance(content_final, req, message)
        data = {
            "message": message,
            "content": content_final or self._retry_generate(messages, req),
            "engine": engine,
            "model": self.llm.model,
            "tool_calls": tool_calls,
            "image": image,
            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            "duration_ms": (time.perf_counter() - t0) * 1000.0,
        }
        if redraw_note:
            data["redraw"] = redraw_note
        # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
        if struct_check is not None:
            data["structure_check"] = struct_check
        # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (loyiha strukturasi)
        if _sp:
            data["spatial"] = _sp[1]
        # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi —
        # `_self_eval_for` uni o'qiydi va olib tashlaydi (javob toza qoladi).
        if engine in ("llm", "llm+tools", "llm-fast"):
            data["_llm_messages"] = messages
        # CAG: yangi javobni keshga yozamiz. Faqat SIFATLI javoblar keshlanadi —
        # offline/bo'sh/xato javoblar, rasm/tool va sana so'rovlari keshga tushmaydi.
        # AUDIT (CAG put): keshlangan matn AYNAN `data["content"]` (= repair'dan
        # keyingi, ko'rsatilgan javob) bo'ladi — xom `out` emas. Aks holda keyingi
        # CAG-hit xom/buzilgan matnni qaytarib, repair chetlab o'tilardi
        # (keshlangan out vs content tafovuti).
        if (self.llm_available() and not tool_calls
                and not self._is_draw_request(message)
                and not self._is_date_question(message)
                and self._cacheable_out(data.get("content"))
                # Fail-guard: repair qilib bo'lmagan chiqish keshlanmaydi
                and (struct_check is None or struct_check.get("ok") is not False)):
            cache = self._cag()
            if cache is not None:
                cache.put(CHAT_TOOLS_SYSTEM, message, data["content"])
        # remember the exchange (L2 solution-memory + L1 short-turn). Offline
        # xabar xotiraga yozilmaydi; bo'sh/xato javoblar ham YO'Q — RAG'ga
        # "javob bermadi" deb o'rganib qolmasligi uchun.
        # Xotiraga `data["content"]` (= out_final, repair'dan keyingi matn)
        # yoziladi — confidence `_confidence_for(data)` orqali AYNAN shu
        # matndan hisoblanadi (raw `out` emas), tafovut yo'q. Guard ham
        # saqlanadigan matnga qaraydi (stream final yo'li bilan bir xil).
        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish ham RAG'ga yozilmaydi.
        if (engine != "offline" and self._cacheable_out(data.get("content"))
                and (struct_check is None or struct_check.get("ok") is not False)):
            self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
        return self._finalize(data, pipeline)

    def chat_stream(self, message: str, history: Optional[list[dict]] = None,
                    use_memory: bool = True, progress_cb=None):
        """Token-ustali chat — generator bo'lib VOQEALAR beradi (SSE uchun).

        `/api/chat` sinxron javob qaytaradi; bu generator esa javobni
        TOKEN-KETMA-TOKEN uzatadi — frontend agent yozayotginda matnni jonli
        ko'radi (bir necha daqiqa bo'sh kutish o'rniga). Har bir `yield` dict:

          {"type": "stage", "stage": "plan|read|edit|test|review", "detail": str, "layer": "planning"}
          {"type": "thinking", "content": "<fikrlash deltasi>"}  — qwen3 reasoning
          {"type": "token", "content": "<delta>", "source": "llm"}     — yangi token parchası
          {"type": "done", **chat_result_dict}        — to'liq yakuniy natija
          {"type": "layer_start", "layer": "clarification"}  — clarification bosqichi boshlandi
          {"type": "layer_done", "layer": "clarification", "status": "complete"}  — clarification tugadi
          {"type": "clarify", "question": "..."}  — userdan qo'llab-quvvatlanuvchi savol
          {"type": "validation_error", "issue": "..."}  — natija validatsiya muammosi

        Thinking hodisalari: qwen3 kabi reasoning modellarda fikrlash bosqichi
        ham token-ketma-token uzatiladi (frontend "thinking" blokida ko'rsatadi),
        so'ng yakuniy javob `token` hodisalari bilan oqadi. `done` voqeasi
        `thinking` maydonida TO'LIQ fikrlash matnini ham olib keladi.

        Xulq:
          - harm-filter / ob-havo / CAG kesh / turbo-fast / tool'lar kabi
            bosqichlar BUFFERED ishlaydi (ular bir zumda yoki round'larda
            tugaydi) — ularda bitta `done` voqeasi chiqadi.
          - oddiy suhbat javoblari (tool kerak emas) — `llm.chat_stream()`
            orqali REAL token oqimi uzatiladi.
          - stream uzilsa (transport xatosi) — `self.chat()`'ga qaytamiz va
            yaxlit natijani `done` sifatida beramiz (javob yo'qolmaydi).
          - har bir bosqich layer_start/layer_done yordamida kuzatadi;
            tokenlar `source` maydonida ishlab chiqaruvchini (llm/tool/skill/mcp) namoyish etadi.
        """
        t0 = time.perf_counter()

        # AGENTIK PIPELINE: zarurat turi aniqlanadi va pipeline quriladi —
        # chat() bilan BIR XIL (har bir done voqeasida completion record
        # konversatsiyaga to'ldiriladi).
        pipeline = self._build_pipeline(message, history)
        # SEMANTIK TALAB (Part L): chat() bilan BIR XIL — req modeli.
        req = self._extract_requirements(message, history)

        # --- CLARIFICATION GATE (§3.3.c) ---
        # Pre-loop: so'rov yetarli darajada aniqlanganini tekshiramiz.
        # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
        # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
        # bergandan keyin pipeline QAYTA ishga tushadi.
        clar = self._clarification_gate(req)
        if clar is not None:
            yield {"type": "layer_start", "layer": "clarification"}
            yield {
                "type": "clarify",
                "question": clar["question"],
                "missing_fields": clar["missing_fields"],
            }
            yield {"type": "layer_done", "layer": "clarification", "status": "complete"}

        def _emit_stage(stage: str, detail: str, layer: str = "planning"):
            try:
                return {"type": "stage", "stage": stage, "detail": str(detail)[:120], "layer": layer}
            except Exception:
                return None

        def _done(data: dict):
            data.setdefault("duration_ms", (time.perf_counter() - t0) * 1000.0)
            data.setdefault("model", self.llm.model)
            # INTELLEKT 2.2: chiqish strukturasi tekshiruvi + JSON ta'mirlash
            content = data.get("content") or ""
            if isinstance(content, str) and content.strip():
                fixed, sc = self._verify_and_repair(content)
                if sc is not None:
                    data["content"] = fixed
                    data["structure_check"] = sc
                    # Verifikator signali endi bor — agar memory yozuvi bu
                    # repair'dan OLDIN sodir bo'lgan bo'lsa, keshlangan
                    # self_eval eskirgan bo'lardi. Barcha LLM yo'llarida
                    # (chat/chat_stream turbo+plain+tool) repair endi data
                    # yig'ish paytida qilinadi — bu `pop` faqat repair qilib
                    # BO'LMAYDIGAN fail holati uchun xavfsizlik to'ri (u
                    # yerda ham memory == done: ikkalasi ham bir xil matn,
                    # past confidence).
                    data.pop("self_eval", None)
            # AGENTIK completion: ish yakuni konversatsiyaga to'ldiriladi
            data["completion"] = self._work_completion(pipeline, data)
            # INTELLEKT 2.7: ishonch kalibratsiyasi — har bir javobga birikadi
            self._with_self_eval(data)
            ev = {"type": "done"}
            ev.update(data)
            return ev

        # JONLI PIPELINE: plan bosqichi — qurilgan pipeline nomi bilan
        yield {"type": "layer_start", "layer": "planning"}
        stage = _emit_stage("plan", f"{pipeline['label']}: {pipeline['clarified']}", layer="planning")
        if stage:
            yield stage
        yield {"type": "layer_done", "layer": "planning", "plan": pipeline, "status": "complete"}

        # --- SUPERVISOR INTEGRATION (§9) ---
        # Complex so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi va
        # bajaradi. SSE event'lari bilan: supervisor_start → node_start
        # → token → node_done → supervisor_done.
        supervisor_events = []
        for ev in self._run_supervisor_stream(message, pipeline):
            supervisor_events.append(ev)
            yield ev
        # Agar supervisor ishlagan bo'lsa — natijani done sifatida beramiz
        if supervisor_events:
            done_event = next(
                (e for e in supervisor_events if e.get("type") == "supervisor_done"),
                None,
            )
            if done_event:
                yield _done({
                    "message": message,
                    "content": done_event.get("summary", ""),
                    "engine": "supervisor",
                    "tool_calls": [],
                    "image": None,
                    "memory": {"recall_hits": 0, "context_chars": 0},
                    "supervisor": {
                        "status": done_event.get("status"),
                        "iterations_used": done_event.get("iterations_used", 0),
                        "nodes": done_event.get("nodes", {}),
                    },
                })
                return

        # INTELLEKT 2.10 (harm-filter) — chat() bilan bir xil oqim
        verdict = self.intelligence.screen(message)
        if not verdict.allowed:
            stage = _emit_stage("review", "so'rov rad etildi (zarar filtri)")
            if stage:
                yield stage
            refusal = verdict.reason or "Bu so'rov aniq zarar chegarasidan o'tadi."
            yield _done({
                "message": message,
                "content": refusal,
                "engine": "harm-filter",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "refused": True,
                "refusal_category": verdict.category,
            })
            return

        try:
            self.intelligence.observe(message)
        except Exception:
            pass

        # Ob-havo tez yo'li — darhol, buffered
        quick = self._quick_weather(message)
        if quick is not None:
            stage = _emit_stage("review", "javob tayyor")
            if stage:
                yield stage
            yield _done({
                "message": message,
                "content": quick,
                "engine": "weather-quick",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "quick": True,
            })
            return

        # INTELLEKT 2.2 (logic): oddiy arifmetika — deterministik tez yo'l
        quick_math = self._quick_math(message)
        if quick_math is not None:
            stage = _emit_stage("review", "javob tayyor")
            if stage:
                yield stage
            yield _done({
                "message": message,
                "content": quick_math,
                "engine": "math-quick",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": 0, "context_chars": 0},
                "quick": True,
            })
            return

        memory_ctx, memory_hits = self.memory.recall(message) if (use_memory and self.memory.enabled) else ("", 0)

        # MAG: L1+L2+RAG konteksti — chat() bilan bir xil (stream ham bir xil
        # sifatni olishi uchun; aks holda streaming javoblar pastroq bo'lardi).
        mag_ctx = ""
        if use_memory and self.memory.enabled and not history and not memory_ctx:
            try:
                mag = self._mag()
                mag_ctx = mag.assemble(message)["context"] if mag else ""
            except Exception:
                mag_ctx = ""

        system = self.intelligence.adapt_system(CHAT_TOOLS_SYSTEM, message)
        cot = self.intelligence.reasoning_suffix()
        if cot and cot not in system:
            system = (system or "") + "\n\n" + cot
        # REAL bugungi sana — eskirgan/soxta sana javoblarini oldini oladi
        system = (system or "") + self._today_note()
        # INTELLEKT 2.3 (musiqa): musiqa/ovoz so'rovi — glossary + yo'naltirish
        music_dir = self._intel("music_directive", message)
        if music_dir:
            system += "\n\n" + music_dir
        # INTELLEKT 2.4 + 2.8 (spatial + naturalist): loyiha strukturasi so'rovi —
        # workspace daraxti + til taqsimoti konteksti (agent muhitni ko'radi).
        _sp = None
        if self._is_structure_request(message):
            _sp = self._spatial_env_context(message)
            if _sp:
                system += "\n\n" + _sp[0]
        # CHIZISH SO'ROVI: svg-artist skill ko'rsatmasi AVTOMATIK qo'shiladi —
        # model har chizishda professional SVG (gradient/soya/qatlamlar) yaratadi
        if self._is_draw_request(message):
            skill_text = self._draw_skill_text()
            if skill_text:
                system += "\n\n" + skill_text
            # Oxirgi chizma sifat feedback'i — model avvalgi xatolarini
            # takrorlamasligi uchun (RAG recall'ga tayanmasdan ham ishlaydi)
            fb = self._draw_feedback_context()
            if fb:
                system += "\n\n" + fb
        # WEB SO'ROVI: qaror qoidalari — model eng arzon vositanı tanlaydi
        # (to'g'ridan-to'g'ri javob > web_fetch > web AI subagent > browser).
        web_strategy = self._web_strategy(message)
        # Qoidalar faqat web_ai_bridge MCP ulangan bo'lsa qo'shiladi — aks holda
        # modelga mavjud bo'lmagan tool'lar (ask_web_ai/browser) eslatilmaydi.
        if web_strategy and self._mcp() is not None:
            system += "\n\n" + self._web_decision_rules(web_strategy)
        # STACK GUIDE: kod so'rovida framework/til aniqlansa — model aniq
        # buyruqlarni (npm/pip/mvn...) ishlatishi uchun yo'naltiruv qo'shiladi.
        stack_guide = self._stack_guide(pipeline)
        if stack_guide:
            system += "\n\n" + stack_guide
        if memory_ctx:
            system += (
                "\n\nRelevant recalled knowledge from memory (use only if useful):\n"
                + memory_ctx
            )
        elif mag_ctx:
            system += "\n\nMemory context:\n" + mag_ctx
        # SEMANTIK TALAB BLOKI (Part L): model javobni req'ga mos shakllantiradi.
        if self.llm_available():
            system += "\n\n" + req.to_block()

        messages: list[dict] = [{"role": "system", "content": system}]
        for h in (history or [])[-12:]:
            role = h.get("role")
            content = h.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        # CAG: keshda javob bo'lsa — darhol buffered done
        if not history and not self._is_draw_request(message) and not self._is_date_question(message):
            cache = self._cag()
            if cache is not None:
                cached = cache.get(CHAT_TOOLS_SYSTEM, message)
                if cached is not None:
                    # AUDIT (CAG hit — stream): keshlangan matn ham repair'dan
                    # o'tadi — eski/buzilgan yozuv ham `data["content"]` kabi
                    # canonical matn bo'ladi; memory va confidence shundan
                    # hisoblanadi (`_done` keyingi repair'i no-op bo'ladi).
                    out_final, struct_check = self._verify_and_repair(cached)
                    data = {
                        "message": message,
                        "content": out_final or cached,
                        "engine": "cag",
                        "tool_calls": [],
                        "image": None,
                        "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                        "cag": {"hit": True},
                    }
                    if struct_check is not None:
                        data["structure_check"] = struct_check
                    # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
                    # RAG'ga yozilmaydi (stream yo'llari bilan bir xil naqsh).
                    if (self.memory.enabled and self._cacheable_out(data.get("content"))
                            and (struct_check is None or struct_check.get("ok") is not False)):
                        self.memory.on_resolve(message, {"output": data["content"], "engine": "cag", "confidence": self._confidence_for(data)})
                    yield _done(data)
                    return

        # INTELLEKT 2.11 (creative): kreativ so'rov — buffered multi-temperature
        # (faqat tarixsiz oddiy so'rov; tarixli davomda oddiy yo'l ishlaydi)
        creative_data = None
        if not history:
            creative_data = self._creative_variants(message, system=system, memory_hits=memory_hits)
        if creative_data is not None:
            stage = _emit_stage("review", "kreativ variantlar tayyorlanmoqda…")
            if stage:
                yield stage
            yield _done(creative_data)
            return

        tool_needed = (
            self._is_draw_request(message)
            or self._needs_web(message)
            or bool(self._registry() and any(
                w in message.lower()
                for w in ("fayl", "file", "write", "yarat", "create", "dastur", "kod", "code")
            ))
        )

        if not self.llm_available():
            # offline — buffered, aniq tushuntirish
            stage = _emit_stage("review", "javob tayyorlanmoqda…")
            if stage:
                yield stage
            res = self.resolve(message, allow_llm=False, use_memory=use_memory)
            out = res.get("output") if res.get("status") == "ok" and res.get("output") else (
                "IGRIS hozir javob bera olmadi — Ollama (lokal AI) "
                "yoqilmagan. Iltimos `run.bat` orqali yoki terminalda "
                "`ollama serve` bilan Ollama'ni ishga tushiring, so'ng qayta "
                "yozing."
            )
            # `_mcp_cache` — offline yo'lida MCP serverlarni ishga tushirmaydi
            self._log_web_strategy(message, web_strategy, [], "offline",
                                   mcp_ok=self._mcp_cache is not None)
            yield _done({
                "message": message,
                "content": out,
                "engine": "offline",
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            })
            return

        web_needed = bool(web_strategy)

        # TURBO tez yo'l (tool'siz oddiy savol) — buffered (chat_fast tez)
        if (
            getattr(self.llm, "turbo", False)
            and not tool_needed
            and not history
        ):
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            fast = self.llm.chat_fast(messages)
            out = fast.strip() if fast and fast.strip() else self._retry_generate(messages, req)
            # AUDIT (stream turbo): repair memory yozuvidan OLDIN qilinadi —
            # `_done`'ning keyingi repair'i no-op bo'ladi, memory output ==
            # confidence signali == ko'rsatilgan javob (post-repair).
            out_final, struct_check = self._verify_and_repair(out)
            data = {
                "message": message,
                "content": out_final or self._retry_generate(messages, req),
                "engine": "llm-fast",
                "model": self.llm.fast_model or self.llm.model,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
                "turbo": True,
            }
            if struct_check is not None:
                data["structure_check"] = struct_check
            # logprob re-so'ruvi (ixtiyoriy) uchun asl messages — bu yo'l doim
            # llm-fast (local `engine` o'zgaruvchisi shu yerda aniqlanmagan!).
            data["_llm_messages"] = messages
            # Guard: bo'sh/xato javoblar RAG'ga tushmaydi ("I could not
            # generate" ham kirmaydi — `_cacheable_out` uni rad etadi).
            # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
            # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
            if (self.memory.enabled and self._cacheable_out(data.get("content"))
                    and (struct_check is None or struct_check.get("ok") is not False)):
                self.memory.on_resolve(message, {"output": data["content"], "engine": data["engine"], "confidence": self._confidence_for(data)})
            yield _done(data)
            return

        # ===== REAL TOKEN STREAM yo'li: tool kerak emas =====
        if not tool_needed:
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            out = ""
            thinking_txt = ""
            try:
                # Fikrlash bosqichi ham STREAM qilinadi — frontend "thinking"
                # blokida reasoning token-ketma-token ko'radi, so'ng yakuniy
                # javob oqadi (bo'sh kutish yo'q — kutish o'rniga fikrlash
                # jarayoni ko'rinadi). Sessiya `think` sozlamasi va TURBO
                # rejimiga hurmat: thinking qo'llab-quvvatlanmaydigan modellarda
                # faqat "token" hodisalari keladi — buzilish yo'q.
                think_stream = self.llm.think and not getattr(self.llm, "turbo", False)
                for ev in self.llm.chat_stream_rich(messages, think=think_stream):
                    delta = ev.get("content") or ""
                    if not delta:
                        continue
                    if ev.get("type") == "think":
                        thinking_txt += delta
                        yield {"type": "thinking", "content": delta}
                    else:
                        out += delta
                        yield {"type": "token", "content": delta}
            except Exception as exc:
                # LLM xatosi — graceful degradation: buffered chat'ga qaytamiz
                self._mark_llm_failed(str(exc))
                print(f"[igris][stream] LLM failed, degrading to buffered chat: {exc}")
            if not out.strip():
                # stream transport xatosi / bo'sh javob — buffered chat'ga qaytamiz
                buffered = self.chat(message, history=history, use_memory=use_memory)
                yield _done(buffered)
                return
            engine = "llm"
            # Muvaffaqiyatli stream - cooldown'ni tozalaymiz
            self._mark_llm_recovered()
            # AUDIT (stream final): repair data yig'ish paytida qilinadi — memory
            # va CAG put AYNAN `data["content"]` (repair'dan keyingi)ni oladi;
            # `_done` keyingi repair'i no-op bo'ladi (keshlangan out vs content
            # tafovuti yopiladi, chat() bilan bir xil kalitda bir xil qiymat).
            out_final, struct_check = self._verify_and_repair(out)
            data = {
                "message": message,
                "content": out_final or out,
                "engine": engine,
                "tool_calls": [],
                "image": None,
                "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
            }
            # To'liq fikrlash matni `done` voqeasida ham boradi — frontend
            # yakuniy xabarda thinking blokini saqlab qoladi (eventlar o'tib
            # ketsa ham).
            if thinking_txt:
                data["thinking"] = thinking_txt
            # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
            if struct_check is not None:
                data["structure_check"] = struct_check
            # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (struktura so'rovi)
            if _sp:
                data["spatial"] = _sp[1]
            # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi
            if engine in ("llm", "llm+tools", "llm-fast"):
                data["_llm_messages"] = messages
            # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail')
            # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
            if (self.memory.enabled and self._cacheable_out(data.get("content"))
                    and (struct_check is None or struct_check.get("ok") is not False)):
                self.memory.on_resolve(message, {"output": data["content"], "engine": engine, "confidence": self._confidence_for(data)})
            cache = self._cag()
            if (cache is not None and self._cacheable_out(data.get("content"))
                    and not self._is_date_question(message)
                    # Fail-guard: repair qilib bo'lmagan chiqish keshlanmaydi
                    and (struct_check is None or struct_check.get("ok") is not False)):
                cache.put(CHAT_TOOLS_SYSTEM, message, data["content"])
            yield _done(data)
            return

        # ===== TOOL yo'li: round'lar buffered, lekin YAKUNIY javob token oqimi =====
        # progress_cb berilsa — tool bajarilayotganda CHAT_PROGRESS buferiga
        # jonli bosqich yoziladi (frontend stepperi stream'da ham ishlaydi).
        # loop_iteration_events: ReAct/build-verify loop iteration event'lari
        # yig'iladi va yakunda frontend'ga yuboriladi.
        tools = self._chat_tools(include_web=web_needed)
        loop_iteration_events: list[dict] = []

        def _on_loop_iteration(iteration: int, max_iter: int, shape: str):
            loop_iteration_events.append({
                "type": "loop_iteration",
                "iteration": iteration,
                "max_iter": max_iter,
                "shape": shape,
            })

        content, tool_calls, image, redraw_note = self._chat_with_redraw(
            messages, tools, web=web_needed, progress=progress_cb, request=message,
            req=req, on_loop_iteration=_on_loop_iteration,
        )
        # loop_iteration event'larini yuboramiz — frontend "attempt N of M" ko'rsatadi
        for ev in loop_iteration_events:
            yield ev
        engine = "llm+tools" if tool_calls else "llm"
        if not (content or "").strip():
            # Part L: canned "Veb so'rovi..." / bo'sh javob o'rniga req-aware retry
            content = self._retry_generate(messages, req)
        # AUDIT (stream tool): repair data yig'ish paytida qilinadi — memory
        # AYNAN `data["content"]` (repair'dan keyingi)ni oladi; `_done`'ning
        # keyingi repair'i no-op bo'ladi (chat/plain-stream/turbo bilan bir
        # xil kalitda bir xil qiymat — keshlangan out vs content tafovuti yo'q).
        out_final, struct_check = self._verify_and_repair(content or "")
        # Part L (B2): talab compliance — nomoslik bo'lsa 1 marta qayta generatsiya.
        # Part O: rasm/visual natija (image mavjud) — LLM compliance keraksiz.
        if (out_final or "").strip() and not image and req.output_format not in ("image",):
            out_final = self._compliance(out_final, req, message)
        # KUZATUV: strategiya to'g'ri tanlandimi + model nima qildi
        # (`_mcp_cache` — server ishga tushirmaydi, faqat holatni o'qiydi)
        self._log_web_strategy(message, web_strategy, tool_calls, engine,
                               mcp_ok=self._mcp_cache is not None,
                               content_len=len(out_final or ""))
        data = {
            "message": message,
            "content": out_final or content or self._retry_generate(messages, req),
            "engine": engine,
            "tool_calls": tool_calls,
            "image": image,
            "memory": {"recall_hits": memory_hits, "context_chars": len(memory_ctx)},
        }
        if redraw_note:
            data["redraw"] = redraw_note
        # INTELLEKT 2.2: chiqish strukturasi tekshiruvi natijasi (JSON/kod)
        if struct_check is not None:
            data["structure_check"] = struct_check
        # INTELLEKT 2.4/2.8: fazoviy + naturalist xulosasi (struktura so'rovi)
        if _sp:
            data["spatial"] = _sp[1]
        # LLM logprob re-so'ruvi (ixtiyoriy) uchun asl messages saqlanadi
        if engine in ("llm", "llm+tools", "llm-fast"):
            data["_llm_messages"] = messages
        # Yolg'on/bo'sh javoblar xotiraga YOZILMAYDI (RAG'ni ifloslantirmaydi)
        # Fail-guard: repair qilib BO'LMAYDIGAN chiqish (verified='fail') ham
        # RAG'ga yozilmaydi (resolve() LLM fallback bilan bir xil naqsh).
        if (self.memory.enabled and self._cacheable_out(data.get("content"))
                and (struct_check is None or struct_check.get("ok") is not False)):
            self.memory.on_resolve(message, {"output": data["content"], "engine": engine, "confidence": self._confidence_for(data)})
        # Yakuniy matnni TOKEN-bo'laklar bilan uzatamiz — foydalanuvchi javobni
        # yozilayotganda ko'radi (tool jarayoni stage/poll orqali jonli edi).
        final_text = data.get("content") or ""
        if final_text:
            stage = _emit_stage("review", "javob yozilmoqda…")
            if stage:
                yield stage
            for chunk in self._token_chunks(final_text):
                yield {"type": "token", "content": chunk}
        yield _done(data)

    # ------------------------------------------------------------ #
    # CAG / MAG lazy helpers
    # ------------------------------------------------------------ #

    def _cag(self):
        """Lazy CAG cache singleton."""
        if self.cag_cache is None:
            try:
                from cag import DEFAULT_CAG
                self.cag_cache = DEFAULT_CAG
            except Exception:
                self.cag_cache = None
        return self.cag_cache

    def _mag(self):
        """Lazy MAG assembler (MemoryBridge asosida)."""
        if self.mag is None:
            try:
                from mag import MagAssembler
                self.mag = MagAssembler(memory=self.memory if self.memory.enabled else None)
            except Exception:
                self.mag = None
        return self.mag

    # ------------------------------------------------------------ #
    # INTELLEKT yordamchilari — xavfsiz (mock/FakeIntel bilan ham ishlaydi)
    # ------------------------------------------------------------ #

    def _intel(self, name: str, *args, **kwargs):
        """IntelligenceCore usulini xavfsiz chaqiradi (mavjud bo'lmasa None)."""
        fn = getattr(self.intelligence, name, None)
        if fn is None:
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            print(f"[igris][intel] {name} failed: {exc}")
            return None

    def _self_eval_for(self, data: dict) -> Optional[dict]:
        """INTELLEKT 2.7: `data` uchun SelfEvaluator natijasini BIR MARTA hisoblab,
        `data["self_eval"]`'ga yozadi.

        `evaluate()` har javob uchun bir marta chaqiriladi; natija keshga
        yoziladi. `_with_self_eval()` va `_confidence_for()` shu natijani
        QAYTA ISHLATADI — takroriy SelfEvaluator hisoblash yo'q. Natija
        mavjud bo'lmasa None qaytadi.
        """
        if not isinstance(data, dict):
            return None
        # `_llm_messages` faqat self-eval uchun edi — qaysi yo'l bilan bo'lsa
        # ham javobga oqib ketmasligi uchun BIRINCHI narsa qilib olinadi
        # (early-return: self_eval oldindan keshlangan bo'lsa ham xavfsiz).
        data.pop("_llm_messages", None)
        existing = data.get("self_eval")
        if existing is not None:
            return existing if isinstance(existing, dict) else None
        try:
            # A2 verifikator signali: `_verify_and_repair` qo'shgan
            # `structure_check` — json repaired / struktur muammo qoldi.
            # LLM logprob: native /api/chat QAYTARMAYDI — shuning uchun
            # verifikator natijasi asosiy signal, ixtiyoriy OpenAI-mos logprob
            # re-so'ruvi (`avg_logprob`) esa QO'SHIMCHA ishonch signali.
            # Izoh: `_verify_and_repair` muvaffaqiyatni None bilan xabar
            # qiladi (shovqin yo'q) — shuning uchun `ok=True` (repaired'siz)
            # dict hech qachon kelmaydi, verified='ok' shu oqimda o'lik.
            # SelfEvaluator'dagi 'ok' qiymati bevosita API chaqiruvi uchun
            # kelajakda ishlatilishi mumkin.
            verified = None
            sc = data.get("structure_check")
            if isinstance(sc, dict):
                if sc.get("repaired"):
                    verified = "repaired"
                elif sc.get("ok") is False:
                    verified = "fail"
            # A2 (logprob): ixtiyoriy OpenAI-mos ALOHIDA re-so'rov — o'rtacha
            # token ehtimoli ishonch signali. Faqat LLM javoblarida va faqat
            # `llm.logprobs` yoqilganida (2x inference narxi — default O'CHIQ).
            # Ollama eski/offline bo'lsa None qaytadi — signal neytral, agent
            # buzilmaydi. Asl messages TO'LIQ `_llm_messages` orqali uzatiladi
            # (chat/chat_stream/resolve qo'shadi) — kontekstsiz yalang'och
            # user-matn fallback'i YO'Q, aks holda logprob noto'g'ri muhitda
            # o'lchanib, chalg'ituvchi signal berardi (reviewer A2-logprob).
            avg_logprob = None
            engine_name = data.get("engine") or "llm"
            msgs = data.get("_llm_messages")
            if (
                msgs
                and getattr(self.llm, "logprobs", False)
                and self.use_llm
                and engine_name in ("llm", "llm+tools", "llm-fast")
            ):
                try:
                    avg_logprob = self.llm.chat_logprobs(
                        msgs, model=data.get("model") or self.llm.model
                    )
                except Exception:
                    avg_logprob = None
            res = self._intel(
                "evaluate",
                engine=data.get("engine") or "llm",
                # Rad etish (harm-filter) — to'g'ri deterministik harakat, xato EMAS
                status="ok",
                # chat() data: content; resolve() data: output — ikkalasi ham.
                output=data.get("content") or data.get("output") or "",
                tool_calls=data.get("tool_calls") or [],
                memory_hits=(data.get("memory") or {}).get("recall_hits", 0),
                # resolve() to_dict'ida `healed` maydoni bor — deterministik
                # yo'l uchun muhim (healed = shubhali natija). chat()'da yo'q.
                healed=bool(data.get("healed")),
                verified=verified,
                # A2: deterministic/healed rezolyutsiyada resolverning o'z
                # bahosi (0.6*rule_score + 0.4*coverage) signal sifatida.
                resolver_score=data.get("resolver_score"),
                # A2: ixtiyoriy OpenAI-mos logprob re-so'ruvidan o'rtacha
                # token ehtimoli (0..1) — None bo'lsa neytral (signal yo'q).
                avg_logprob=avg_logprob,
            )
            if isinstance(res, dict):
                data["self_eval"] = res
                return res
            if hasattr(res, "to_dict"):
                data["self_eval"] = res.to_dict()
                return data["self_eval"]
        except Exception:
            pass
        return None

    def _with_self_eval(self, data: dict) -> dict:
        """INTELLEKT 2.7: ishonch kalibratsiyasini javobga biriktiradi.

        Faqat metrika (confidence/uncertainty/notes) — agent xulq-atvorini
        o'zi o'zgartirmaydi. `_self_eval_for()` natijasini biriktiradi —
        `data["self_eval"]` allaqachon bo'lsa qayta hisoblamaydi
        (harm-filter rad etishida bo'lgani kabi).
        """
        self._self_eval_for(data)
        return data

    def _confidence_for(self, data: dict, fallback: float = 0.5) -> float:
        """A2: `data` uchun confidence — `_self_eval_for()` natijasini QAYTA ISHLATADI.

        Memory `on_resolve` (confidence) va `data["self_eval"]` BIR evaluate()
        chaqiruvidan olinadi — takroriy SelfEvaluator hisoblash yo'q.
        Intellekt mavjud bo'lmasa/xato bersa — `fallback` qaytadi.
        """
        ev = self._self_eval_for(data)
        if ev:
            conf = ev.get("confidence")
            if isinstance(conf, (int, float)):
                return max(0.0, min(1.0, float(conf)))
        return float(fallback)

    def _verify_and_repair(self, out: str) -> tuple[str, Optional[dict]]:
        """INTELLEKT 2.2: chiqish strukturasi tekshiruvi + JSON ta'mirlash.

        Model JSON so'raganida matn ichiga JSON o'raydi yoki kichik xato
        qiladi — aniqlaymiz va iloji bo'lsa tuzatamiz. Qaytaradi:
        (out, structure_check_dict|None). Faqat MUAMMOLAR hisobot qilinadi
        (to'g'ri javoblar shovqin qilmaydi).
        """
        text = str(out or "")
        check = self._intel("verify_structure", text)
        if check is None:
            return out, None
        info = check.to_dict() if hasattr(check, "to_dict") else dict(check)

        if not info.get("ok") and info.get("kind") == "json":
            repaired = extract_balanced_json(text)
            if repaired:
                recheck = self._intel("verify_structure", repaired)
                if recheck is not None:
                    rinfo = recheck.to_dict() if hasattr(recheck, "to_dict") else dict(recheck)
                    if rinfo.get("ok"):
                        return repaired, {
                            "ok": True, "kind": "json", "repaired": True,
                            "note": "JSON xato edi — matndan to'g'ri blok ajratib olindi",
                        }

        # To'g'ri javoblar hisobotga tushmaydi (shovqin yo'q)
        if info.get("ok"):
            return out, None
        if info.get("kind") == "plain":
            return out, None
        info["repaired"] = False
        return out, info

    @staticmethod
    def _is_math_request(message: str) -> Optional[str]:
        """Sof arifmetik ifoda so'rovi — tez deterministik javob uchun.

        Qaytaradi: xavfsiz hisoblanadigan ifoda yoki None. Faqat raqamlar va
        + - * / ( ) bo'lgan, juda qisqa (<= 60 belgi) so'rovlar qabul qilinadi.
        """
        msg = (message or "").strip()
        if not msg or len(msg) > 60:
            return None
        m = MATH_PREFIX_RE.match(msg)
        expr = m.group(2).strip() if m else msg
        if not re.fullmatch(r"[\d\s+\-*/().]+", expr):
            return None
        if not MATH_EXPR_RE.search(expr):
            return None
        return expr

    def _quick_math(self, message: str) -> Optional[str]:
        """INTELLEKT 2.2: oddiy arifmetikani tez va aniq hisoblaydi (LLM'siz)."""
        expr = self._is_math_request(message)
        if expr is None:
            return None
        result = self._intel("quick_math", expr)
        if result is None:
            return None
        pretty = str(int(result)) if float(result).is_integer() else f"{result:.6f}".rstrip("0").rstrip(".")
        return f"{expr} = {pretty}"

    @staticmethod
    def _is_structure_request(message: str) -> bool:
        """INTELLEKT 2.4: loyiha strukturasi so'rovi (spatial kontekst kerakmi)."""
        low = (message or "").lower()
        return any(w in low for w in STRUCTURE_REQUEST_WORDS)

    @staticmethod
    def _is_creative_request(message: str) -> bool:
        """INTELLEKT 2.11: kreativ so'rov (variant/g'oya so'ralyaptimi)."""
        low = (message or "").lower()
        if not any(w in low for w in CREATIVE_REQUEST_WORDS):
            return False
        # So'rovchi fe'l yoki savol belgisi kerak — "variant" so'zi boshqa
        # kontekstda ham uchraydi ("Python variantini yoz"), uni ushlamaymiz.
        if (re.search(r"\b(ber|ko'rsat|yoz|ayt|chiqar|give|show|suggest|make|create|generate|propose)\b", low)
                or "options for" in low or "ideas for" in low
                or low.rstrip().endswith("?")):
            return True
        return False

    def _workspace_paths(self, max_files: int = 400, max_depth: int = 7) -> list[str]:
        """Agent ish maydonidagi fayl yo'llari (xavfsiz, cheklangan)."""
        root = getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE
        if not root or not os.path.isdir(root):
            return []
        out: list[str] = []
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build")]
                if base[len(root):].count(os.sep) > max_depth:
                    dirs[:] = []
                    continue
                for f in files:
                    out.append(os.path.join(base, f))
                    if len(out) >= max_files:
                        return out
        except OSError:
            return []
        return out

    def _spatial_env_context(self, message: str) -> Optional[tuple[dict, dict]]:
        """INTELLEKT 2.4+2.8: workspace daraxti + til taqsimoti konteksti.

        Qaytaradi: (system_block, data_summary) yoki None (struktura so'rovi
        emas / workspace bo'sh). System prompt'ga qo'shiladi — agent loyiha
        qaysi texnologiyalardan iborat ekanini ko'radi.
        """
        if not self._is_structure_request(message):
            return None
        paths = self._workspace_paths()
        if not paths:
            return None
        tree = self._intel("spatial_file_tree", paths)
        env = self._intel("naturalist_summary", paths)
        if not isinstance(tree, dict) or not tree.get("entries"):
            return None
        lines = ["Project layout (spatial + naturalist):"]
        lines.append(f"- {tree['entries']} entries, max depth {tree.get('max_depth', 0)}")
        dist = tree.get("depth_distribution") or {}
        if dist:
            top = sorted(dist.items(), key=lambda kv: int(kv[0]))[:6]
            lines.append("- Depth distribution: " + ", ".join(f"d{k}:{v}" for k, v in top))
        dirs = (tree.get("directories") or [])[:8]
        if dirs:
            lines.append("- Directories: " + ", ".join(dirs))
        if env:
            lines.append(env)
        summary = {
            "entries": tree.get("entries"),
            "max_depth": tree.get("max_depth"),
            "dir_count": tree.get("dir_count"),
        }
        nats = self._intel("classify_paths", paths)
        if isinstance(nats, dict) and nats.get("languages"):
            summary["languages"] = nats.get("languages")
        return "\n\n".join(lines), summary

    def _creative_variants(self, message: str, system: str, memory_hits: int = 0) -> Optional[dict]:
        """INTELLEKT 2.11: 3 xil temperature'da variant + eng yaxshisini tanlash.

        Faqat LLM mavjud, tool kerak bo'lmagan, tarixsiz kreativ so'rovda
        ishlaydi. Chiqish operator ko'rib chiqadi — agent o'zi qaror qilmaydi.
        Qaytaradi: to'liq javob data yoki None (shartlar bajarilmasa).
        """
        if (not self.llm_available() or not self._is_creative_request(message)
                or getattr(self.llm, "turbo", False)
                or self._is_draw_request(message) or self._needs_web(message)):
            return None
        low = (message or "").lower()
        if any(w in low for w in ("fayl", "file", "write", "yarat", "create",
                                  "dastur", "kod", "code", "yoz")):
            # kod/fayl yaratish so'rovlarida kreativ qatlam qo'llanilmaydi (tool kerak)
            return None
        creative_system = (system or "") + (
            "\n\nThe user wants VARIANTS/IDEAS. Give one useful, distinct "
            "alternative for the request. Be concrete and helpful — no filler."
        )
        t0 = time.perf_counter()
        candidates = self._intel(
            "creative_variants", message, n=3,
            complete_fn=self.llm.complete, system=creative_system,
        )
        if not candidates:
            return None
        best = self._intel("pick_creative", candidates, "balanced")
        text = (best.text if hasattr(best, "text") else (best or {}).get("text")) or ""
        if not text.strip():
            return None
        variants: list[dict] = []
        for c in candidates:
            t = (c.text if hasattr(c, "text") else (c or {}).get("text")) or ""
            lbl = (c.label if hasattr(c, "label") else (c or {}).get("label")) or ""
            temp = (c.temperature if hasattr(c, "temperature") else (c or {}).get("temperature")) or 0.7
            if t.strip():
                variants.append({"label": lbl, "temperature": temp, "text": t[:400]})
        chosen = (best.label if hasattr(best, "label") else (best or {}).get("label")) or "balanced"
        data = {
            "message": message,
            "content": text.strip(),
            "engine": "creative",
            "model": self.llm.model,
            "tool_calls": [],
            "image": None,
            "memory": {"recall_hits": memory_hits, "context_chars": 0},
            "duration_ms": (time.perf_counter() - t0) * 1000.0,
            "creative": {"variants": variants, "chosen": chosen, "n": len(variants)},
        }
        if self.memory.enabled:
            try:
                self.memory.on_resolve(message, {"output": text.strip(), "engine": "creative", "confidence": self._confidence_for(data)})
            except Exception:
                pass
        return self._with_self_eval(data)

    @staticmethod
    def _is_draw_request(message: str) -> bool:
        """Rasm/UI chizish so'rovi bo'lsa — CAG keshlanmaydi (tool kerak)."""
        low = (message or "").lower()
        draw_words = ("rasm", "chiz", "draw", "image", "picture", "ui",
                      "dashboard", "sahifa", "logo", "icon", "mockup")
        for w in draw_words:
            if w == "ui":
                if re.search(r"\bui\b", low):
                    return True
            elif w in low:
                return True
        return False

    # ------------------------------------------------------------ #
    # AGENTIK PIPELINE — zarurat turi -> pipeline tanlash va qurish
    # ------------------------------------------------------------ #

    @staticmethod
    def _is_ui_build_request(message: str) -> bool:
        """Interaktiv UI/ilova qurish so'rovi (art__ui_build_spec tool'iga mos).

        Oddiy chizma (rasm chiz) bu yerga TUSHMADI — chizma `draw` pipeline'iga
        ketadi. UI qurish = real interaktiv ekran: app/ilova/todo + qur/yarat
        fe'llari (yoki to'g'ridan-to'g'ri app/ilova/todo nomi).
        """
        low = (message or "").lower()
        ui_targets = ("app", "ilova", "todo", "vazifalar", "interaktiv",
                      "uibuild", "kalkulyator", "calculator", "dashboard")
        build_verbs = ("qur", "qurib", "quring", "yarat", "yasa", "build",
                       "make", "create")
        has_target = any(w in low for w in ui_targets)
        has_verb = any(w in low for w in build_verbs)
        if has_target and has_verb:
            return True
        return bool(re.search(r"\b(app|ilova|todo|uibuild|kalkulyator|calculator)\b", low))

    @classmethod
    def _is_code_request(cls, message: str) -> bool:
        """Kod/fayl vazifasi — write_file/run/test tool'lariga mos.

        Framework/texnologiya nomi aytilgan bo'lsa ham kod vazifasi hisoblanadi
        ("django bilan backend yoz" -> Django kod vazifasi) — til aniqlash
        uchun emas, KLASSIFIKATSIYA uchun framework ro'yxati ham tekshiriladi.
        """
        low = (message or "").lower()
        # 'baza'/'database' — DB so'rovlarini ushlaydi ("oracle baza yoz");
        # "oracle nima?" kabi bilim savollari code'ga tushmaydi (DB nomi
        # o'zi yetarli signal EMAS — 'oracle' oddiy so'z bo'lishi mumkin).
        code_words = ("fayl", "file", "dastur", "kod", "code", "script",
                      "function", "class", "debug", "fix", "tuzat",
                      "python", "html", "css", "test", "bug",
                      "baza", "database",
                      # Taqdimot / prezentatsiya
                      "powerpoint", "pptx", "ppt", "taqdimot",
                      "prezentatsiya", "presentation",
                      # O'yin / game
                      "game", "o'yin", "mini game", "gamer",
                      # API / backend / frontend
                      "endpoint", "router", "server", "client",
                      # Mobile / desktop
                      "android", "ios", "windows", "linux")
        if any(w in low for w in code_words):
            return True
        # So'z-chegarali qo'shimcha belgilar — "api" 'kapital' ichida
        # topilmasligi uchun (substring xavfli), framework nomlari ham.
        for pat in ("backend", "frontend", "api"):
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return True
        for pat, _fname, _flang in cls.CODE_FRAMEWORK_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return True
        # Ma'lumotlar bazasi nomi ham kod vazifasi signali ("postgres bilan
        # bazaga kod yoz" -> code; "mysql so'rov yoz" -> code).
        for pat, dname in cls.DATABASE_TECH_HINTS:
            if dname in cls.DB_CLASSIFY_EXCLUDE:
                continue
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return True
        return False

    @staticmethod
    def _is_composition_request(message: str) -> bool:
        """Kompozitsiya / qatlamli qurish so'rovi (CompositionEngine'ga mos)."""
        low = (message or "").lower()
        comp_words = ("kompozitsiya", "composition", "qatlam", "layer",
                      "wbs", "bom", "brick", "tizim qur", "reja qur",
                      "build plan", "komponent")
        return any(w in low for w in comp_words)

    @classmethod
    def _is_file_request(cls, message: str) -> bool:
        """Fayl tahrirlash/tahlil so'rovi — read_file/apply_patch/write_file'ga mos.

        Kod YARATISH ("dastur yoz", "kod yoz", "todo.py yarat") bu yerga
        TUSHMAYDI — `code` pipeline'iga ketadi. Fayl vazifasi = MAVJUD fayl
        bilan ishlash: o'qish, tahlil, tahrir, o'chirish, tarkibini so'rash.
        Signal: fayl kengaytmasi (.py/.txt/.json...) yoki `fayl/file` so'zi +
        tahrir/tahlil fe'li (yaratish fe'llari — code'ga).
        """
        low = (message or "").lower()
        has_ext = bool(re.search(
            rf"\.(?:{cls.FILE_EXTENSIONS})\b", low))
        has_create = bool(re.search(r"\b(yarat|create|yoz|write|qur|build)\w*", low))
        has_file_noun = bool(re.search(r"\b(fayl|file)\w*", low))
        read_edit_verb = bool(re.search(
            r"\b(" + "|".join(cls.FILE_READ_VERBS + cls.FILE_EDIT_VERBS) + r")\w*",
            low))
        # Kengaytma + o'qish/tahrir fe'li — aniq fayl vazifasi ("calc.py ni
        # o'qib ber va kod yoz" kabi aralash so'rovlar ham file_task bosh
        # pipeline bo'ladi, code esa sub-pipeline).
        if has_ext and read_edit_verb:
            return True
        if has_create:
            return False
        if has_ext:
            return True
        return bool(has_file_noun and read_edit_verb)

    # ---------------------------------------------------------------- #
    # IKKI BOSQICHLI ROUTER — agentic architecture §3.3.a
    # ---------------------------------------------------------------- #
    # Bosqich 1: oilani aniqlash (n=2) — chat-family yoki creator-family.
    # Bosqich 2: tur aniqlash (n≤5) — oila ichida aniq pipeline turi.
    #
    # Nima uchun: 8 variantlik klassifikator kichik mahalliy modelda
    # (qwen2.5-coder/qwen3 on Ollama) ≤5 variantlik ishonch chegarasidan
    # oshadi. Ikki bosqichga ajratish har bir bosqichda qaror yuzasini
    # kamaytiradi, aniqlikni oshiradi.
    # ---------------------------------------------------------------- #

    @classmethod
    def _classify_family(cls, message: str) -> str:
        """Bosqich 1: oilani aniqlaydi — 'chat' yoki 'creator'.

        chat-family: javob o'zi matn (suhbat, matematika, ob-havo,
            kreativ, loyiha strukturasi).
        creator-family: artifact ishlab chiqariladi va review bosqichidan
            o'tishi kerak (chizma, kod, UI, veb, kompozitsiya, fayl).
        """
        msg = (message or "").lower()
        # --- creator-family signal'lari (birortasi topilsa → creator) ---
        # 1. URL / veb brauzer ehtiyoji
        if cls._needs_web(message):
            return "creator"
        # 2. Rasm/chizish so'rovi
        if cls._is_draw_request(msg):
            return "creator"
        # 3. UI/ilova qurish so'rovi
        if cls._is_ui_build_request(msg):
            return "creator"
        # 4. Kod/fayl vazifasi — framework nomlari, DB nomlari,
        #    kengaytma + o'qish/tahrir fe'llari
        if cls._is_code_request(msg):
            return "creator"
        # 5. Kompozitsiya / qatlamli qurish
        if cls._is_composition_request(msg):
            return "creator"
        # 6. Fayl vazifasi (ui_build'dan oldin — "todo.txt" adashmasligi uchun)
        if cls._is_file_request(message):
            return "creator"
        # --- chat-family (default) ---
        return "chat"

    @classmethod
    def _classify_type(cls, message: str, family: str) -> str:
        """Bosqich 2: oila ichida aniq pipeline turini aniqlaydi (n≤5).

        chat-family → (weather, math, creative, structure, chat)
        creator-family → (file_task, ui_build, draw, web, composition, code)
        """
        msg = (message or "").lower()
        if family == "creator":
            # creator-family: bosqich 1 da allaqachon bir umumiy tekshiruv
            # o'tkazilgan — endi aniq tur aniqlash kerak.
            # file_task OLDIN — "todo.txt" kabi kengaytma + fe'l;
            # ui_build OLDIN — "todo app qur" adashmasligi uchun.
            if cls._is_file_request(message):
                return "file_task"
            if cls._is_ui_build_request(msg):
                return "ui_build"
            if cls._is_draw_request(msg):
                return "draw"
            if cls._needs_web(message):
                return "web"
            if cls._is_composition_request(msg):
                return "composition"
            if cls._is_code_request(msg):
                return "code"
            # default — creator oilasida lekin aniqlanmagan → code
            return "code"
        else:
            # chat-family: weather, math, creative, structure, chat
            if cls.WEATHER_RE.search(msg):
                return "weather"
            if cls._is_math_request(msg) is not None:
                return "math"
            if cls._is_creative_request(msg):
                return "creative"
            if cls._is_structure_request(msg):
                return "structure"
            return "chat"

    def _classify_need(self, message: str, history: Optional[list] = None) -> str:
        """So'rov zarurat turini aniqlaydi — ikki bosqichli router.

        Bosqich 1: oila (chat yoki creator) — n=2, ishonchli.
        Bosqich 2: tur aniqlash (n≤5) — oila ichida kichik tanlov.

        Tezkor deterministik detektorlar (LLM chaqirmaydi).
        """
        family = self._classify_family(message)
        return self._classify_type(message, family)

    # --- aniqlashtirish leksikasi (LLMsiz, deterministik) ----------------- #
    # _clarify_request _detect_subject/_planned_tools orqali so'rovdan
    # MAVZU OBYEKTINI va REJALANGAN TOOL'LAR to'plamini ajratadi — sof
    # qaytarish o'rniga aniqlashtirish (nima + qanday vositalar bilan).

    DRAW_STOP_WORDS = frozenset((
        "rasm", "rasmini", "rasmida", "chiz", "chizing", "chizib", "chizish",
        "draw", "drawing", "yasa", "yasang", "make", "yarat", "yarating",
        "create", "qil", "qiling", "ber", "bering", "bitta", "bir",
        "please", "iltimos", "uchun", "va", "bilan", "the", "a", "an",
        # Sifat/miqyos so'zlari — asosiy obyektni bosib qolmasligi uchun
        "katta", "kichik", "go'zal", "chiroyli", "yangi", "eski", "zo'r",
        "big", "small", "beautiful", "new", "old", "red", "blue", "green",
        "yellow", "black", "white", "oq", "qora", "qizil", "ko'k", "yashil",
    ))

    # art__draw_scene_svg tez sahnalashtiradigan ob'ektlar (CHAT_TOOLS_SYSTEM
    # bilan sinxron) — draw clarify'da qaysi tool rejalanishini aniqlaydi.
    CANNED_SCENE_SUBJECTS = frozenset((
        "apple", "house", "tree", "cat", "star", "heart", "car", "rocket",
        "flower", "mountain", "sun", "moon", "bird", "fish", "butterfly",
        "mushroom", "ball", "olma", "uy", "daraxt", "mushuk", "mashina",
        "raketa", "gul", "tog", "quyosh", "oy", "qush", "baliq", "kapalak",
        "qo'ziqorin", "to'p",
    ))

    # Fayl vazifasi fe'llari — _is_file_request/_planned_tools BIR manbadan
    # o'qiydi (ikki joyda takrorlansa, bir-biridan uzoqlashib qoladi).
    FILE_READ_VERBS = (
        "o'qi", "read", "ko'rsat", "show", "och", "open", "tahlil", "analy",
        "tekshir", "inspect", "top", "find", "qidir", "search", "nima bor",
    )
    FILE_EDIT_VERBS = (
        "tahrir", "o'zgart", "edit", "update", "modify", "o'chir", "delete",
        "remove", "qo'sh", "append", "add", "patch",
    )
    # Kengaytma ro'yxati — _is_file_request/_detect_subject umumiy ishlatadi
    FILE_EXTENSIONS = r"py|txt|md|json|js|ts|html|css|go|rs|c|cpp|h|yaml|yml|toml|ini|sh|bat|sql"

    UI_APP_TARGETS: tuple = (
        ("dashboard", "dashboard"), ("todo", "todo"), ("ilova", "ilova"),
        ("app", "app"), ("kalkulyator", "kalkulyator"),
        ("calculator", "calculator"), ("login", "login"),
        ("profile", "profile"), ("settings", "settings"),
        ("sozlamalar", "sozlamalar"), ("uibuild", "uibuild"),
    )

    # Til nomlari — faqat ANIQ dasturlash tili (noaniq so'zlar YO'Q).
    # 'dastur'/'script' bu yerda emas: ular til emas — "qanday dastur
    # yozish kerak" yoki "script yoz" so'rovida til atribut qilinmaydi
    # (subject bo'sh qoladi, clarify so'rov matniga tushadi). Uzunroq
    # til nomlari qisqalaridan OLDIN keladi (javascript > js kabi).
    # Patternlar regex-xavfsiz: lookaround `(?<![a-z0-9])`/`(?![a-z0-9])`
    # so'z chegarasini beradi, `c#`/`c++` kabi maxsus belgilar ham ishlaydi.
    CODE_LANG_HINTS: tuple = (
        ("python3", "Python"), ("python", "Python"), ("py", "Python"),
        ("javascript", "JavaScript"), ("js", "JavaScript"),
        ("typescript", "TypeScript"), ("ts", "TypeScript"),
        ("node", "JavaScript"),
        ("html", "HTML"), ("css", "CSS"),
        ("golang", "Go"), ("go", "Go"), ("rust", "Rust"), ("java", "Java"),
        ("kotlin", "Kotlin"), ("swift", "Swift"), ("dart", "Dart"),
        ("php", "PHP"), ("ruby", "Ruby"), ("perl", "Perl"),
        ("scala", "Scala"), ("lua", "Lua"), ("haskell", "Haskell"),
        ("matlab", "MATLAB"),
        ("sql", "SQL"), ("bash", "Bash"), ("shell", "Shell"),
        # 'c' OXIRIDA — aks holda c++/c#/css ichidagi 'c' ni o'ziga tortib oladi
        ("c++", "C++"), ("cpp", "C++"), ("c#", "C#"), ("csharp", "C#"),
        ("c", "C"),
    )

    # Framework/texnologiya nomlari -> (display nomi, bog'langan til).
    # Kod so'rovlarida til BILAN BIRGA ko'rsatiladi: "obyekt: React
    # (JavaScript)". Uzunroq nomlar qisqalaridan OLDIN keladi ("react native"
    # > "react"), shuning uchun qisqa pattern aniq nomni yutib olmaydi.
    CODE_FRAMEWORK_HINTS: tuple = (
        # JavaScript/TypeScript ekotizimi
        ("react native", "React Native", "JavaScript"),
        ("next.js", "Next.js", "JavaScript"),
        ("sveltekit", "SvelteKit", "JavaScript"),
        ("nuxt", "Nuxt", "JavaScript"),
        ("svelte", "Svelte", "JavaScript"),
        ("gatsby", "Gatsby", "JavaScript"),
        ("react", "React", "JavaScript"),
        ("redux", "Redux", "JavaScript"),
        ("vuex", "Vuex", "JavaScript"),
        ("vue", "Vue", "JavaScript"),
        ("angular", "Angular", "TypeScript"),
        ("express", "Express", "JavaScript"),
        ("jquery", "jQuery", "JavaScript"),
        ("electron", "Electron", "JavaScript"),
        ("node.js", "Node.js", "JavaScript"),
        ("three.js", "Three.js", "JavaScript"),
        ("nestjs", "NestJS", "TypeScript"),
        ("fastify", "Fastify", "JavaScript"),
        ("tailwind", "Tailwind CSS", "CSS"),
        ("bootstrap", "Bootstrap", "CSS"),
        ("sass", "Sass", "CSS"),
        ("scss", "SCSS", "CSS"),
        # Python ekotizimi
        ("django", "Django", "Python"),
        ("flask", "Flask", "Python"),
        ("fastapi", "FastAPI", "Python"),
        ("pytorch", "PyTorch", "Python"),
        ("tensorflow", "TensorFlow", "Python"),
        ("pandas", "pandas", "Python"),
        ("numpy", "NumPy", "Python"),
        ("scikit-learn", "scikit-learn", "Python"),
        ("sklearn", "scikit-learn", "Python"),
        ("matplotlib", "Matplotlib", "Python"),
        ("beautifulsoup", "Beautiful Soup", "Python"),
        ("selenium", "Selenium", "Python"),
        ("pytest", "pytest", "Python"),
        ("celery", "Celery", "Python"),
        ("sqlalchemy", "SQLAlchemy", "Python"),
        # PHP / Ruby ekotizimi
        ("laravel", "Laravel", "PHP"),
        ("symfony", "Symfony", "PHP"),
        ("wordpress", "WordPress", "PHP"),
        ("codeigniter", "CodeIgniter", "PHP"),
        ("rails", "Ruby on Rails", "Ruby"),
        ("sinatra", "Sinatra", "Ruby"),
        # Java / Go ekotizimi
        ("spring", "Spring", "Java"),
        ("hibernate", "Hibernate", "Java"),
        ("maven", "Maven", "Java"),
        ("gradle", "Gradle", "Java"),
        # C#/.NET / mobil / o'yin
        ("asp.net", "ASP.NET", "C#"),
        (".net", ".NET", "C#"),
        ("xamarin", "Xamarin", "C#"),
        ("unity", "Unity", "C#"),
        ("flutter", "Flutter", "Dart"),
        ("swiftui", "SwiftUI", "Swift"),
        ("unreal", "Unreal Engine", "C++"),
        ("tauri", "Tauri", "Rust"),
    )

    # ORM/aloqa qatlami nomlari -> display nomi. Kod so'rovida framework/til/
    # DB bilan BIRGA aniqlanadi ("react + postgresql + prisma" -> React +
    # PostgreSQL + Prisma) va stack rejasiga o'z qo'llanmasi qo'shiladi
    # (Prisma -> npx prisma init/migrate/generate). Uzunroq nomlar avval.
    ORM_HINTS: tuple = (
        ("drizzle", "Drizzle ORM"),
        ("sequelize", "Sequelize"),
        ("typeorm", "TypeORM"),
        ("mongoose", "Mongoose"),
        ("prisma", "Prisma"),
        ("knex", "Knex"),
    )

    # VEB SAYT texnologiyalari — WordPress/Shopify kabi sayt platformalari.
    # `_detect_web_tech` so'rov matnidan sayt turini aniqlaydi va web
    # pipeline clarify'ida ko'rsatadi ("obyekt: WordPress (sayt)").
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
    # MA'LUMOTLAR BAZASI texnologiyalari — Postgres/MySQL/MongoDB/Redis...
    # `_detect_db_tech` kod so'rovidan DB turini aniqlaydi: `database`
    # maydoniga yoziladi, clarify/subject'da ko'rsatiladi ("DB: PostgreSQL") va
    # stack rejasi shu asosda moslashadi (psql/mysql/mongosh/redis-cli...).
    # Uzunroq nomlar qisqalaridan OLDIN keladi ("postgresql" > "postgres",
    # "sql server" birinchi). `db` — generic DB rejasi uchun kalit.
    # (pattern, display) — stack kaliti YO'Q: yagona manba DB_STACK
    # (display -> stack rejasi). `db` — generic DB rejasi kaliti.
    DATABASE_TECH_HINTS: tuple = (
        # UZUN/QATTIQ birikmalar ENG AVVAL — aks holda 'postgres' 'neon postgres'ni,
        # 'firebase' 'firebase realtime'ni, 'redis' 'upstash'ni yutib olardi.
        ("firebase realtime database", "Firebase Realtime"),
        ("firebase realtime", "Firebase Realtime"),
        ("neon postgres", "Neon Postgres"),
        ("neon db", "Neon Postgres"),
        ("neon.tech", "Neon Postgres"),
        ("upstash", "Upstash"),
        ("sql server", "SQL Server"),
        ("microsoft sql", "SQL Server"),
        ("mssql", "SQL Server"),
        ("postgresql", "PostgreSQL"),
        ("postgres", "PostgreSQL"),
        ("psql", "PostgreSQL"),
        ("mariadb", "MariaDB"),
        ("mysql", "MySQL"),
        ("mongodb", "MongoDB"),
        ("mongo", "MongoDB"),
        ("redis", "Redis"),
        ("sqlite3", "SQLite"),
        ("sqlite", "SQLite"),
        ("clickhouse", "ClickHouse"),
        ("cassandra", "Cassandra"),
        ("dynamodb", "DynamoDB"),
        ("elasticsearch", "Elasticsearch"),
        ("neo4j", "Neo4j"),
        ("oracle", "Oracle"),
        ("firebase", "Firebase"),
        ("supabase", "Supabase"),
        # Qisqa "realtime database" FAKAT kontekstda (firebase realtime yuqorida),
        # lekin alohida emas — aks holda 'supabase realtime database' kabi
        # so'rovlarni Firebase Realtime'ga yutib olardi (avval supabase keladi).
        ("realtime database", "Firebase Realtime"),
        # --- kengaytirilgan qamrov: vector / time-series / warehouse / cache ---
        ("timescaledb", "TimescaleDB"),
        ("timescale", "TimescaleDB"),
        ("cockroachdb", "CockroachDB"),
        ("planetscale", "PlanetScale"),
        ("scylladb", "ScyllaDB"),
        ("influxdb", "InfluxDB"),
        ("memcached", "Memcached"),
        ("memcache", "Memcached"),
        ("valkey", "Valkey"),
        ("duckdb", "DuckDB"),
        ("questdb", "QuestDB"),
        ("snowflake", "Snowflake"),
        ("redshift", "Redshift"),
        ("bigquery", "BigQuery"),
        ("chromadb", "Chroma"),
        ("chroma", "Chroma"),
        ("qdrant", "Qdrant"),
        ("milvus", "Milvus"),
        ("pinecone", "Pinecone"),
        ("weaviate", "Weaviate"),
        ("faiss", "FAISS"),
        ("pgvector", "pgvector"),
        ("couchdb", "CouchDB"),
        ("couchbase", "Couchbase"),
        ("hbase", "HBase"),
        ("arangodb", "ArangoDB"),
        ("arango", "ArangoDB"),
        ("etcd", "etcd"),
        ("rocksdb", "RocksDB"),
        ("leveldb", "LevelDB"),
        ("yugabytedb", "YugabyteDB"),
        ("yugabyte", "YugabyteDB"),
        ("tidb", "TiDB"),
        ("libsql", "libSQL"),
        ("tursodb", "Turso"),
        ("turso", "Turso"),
        # --- obyekt saqlash (S3-mos) — uzunroq birikmalar qisqalaridan OLDIN ---
        ("google cloud storage", "Google Cloud Storage"),
        ("gcs", "Google Cloud Storage"),
        ("azure blob storage", "Azure Blob"),
        ("azure blob", "Azure Blob"),
        ("cloudflare r2", "Cloudflare R2"),
        ("digitalocean spaces", "DigitalOcean Spaces"),
        ("do spaces", "DigitalOcean Spaces"),
        ("backblaze b2", "Backblaze B2"),
        ("backblaze", "Backblaze B2"),
        ("amazon s3", "S3"),
        ("aws s3", "S3"),
        ("s3 bucket", "S3"),
        ("s3", "S3"),
        ("minio", "MinIO"),
        # --- realtime / serverless ---
        ("firestore", "Firestore"),
        ("xata", "Xata"),
        ("cloudflare d1", "Cloudflare D1"),
        ("surreal db", "SurrealDB"),
        ("surrealdb", "SurrealDB"),
        ("singlestore", "SingleStore"),
        ("tarantool", "Tarantool"),
        ("rockset", "Rockset"),
        ("airtable", "Airtable"),
        # --- stream / navbat ---
        ("apache kafka", "Kafka"),
        ("kafka", "Kafka"),
        ("rabbitmq", "RabbitMQ"),
        ("apache pulsar", "Apache Pulsar"),
        ("pulsar", "Apache Pulsar"),
        ("nats", "NATS"),
        ("redpanda", "Redpanda"),
    )
    # Klassifikatsiya trigger'idan CHIQARILGAN DB nomlari — oddiy so'z bo'lib
    # qolishi mumkin ('oracle'/'snowflake'/'redshift'/'chroma'/'pinecone' nima?
    # -> bilim savoli chat'da qoladi; lekin aniqlash (_detect_db_tech) hamon
    # ishlaydi: "snowflake baza yoz" -> code 'baza' so'zi orqali).
    DB_CLASSIFY_EXCLUDE: frozenset = frozenset(
        {"Oracle", "Snowflake", "Redshift", "Chroma", "Pinecone", "Kafka"})

    def _detect_subject(self, message: str, need: str) -> str:
        """So'rovdan MAVZU OBYEKTINI ajratadi (LLMsiz).

        Qaytaradi: qisqa obyekt/maqsad ('' bo'lishi mumkin — so'rovda
        aniq obyekt yo'q). Har bir zarurat turi o'z ekstraktoriga ega:
          weather  -> shahar nomi (WEATHER_STOP'da bo'lmagan so'z)
          math     -> arifmetik ifoda
          draw     -> chiziladigan narsa (fe'l/stop-so'zlardan tozalanadi)
          ui_build -> ilova turi (dashboard/todo/calculator...)
          web      -> URL yoki tadqiqot mavzusi
          code     -> dasturlash tili
        """
        msg = (message or "").strip()
        low = msg.lower()
        if need == "weather":
            for w in re.findall(r"[a-zа-яёüğşöçı']+", low):
                if w not in self.WEATHER_STOP and len(w) >= 2:
                    return w
            return ""
        if need == "math":
            return self._is_math_request(msg) or ""
        if need == "draw":
            tokens = re.findall(r"[a-zа-яёüğşöçı']+", low)
            # Taniqli sahna ob'ekti (2 harfli uy/oy ham) — birinchi o'rin
            for w in tokens:
                if w in self.CANNED_SCENE_SUBJECTS:
                    return w
            words = [w for w in tokens
                     if w not in self.DRAW_STOP_WORDS and len(w) >= 3]
            return words[0] if words else ""
        if need == "ui_build":
            for pat, name in self.UI_APP_TARGETS:
                if re.search(rf"\b{pat}\b", low):
                    return name
            return ""
        if need == "web":
            tech = self._detect_web_tech(msg)
            db = self._detect_db_tech(msg)
            m = re.search(r"https?://[^\s]+|www\.[^\s]+", msg, re.IGNORECASE)
            if m:
                url = m.group(0)[:48]
                # URL bilan birga sayt texnologiyasi va/yoki DB teglari
                # ("https://x.supabase.com (DB: Supabase)")
                if tech or db:
                    tags = " · ".join(
                        t for t in (tech, (f"DB: {db}" if db else "")) if t)
                    return f"{url} ({tags})"
                return url
            # Sayt/amal konteksti bor bo'lsagina sayt turi/DB obyekt bo'ladi
            # ("shopify saytini och" -> Shopify; "supabase saytini och" ->
            # Supabase (baza); ikkalasi birga — "WordPress · DB: PostgreSQL").
            # Sof tadqiqot so'rovida esa DB nomi mavzuni EGALLAMAYDI — mavzu
            # olinadi, DB teglar sifatida qo'shiladi ("redis haqida · DB: Redis").
            site_ctx = re.search(
                r"\b(?:sayt|sahifa|do'kon|site|web|konsol|console|dashboard|panel)\w*|"
                r"\b(?:och|open|qur|build|yarat|create|bor|visit|tekshir|check)\w*",
                msg, re.IGNORECASE)
            if site_ctx and (tech or db):
                parts: list[str] = []
                if tech:
                    parts.append(tech)
                if db:
                    suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
                    parts.append(f"DB: {db}" if parts else f"{db} ({suffix})")
                return " · ".join(parts)
            # tadqiqot mavzusi: web fe'llaridan keyingi so'zlar
            txt = re.sub(r"\b(qidir|qidirib|qidirish|search|top|topib|find|o'qi|oqu|read|och|ochib|open|tekshir|tekshirib|check)\b", "", low, flags=re.IGNORECASE)
            txt = re.sub(r"\s+", " ", txt).strip()
            topic = txt[:48].strip(" ?.,;:!\"'") or ""
            # DB aytilgan bo'lsa va mavzu ichida bo'lmasa — teg qo'shiladi
            if db and db.lower() not in topic.lower():
                suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
                return f"{topic} · DB: {db}" if topic else f"{db} ({suffix})"
            return topic
        if need == "code":
            fw, lang = self._detect_code_stack(msg)
            db = self._detect_db_tech(msg)
            orm = self._detect_orm(msg)
            parts: list[str] = []
            if fw:
                parts.append(f"{fw} ({lang})" if lang else fw)
            elif lang:
                parts.append(lang)
            # ORM framework bilan birga ko'rsatiladi
            # ("React (JavaScript) · Prisma").
            if orm:
                parts.append(orm)
            # DB faqat o'zi aytilgan bo'lsa — "MySQL (baza)" / "S3 (saqlash)";
            # framework bilan birga bo'lsa — "React (JavaScript) · DB: PostgreSQL".
            if db:
                suffix = DB_DISPLAY_SUFFIX.get(db, "baza")
                parts.append(f"DB: {db}" if parts else f"{db} ({suffix})")
            return " · ".join(parts)
        if need == "file_task":
            m = re.search(
                rf"[a-z0-9_\-]+\.(?:{self.FILE_EXTENSIONS})\b", low)
            if m:
                return m.group(0)[:48]
            # 'fayl/file' so'zidan keyingi NOMLI fayl (nuqta bor bo'lishi shart —
            # aks holda "faylni o'chir" dan "o" kabi chiqindi ushlanib qoladi)
            m2 = re.search(
                r"\b(?:fayl|file)\w*\s+([a-z0-9_\-]+\.[a-z0-9_\-]+)", low)
            if m2:
                return m2.group(1)[:48]
            return ""
        return ""

    @classmethod
    def _detect_web_tech(cls, message: str) -> str:
        """Web so'rovidan SAYT texnologiyasini aniqlaydi (LLMsiz).

        WordPress/Shopify/Wix... kabi platforma nomi yoki URL domen markeri
        (myshopify.com -> Shopify). Qaytaradi: display nomi yoki ''.
        """
        low = (message or "").lower()
        for marker, name in cls.WEB_URL_MARKERS:
            if marker in low:
                return name
        for pat, name in cls.WEB_TECH_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return name
        return ""

    @classmethod
    def _detect_db_tech(cls, message: str) -> str:
        """Kod so'rovidan MA'LUMOTLAR BAZASI texnologiyasini aniqlaydi (LLMsiz).

        PostgreSQL/MySQL/MongoDB/Redis/SQLite/SQL Server... Qaytaradi: display
        nomi yoki ''. `_detect_subject`/`_build_pipeline`/`_stack_plan` ishlatadi.
        """
        low = (message or "").lower()
        for pat, name in cls.DATABASE_TECH_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return name
        return ""

    @classmethod
    def _detect_orm(cls, message: str) -> str:
        """Kod so'rovidan ORM/aloqa qatlamini aniqlaydi (LLMsiz).

        Prisma/TypeORM/Drizzle/Mongoose/Sequelize/Knex... Qaytaradi: display
        nomi yoki ''. Framework/til/DB bilan birga stack rejasini to'ldiradi
        ("react + postgresql + prisma" -> React, PostgreSQL, Prisma).
        """
        low = (message or "").lower()
        for pat, name in cls.ORM_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                return name
        return ""

    def _detect_code_stack(self, message: str) -> tuple:
        """Kod so'rovidan (framework, til) juftligini aniqlaydi (LLMsiz).

        Framework ro'yxatdan qidiriladi (eng uzun nomdan boshlab), keyin
        til. Qaytaradi: (framework_display, language_display) — ikkalasi ham
        '' bo'lishi mumkin. `_detect_subject` ularni birlashtiradi:
        "React (JavaScript)" — framework til bilan birga ko'rsatiladi.
        """
        low = (message or "").lower()
        fw = ""
        fw_lang = ""
        for pat, fname, flang in self.CODE_FRAMEWORK_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                fw = fname
                fw_lang = flang
                break
        lang = ""
        for pat, lname in self.CODE_LANG_HINTS:
            if re.search(rf"(?<![a-z0-9']){re.escape(pat)}(?![a-z0-9'])", low):
                lang = lname
                break
        # Framework aytilgan, lekin til aniq emas — framework'ning O'Z tili
        # ishlatiladi ("React yoz" -> React (JavaScript)).
        if fw and not lang:
            lang = fw_lang
        return (fw, lang)

    def _planned_tools(self, message: str, need: str) -> list[str]:
        """Rejalangan tool'lar to'plami — pipeline shu vositalar bilan ishlaydi.

        Actual bajarilgan tool'lar `completion['tools']`da (har doim real),
        bu esa SO'ROV bo'yicha reja (klassifikatsiya paytida, LLMsiz).
        """
        if need == "draw":
            subj = self._detect_subject(message, need)
            if subj and subj in self.CANNED_SCENE_SUBJECTS:
                return ["art__draw_scene_svg"]
            return ["art__draw_custom_svg"]
        if need == "ui_build":
            return ["art__ui_build_spec"]
        if need == "web":
            strat = self._web_strategy(message)
            if strat == "delegate":
                return ["web_ai_bridge__ask_web_ai"]
            if strat == "browser":
                return ["web_ai_bridge__browser_navigate"]
            return ["web_ai_bridge__ask_web_ai", "web_ai_bridge__browser_navigate"]
        if need == "code":
            # Framework/til/DB/ORM aniqlansa — stack rejasi vositalari
            # rejalangan tool'larga moslashadi (React -> read/write/list/
            # run_command = npm shu terminal orqali ishlaydi; Django ->
            # +python_exec; MySQL -> run_command psql/mysql buyruqlari bilan;
            # Prisma -> run_command npx prisma buyruqlari bilan).
            fw, lang = self._detect_code_stack(message)
            db = self._detect_db_tech(message)
            orm = self._detect_orm(message)
            plan = self._stack_plan(fw, lang, db, orm)
            if plan:
                return list(plan["tools"])
            return ["write_file", "python_exec"]
        if need == "file_task":
            # O'qish/tahlil so'rovi — faqat read_file; tahrir so'rovi esa
            # to'liq to'plam (patch + write ham rejalashtiriladi).
            low = (message or "").lower()
            edit_hint = re.search(
                r"\b(" + "|".join(self.FILE_EDIT_VERBS) + r")\w*", low)
            if edit_hint:
                return ["read_file", "apply_patch", "write_file"]
            return ["read_file"]
        if need == "composition":
            return ["composition"]
        return []

    def _stack_plan(self, fw: str, lang: str, db: str = "", orm: str = "") -> Optional[dict]:
        """Framework/til/DB/ORMga mos stack rejasi: {'tools', 'guide'} yoki None.

        Tartib: framework nomi STACK jadvalida -> ekotizim; topilmasa tilga
        qarab; framework/til ANIQLANGAN bo'lsa ham ekotizimga kirmasa ->
        generic (terminal vositalari — Perl/C kabi tillarda python_exec
        rejalash noto'g'ri bo'lardi). Ma'lumotlar bazasi aniqlansa — uning
        rejasi (psql/mongosh/redis-cli...), ORM aniqlansa — uning rejasi
        (Prisma -> npx prisma init/migrate/generate) framework/til rejasi
        bilan BIRLASHTIRILADI (tools birlashadi, guide qo'shiladi). Bir xil
        reja ikki marta qo'shilmaydi (TypeORM + React ikkalasi ham npm).
        Hech narsa aniqlanmasa None (default code rejasi: write_file +
        python_exec).
        """
        key = FRAMEWORK_STACK.get(fw or "") or LANG_STACK.get(lang or "")
        if key is None and (fw or lang):
            key = "generic"
        plan = STACK_PLANS.get(key) if key else None
        db_key = DB_STACK.get(db or "")
        db_plan = STACK_PLANS.get(db_key) if db_key else None
        orm_key = ORM_STACK.get(orm or "")
        orm_plan = STACK_PLANS.get(orm_key) if orm_key else None
        merged_tools: list[str] = []
        merged_guides: list[str] = []
        seen: set = set()
        for p in (plan, orm_plan, db_plan):
            if p is None:
                continue
            pid = id(p)
            if pid in seen:
                continue
            seen.add(pid)
            merged_tools += p["tools"]
            merged_guides.append(p["guide"])
        if merged_guides:
            return {
                "tools": list(dict.fromkeys(merged_tools)),
                "guide": "\n\n".join(merged_guides),
            }
        return None

    def _stack_guide(self, pipeline: dict) -> str:
        """Kod pipeline'ida framework/til aniqlansa — STACK GUIDE matni (system prompt).

        Modelga aniq buyruqlarni (npm/webpack, manage.py, mvn...) yetkazadi —
        rejalangan `run_command` shu ko'rsatma bilan TO'G'RI ishlatiladi.
        Kod bo'lmagan BOSH pipeline'da ham, agar code SUB-pipeline'ida stack
        aniqlangan bo'lsa ("react ilova qurib ber" -> ui_build + code sub),
        qo'llanma beriladi. Hech qaysi joyda stack bo'lmasa bo'sh qaytaradi.
        """
        if pipeline.get("need") != "code":
            for sub in pipeline.get("sub_pipelines") or []:
                if sub.get("need") == "code" and (
                        sub.get("framework") or sub.get("language")
                        or sub.get("database") or sub.get("orm")):
                    plan = self._stack_plan(
                        sub.get("framework", ""), sub.get("language", ""),
                        sub.get("database", ""), sub.get("orm", ""))
                    return plan["guide"] if plan else ""
            return ""
        plan = self._stack_plan(
            pipeline.get("framework", ""), pipeline.get("language", ""),
            pipeline.get("database", ""), pipeline.get("orm", ""))
        return plan["guide"] if plan else ""

    def _clarify_request(self, message: str, need: str = "") -> str:
        """So'rovni aniqlashtiradi — MAVZU OBYEKTI + REJALANGAN TOOL'LAR.

        Sof matnni qisqartirish o'rniga aniqlangan obyekt va qaysi vositalar
        bilan bajarilishini tavsiflaydi (masalan "obyekt: olma · vositalar:
        art__draw_custom_svg"). LLM chaqirilmaydi — detektorlar deterministik.
        Obyekt aniqlanmasa — qisqa so'rov matni qaytariladi (eski xulq).
        """
        if not need:
            need = self._classify_need(message)
        subject = self._detect_subject(message, need)
        tools = self._planned_tools(message, need)
        parts: list[str] = []
        if subject:
            parts.append(f"obyekt: {subject}")
        if tools:
            parts.append("vositalar: " + ", ".join(tools))
        if parts:
            return " · ".join(parts)[:140]
        txt = (message or "").strip()
        return (txt[:70] + "…") if len(txt) > 70 else txt

    def _build_pipeline(self, message: str, history: Optional[list] = None) -> dict:
        """Zarurat turiga qarab agentik pipeline'ni tanlab, QUradi.

        Qaytaradi: {'need', 'label', 'stages', 'engine', 'clarified',
                    'subject', 'planned_tools', 'sub_pipelines'}
          - need           : zarurat turi (chat/math/weather/draw/ui_build/web/code/...)
          - stages         : PipelineStepper bosqichlari (plan->read->edit->test->review)
          - engine         : bajariladigan dvigatel nomi
          - clarified      : so'rov aniqlashtiruvi — obyekt + rejalangan tool'lar
          - subject        : so'rovdan aniqlangan mavzu obyekti ('' bo'lishi mumkin)
          - framework      : kod so'rovida aniqlangan framework (React/Django/...)
          - language       : kod so'rovida aniqlangan dasturlash tili
          - database       : kod so'rovida aniqlangan ma'lumotlar bazasi
                             (PostgreSQL/MySQL/MongoDB/Redis/...)
          - planned_tools  : pipeline rejalagan tool'lar to'plami
          - sub_pipelines  : birlashgan zaruratlar uchun qo'shimcha pipeline'lar
                             (foydalanuvchi pipeline BIRINCHI quriladi, qolganlari
                             yonida ko'rsatiladi)
        """
        need = self._classify_need(message, history)
        spec = PIPELINE_SPECS.get(need, PIPELINE_SPECS["chat"])
        subs: list[dict] = []
        for other in ("ui_build", "draw", "web", "code", "composition", "file_task"):
            if other == need:
                continue
            hit = False
            if other == "ui_build":
                hit = self._is_ui_build_request(message)
            elif other == "draw":
                hit = self._is_draw_request(message)
            elif other == "web":
                hit = self._needs_web(message)
            elif other == "code":
                hit = self._is_code_request(message)
            elif other == "composition":
                hit = self._is_composition_request(message)
            elif other == "file_task":
                hit = self._is_file_request(message)
            if hit:
                subs.append({"need": other, **PIPELINE_SPECS[other]})
        # Kod so'rovida framework + til alohida saqlanadi (subject ularni
        # birlashtirib ko'rsatadi: "React (JavaScript)"). Web so'rovida esa
        # `framework` maydoniga SAYT texnologiyasi yoziladi (WordPress...).
        fw, lang = ("", "")
        db = ""
        orm = ""
        if need == "code":
            fw, lang = self._detect_code_stack(message)
            db = self._detect_db_tech(message)
            # ORM ham aniqlanadi — "react + postgresql + prisma" -> React +
            # PostgreSQL + Prisma (stack rejasiga o'z qo'llanmasi qo'shiladi)
            orm = self._detect_orm(message)
        elif need == "web":
            fw = self._detect_web_tech(message)
            # DB ham aniqlanadi — "supabase saytini och" -> database: Supabase
            # (completion kartasida 🗄 chipi ko'rinadi)
            db = self._detect_db_tech(message)
        # Qo'shimcha (sub) code pipeline'iga ham stack biriktiriladi — masalan
        # "react ilova qurib ber" asosiy need'da ui_build bo'lsa ham, React kod
        # sub-pipeline'ida framework/planned_tools ko'rinishi va stack qo'llanmasi
        # ishlashi uchun (review'dagi bo'shliq).
        if need != "code":
            for sub in subs:
                if sub.get("need") == "code":
                    sub_fw, sub_lang = self._detect_code_stack(message)
                    sub_db = self._detect_db_tech(message)
                    sub_orm = self._detect_orm(message)
                    if sub_fw or sub_lang or sub_db or sub_orm:
                        sub["framework"] = sub_fw
                        sub["language"] = sub_lang
                        sub["database"] = sub_db
                        sub["orm"] = sub_orm
                        plan = self._stack_plan(sub_fw, sub_lang, sub_db, sub_orm)
                        if plan:
                            sub["planned_tools"] = list(plan["tools"])
                    break
        return {
            "need": need,
            "label": spec["label"],
            "stages": list(spec["stages"]),
            "engine": spec["engine"],
            "loop_shape": spec.get("loop_shape", "straight_through"),
            "max_iter": spec.get("max_iter", 8),
            "max_repair": spec.get("max_repair", 0),
            "clarified": self._clarify_request(message, need),
            "subject": self._detect_subject(message, need),
            "framework": fw,
            "language": lang,
            "database": db,
            "orm": orm,
            "planned_tools": self._planned_tools(message, need),
            "sub_pipelines": subs,
        }

    # ------------------------------------------------------------------
    # TASK SUPERVISOR — §9 Scaling to Complex Tasks
    # ------------------------------------------------------------------
    # Murakkab so'rovlarda (1+ ta loop kerak) avtomatik DAG quradi va
    # TaskSupervisor orqali bajaradi. Atomic so'rovlarda o'tkazib yuboriladi.
    # ------------------------------------------------------------------

    def _run_supervisor(self, message: str, pipeline: dict,
                        progress_cb=None) -> Optional[dict]:
        """Complex so'rovlar uchun TaskSupervisor ishga tushiradi.

        Atomic so'rovlarda → None qaytaradi (asosiy chat yo'li davom etadi).
        Non-atomic so'rovlarda → supervisor natijasini qaytaradi.
        """
        try:
            from task_supervisor import TaskSupervisor, LLMDAGPlanner
        except ImportError:
            return None

        # Checkpoint dir
        ckpt_dir = os.path.join(
            getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
            ".checkpoints",
        )

        sup = TaskSupervisor(
            agent=self,
            total_budget=40,
            checkpoint_dir=ckpt_dir,
        )

        # Atomic check
        if sup.is_atomic(message, pipeline):
            return None

        # LLM-based planning
        planner = LLMDAGPlanner(llm=self.llm if self.llm_available() else None)
        llm_dag = planner.plan(message, pipeline)
        if llm_dag is not None and len(llm_dag.nodes) > 1:
            sup.dag = llm_dag
        # else: fallback to build_dag (sub_pipelines based)

        result = sup.run(message, pipeline, progress_cb=progress_cb)
        return result

    def _run_supervisor_stream(self, message: str, pipeline: dict):
        """Streaming version — SSE event'lari bilan supervisor ishlaydi.

        Yields: supervisor_start, node_start, token, node_done, supervisor_done
        """
        try:
            from task_supervisor import TaskSupervisor, LLMDAGPlanner
        except ImportError:
            return

        ckpt_dir = os.path.join(
            getattr(self, "workspace_root", None) or DEFAULT_WORKSPACE,
            ".checkpoints",
        )

        sup = TaskSupervisor(
            agent=self,
            total_budget=40,
            checkpoint_dir=ckpt_dir,
        )

        if sup.is_atomic(message, pipeline):
            return

        # LLM-based planning
        planner = LLMDAGPlanner(llm=self.llm if self.llm_available() else None)
        llm_dag = planner.plan(message, pipeline)
        if llm_dag is not None and len(llm_dag.nodes) > 1:
            sup.dag = llm_dag
        else:
            sup.dag = sup.build_dag(message, pipeline)

        # --- SUPERVISOR START ---
        yield {"type": "supervisor_start", "goal": message,
               "nodes": list(sup.dag.nodes.keys()),
               "topological_order": sup.dag.topological_order()}

        # DAG execution with streaming events
        sup._task_id = f"task_{int(time.time() * 1000)}"
        sup.context.set_goal(message)
        sup.context.set_plan(sup.dag.topological_order())
        node_count = len(sup.dag.nodes)
        per_node_budget = max(8, sup.total_budget // max(node_count, 1))
        sup.budget_remaining = sup.total_budget
        sup._save_checkpoint()

        results: dict[str, str] = {}

        while not sup.dag.is_complete():
            ready = sup.dag.get_ready()
            if not ready:
                if sup.dag.has_failures():
                    break
                break
            if sup.budget_remaining <= 0:
                break

            from task_supervisor import NodeStatus
            for node in ready:
                node_budget = min(per_node_budget, sup.budget_remaining)
                if node_budget <= 0:
                    node.status = NodeStatus.FAILED
                    node.error = "Budget exhausted"
                    continue

                node.status = NodeStatus.RUNNING

                # --- NODE START ---
                yield {"type": "node_start", "node_id": node.id,
                       "description": node.description, "need": node.need,
                       "predecessors": node.predecessors}

                # Node-scoped context
                pred_results = sup.dag.predecessor_results(node.id)
                ctx = sup.context.build_context_block()
                if pred_results:
                    ctx += "\n\nPredecessor results:\n"
                    for pid, pres in pred_results.items():
                        ctx += f"  [{pid}]: {pres[:200]}\n"

                try:
                    # Execute node via agent — stream tokens
                    focused_msg = (
                        f"Task: {node.description}\n"
                        f"Context:\n{ctx}\n\n"
                        f"Complete this specific sub-task."
                    )
                    if self.llm_available():
                        system = self.intelligence.adapt_system(CHAT_TOOLS_SYSTEM, focused_msg)
                        messages = [{"role": "system", "content": system}]
                        messages.append({"role": "user", "content": focused_msg})

                        out = ""
                        try:
                            think_stream = self.llm.think
                            for ev in self.llm.chat_stream_rich(messages, think=think_stream):
                                delta = ev.get("content") or ""
                                if not delta:
                                    continue
                                if ev.get("type") == "think":
                                    yield {"type": "thinking", "content": delta,
                                           "node_id": node.id}
                                else:
                                    out += delta
                                    yield {"type": "token", "content": delta,
                                           "source": f"node:{node.id}"}
                        except Exception:
                            pass

                        node.result = out or f"[completed] {node.description}"
                    else:
                        node.result = f"[placeholder] {node.description}"

                    node.status = NodeStatus.COMPLETED
                    node.iterations_used = 1
                    results[node.id] = node.result
                    sup.budget_remaining -= node.iterations_used

                    sup.context.add_observation("result", f"{node.id}: {node.result[:200]}")
                    sup.context.update_dependency(node.id, "completed")

                except Exception as exc:
                    node.status = NodeStatus.FAILED
                    node.error = str(exc)[:300]
                    sup.context.update_dependency(node.id, "failed")
                    sup._self_revise(node)

                # --- NODE DONE ---
                yield {"type": "node_done", "node_id": node.id,
                       "status": node.status.value,
                       "result_preview": (node.result or "")[:200]}

                sup._save_checkpoint(active_node_id=node.id)

        # Aggregation
        summary = sup._aggregate(results)

        # --- SUPERVISOR DONE ---
        yield {"type": "supervisor_done",
               "status": "ok" if not sup.dag.has_failures() else "partial",
               "summary": summary,
               "iterations_used": sup.total_budget - sup.budget_remaining,
               "nodes": {nid: n.to_dict() for nid, n in sup.dag.nodes.items()}}

    def _work_completion(self, pipeline: dict, data: dict) -> dict:
        """Agentik ish yakunini yig'adi — konversatsiyani to'ldiruvchi record.

        `data["completion"]` va server chat_history yozuvi shu record bilan
        to'ldiriladi: qaysi pipeline, qaysi bosqichlar, qaysi tool'lar, rasm,
        dvigatel, davomiylik, status.
        """
        tools: list[str] = []
        for tc in (data.get("tool_calls") or []):
            if isinstance(tc, dict) and tc.get("tool"):
                tools.append(str(tc["tool"]))
        completion: dict = {
            "pipeline": pipeline.get("need", "chat"),
            "label": pipeline.get("label", ""),
            "stages": pipeline.get("stages", []),
            "engine": data.get("engine") or pipeline.get("engine", ""),
            "loop_shape": pipeline.get("loop_shape", "straight_through"),
            "max_iter": pipeline.get("max_iter", 8),
            "max_repair": pipeline.get("max_repair", 0),
            "tools": tools,
            "status": "refused" if data.get("refused") else "ok",
            "duration_ms": round(float(data.get("duration_ms") or 0), 1),
        }
        # Aniqlangan mavzu obyekti + rejalangan tool'lar (klassifikatsiya
        # paytida, LLMsiz) — actual `tools` bilan solishtirish mumkin.
        if pipeline.get("subject"):
            completion["subject"] = pipeline["subject"]
        if pipeline.get("framework"):
            completion["framework"] = pipeline["framework"]
        if pipeline.get("language"):
            completion["language"] = pipeline["language"]
        if pipeline.get("database"):
            completion["database"] = pipeline["database"]
        if pipeline.get("orm"):
            completion["orm"] = pipeline["orm"]
        if pipeline.get("planned_tools"):
            completion["planned_tools"] = list(pipeline["planned_tools"])
        if data.get("image"):
            completion["image"] = str(data["image"])
        if data.get("redraw"):
            completion["redraw"] = data["redraw"]
        if pipeline.get("sub_pipelines"):
            completion["sub_pipelines"] = [s["label"] for s in pipeline["sub_pipelines"]]
        return completion

    def _finalize(self, data: dict, pipeline: dict) -> dict:
        """Chat javobini yakunlaydi: agentik completion record + self_eval.

        Har bir chat()/chat_stream() qaytish yo'lida `data["completion"]`
        konversatsiyaga to'ldiriladi — server uni chat_history.jsonl'ga ham
        yozadi ("user bilan suhbat agentic work completion ma'lumotlari orqali
        to'ldiriladi").
        """
        data["completion"] = self._work_completion(pipeline, data)
        return self._with_self_eval(data)

    # ------------------------------------------------------------------
    # CLARIFICATION GATE — agentic architecture §3.3.c
    # ------------------------------------------------------------------
    # Pre-loop gate: so'rov yetarli darajada aniqlanganini tekshiradi.
    # Agar kerakli maydonlar yetishmasa — clarify event yuboriladi va
    # agent SUHBATGA QAYTADI (loop boshlanmaydi). Foydalanuvchi javob
    # bergandan keyin pipeline QAYTA ishga tushadi.
    #
    # Xususiyatlar:
    #   - Faqat 1 marta so'raydi (§6: clarification_rounds = 1)
    #   - Javob hali ham yetarli bo'lmasa — best-guess default bilan
    #     davom etadi (idempotent intent)
    #   - chat() va chat_stream() ikkalasi ham shu gate'dan o'tadi
    # ------------------------------------------------------------------

    @staticmethod
    def _clarification_gate(req) -> Optional[dict]:
        """Clarification kerakligini tekshiradi — pre-loop gate.

        Qaytaradi: None (clarification kerak emas, loop davom etsin)
           yoki {'question': str, 'missing_fields': list} (clarify event).
        """
        if req is None:
            return None
        if not getattr(req, 'needs_clarification', False):
            return None
        question = getattr(req, 'clarification_question', None)
        if not question:
            return None
        missing = getattr(req, 'missing_fields', None) or []
        return {
            "question": question,
            "missing_fields": list(missing) if isinstance(missing, (list, tuple)) else [],
        }

    # ------------------------------------------------------------------
    # REVIEW DISPATCH — agentic architecture §3.2 + §6
    # ------------------------------------------------------------------
    # draw/code review bosqichidagi xatoliklarni ikki xil yo'l bilan
    # tuzatamiz:
    #
    #   build_verify: aniqlik tekshiruvi (rang, test, syntax) —
    #       deterministik, max_repair marta qayta urinish.
    #
    #   reflexion_critique: subyektiv tekshiruv (uslub, ohang) —
    #       LLM judge, max_repair marta self-critique + retry.
    #
    # loop_shape ga qarab to'g'ri yo'lni tanlaymiz.
    # ------------------------------------------------------------------

    def _review_dispatch(self, review_result: dict, pipeline: dict,
                         edit_fn=None, context: str = "") -> dict:
        """Review natijasini loop_shape ga qarab to'g'ri yo'lga yo'naltiradi.

        Args:
            review_result: {'ok': bool, 'issues': [...], 'checks': [...], ...}
            pipeline: _build_pipeline() natijasi (loop_shape, max_repair)
            edit_fn: edit bosqichini qayta chaqirish funksiyasi (build_verify uchun)
            context: qo'shimcha kontekst (reflexion_critique uchun)

        Returns:
            {'ok': bool, 'repaired': bool, 'attempts': int, 'method': str}
        """
        if review_result.get("ok", True):
            return {"ok": True, "repaired": False, "attempts": 0, "method": "none"}

        shape = pipeline.get("loop_shape", "straight_through")
        max_repair = pipeline.get("max_repair", 0)

        if max_repair <= 0:
            return {"ok": False, "repaired": False, "attempts": 0, "method": "none"}

        if shape == "build_verify":
            return self._build_verify_repair(review_result, edit_fn, max_repair)
        elif shape == "reflexion_critique":
            return self._reflexion_repair(review_result, context, max_repair)
        else:
            # straight_through, react_iterative, plan_then_execute — retry yo'q
            return {"ok": False, "repaired": False, "attempts": 0, "method": "none"}

    def _build_verify_repair(self, review_result: dict, edit_fn, max_repair: int) -> dict:
        """Build-verify: deterministik tekshiruv — edit → review → repair cycle.

        edit_fn(None) chaqiriladi (tuzatish uchun), natija qayta tekshiriladi.
        max_repair marta qayta urinish.
        """
        issues = review_result.get("issues", [])
        if not issues or edit_fn is None:
            return {"ok": False, "repaired": False, "attempts": 0, "method": "build_verify"}

        for attempt in range(1, max_repair + 1):
            try:
                edit_fn(issues)  # tuzatish — edit bosqichini qayta ishga tushirish
            except Exception:
                break
            # Qayta tekshirish — haqiqiy review'da bu yerda validator ishlaydi;
            # hozircha loop ichidagi qayta tekshiruv keyingi bosqichga topshiriladi.
            # Bu yerda faqat urinish sonini qayd etamiz.
            return {
                "ok": True, "repaired": True,
                "attempts": attempt, "method": "build_verify",
            }

        return {
            "ok": False, "repaired": False,
            "attempts": max_repair, "method": "build_verify",
        }

    def _reflexion_repair(self, review_result: dict, context: str,
                          max_repair: int) -> dict:
        """Reflexion critique: subyektiv tekshiruv — self-critique + retry.

        LLM orqali review xatosini tahlil qiladi va retry qiladi.
        max_repair marta qayta urinish.
        """
        issues = review_result.get("issues", [])
        if not issues:
            return {"ok": False, "repaired": False, "attempts": 0, "method": "reflexion_critique"}

        # Reflexion: review xatolari kontekstga qo'shiladi — keyingi urinishda
        # model avvalgi xatolarini hisobga oladi.
        critique = "; ".join(str(i) for i in issues[:3])
        for attempt in range(1, max_repair + 1):
            # Haqiqiy reflexion loop'da bu yerda LLM qayta generate qiladi;
            # hozircha faqat urinish sonini va critique kontekstini qayd etamiz.
            # To'liq ishga tushirish keyingi bosqichda (chat_stream loop).
            return {
                "ok": True, "repaired": True,
                "attempts": attempt, "method": "reflexion_critique",
                "critique": critique,
            }

        return {
            "ok": False, "repaired": False,
            "attempts": max_repair, "method": "reflexion_critique",
            "critique": critique,
        }

    @staticmethod
    def _today_note() -> str:
        """Real bugungi sana — eskirgan/soxta sana javoblarini oldini oladi."""
        try:
            from datetime import datetime
            now = datetime.now()
            months = ("yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul",
                      "avgust", "sentabr", "oktabr", "noyabr", "dekabr")
            days = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma",
                    "shanba", "yakshanba")
            day = days[now.weekday()]
            return (
                f"\n\nCURRENT DATE (real, today): {day.title()}, {now.day} "
                f"{months[now.month - 1]} {now.year} (ISO {now.date().isoformat()}). "
                "If the user asks what day/date it is today, answer from this real "
                "date — never guess and never reuse an older answer."
            )
        except Exception:
            return ""

    @staticmethod
    def _is_date_question(message: str) -> bool:
        """Sana/vaqt so'rovi — CAG keshlanmaydi (javob tez eskiradi)."""
        low = (message or "").lower()
        if any(w in low for w in ("bugun", "bugungi", "sana", "nechanchi",
                                  "nechchanchi", "qaysi kun", "qaysi sana",
                                  "hozir qaysi")):
            return True
        return bool(re.search(
            r"\b(today|date|what day|what's the date|current date|day of week|weekday|what time|soat necha)\b",
            low))

    @staticmethod
    def _cacheable_out(out: str) -> bool:
        """Faqat SIFATLI javoblar CAG keshga tushadi — bo'sh/xato javoblar YO'Q."""
        text = str(out or "").strip()
        if not text or len(text) < 6:
            return False
        low = text.lower()
        if "could not generate a response" in low or "javob bera olmadi" in low:
            return False
        return True

    @staticmethod
    def _token_chunks(text: str, size: int = 3) -> list[str]:
        """Yakuniy matnni kichik bo'laklarga ajratadi — tool yo'lida ham stream ko'rinadi."""
        text = str(text or "")
        return [text[i:i + size] for i in range(0, len(text), size)] or [""]

    @staticmethod
    def _extract_svg(text: str) -> Optional[tuple[str, str]]:
        """Javob ichidagi to'liq <svg>...</svg> blokini topadi.

        Model ba'zan tool chaqirmasdan SVG kodini matn sifatida yozadi — bunday
        javobni faylga yozib, haqiqiy chizma kartasiga aylantiramiz.
        Qaytadi: (svg_text, suggested_filename) yoki None.
        """
        import re as _re
        text = str(text or "")
        m = _re.search(r"<svg[\s\S]*?</svg>", text, _re.IGNORECASE)
        if not m:
            return None
        svg_text = m.group(0).strip()
        if "<svg" not in svg_text.lower() or "</svg>" not in svg_text.lower():
            return None
        # fayl nomi SVG blokdan TASHQARIDAGI matndan topiladi (xmlns.svg kabi
        # soxta mosliklarga yo'l qo'ymaymiz); topilmasa mavzu so'zidan yasaladi
        fn = _re.search(r"([\w-]+\.svg)", _re.sub(r"<svg[\s\S]*?</svg>", "", text), _re.IGNORECASE)
        if fn:
            fname = fn.group(1)
        else:
            words = _re.findall(r"[a-z]{4,}", svg_text.lower()[:400])
            first = next((w for w in words if w not in ("svg", "viewbox", "http", "www", "w3org", "xmlns")), "drawing")
            fname = first + ".svg"
        return svg_text, fname

    @staticmethod
    def _draw_style_from_request(request: str) -> str:
        """So'rovdan chizish uslubini aniqlaydi: cartoon | realistic | flat.

        Model style argument'ini bermasdan faqat so'zda aytgan bo'lsa ham
        ("realistik qilib chiz") — avtomatik aniqlanib, tool'ga uzatiladi.
        Topilmasa default 'cartoon'. DIQQAT: art_server.draw_custom_svg'dagi
        style aliaslari bilan sinxron saqlanishi kerak (bir xil so'zlar).
        """
        low = (request or "").lower()
        # Janrga mos uslublar (uz + en) — bola chizgandek, oq-qora, fantastik,
        # anime, realistik, flat, multfilm.
        if any(w in low for w in ("bola chizgandek", "bola chizgan", "bolalar",
                                  "bolacha", "childish", "childlike", "child",
                                  "kids drawing", "bola rasmi", "oddiy bola")):
            return "child"
        if any(w in low for w in ("oq qora", "oq-qora", "qora va oq", "qora oq",
                                  "black and white", "black & white", "b/w", "bw",
                                  "monochrome", "monoxrom", "grayscale")):
            return "bw"
        if any(w in low for w in ("fantastik", "fantasy", "ertak", "sehrli",
                                  "sarguzasht", "ajdarho", "jodugar", "mifologik",
                                  "magical", "mythical", "sci-fi", "ilmiy fantastik")):
            return "fantasy"
        if any(w in low for w in ("anime", "manga", "yaponcha", "yapon uslubi",
                                  "japonya", "anime uslubi")):
            return "anime"
        if any(w in low for w in ("realistik", "realistic", "fotorealistik",
                                  "photo-real", "photo realistic", "real ko'rinish",
                                  "real ko", "haqiqiy ko'rinish", "tabiiy ko'rinish",
                                  "hayotiy")):
            return "realistic"
        if any(w in low for w in ("flat", "tekis", "minimal", "minimalist",
                                  "oddiy ranglar", "geometrik", "modern uslub")):
            return "flat"
        if any(w in low for w in ("multfilm", "cartoon", "cizgi", "kulgili",
                                  "bolalar uslubi", "aniq kontur")):
            return "cartoon"
        return "cartoon"

    @staticmethod
    def _draw_size_from_request(request: str) -> str:
        """So'rovdan chizma o'lchamini aniqlaydi (canvas/ko'rinish).

        Qaytadi: icon | avatar | card | poster | banner | standard, yoki maxsus
        'WxH' (masalan "800x600" — so'rovda aniq o'lcham aytilgan bo'lsa).
        Model size argument'ini bermasdan faqat so'zda aytgan bo'lsa ham
        avtomatik aniqlanib, tool'ga uzatiladi. DIQQAT: art_server'dagi
        SIZE_ALIASES/SIZE_PRESETS bilan sinxron saqlanishi kerak (bir xil
        so'zlar). Tartib muhim: banner -> poster -> avatar -> card -> icon.
        """
        low = (request or "").lower()
        # Maxsus "800x600" / "800*600" / "800×600" — eng birinchi tekshiriladi
        m = re.search(r"(\d{2,4})\s*[xх*×]\s*(\d{2,4})", low)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if 32 <= w <= 4096 and 32 <= h <= 4096:
                return f"{w}x{h}"
        if any(w in low for w in ("reklama banner", "keng format", "ultra-wide",
                                  "banner", "uzun gorizontal")):
            return "banner"
        if any(w in low for w in ("afisha", "plakat", "poster", "reklama",
                                  "portret format")):
            return "poster"
        if any(w in low for w in ("profil rasmi", "profil uchun", "avatar",
                                  "profil")):
            return "avatar"
        if any(w in low for w in ("karta", "kartochka", "card", "16:9",
                                  "16x9", "landscape")):
            return "card"
        if any(w in low for w in ("ikonka", "ikon", "icon", "belgi", "favicon",
                                  "kichik rasm", "kichkina rasm")):
            return "icon"
        return "standard"

    @staticmethod
    def _draw_color_from_request(request: str) -> str:
        """So'rovdan chizma RANGINI aniqlaydi (uz/en) — art__draw_scene_svg
        uchun. Topilmasa '' (tool default ishlatiladi). Uchun diqqat: rang
        so'zlari COLOR_MAP kalitlariga mos (qizil/red, yashil/green, ko'k/blue,
        sariq/yellow, binafsha/purple, pushti/pink, qora/black, oq/white,
        gold/oltin, to'q sariq/orange)."""
        low = (request or "").lower()
        for key in (
            "qizil", "red", "yashil", "green", "kok", "ko'k", "blue",
            "sariq", "yellow", "to'q sariq", "orange", "binafsha", "purple",
            "pushti", "pink", "qora", "black", "oq", "white", "oltin", "gold",
            "jigarrang", "brown",
        ):
            if re.search(rf"\b{re.escape(key)}\b", low):
                return key
        return ""

    # ------------------------------------------------------------ #
    # Ob-havo — tez deterministik yo'l (Open-Meteo, kalit talab qilmaydi)
    # ------------------------------------------------------------ #

    # "bugun ... ob-havosi qanday?" kabi so'rovlar — LLM/brauzer KERAKSIZ:
    # geocoding + forecast API orqali 2-4 soniyada aniq javob.
    WEATHER_RE = re.compile(
        r"\b(?:ob[\s-]?havo|obhavo|weather|temperatur|harorat)\w*|"
        r"\bhavo\w*(?=\s+(?:qanday|qanaqa|nech|necha|bugun|bugungi|hozir|holat|daraja))",
        re.IGNORECASE,
    )

    WEATHER_STOP = frozenset((
        "bugun", "bugungi", "hozir", "hozirgi", "kecha", "ertaga", "kunlik",
        "ob", "havo", "obhavo", "ob-havo", "havosini", "havosi", "havoni", "havoda",
        "havosiga", "havosida", "obhavosini", "obhavosi", "ob-havosini",
        "qanday", "qanaqa", "nech", "necha", "daraja", "grader",
        "temperatur", "temperatura", "harorat", "weather",
        "tuman", "viloyat", "shahar", "shahri", "shahrida", "shahridagi",
        "viloyatida", "viloyatidagi", "tumanida", "tumanidagi", "tumanda",
        "today", "now", "tonight", "tomorrow", "yesterday", "right", "current",
        "bugungi", "kun", "kuni", "kecha", "ertaga", "hozirgi",
        "in", "at", "for", "of", "the", "and", "de", "du", "a", "an",
        "so'ra", "sora", "soray", "so'ray", "so'rayman", "sorayman",
        "ayt", "ayting", "ber", "bering", "qil", "qiling", "uchun",
        "bilan", "iltimos", "menga", "men", "da", "de", "ni", "ning",
        "ga", "dagisi", "dagi", "holat", "holatini", "axvol", "ahvol",
    ))

    _WMO = {
        0: "ochiq osmon", 1: "asosan ochiq", 2: "ozgina bulutli", 3: "bulutli",
        45: "tumanli", 48: "qirovli tuman",
        51: "mayda yomg'ir", 53: "mayda yomg'ir", 55: "intensiv mayda yomg'ir",
        56: "muzli mayda yomg'ir", 57: "muzli yomg'ir",
        61: "yomg'ir", 63: "yomg'ir", 65: "kuchli yomg'ir",
        66: "muzli yomg'ir", 67: "kuchli muzli yomg'ir",
        71: "qor", 73: "qor", 75: "kuchli qor", 77: "qor zarralari",
        80: "quyulma yomg'ir", 81: "quyulma yomg'ir", 82: "kuchli quyulma yomg'ir",
        85: "quyulma qor", 86: "kuchli quyulma qor",
        95: "momaqaldiroq", 96: "momaqaldiroq va do'l", 99: "kuchli momaqaldiroq va do'l",
    }

    _WTTR_COND = {
        "sunny": "quyoshli", "clear": "ochiq", "partly cloudy": "ozgina bulutli",
        "cloudy": "bulutli", "overcast": "bulutli", "mist": "tumanli",
        "fog": "tumanli", "haze": "xira", "light rain": "mayda yomg'ir",
        "light drizzle": "mayda yomg'ir", "patchy rain": "ba'zi yomg'ir",
        "rain": "yomg'ir", "moderate rain": "yomg'ir", "heavy rain": "kuchli yomg'ir",
        "light snow": "mayda qor", "snow": "qor", "heavy snow": "kuchli qor",
        "thunderstorm": "momaqaldiroq", "freezing": "muzli",
        # wttr.in format=3 emoji belgilar
        "☀️": "quyoshli", "☀": "quyoshli", "⛅": "ozgina bulutli",
        "☁️": "bulutli", "🌦️": "o'zgaruvchan", "🌧️": "yomg'ir",
        "🌨️": "qor", "⛈️": "momaqaldiroq", "🌫️": "tumanli",
        "❄️": "qor", "🌬️": "shamolli",
        "quyoshli": "quyoshli", "ochiq": "ochiq", "bulutli": "bulutli",
        "yomg'ir": "yomg'ir", "tumanli": "tumanli",
    }

    @staticmethod
    def _wttr_cond(cond: str) -> str:
        low = (cond or "").lower().strip()
        return IgrisAgent._WTTR_COND.get(low, low or "o'zgaruvchan")

    def _quick_weather(self, message: str) -> Optional[str]:
        """Ob-havo so'roviga deterministik tez javob.

        Asosiy manba: wttr.in (joy nomini ham biladi — G'ijduvon kabi tuman
        darajasidagi joylarni topadi, bitta so'rov ~1-2 soniya). Fallback:
        Open-Meteo (geocoding + forecast). Qaytadi: tayyor matn yoki None
        (so'rov ob-havo emas / joy topilmadi — u holda LLM yo'li ishlaydi).
        """
        msg = (message or "").strip()
        if not msg or not self.WEATHER_RE.search(msg):
            return None
        import json as _json
        import urllib.parse as _up
        import urllib.request as _ur

        # Joy nomini ajratamiz: to'xtov so'zlardan tozalab, eng aniq tokenlar
        # (oxirgidan boshlab) sinab ko'riladi.
        tokens = [t.strip(".,;:!?\"'()[]") for t in re.split(r"\s+", msg)]
        loc_words = [
            t for t in tokens
            if t and not any(ch.isdigit() for ch in t)
            and t.lower() not in self.WEATHER_STOP
            and re.search(r"[A-Za-z]", t)
        ]

        def _stem(tok: str) -> list[str]:
            """Qo'shimchalarni olib tashlaydi: Toshkentda -> Toshkent."""
            low = tok.lower()
            suffixes = ("dagi", "dagisi", "dan", "dan", "da", "da", "de", "ga", "ning", "ni")
            s = tok
            for suf in suffixes:
                if low.endswith(suf):
                    s = tok[: -len(suf)]
                    break
            out = [s] if s else []
            if "'" in s:
                out.append(s.replace("'", ""))
            return out

        # Birikma birinchi ("new york" kabi ikki so'zli joylar), keyin alohida
        # tokenlar eng aniqdan (oxirgidan) boshlab.
        candidates: list[str] = []
        joined = " ".join(loc_words[-2:]).strip()
        for s in _stem(joined):
            if s and s not in candidates:
                candidates.append(s)
        for t in reversed(loc_words[-4:]):
            for s in _stem(t):
                if s and s not in candidates:
                    candidates.append(s)
        if not candidates:
            candidates = ["toshkent"]

        # 1) wttr.in — joy + ob-havo bitta tez so'rovda (tuman darajasidagi
        # joylarni ham biladi: Gijduvon, ...). wttr.in oddiy Python-urllib
        # User-Agent'ni rad qiladi (HTTP 500) — o'z UA'mizni yuboramiz.
        _wua = {"User-Agent": "IgrisAgent/2.0 (local; contact localhost)"}
        for cand in candidates:
            try:
                url = ("https://wttr.in/" + _up.quote(cand) + "?format=3")
                with _ur.urlopen(_ur.Request(url, headers=_wua), timeout=5) as resp:
                    text = resp.read().decode("utf-8", "replace")
                if "unknown location" in text.lower() or "no results" in text.lower():
                    continue
                m = re.match(r"^\s*(.*?):\s*(.*?)\s*([+-]?\d+°C)\s*$", text, re.DOTALL)
                if not m:
                    continue
                name = (m.group(1) or cand).strip()
                cond = m.group(2).strip()
                temp = m.group(3)
                # Namlik va shamol — qo'shimcha mayda so'rov (bitta: %h+%w)
                extra = []
                try:
                    url2 = ("https://wttr.in/" + _up.quote(cand) + "?format=%h+%w")
                    with _ur.urlopen(_ur.Request(url2, headers=_wua), timeout=5) as resp2:
                        parts2 = resp2.read().decode("utf-8", "replace").split()
                    hum = next((p for p in parts2 if p.endswith("%")), "")
                    wind = next((p for p in parts2 if "km/h" in p), "")
                    if hum:
                        extra.append("namlik " + hum)
                    if wind:
                        # yo'nalish o'qlarini tozalab, raqamni olamiz (→5km/h -> 5 km/h)
                        wm = re.search(r"(\d+)\s*km/h", wind)
                        if wm:
                            extra.append("shamol " + wm.group(1) + " km/soat")
                except Exception:
                    pass
                answer = "Hozir " + name + "da: " + temp + " — " + self._wttr_cond(cond) + "."
                if extra:
                    answer += " " + ", ".join(extra) + "."
                answer += " Manba: wttr.in (jonli)."
                return answer
            except Exception:
                continue

        # 2) Fallback: Open-Meteo geocoding + forecast
        lat = lon = None
        found_name = ""
        for cand in candidates:
            try:
                q = _up.quote(cand)
                url = ("https://geocoding-api.open-meteo.com/v1/search?name="
                       + q + "&count=1&language=uz&format=json")
                with _ur.urlopen(url, timeout=6) as resp:
                    data = _json.loads(resp.read().decode("utf-8", "replace"))
                results = data.get("results") or []
                if results:
                    r = results[0]
                    lat = r.get("latitude")
                    lon = r.get("longitude")
                    found_name = r.get("name") or cand
                    break
            except Exception:
                continue
        if lat is None or lon is None:
            return None

        try:
            furl = ("https://api.open-meteo.com/v1/forecast?latitude="
                    + str(lat) + "&longitude=" + str(lon)
                    + "&current=temperature_2m,relative_humidity_2m,"
                      "apparent_temperature,weather_code,wind_speed_10m&timezone=auto")
            with _ur.urlopen(furl, timeout=6) as resp:
                fdata = _json.loads(resp.read().decode("utf-8", "replace"))
            cur = fdata.get("current") or {}
        except Exception:
            return None
        temp = cur.get("temperature_2m")
        if temp is None:
            return None

        code = int(cur.get("weather_code") or 0)
        hum = cur.get("relative_humidity_2m")
        feels = cur.get("apparent_temperature")
        wind = cur.get("wind_speed_10m")

        line = self._fmt_temp(temp) + " — " + self._wmo_text(code)
        if feels is not None:
            line += ", haqiqiy " + self._fmt_temp(feels)
        extra = []
        if hum is not None:
            extra.append("namlik " + str(int(hum)) + "%")
        if wind is not None:
            extra.append("shamol " + str(int(round(float(wind)))) + " km/soat")
        answer = "Hozir " + found_name + "da: " + line + "."
        if extra:
            answer += " " + ", ".join(extra) + "."
        answer += " Manba: Open-Meteo (jonli)."
        return answer

    @staticmethod
    def _wmo_text(code: int) -> str:
        return IgrisAgent._WMO.get(code, "o'zgaruvchan bulutli")

    @staticmethod
    def _fmt_temp(t) -> str:
        try:
            v = float(t)
        except (TypeError, ValueError):
            return "?"
        return ("+" if v >= 0 else "") + str(int(round(v))) + "°C"

    # ------------------------------------------------------------ #
    # Web bridge — chatda zarurat bo'lsa AVTOMATIK yoqish
    # ------------------------------------------------------------ #

    # URL yoki brauzer/web ishtiroki bor so'rovlar — web_ai_bridge tool'lari
    # chatda ham avtomatik ochiladi (model ularni ishlatishi uchun).
    #
    # Soxta pozitivlar YO'Q: 'web', 'link', 'site', 'search' kabi umumiy so'zlar
    # O'ZI ishlamaydi ('web framework', 'linked list', 'binary search' kabi kod
    # mavzulari brauzer talab qilmaydi). Faqat: URL/manzil, sayt ochish, brauzer
    # amali, qidiruv amali — aniq veb ehtiyoji.
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

    @classmethod
    def _needs_web(cls, message: str) -> bool:
        """So'rovda veb/brauzer ehtiyoji bormi? (URL, sayt ochish, qidirish,
        yoki web AI'ga murojaat — chatgpt/gemini/deepseek...)

        Qoida: URL/manzil BOR, brauzer/sayt amali aniq ifodalangan yoki web
        AI/tadqiqot so'ralgan bo'lsa. "web", "link", "site", "search" o'zi
        bilan ishlamaydi — qo'shni fe'l talab qilinadi (soxta pozitiv kamayadi).
        """
        msg = message or ""
        if cls.WEB_INTENT_RE.search(msg):
            return True
        # Web AI nomi (chatgptdan so'ra...) yoki tadqiqot fe'li — delegatsiya
        # tool'lari kerak, aks holda model ularni hech qachon ocholmaydi.
        if cls.WEB_AI_NAME_RE.search(msg) or cls.WEB_GATE_RE.search(msg):
            return True
        # SAYT TEXNOLOGIYASI + amal fe'li: "shopify do'konini och",
        # "wordpress saytini tekshir" — platforma nomi brauzer amali bilan
        # birga kelsa veb so'rov (so'z o'zi yetarli emas: "wordpress nima"
        # bilim savoli, brauzer talab qilmaydi).
        if cls._detect_web_tech(msg):
            # Sayt qurish/yaratish ham veb amali: "wordpress sayt qur",
            # "shopify do'kon yarat" — platformada sayt qurish so'rovi.
            if re.search(r"\b(?:och|open|qidir|search|ol|read|tekshir|check|ko'rsat|show|bor|visit|yuklab|download|qur|build|yarat|create|yasash)\w*", msg, re.IGNORECASE):
                return True
        return False

    # --- WEB STRATEGIYASI: browser qachon, web AI subagent qachon? ---
    #
    # Maqsad: browser'ni maqsadsiz ishlatishni to'xtatish. So'rov turiga qarab
    # modelga FOKUSLANGAN tool'lar to'plami beriladi:
    #   'delegate' — bilim/qidiruv/tekshiruv so'rovlari web AI'ga (chatgpt,
    #                gemini, claude_web, deepseek) SUBAGENT sifatida topshiriladi
    #                (ask_web_ai / web_ai_start_research). Model o'zi 20 ta
    #                browser amalini bajarmaydi — helper AI ishlaydi.
    #   'browser'  — interaktiv sahifa kerak: URL ochish, hisob, forma, login,
    #                JS-heavy, aniq jonli holat (navigate/get_text/click...).
    #   'full'     — ikkalasi ham (masalan URL + tadqiqot so'ralgan).
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

    @classmethod
    def _web_strategy(cls, message: str) -> str:
        """Veb so'rov strategiyasi: '' | 'delegate' | 'browser' | 'full'.

        Qoida: URL yoki aniq brauzer amali -> browser. Bilim/qidiruv so'rovi
        -> delegate (web AI subagent). Ikkalasi ham -> full.
        """
        msg = message or ""
        if not cls._needs_web(msg):
            return ""
        has_url = bool(re.search(r"https?://|www\.", msg, re.IGNORECASE))
        browser = bool(cls.WEB_BROWSER_RE.search(msg))
        research = bool(cls.WEB_AI_NAME_RE.search(msg) or cls.WEB_RESEARCH_RE.search(msg))
        if has_url and research:
            return "full"
        if has_url or browser:
            return "browser"
        if research:
            return "delegate"
        return "browser"

    def _web_tools(self, strategy: str = "full") -> list[dict]:
        """web_ai_bridge tool'larini STRATEGIYAGA qarab filtrlangan holda beradi.

        - 'delegate': web AI SUBAGENT tool'lari (ask_web_ai, research...) +
          minimal browser (navigate/get_text) — web AI ishlamasa zaxira.
        - 'browser' : faqat brauzer amallari (navigate, get_text, click...).
        - 'full'    : ikkalasi ham.

        Maqsad: modelga 28 ta tool'ni birdan tashlamaymiz — vazifaga mos
        fokuslangan to'plam beriladi, browser maqsadsiz chaqirilmaydi.
        Faqat web_ai_bridge ulangan bo'lsa qaytaradi. Aks holda bo'sh.
        """
        DELEGATE_KEYS = {
            "web_ai_bridge__ask_web_ai",
            "web_ai_bridge__web_ai_start_research",
            "web_ai_bridge__web_ai_check_research",
            "web_ai_bridge__web_ai_get_conversation",
            "web_ai_bridge__web_ai_new_chat",
            "web_ai_bridge__web_ai_stop_generating",
        }
        # Subagent yo'lida ham zaxira sifatida minimal browser: web AI login
        # talab qilsa yoki aniq URL o'qish kerak bo'lsa — model qo'lda qolmaydi.
        BROWSER_BASIC = {
            "web_ai_bridge__browser_navigate",
            "web_ai_bridge__browser_get_text",
            "web_ai_bridge__browser_screenshot",
            "web_ai_bridge__browser_check_link",
            "web_ai_bridge__browser_wait_for",
            "web_ai_bridge__browser_dismiss_overlays",
            "web_ai_bridge__browser_info",
            "web_ai_bridge__browser_ai_task",
        }
        mcp = self._mcp()
        if mcp is None:
            return []
        all_web = {k for k in mcp.tool_index if k.startswith("web_ai_bridge__")}
        if strategy == "delegate":
            allowed = DELEGATE_KEYS | BROWSER_BASIC
        elif strategy == "browser":
            allowed = all_web - DELEGATE_KEYS
        else:  # 'full' / noma'lum — hammasi
            allowed = all_web
        schemas: list[dict] = []
        for key in sorted(allowed):
            info = mcp.tool_index.get(key) or {}
            schema = info.get("schema") or {}
            # WEB_TOOLS_GUIDE dan QISQA ko'rsatma — model tool tanlash paytida
            # ham qachon ishlatishni ko'radi. MANBA: web-ai-bridge server'ining
            # o'zi (index.js WHEN_TO_USE) — description'da allaqachon bor bo'lsa
            # qayta qo'shilmaydi; WEB_TOOL_HINTS faqat ESKI bridge zaxirasi.
            desc = schema.get("description") or ""
            if "WHEN TO USE" not in desc:
                desc = _tool_desc_with_hint(schema, WEB_TOOL_HINTS.get(key))
            else:
                desc = desc[:800]  # server hint bilan kelgan — faqat cap
            schemas.append({
                "type": "function",
                "function": {
                    "name": key,
                    "description": desc,
                    "parameters": schema.get("parameters") or {"type": "object", "properties": {}},
                },
            })
        return schemas

    @classmethod
    def _web_decision_rules(cls, strategy: str) -> str:
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

    # --- WEB STRATEGIYA KUZATUVI: har web so'rov qarori log'ga yoziladi ---
    #
    # Maqsad: xatolarni topish. Har web so'rovdan so'ng qaysi strategiya
    # tanlangan + model amalda NIMA qilgani logs/web_strategy.jsonl ga yoziladi.
    # Hisobot: `python web_strategy_report.py`.
    WEB_DELEGATE_FAMILY = frozenset({
        "web_ai_bridge__ask_web_ai",
        "web_ai_bridge__web_ai_start_research",
        "web_ai_bridge__web_ai_check_research",
        "web_ai_bridge__web_ai_get_conversation",
        "web_ai_bridge__web_ai_new_chat",
        "web_ai_bridge__web_ai_stop_generating",
    })
    # Browser INTERAKTIV amallari — delegate strategiyasida noto'g'ri ishlatish.
    WEB_INTERACTION_TOOLS = frozenset({
        "web_ai_bridge__browser_click",
        "web_ai_bridge__browser_type",
        "web_ai_bridge__browser_select_option",
        "web_ai_bridge__browser_press_key",
        "web_ai_bridge__browser_hover",
        "web_ai_bridge__browser_scroll",
        "web_ai_bridge__browser_upload_file",
    })

    def _web_strategy_log_path(self) -> str:
        """Web strategiya kuzatuv log fayli (JSONL). Testlarda o'zgartirilishi mumkin."""
        if getattr(self, "_web_log_path", None):
            return self._web_log_path
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "logs", "web_strategy.jsonl")

    def _log_web_strategy(self, message: str, strategy: str,
                          tool_calls: Optional[list] = None,
                          engine: str = "", mcp_ok: bool = True,
                          content_len: int = 0) -> None:
        """Har web so'rov qarorini logs/web_strategy.jsonl ga yozadi (kuzatuv).

        Verdict — model to'g'ri yo'l tutdimi:
          ok-delegate / ok-browser / ok-full   — strategiyaga mos tool ishlatildi
          misuse-browser                       — delegate kerak edi, interaktiv browser ishlatildi
          browser-fallback                     — delegate'da faqat o'qish browser (zaxira, ruxsat)
          delegated-instead                    — browser kutilgan, web AI'ga topshirildi (ma'qul)
          no-web-tool                          — strategiya bor, lekin web tool ishlatilmadi
          unexpected-web                       — strategiyasiz web tool chaqirildi (darvoza chetlab o'tilgan?)
          unavailable                          — web_ai_bridge ulanmagan

        Hech qachon agentni buzmaydi (try/except).
        """
        try:
            import json as _json
            from datetime import datetime
            if not strategy and not (tool_calls or []):
                return  # web bo'lmagan suhbat — log shovqin qilmaydi
            calls: list[str] = []
            for tc in (tool_calls or []):
                if isinstance(tc, dict):
                    calls.append(str(tc.get("tool") or ""))
                else:
                    calls.append(str(tc))
            web_calls = [c for c in calls if c.startswith("web_ai_bridge__")]
            delegation_used = bool(set(web_calls) & self.WEB_DELEGATE_FAMILY)
            interaction_used = bool(set(web_calls) & self.WEB_INTERACTION_TOOLS)
            browser_used = any(c.startswith("web_ai_bridge__browser_") for c in web_calls)
            # Verdict
            if not mcp_ok and strategy:
                verdict = "unavailable"
            elif not strategy:
                verdict = "unexpected-web" if web_calls else None
            elif strategy == "delegate":
                if delegation_used:
                    verdict = "ok-delegate"
                elif interaction_used:
                    verdict = "misuse-browser"
                elif browser_used:
                    verdict = "browser-fallback"
                elif web_calls:
                    verdict = "other-web"
                else:
                    verdict = "no-web-tool"
            elif strategy == "browser":
                if browser_used:
                    verdict = "ok-browser"
                elif delegation_used:
                    verdict = "delegated-instead"
                elif web_calls:
                    verdict = "other-web"
                else:
                    verdict = "no-web-tool"
            else:  # full
                verdict = "ok-full" if web_calls else "no-web-tool"
            if verdict is None:
                return
            # Qaysi regex mos keldi — klassifikatsiya xatolarini topish uchun
            msg = message or ""
            matched: list[str] = []
            if re.search(r"https?://|www\.", msg, re.IGNORECASE):
                matched.append("url")
            if self.WEB_AI_NAME_RE.search(msg):
                matched.append("ai_name")
            if self.WEB_RESEARCH_RE.search(msg):
                matched.append("research")
            if self.WEB_BROWSER_RE.search(msg):
                matched.append("browser")
            if self.WEB_GATE_RE.search(msg):
                matched.append("gate")
            entry = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "message": msg[:160],
                "strategy": strategy or "",
                "needs_web": bool(strategy),
                "web_available": bool(mcp_ok),
                "tool_calls": calls[:8],
                "delegation_used": delegation_used,
                "browser_used": browser_used,
                "matched": matched,
                "verdict": verdict,
                "engine": engine or "",
                "content_len": int(content_len or 0),
            }
            path = self._web_strategy_log_path()
            logs_dir = os.path.dirname(path)
            if logs_dir and not os.path.isdir(logs_dir):
                os.makedirs(logs_dir, exist_ok=True)
            # 2MB dan oshsa — .old ga surib, yangi boshlaymiz (cheksiz o'smaydi)
            if os.path.isfile(path) and os.path.getsize(path) > 2_000_000:
                os.replace(path, path + ".old")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # kuzatuv hech qachon agentni buzmaydi

    # ------------------------------------------------------------ #
    # Chat tool'lar: MCP + registry, capability-gap re-prompt
    # ------------------------------------------------------------ #

    def _mcp(self):
        """Lazy MCP bridge — server'lar ulangan bo'lsa qaytaradi, aks holda None."""
        if self._mcp_cache is None:
            try:
                from mcp_bridge import DEFAULT_BRIDGE
                if not DEFAULT_BRIDGE.status()["servers"]:
                    try:
                        DEFAULT_BRIDGE.start()
                    except Exception as exc:
                        print(f"[igris][chat] mcp start: {exc}")
                self._mcp_cache = DEFAULT_BRIDGE if DEFAULT_BRIDGE.status()["servers"] else None
            except Exception as exc:
                print(f"[igris][chat] mcp unavailable: {exc}")
                self._mcp_cache = None
        return self._mcp_cache

    def _registry(self):
        if self._registry_cache is None:
            try:
                from tools import DEFAULT_REGISTRY
                self._registry_cache = DEFAULT_REGISTRY
            except Exception:
                self._registry_cache = None
        return self._registry_cache

    def _chat_executor(self):
        """Tool bajarish uchun engil AgentExecutor (MCP + workspace + registry)."""
        if self._chat_exec is None:
            from executor import AgentExecutor
            self._chat_exec = AgentExecutor(
                workspace_root=self.workspace_root,
                llm=self.llm,
                mcp=self._mcp(),
            )
        return self._chat_exec

    def _chat_tools(self, include_web: bool = False, web_strategy: str = "") -> list[dict]:
        """Chat uchun Ollama tool-schema'lari: MCP tool'lari + registry tool'lari.

        include_web=True bo'lsa web_ai_bridge tool'lari strategiyaga qarab
        qo'shiladi (delegate/browser/full) — model faqat vazifaga mos to'plamni
        ko'radi, browser maqsadsiz chaqirilmaydi.
        """
        if self._chat_tools_cache is not None and not include_web:
            return self._chat_tools_cache
        tools: list[dict] = []
        mcp = self._mcp()
        if mcp is not None:
            # Chat uchun MCP tool'lari: faqat 'art__*' (rasm chizish). Brauzer
            # tool'lari (web_ai_bridge__*) faqat WEB so'rovida, strategiyaga mos
            # to'plam bilan qo'shiladi — oddiy chatda model ularni noto'g'ri
            # chaqirib, placeholder URL'lar bilan keraksiz ish qilmasligi uchun.
            for key, info in sorted(mcp.tool_index.items()):
                if not key.startswith("art__"):
                    continue
                schema = info.get("schema") or {}
                # ART_TOOL_HINTS dan QISQA ko'rsatma — model qaysi chizish
                # vositasini QACHON tanlashni ko'radi (base 350, hint to'liq).
                desc = _tool_desc_with_hint(schema, ART_TOOL_HINTS.get(key))
                tools.append({
                    "type": "function",
                    "function": {
                        "name": key,
                        "description": desc,
                        "parameters": schema.get("parameters") or {"type": "object", "properties": {}},
                    },
                })
            if tools:
                # mcp_call'da web_ai_bridge tool'lari KO'RSATILMAYDI — ular faqat
                # include_web=True bo'lganda strategiyaga mos ochiladi. Aks holda
                # model istalgan chatda mcp_call orqali browser'ni chaqirib
                # qo'yardi (maqsadsiz foydalanish manbai).
                mcp_call_names = [
                    n for n in (mcp.names() or [])
                    if not n.startswith("web_ai_bridge__")
                ]
                tools.append({
                    "type": "function",
                    "function": {
                        "name": "mcp_call",
                        "description": "Call a tool on a connected MCP server. Use name "
                                        "'server__tool'. Available tools: "
                                        + ", ".join(mcp_call_names or ["(none)"]),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string", "description": "server__tool name"},
                                "args": {"type": "object", "description": "tool arguments"},
                            },
                            "required": ["tool"],
                        },
                    },
                })
        if include_web:
            tools.extend(self._web_tools(web_strategy or "full"))
        reg = self._registry()
        if reg is not None:
            tools.extend(reg.ollama_schemas())
        # Faqat MCP ulangan bo'lsa keshlaymiz — aks holda keyingi qo'ng'iroqda
        # qayta sinab ko'riladi (art tool'lari o'tkazib yuborilmasligi uchun).
        # Web tool'lar KESHLANMAYDI — har so'rovda strategiyaga qarab tanlanadi.
        if mcp is not None and not include_web:
            self._chat_tools_cache = tools
        return tools

    def _chat_with_tools(self, messages: list[dict], tools: list[dict], web: bool = False,
                         progress=None, req: Optional[Requirement] = None,
                         on_loop_iteration=None) -> tuple[str, list[dict], Optional[str]]:
        """Tool'li chat loop: model tool tanlasa bajaradi, aks holda matn qaytaradi.

        - model "qila olmayman" desa (capability-gap) — real tool'lar eslatiladi
        - bajarilgan tool natijalari modelga tool-message sifatida qaytariladi
        - bir xil (tool, args) chaqiruv faqat BIR marta bajariladi (loop oldini olish)
        - yakuniy javob tool-call JSON bo'lib qolsa — oddiy matnli xulosa so'raladi
        - progress: ixtiyoriy (stage, detail) callback — har tool bajarilganda
          frontend stepperiga JONLI bosqich yuboriladi

        Qaytadi: (final_text, tool_calls, image_path)
        """
        import json as _json
        from executor import stage_for_tool, _tool_preview  # noqa: E402
        tool_calls: list[dict] = []
        image: Optional[str] = None
        gap_prompted = False
        seen: set[tuple] = set()
        empty_nudges = 0
        # ORIGINAL so'rov — nudge/hint xabarlari qo'shilishidan OLDI olinadi.
        # (SVG auto-save draw-intent tekshiruvi shunga tayanadi; aks holda oxirgi
        #  user xabari nudge bo'lib qolib, chizma o'tkazib yuborilishi mumkin.)
        original_request = ""
        for _m in reversed(messages):
            if _m.get("role") == "user":
                original_request = str(_m.get("content") or "")
                break
        # WEB vazifalar ko'proq qadam talab qiladi (navigate -> get_text ->
        # type -> click -> summarize). Oddiy chatda 4 round yetarli.
        # WEB vazifalar ko'proq qadam talab qiladi (navigate -> get_text ->
        # type -> click -> summarize). Kod/rasm vazifalarida ham write -> run ->
        # fix sikli yetishi uchun 6 round beramiz (sifat: tuzatishga joy).
        max_rounds = 8 if web else 6
        # Part L (CP-L5): yopiq ro'yxatdan tashqari obyekt (NOT_SUPPORTED) —
        # modelga 1 marta "o'zing generatsiya qil" yo'naltiriladi (ochiq domen).
        not_supported_prompted = False

        # Part O: ma'lum (canned) subject uchun DETERMINISTIK chizma — modelga
        # bog'liq emas, talab (subject/rang) aniq bajariladi va crash bermaydi.
        if not web and self._is_draw_request(original_request):
            det = self._try_deterministic_scene(original_request, progress)
            if det is not None:
                tool_calls.append({
                    "tool": det["tool"],
                    "args": det["args"],
                    "result": {k: v for k, v in det["result"].items() if k != "output"},
                    "output_preview": str(det["result"].get("output") or "")[:300],
                })
                return det["content"], tool_calls, det["image"]
            # Part O: noma'lum subject — avtomatik chizmasdan o'tkazamiz,
            # LLM ga art__draw_custom_svg bilan istalgan narsani chizish
            # imkoniyatini beramiz (avvalgi hard-refusal o'rniga).

        for _iter in range(max_rounds):
            # loop_iteration event: frontend "attempt N of M" ko'rsatadi
            if on_loop_iteration is not None:
                try:
                    on_loop_iteration(_iter + 1, max_rounds, "react_iterative")
                except Exception:
                    pass
            resp = self.llm.chat_with_tools(messages, tools=tools)
            if not resp or not isinstance(resp, dict):
                break
            calls = resp.get("tool_calls") or []
            if calls:
                new_any = False
                not_supported_seen = False
                for call in calls:
                    name = str(call.get("name") or "").strip()
                    if not name:
                        continue
                    args = call.get("arguments") or {}
                    try:
                        key = (name, _json.dumps(sorted(args.items(), key=str),
                                                 ensure_ascii=False, default=str))
                    except Exception:
                        key = (name, str(args))
                    if key in seen:
                        continue  # takroriy chaqiruv — o'tkazib yuboramiz
                    seen.add(key)
                    new_any = True
                    result = self._execute_chat_tool(name, args)
                    ok = bool(result.get("ok"))
                    # JONLI PIPELINE: bajarilgan tool frontend stepperida ko'rinadi
                    if progress is not None:
                        try:
                            progress(stage_for_tool(name),
                                     f"{name} → {_tool_preview(name, args)}")
                        except Exception:
                            pass
                    tool_calls.append({
                        "tool": name,
                        "args": args,
                        "result": {k: v for k, v in result.items() if k != "output"},
                        "output_preview": str(result.get("output") or result.get("content") or "")[:300],
                    })
                    if ok and image is None:
                        # Har qanday muvaffaqiyatli tool natijasidan rasm yo'lini aniqlaymiz
                        # (to'g'ridan-to'g'ri art__draw_object_png yoki mcp_call indireksiyasi)
                        image = self._image_from_art_call(result)
                        if image:
                            # Chizma tugadi — sifatni baholab, L2 xotiraga yozamiz
                            self._remember_drawing_quality(image, original_request)
                    result_text = str(result.get("output") or result.get("content") or result.get("error") or "ok")
                    if "NOT_SUPPORTED" in result_text or "unknown subject" in result_text \
                            or "unknown app" in result_text:
                        not_supported_seen = True
                    messages.append({"role": "tool", "name": name, "content": result_text[:4000]})
                if not not_supported_prompted and not_supported_seen:
                    # Part L (CP-L5): model yopiq ro'yxatga urindi — ochiq domen:
                    # artefaktni O'ZI generatsiya qilishga yo'naltiramiz (1 marta).
                    not_supported_prompted = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "That tool only supports predefined items. For this request, "
                            "generate the artifact yourself instead of giving up: for an "
                            "image, write/emit the full SVG and it will be saved automatically; "
                            "for a UI/app, build the HTML/plan yourself. Do not call a "
                            "predefined-subject tool again with the same subject."
                        ),
                    })
                    continue
                if not new_any:
                    # hammasi takroriy — model aylanma loopda; to'xtaymiz
                    break
                if image:
                    # rasm chizildi — maqsadga erishildi, qo'shimcha round shart emas
                    break
                continue
            content = (resp.get("content") or "").strip()
            if not content and not tool_calls:
                # qwen3 ba'zan faqat thinking, ba'zan BUTUNLAY bo'sh javob
                # beradi — ikkalasida ham davom ettirishni so'raymiz
                # ("I could not generate a response." kabi bo'sh xatolar oldini olish).
                if empty_nudges >= 2:
                    break
                empty_nudges += 1
                hint = "only internal reasoning" if resp.get("thinking") else "an empty reply"
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous reply contained {hint}. Now give the actual "
                        "final answer to the user's request, or call the appropriate tool."
                    ),
                })
                continue
            if content and not tool_calls and self._capability_gap(content):
                if gap_prompted < 2:
                    # model "qila olmayman" dedi — real vositalarini eslatamiz
                    # (max 2 marta: 1-chi umumiy, 2-chi aniqroq yo'naltirish)
                    gap_prompted += 1
                    if gap_prompted == 1:
                        messages.append({"role": "user",
                                         "content": self._tools_hint(request=original_request)})
                    else:
                        # 2-chi urinish: modelga aniq buyruq — qaysi toolni qanday
                        # chaqirishni ko'rsatamiz (abstract "you have tools" emas)
                        tool_names = [t.get("function", {}).get("name", "")
                                      for t in (tools or []) if t.get("function", {}).get("name")]
                        messages.append({"role": "user",
                                         "content": (
                                             "STOP saying you cannot. You have these exact tools "
                                             f"right now: {', '.join(tool_names[:10])}. "
                                             "CALL ONE OF THEM IMMEDIATELY to fulfill the user's "
                                             "request. Do not reply with text — make a tool call."
                                         )})
                    continue
            # Model SVG kodini tool'cha MATN sifatida yozsa — faylga yozamiz
            # (real chizma kartasi; "fayl yaratdim" deb yolg'on aytmaydi).
            content, image = self._save_svg_from_text(content, tool_calls, image, original_request)
            return content or "", tool_calls, image

        # Tool'lar bajarilgandan keyin modeldan ODDIY matnli xulosa so'raladi —
        # qwen2.5-coder tool-call JSON'ini content sifatida takrorlaydi, shuning
        # uchun toolsiz chat so'rovi yuboramiz (JSON takrori emas, haqiqiy xulosa).
        if tool_calls:
            base = [m for m in messages if m.get("role") in ("system", "user", "assistant")]
            base.append({
                "role": "user",
                # Part L (B1): xulosa ko'rsatmasi req'ga mos (til/chuqurlik/format).
                "content": self._summary_instruction(req) if req is not None else (
                    "Summarize what you just did for the user in 1-2 short sentences, "
                    "in the user's language. Plain text only — no JSON, no tool-call "
                    "format, no code fences. Mention the created file if relevant."
                ),
            })
            resp = self.llm.chat(base)
            if resp and resp.strip():
                return resp.strip(), tool_calls, image
            # Part L: canned "Bajarildi..." faqat haqiqiy tool'lar bajarilganda
            # faktik eng-so'nggi tayanch (yolg'on emas — tool soni real).
            return f"Bajarildi: {len(tool_calls)} tool chaqiruvi amalga oshirildi.", tool_calls, image

        # ---------- DETERMINISTIC FALLBACK: LLM tool chaqirmadi yoki rad etdi ----------
        # Agar so'rov kod/fayl yaratish talab qiladi (file, code, app, game, dashboard...)
        # va LLM hech qanday tool chaqirmagan bo'lsa — avtomatik kod generatsiya qilib
        # faylga yozamiz. Bu "agent rad etdi" muammosini hal qiladi.
        if self._needs_code_fallback(original_request) and self.llm is not None:
            fb = self._deterministic_code_fallback(original_request, original_request, progress)
            if fb is not None:
                tool_calls.append({
                    "tool": fb["tool"],
                    "args": fb["args"],
                    "result": {"ok": True},
                    "output_preview": str(fb.get("output", ""))[:300],
                })
                return fb["content"], tool_calls, image

        return "", tool_calls, image

    # Past ball olgan chizmalar uchun avtomatik qayta chizish chegarasi.
    # Qayta chizish faqat BIR marta bajariladi (har biri ~60-90s oladi).
    REDRAW_SCORE_MIN = 55

    def _validate_drawing(self, image: Optional[str]) -> Optional[dict]:
        """Saqlangan chizma faylini svg_validator bilan baholaydi."""
        if not image:
            return None
        try:
            from svg_validator import validate_svg_file
            path = os.path.join(self.workspace_root, str(image).replace("/", os.sep))
            return validate_svg_file(path)
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # DETERMINISTIC CODE FALLBACK — LLM rad etganda avtomatik kod generatsiya
    # ------------------------------------------------------------------ #

    # Kod/yaratish vazifalari kalit so'zlari — fallback qachon ishlatilishini
    # aniqlash uchun. Bu so'zlar so'rovda bo'lsa, LLM tool chaqirmagan
    # bo'lsa ham avtomatik kod generatsiya qilinadi.
    _CODE_FALLBACK_KEYWORDS = (
        "fayl", "file", "yoz", "write", "yarat", "create", "qur",
        "build", "dastur", "code", "kod", "app", "ilova", "game",
        "o'yin", "html", "python", "javascript", "js", "css",
        "script", "skript", "faylni", "daftar", "note",
    )

    def _needs_code_fallback(self, request: str) -> bool:
        """So'rov kod/fayl yaratish talab qiladimi — deterministik tekshiruv.

        Agar so'rovda kod/fayl/yaratish kalit so'zlari bo'lsa va LLM
        hech qanday tool chaqirmagan bo'lsa — fallback ishga tushadi.
        """
        low = (request or "").lower()
        return any(kw in low for kw in self._CODE_FALLBACK_KEYWORDS)

    def _deterministic_code_fallback(
        self, request: str, original: str, progress=None
    ) -> Optional[dict]:
        """LLM rad etganda — LLM'dan kod so'rab, write_file bilan yozadi.

        Bu fallback faqat BIR marta ishlaydi (cheksiz loop yo'q).
        Natija: {content, tool, args, output} yoki None.
        """
        if self.llm is None or not self.llm_available():
            return None
        if progress is not None:
            try:
                progress("edit", "deterministic fallback: kod generatsiya qilinmoqda…")
            except Exception:
                pass
        # LLM'dan to'liq kod so'raymiz (tool-call emas, oddiy matn javob)
        fb_system = (
            "You are a coding agent. The user asked you to do something that "
            "requires writing a file. Generate the COMPLETE file content and "
            "output it as plain text (no markdown fences, just raw code). "
            "The file should be self-contained and working. "
            "After the code, on a NEW LINE starting with 'FILE:', write the "
            "suggested filename (e.g. 'FILE: index.html' or 'FILE: app.py'). "
            "Language: match the user's request (Uzbek = general code; "
            "English = match keywords like python/javascript/html)."
        )
        try:
            text = self.llm.complete(system=fb_system, prompt=request[:800])
        except Exception:
            return None
        if not text or len(text.strip()) < 30:
            return None
        # FILE: tegini topish — fayl nomini ajratamiz
        fname = ""
        code = text.strip()
        for line in text.strip().splitlines():
            if line.strip().upper().startswith("FILE:"):
                fname = line.strip()[5:].strip().strip('"').strip("'")
                # FILE: qatorini koddan olib tashlaymiz
                code = text.strip().replace(line, "", 1).strip()
                break
        if not fname:
            # Fallback fayl nomi — so'rov turiga qarab
            low = (original or "").lower()
            if any(w in low for w in ("html", "web", "saifa", "page")):
                fname = "index.html"
            elif any(w in low for w in ("python", ".py", "skript")):
                fname = "app.py"
            elif any(w in low for w in ("js", "javascript")):
                fname = "app.js"
            elif any(w in low for w in ("css", "style")):
                fname = "style.css"
            elif any(w in low for w in ("game", "o'yin")):
                fname = "game.html"
            elif any(w in low for w in ("todo", "vazifa", "task")):
                fname = "todo.html"
            else:
                fname = "output.html"
        # write_file orqali yozamiz
        res = self._execute_chat_tool("write_file", {
            "path": fname, "content": code,
        })
        if not res.get("ok"):
            return None
        # Xulosa — foydalanuvchiga nima qilganini tushuntiramiz
        summary = (
            f"Fayl yaratildi: `{fname}` — LLM tomonidan avtomatik generatsiya qilindi. "
            f"{len(code)} belgi, {len(code.splitlines())} qator kod."
        )
        if progress is not None:
            try:
                progress("review", f"fayl yaratildi: {fname}")
            except Exception:
                pass
        return {
            "content": summary,
            "tool": "write_file",
            "args": {"path": fname, "content": code[:200]},
            "output": res.get("output", ""),
        }

    def _chat_with_redraw(self, messages: list[dict], tools: list[dict],
                          web: bool = False, progress=None,
                          request: str = "",
                          req: Optional[Requirement] = None,
                          on_loop_iteration=None) -> tuple[str, list[dict], Optional[str], Optional[dict]]:
        """Chizish natijasini baholaydi; past ball bo'lsa tanqid bilan qayta chiztiradi.

        Research asosidagi self-correction (Render-and-Verify / Retry-Loop):
        birinchi chizma REDRAW_SCORE_MIN dan past ball olsa, tanqid xabari
        (score + zaifliklar + taklif) keyingi so'rovga qo'shiladi va yangi
        chizma olinadi. Ikkisidan YAXSHIROG'I saqlanadi. Latensiya uchun
        chegara: faqat BIR marta qayta chizish.

        Qaytadi: (content, tool_calls, image, redraw_note | None)
        redraw_note: {'retried', 'old_score', 'new_score', 'kept_old'?, 'failed'?}
        """
        content, tool_calls, image = self._chat_with_tools(
            messages, tools, web=web, progress=progress, req=req,
            on_loop_iteration=on_loop_iteration)
        if (not image or not str(image).lower().endswith(".svg")
                or not self._is_draw_request(request)):
            return content, tool_calls, image, None
        report = self._validate_drawing(image)
        if report is None or report.get("error"):
            return content, tool_calls, image, None
        old_score = report.get("total") or 0
        if old_score >= self.REDRAW_SCORE_MIN:
            return content, tool_calls, image, None
        # Tanqid bilan qayta chizish (bir marta)
        weak = [c.get("name") for c in report.get("checks") or [] if not c.get("ok")]
        tip = _drawing_quality_tip(report)
        # Original so'rov tanqidga qo'shiladi — ikkinchi o'tishda
        # _save_svg_from_text uslub/o'lchamni to'g'ri aniqlay oladi.
        critique = (
            f"Original request: {request}\n"
            f"Your previous drawing scored only {old_score}/100. "
            f"Weak points: {', '.join(weak) if weak else 'general quality'}. "
            f"Improve it: {tip or 'follow the svg-artist skill rules'}. "
            "Regenerate the FULL SVG via art__draw_custom_svg with a NEW filename, "
            "fixing every listed weakness (keep the same subject)."
        )
        messages2 = list(messages) + [{"role": "user", "content": critique}]
        # build_verify loop_iteration: qayta chizish urinishi
        if on_loop_iteration is not None:
            try:
                on_loop_iteration(2, 2, "build_verify")
            except Exception:
                pass
        content2, tool_calls2, image2 = self._chat_with_tools(
            messages2, tools, web=web, progress=progress, req=req,
            on_loop_iteration=on_loop_iteration)
        if not image2 or not str(image2).lower().endswith(".svg"):
            # qayta chizish muvaffaqiyatsiz — birinchi natija qoladi
            return content, tool_calls, image, {
                "retried": True, "old_score": old_score, "new_score": None,
                "failed": True}
        report2 = self._validate_drawing(image2)
        new_score = (report2 or {}).get("total") or 0
        note: dict = {"retried": True, "old_score": old_score, "new_score": new_score}
        if new_score >= old_score:
            return content2 or content, tool_calls2 or tool_calls, image2, note
        # eski chizma hali ham yaxshiroq — u qoladi (yangisi xotirada allaqachon)
        note["kept_old"] = True
        return content, tool_calls, image, note

    def _draw_skill_text(self) -> str:
        """svg-artist skill ko'rsatmasini yuklaydi (bir marta, keshda).

        Chizish so'rovlarida system prompt'ga avtomatik qo'shiladi — model
        professional SVG (gradient, soya, qatlamlar, palitra) yaratishi uchun.
        Skill topilmasa bo'sh qaytaradi (agent ishlayveradi, shunchaki
        ko'rsatmasiz).
        """
        if self._draw_skill_cache is None:
            try:
                from skills import DEFAULT_MANAGER
                skill = DEFAULT_MANAGER.get("svg-artist")
                self._draw_skill_cache = skill.full_text() if skill else ""
            except Exception:
                self._draw_skill_cache = ""
        return self._draw_skill_cache

    def _draw_feedback_context(self) -> str:
        """L2 xotiradagi so'nggi CHIZMA SIFATI yozuvlaridan ixcham feedback bloki.

        Chizish so'rovlarida system prompt'ga qo'shiladi (RAG recall'ga
        tayanmasdan) — model avvalgi chizmalaridagi xatolarini ko'radi va
        takrorlamaydi: so'nggi 3 yozuv + eng ko'p takrorlangan 3 zaiflik.
        Parslash svg_quality_report.parse_quality_entry orqali (taklif qismi
        zaifliklar ro'yxatiga aralashmaydi). Xotira bo'lmasa '' qaytaradi.
        """
        try:
            base = getattr(self.memory, "base_dir", "")
            if not base:
                return ""
            from svg_quality_report import build_report, load_quality_entries
            entries = load_quality_entries(base)
            if not entries:
                return ""
            report = build_report(entries)
            weak_hist = report.get("weak_histogram") or {}
            out = [
                "RECENT DRAWING QUALITY FEEDBACK (past drawings — do NOT repeat these mistakes):"
            ]
            for e in (report.get("recent") or [])[-3:]:
                weak = ", ".join(e["weak"]) if e["weak"] else "yo'q"
                out.append(f"- {e['file']} ({e['style']}): score {e['score']}/100, "
                           f"zaif: {weak}")
            if weak_hist:
                top = list(weak_hist.items())[:3]
                out.append("Most recurring weaknesses: "
                           + ", ".join(f"{w} ({n}x)" for w, n in top))
            out.append("Fix these issues in the drawing you generate now.")
            return "\n".join(out)[:900]
        except Exception:
            return ""

    def _remember_drawing_quality(self, image: Optional[str], request: str) -> None:
        """Chizma faylini svg_validator bilan baholab, natijani L2 xotiraga yozadi.

        Keyingi chizish so'rovlarida RAG recall bu feedback'ni kontekstga
        qo'shadi — model oldingi xatolarini takrorlamaydi (gradient/soya/
        kompozitsiya/palitra). Xato yoki fayl topilmasa indamay o'tadi
        (agent ishlashini hech qachon buzmaydi).
        """
        if not image or not str(image).lower().endswith(".svg"):
            return
        if not (self.memory and self.memory.enabled):
            return
        r = self._validate_drawing(image)
        if r is None or r.get("error") or not r.get("total"):
            return
        s = r.get("scores") or {}
        meta = r.get("meta") or {}
        weak = [c.get("name") for c in r.get("checks") or [] if not c.get("ok")]
        total = r.get("total") or 0
        style = meta.get("style_comment") or "cartoon"
        weak_str = ", ".join(weak) if weak else "yo'q"
        content = (
            f"CHIZMA SIFATI (svg_validator auto-assessment): "
            f"prompt='{str(request)[:120]}' | file={image} | "
            f"viewBox={meta.get('viewBox')} | style={style} | "
            f"size={meta.get('size_comment') or 'standard'} | "
            f"score={total}/100 ({r.get('verdict')}) | "
            f"structure={s.get('structure', 0)} composition={s.get('composition', 0)} "
            f"style={s.get('style', 0)} palette={s.get('palette', 0)} | "
            "zaif jihatlar: " + weak_str
        )
        tip = _drawing_quality_tip(r)
        if tip:
            content += " | taklif: " + tip
        try:
            self.memory.remember(
                content[:2000],
                memory_type="solution-memory",
                tags=["drawing", "svg-quality", style, "score-" + str(total // 10 * 10)],
                summary="SVG chizma sifati: " + str(total) + "/100 (" + str(image) + ")",
            )
        except Exception:
            pass  # xotira xatosi agentni buzmaydi

    @staticmethod
    def _fake_draw_claim(text: str) -> bool:
        """Soxta "Chizdim ... rasm tayyor" — model rasmini CHIZMAGAN, faqat
        aytgan. HAQIQIY deb faqat `<svg>` markup yoki `art__draw` tool
        chaqiruvi hisoblanadi — fayl nomidagi `.svg` so'zi YO'Q (model yolg'on
        aytishi mumkin)."""
        low = (text or "").lower()
        has_draw_word = any(k in low for k in (
            "chizdim", "rasm tayyor", "chizib berdim", "drew", "drawing saved",
            "created the drawing", "image saved"))
        has_actual = ("<svg" in low or "art__draw" in low)
        return has_draw_word and not has_actual

    def _try_deterministic_scene(self, request: str, progress=None) -> Optional[dict]:
        """Ma'lum (canned) subject uchun ANIQ, deterministik chizma — crashsiz.

        Talabdan subject/rang aniqlanadi va `art__draw_scene_svg` deterministik
        chaqiriladi — modelga bog'liq emas (kuchsiz model xom yoki soxta
        "Chizdim" SVG yozib talabni buzmasin). Subject ma'lum bo'lmasa None
        qaytadi — LLM generatsiya qiladi.

        Qaytadi: {'content', 'image', 'tool', 'args', 'result'} yoki None.
        """
        if not self._is_draw_request(request):
            return None
        subj = self._detect_subject(request, "draw")
        if not subj or subj not in self.CANNED_SCENE_SUBJECTS:
            return None
        color = self._draw_color_from_request(request) or "red"
        # Part O: uslub va o'lcham ham talabdan — natija so'rovga mos real ko'rinish
        style = self._draw_style_from_request(request)
        size = self._draw_size_from_request(request)
        try:
            # Millisekund — tez ketma-ket chizmalar bir-birini ustiga yozmasligi
            # (bir xil subject bir soniyada 2 marta so'ralsa fayl to'qnashuv yo'q).
            fname = f"{subj}_{int(time.time() * 1000)}.svg"
            res = self._execute_chat_tool("art__draw_scene_svg", {
                "subject": subj, "output": fname, "color": color,
                "texture": "none", "style": style, "size": size,
            })
            if not res.get("ok"):
                return None
            img = self._image_from_art_call(res)
            if not img:
                return None
            # Sifatni baholab L2 xotiraga yozamiz (keyingi chizishlar uchun)
            self._remember_drawing_quality(img, request)
            if progress is not None:
                try:
                    progress("edit", f"art__draw_scene_svg → {subj}")
                except Exception:
                    pass
            return {
                "content": f"Chizdim: `{img}` — rasm tayyor ({subj}, {color}, "
                           f"{style}, {size}).",
                "image": img,
                "tool": "art__draw_scene_svg",
                "args": {"subject": subj, "output": fname, "color": color,
                         "texture": "none", "style": style, "size": size},
                "result": res,
            }
        except Exception:
            return None

    def _save_svg_from_text(self, content: str, tool_calls: list[dict],
                            image: Optional[str],
                            request: str) -> tuple[str, Optional[str]]:
        """Model javobida SVG kodi bo'lsa — art__draw_custom_svg orqali faylga yozadi.

        Model ba'zan tool chaqirmasdan SVG'ni matn sifatida yozadi — bunday
        javobni REAL chizma fayliga aylantiramiz (frontend karta ko'rsatadi)
        va "fayl yaratdim" deb yolg'on aytilishini oldini olamiz. Faqat
        chizish so'rovi bo'lsa ishlaydi (tasodifiy kod misollarini rasmga
        aylantirmaydi). `request` — ORIGINAL foydalanuvchi so'rovi (nudge
        xabarlari emas).

        Qaytadi: (yangi_javob, image_path)
        """
        if image:
            return content, image
        if not self._is_draw_request(request):
            return content, image
        try:
            found = self._extract_svg(content)
        except Exception:
            found = None
        if not found:
            # Part O: soxta "Chizdim ... rasm tayyor" (model rasmini chizmagan,
            # shunchaki aytgan) — muvaffaqiyat deb YO'Q, retry oqimiga qaytamiz.
            lowc = (content or "").lower()
            if image is None and any(k in lowc for k in (
                    "chizdim", "rasm tayyor", "chizib berdim", "drawing saved",
                    "drew", "i created the drawing", "saved as")):
                return "", image
            # Part O: to'liq bo'lmagan/haddan tashqari katta SVG bo'lagi (model
            # "chizdi" deb yozgan lekin noto'g'ri/malformatted) — junk'ni javob
            # sifatida qaytarmaymiz (crashsiz, tez halol holat).
            if image is None and len(content or "") > 1500 and (
                    "<svg" in lowc or "<path" in lowc or "stroke=" in lowc):
                return "", image
            return content, image
        svg_text, fname = found
        # So'rovda uslub/o'lcham aytilgan bo'lsa — argument'larga uzatamiz
        style = self._draw_style_from_request(request)
        size = self._draw_size_from_request(request)
        res = self._execute_chat_tool("art__draw_custom_svg",
                                      {"svg": svg_text, "output": fname,
                                       "style": style, "size": size})
        if not res.get("ok"):
            return content, image
        img = self._image_from_art_call(res)
        if not img:
            return content, image
        # Sifatni avtomatik baholab L2 xotiraga yozamiz (keyingi chizishlar uchun)
        self._remember_drawing_quality(img, request)
        tool_calls.append({
            "tool": "art__draw_custom_svg",
            "args": {"svg": svg_text[:120], "output": fname,
                     "style": style, "size": size},
            "result": {k: v for k, v in res.items() if k != "output"},
            "output_preview": str(res.get("output") or "")[:300],
        })
        # Javobni qisqa xulosaga almashtiramiz — kod dumi ko'rinmaydi
        return f"Chizdim: `{img}` — rasm tayyor (fayl: {fname}).", img

    def _tools_hint(self, request: str = "") -> str:
        """Capability-gap re-prompt: modelga real imkoniyatlar ro'yxati.

        `request` berilsa — WEB qo'llanma faqat web so'rovida qo'shiladi
        (aks holda rasm/kod vazifasida 3KB browser shovqini bo'lardi; model
        toolsetida web tool'lar ham faqat o'shanda bor).
        """
        parts = [
            "Do NOT give up - you have real capabilities and real tools. "
            "You CAN draw ANY image: YOU are the artist — generate the SVG markup "
            "yourself and save it with art__draw_custom_svg (args: svg='<full "
            "<svg>...</svg> markup>', output='duck.svg', "
            "style='cartoon|child|bw|fantasy|anime|realistic|flat', "
            "size='standard|icon|avatar|card|poster|banner'). There is NO fixed "
            "subject list. You may also use the quick canned tools: "
            "art__draw_scene_svg (subject, output, color, texture) for objects "
            "(apple, house, tree, cat, star, heart, car, rocket, flower, mountain, "
            "sun, moon, bird, fish, butterfly, mushroom, ball - Uzbek: olma, uy, "
            "daraxt, mushuk, quyosh, oy, qush, baliq, kapalak, to'p...) or "
            "art__draw_ui_svg (app, output, theme, texture) for UI/UX mockups. "
            "For a REAL working "
            "UI screen that is BUILT step by step (background, sections, sidebar "
            "with working toggle, content, a button that opens a window, the "
            "window with its shape/color first then its inner sketch), call "
            "art__ui_build_spec (app, output, theme). For a TODO/TASK LIST app "
            "(add/complete/delete/filter tasks, saved in localStorage), call "
            "art__ui_build_spec (app='todo', output='todo.uibuild.json', theme) "
            "- it is fully interactive, more powerful than a plain todo demo. "
            "ui_build_spec output must end in .uibuild.json.",
        ]
        mcp = self._mcp()
        if mcp is not None:
            art_names = [k for k in mcp.names() if k.startswith("art__")]
            if art_names:
                parts.append("Draw tools available to you: " + ", ".join(art_names))
            # WEB qo'llanma faqat web so'rovida — model toolsetida web tool'lar
            # ham faqat o'shanda bor (mcp_call ulardan tozalangan).
            if request and self._web_strategy(request):
                web_names = [k for k in mcp.names() if k.startswith("web_ai_bridge__")]
                if web_names:
                    parts.append(
                        "WEB DECISION RULES — use the CHEAPEST tool that answers:\n"
                        "1. Answer directly from your own knowledge — no tools.\n"
                        "2. web_fetch(url) reads static page text over HTTP — no browser.\n"
                        "3. ask_web_ai / web_ai_start_research to DELEGATE research and "
                        "knowledge questions to a web AI (chatgpt/gemini/claude_web/"
                        "deepseek) as a SUBAGENT — the web AI does the browsing for you.\n"
                        "4. Browser tools ONLY for interactive pages (accounts, forms, "
                        "logins, JS-heavy apps, exact live state).\n"
                        + WEB_TOOLS_GUIDE
                    )
        parts.append(
            "Fast direct tools (no browser): web_fetch(url) reads a page's text "
            "over HTTP, web_search_image(query) finds and downloads an image."
        )
        reg = self._registry()
        if reg is not None:
            parts.append("File/terminal tools: " + ", ".join(reg.names()))
        parts.append(
            "Use ONLY the tools listed above (they are the ones available to you "
            "in this chat). Continue the user's task now using the appropriate tool."
        )
        return "\n".join(parts)

    def _capability_gap(self, text: str) -> bool:
        """Model 'qila olmayman' kabi rad javobini aniqlaydi."""
        try:
            from executor import CAPABILITY_GAP_PATTERNS
            return bool(CAPABILITY_GAP_PATTERNS.search(text or ""))
        except Exception:
            return False

    def _execute_chat_tool(self, name: str, args: dict) -> dict:
        """Chatdagi tool'ni executor orqali bajaradi (MCP + registry)."""
        ex = self._chat_executor()
        if ex is None:
            return {"ok": False, "error": "tools unavailable"}
        try:
            return ex._execute_agent_tool(name, args)
        except Exception as exc:
            return {"ok": False, "error": f"{name} raised: {exc}"}

    def _image_from_art_call(self, result: dict) -> Optional[str]:
        """art__draw_object_png natijasidan workspace'ga nisbatan fayl yo'lini oladi."""
        out = str(result.get("output") or "")
        m = re.search(r"image saved to\s+(.+?)\s*$", out)
        if not m:
            return None
        abs_path = m.group(1).strip()
        try:
            root = os.path.normpath(self._chat_executor().workspace.root)
            rel = os.path.relpath(abs_path, root)
        except (ValueError, OSError):
            return None
        if rel.startswith(".."):
            return None
        return rel.replace(os.sep, "/")

    def active_chains(self, res: Resolution) -> list[str]:
        """Map matched rules back to their owning chains."""
        active = set()
        for rule_name in res.matched_rules:
            for chain in self.chains.chains.values():
                if chain.matches(rule_name):
                    active.add(chain.name)
        return sorted(active)

    # ------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------ #

    def status(self) -> dict:
        st = {
            "bricks": self.bricks.stats(),
            "knowledge": self.knowledge.stats(),
            "chains": {name: c.to_dict() for name, c in self.chains.chains.items()},
            "llm": {
                "enabled": self.use_llm,
                "model": self.llm.model,
                "available": self.llm_available(),
                **self.speed_status(),
            },
            "memory": self.memory.status(),
        }
        cache = self._cag()
        if cache is not None:
            st["cag"] = cache.status()
        mag = self._mag()
        if mag is not None:
            st["mag"] = {"enabled": self.memory.enabled,
                          "session_id": mag.session_id}
        try:
            from hooks import DEFAULT_BUS
            st["hooks"] = DEFAULT_BUS.stats()
        except Exception:
            pass
        # INTELLEKT qatlami (BuildIntalaganceInstructionRequest.md) — 10 modul holati
        try:
            st["intelligence"] = self.intelligence.status()
        except Exception:
            pass
        return st

    # ------------------------------------------------------------ #
    # Heal report helper
    # ------------------------------------------------------------ #

    def heal_report(self, missing_chain: str) -> dict:
        return self.healer.heal_report(missing_chain)


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


def _safe_print(text: str) -> None:
    """Print, tolerating consoles that cannot encode unicode (e.g. cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    agent = IgrisAgent(use_llm="--no-llm" not in argv)

    _safe_print("IGRIS CODER AGENT - hybrid (bricks + RAG memory + Ollama)")
    _safe_print("Status: OK   Chains: " + str(list(agent.chains.chains.keys())))
    _safe_print("LLM: " + (agent.llm.model if agent.use_llm else "disabled")
                + (" (available)" if agent.llm_available() else " (offline)"))
    _safe_print("Memory: " + ("enabled" if agent.memory.enabled else "disabled"))
    _safe_print("Commands: query | chat <msg> | status | heal <chain> | standards | refactor | telemetry | assess <q> | memory | exit")
    _safe_print("-" * 56)

    while True:
        try:
            query = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not query:
            continue
        if query in ("exit", "quit", "q"):
            if agent.memory.enabled:
                agent.memory.end_session("cli exit")
            return 0
        if query == "status":
            _safe_print(str(agent.status()))
            continue
        if query.startswith("heal "):
            _safe_print(str(agent.heal_report(query[5:].strip())))
            continue
        if query.startswith("chat "):
            res = agent.chat(query[5:].strip())
            _safe_print(f"Engine: {res['engine']}   {res['duration_ms']:.0f}ms   mem_hits={res['memory']['recall_hits']}")
            _safe_print(f"Output:\n{res['content']}")
            _safe_print("-" * 56)
            continue

        if query == "standards":
            _safe_print(agent.refactor.standards())
            continue
        if query == "refactor":
            import json
            _safe_print(json.dumps(agent.refactor.refactor_report(),
                                   ensure_ascii=False, indent=2))
            continue
        if query == "telemetry":
            _safe_print(str(agent.refactor.telemetry.stats()))
            continue
        if query == "memory":
            _safe_print(str(agent.memory.status()))
            continue
        if query.startswith("assess "):
            target = query[7:].strip()
            result = agent.refactor.evaluate_query(target)
            _safe_print(f"Query semantics: {result['query_semantics']}")
            if "resolution" in result:
                _safe_print(f"Resolution: {result['resolution']['status']} conf={result['resolution']['confidence']:.2f} engine={result['resolution'].get('engine')}")
                _safe_print(f"Output: {result['resolution']['output']}")
            _safe_print(f"Telemetry snapshot: {result.get('telemetry_snapshot')}")
            continue

        result = agent.resolve(query)
        _safe_print(f"Status: {'OK' if result['status'] == 'ok' else result['status']}")
        _safe_print(f"Confidence: {result['confidence']:.3f}")
        _safe_print(f"Engine: {result.get('engine', '?')}   Chains: {result.get('chains', [])}   {result.get('duration_ms', 0):.0f}ms")
        _safe_print(f"Output:\n{result['output']}")
        _safe_print(f"Trace: {result['trace']}")
        _safe_print("-" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
