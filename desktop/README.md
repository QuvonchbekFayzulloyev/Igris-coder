# igris desktop

Tauri + React shell around the igris Python backend (`igris/server.py`).
Same reprompt loop, same MCP tools, same projects/ workspace as the CLI --
this just gives it a visible face: live Loop panel, project switcher,
skill/MCP tool inspector, and manual provider/model/API-key settings.

## Layout

```
desktop/
  src/                    React + TypeScript (Vite)
    App.tsx                state + layout composition
    components/
      TopBar.tsx            search / workspace / settings
      Sidebar.tsx            projects, provider, skills, MCP tools
      Conversation.tsx       message thread + prompt editor
      RuntimePanel.tsx       right sidebar: Loop tracker, context, logs
      LoopTracker.tsx        live per-stage progress (the signature element)
      StatusBar.tsx          bottom bar: provider, model, run status
      SettingsPanel.tsx      manual provider/model/host/API-key editor
    lib/
      api.ts                 REST + WebSocket client
      types.ts                shared types
  src-tauri/               Rust shell
    src/main.rs              spawns the Python backend, hosts the window
    Cargo.toml
    tauri.conf.json
```

See [`src/README.md`](src/README.md) for the React app's own boundary
and testing conventions, [`src/components/README.md`](src/components/README.md)
and [`src/lib/README.md`](src/lib/README.md) for the two sub-modules
underneath it.

## Setup (Windows, PowerShell)

```powershell
# 1. igris-cli itself must already be installed (this is what the shell spawns)
cd path\to\igris-cli
pip install -e .

# 2. Desktop app dependencies
cd desktop
npm install

# 2.5. Sanity-check the web app itself before touching Rust at all --
#      builds and actually executes the production bundle in a real JS
#      engine, checking both the normal and backend-unreachable paths
npm run build
npm run verify:bundle

# 3. Rust + Tauri CLI -- install rustup from https://rustup.rs if you don't have it
#    (apt/system rustc is often too old for Tauri v2; rustup keeps it current)
npm install -g @tauri-apps/cli   # or use `npx tauri` directly, already a devDependency

# 4. Run in dev mode -- this starts Vite AND spawns the Python backend
npx tauri dev
```

`tauri dev` builds and launches the Rust shell, which spawns
`python -m uvicorn igris.server:app --port 8765` as a child process (see
`src-tauri/src/main.rs`) and points the webview at the Vite dev server.
Closing the window kills the backend process too.

To run the frontend alone against a manually-started backend (e.g. while
iterating on UI without touching Rust):

```powershell
# terminal 1
uvicorn igris.server:app --port 8765 --reload

# terminal 2
npm run dev
```

## Building a release

```powershell
npx tauri icon path\to\a-1024x1024.png   # generates all required icon sizes first
npx tauri build
```

Produces an MSI/NSIS installer under `src-tauri/target/release/bundle/`.

## Settings panel

The gear icon in the top bar opens provider/model/host/API-key editing for
all three providers (Ollama, LM Studio, OpenRouter) -- not just a
provider-name dropdown. Changes are written through to the active
project's `.igris/config.yaml` via `POST /api/settings`
(`Config.save_overrides` on the Python side), so they survive an app
restart. The OpenRouter API key is never echoed back by the API -- the
panel only ever learns whether one is set, never its value.

## Known limitations

- **The web app itself is now verified by real execution, not just static
  checks.** `npm run verify:bundle` loads the actual production-built
  `dist/` bundle (exactly what the Tauri webview would load) into a real
  JS engine (jsdom) and executes it -- confirming React actually mounts
  real DOM content, in both the backend-unreachable fallback path and
  the normal path (project list, provider selector, skills/MCP sections
  all render with real mocked data), with zero uncaught script errors or
  unhandled rejections in either case. This is meaningfully stronger
  than `tsc`/`vitest`/`vite build` alone, which only prove static
  correctness -- this proves the shipped artifact actually runs.
- **The native Tauri shell itself remains unverified** -- this is the one
  real gap `verify:bundle` cannot close, since it requires an actual
  window/webview, which needs a real display and (on Linux) webkit2gtk
  system libraries not installable in a headless sandbox regardless of
  Rust toolchain. Confirmed two independent blockers when attempting
  this: (1) `rustup`/`static.rust-lang.org` are network-denied at the
  egress-proxy level (`403 host_not_allowed`) -- apt's rustc 1.75 is the
  only option here, and Tauri v2's dependency tree needs 1.85+ for
  Cargo's `edition2024` feature; (2) even pinning around that (attempted
  and reverted -- a transitive dependency inside Tauri's own tree hard-
  requires `getrandom` 0.4.x regardless) wouldn't help, since `chromium`/
  `chromium-browser` also fail to install here (the apt package requires
  snapd, which fails on transitive-package 404s in this container) --
  so there's no path to a real rendered window in this environment at
  all, independent of the Rust version problem. Verify with `cargo tauri
  dev` on Windows via `rustup` (the actual target platform, WebView2-
  based, no webkit2gtk needed) before relying on the native shell.
- **No bundled Python runtime yet.** `main.rs` spawns `python -m uvicorn`
  assuming Python + `igris` are already installed on PATH, same as the
  CLI requires. A double-click installer that needs zero Python setup
  would freeze the backend with PyInstaller and wire it up as a Tauri
  `externalBin` sidecar instead -- a packaging change, not a behavior
  change; `igris/server.py` itself doesn't need to change for that.
- **No app icons yet** -- `tauri.conf.json` has an empty icon list, fine
  for `tauri dev` but `tauri build` needs `tauri icon` run first (see
  above).
