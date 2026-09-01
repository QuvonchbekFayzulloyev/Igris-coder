---
name: interface-designer
description: >-
  Use whenever building, redesigning, or reviewing any UI/UX/GUI/CLI interface —
  new screens, windows, panels, dashboards, sidebars, modals, toolbars, or
  terminal (TUI) layouts, or any single interface component. Mandatory first
  step before writing any interface code — build a full component inventory,
  audit necessity, pre-allocate layers/regions, verify no collisions with
  existing components, and confirm shape/size/spacing against a defined scale.
  Trigger on 'interfeys yarat', 'UI yasa', 'dizayn qil', 'panel qo'sh',
  'komponent joylashtir', 'layerga joylashtir', GUI/CLI dizayn so'rovlari, or
  any request to add/move/resize an interface element, or involving
  layer/z-index/region placement. Always run this before
  senior-software-engineer touches a file that renders UI — a component
  written without this skill's inventory/layer pass is treated as unfinished,
  not done.
---
 
# Interface Designer
 
**Pipeline stage:** Implementation (UI/UX/GUI/CLI layer). Runs after `architecture-expert` has set system structure, and gates any UI-rendering work `senior-software-engineer` would otherwise start on directly.
 
## Scope
 
Discipline for *placing* interface work correctly: what exists, whether it should exist, which layer/region it lives in, whether it collides with anything already there, what shape and size it takes, and whether it's actually usable — for both graphical UI (Electron/React/Tauri desktop apps) and text UI (CLI/TUI agent tools). Not visual taste or color theory (see the public `frontend-design` skill for that) — this skill is the layout/layer/necessity gate that runs *before* and *after* the visual polish pass.
 
The core failure this skill exists to prevent: an agent opens a file and starts adding a `<div>` or a terminal panel directly, with no record of what else occupies that space, no defined layer for it to live in, and no check that it doesn't collide with or duplicate something that's already there.
 
## The rule
 
**No component gets written until Steps 1–4 below produce a written inventory + layer map.** This isn't a formality — skipping it is exactly how two elements end up sharing a z-index, a sidebar overlaps a modal, or a component gets added that already exists three files away under a different name. If the task is trivial (one-line text change, color tweak, moving an already-inventoried component), Steps 1–4 can be answered in a couple of lines instead of a full table — but they must still be answered, not skipped.
 
---
 
## Step 1 — Component Inventory
 
Before touching code, list every component the task touches or introduces. Use this table (fill it inline in your response before writing code, don't just hold it in your head):
 
| Component | Region/Layer | Position | Size (W×H) | Depends on | Conflicts with | Necessity |
|---|---|---|---|---|---|---|
| e.g. `AgentStatusBadge` | overlay-panel | top-right, 16px inset | 96×28 | agent state store | none found | shows live agent state — no existing component covers this |
 
For an existing codebase, this means actually reading the current layout (files, JSX tree, or TUI render tree) before adding to it — never assume a spot is free.
 
## Step 2 — Necessity Audit
 
For every row in the inventory, answer explicitly:
- Is this component solving a problem nothing else on screen already solves? If it overlaps in purpose with an existing component, that's a merge candidate, not a new component.
- What breaks if this is removed? If the honest answer is "nothing," don't add it.
- Is it earning permanent screen/terminal real estate, or should it be a secondary/on-demand view (menu item, `--flag`, collapsed panel) instead?
Flag anything that fails this audit and ask the user rather than building it silently.
 
## Step 3 — Layer & Region Allocation (pre-allocate before filling in)
 
Allocate every component to a named layer/region **first**, across the whole set, before implementing any single one. Filling one component in completely before the others even have a slot assigned is how collisions happen later.
 
### GUI layer model (Electron/React/Tauri)
 
Use a single shared layer-token scale — never hand-roll a `z-index: 9999`. A reasonable default scale:
 
| Layer | z-index range | Contents |
|---|---|---|
| `background` | 0–9 | canvas, decorative background, static chrome |
| `content` | 10–49 | main app content, cards, primary panes |
| `chrome` | 50–69 | nav bars, sidebars, toolbars, status bars |
| `overlay-panel` | 70–89 | docked/floating panels, dropdowns, popovers |
| `modal` | 90–99 | dialogs, blocking modals |
| `toast` | 100–109 | notifications, toasts |
| `tooltip-cursor` | 110+ | tooltips, drag-ghosts, cursors — always topmost |
 
Keep this scale in one shared file (e.g. `theme/layers.ts` or CSS custom properties) that every component imports — not literal numbers scattered across files.
 
### CLI/TUI region model (ink, textual, ratatui, blessed, raw ANSI)
 
Terminals have no true z-index, only paint order and screen-buffer regions, so the equivalent discipline is fixed **regions**, not stacking:
 
| Region | Typical placement | Notes |
|---|---|---|
| `header/status` | row 0–1 | agent name, mode, connection state |
| `sidebar` | fixed-width column | optional; hide below a min-width breakpoint |
| `main-viewport` | remaining rows/cols | primary scrollable content |
| `footer/input` | last 1–2 rows | prompt line, key hints |
| `overlay-popup` | centered, saved/restored buffer | modals — must save and restore the screen underneath |
| `status-line` | single reserved row | transient notifications, never steals focus |
 
Define the minimum supported terminal size (default assumption: 80×24) and what each region does when the terminal shrinks below it (collapse sidebar first, never truncate the input line).
 
## Step 4 — Collision & Conflict Check
 
Before writing code, check the inventory against itself and against what already exists:
- Do any two components' bounding boxes overlap at any supported size/breakpoint?
- Does anything claim the same GUI z-index band or the same TUI region without a defined stacking/focus order between them?
- Do keyboard shortcuts, focus order (Tab order in GUI, key bindings in TUI), or scroll containers conflict?
- Does a new element sit on a background that kills its contrast/legibility?
- Can a new overlay/modal steal focus from something that needs to keep it (e.g. a live input line)?
Any "yes" here blocks implementation until resolved — resolve it in the inventory, not by patching after the fact.
 
## Step 5 — Shape, Size & Visual Spec
 
Concrete, not vibes:
- **GUI:** spacing/sizing on an 8px grid, one consistent corner-radius value per surface type, minimum interactive target ≈24–44px, type scale limited to a handful of steps (not arbitrary px values per component).
- **CLI/TUI:** fixed character-cell alignment (no fractional padding), consistent box-drawing style across panels, sparing color use (assume 16-color fallback works even if 256-color is available), never encode meaning by color alone.
- Both: state the component's behavior at min and max size explicitly (truncate? wrap? scroll? hide?) — "shape" isn't defined until that's answered.
## Step 6 — Usability Pass
 
- Is the component discoverable without being told it's there?
- Is it consistent with how equivalent components already behave elsewhere in this app/agent?
- Does a keyboard-only (GUI) or non-mouse (TUI is always this) path fully reach it?
- Are loading, empty, and error states defined — not just the happy path?
- GUI: contrast ratio, visible focus ring, accessible labeling. TUI: readable in a screen reader / plain-text log capture, not solely reliant on color or box-drawing to convey state.
## Step 7 — Ask, don't assume
 
If any of the following aren't already known, ask before building rather than guessing:
- Target surface: desktop GUI, CLI, TUI, or more than one?
- Is there an existing theme/token file or design system to match, or is this greenfield?
- Minimum supported window size (GUI) or terminal size (TUI)?
- Light/dark mode, or single theme only?
- Is this a new layer/region, or does it join an existing one — and if existing, what already lives there?
- What's the one primary action this surface exists for? (Everything else is secondary and should look secondary.)
Ask these as a short batch, not one at a time, and only ask what the inventory/audit above couldn't already answer from the existing codebase.
 
## Step 8 — Post-build professional-placement audit
 
After implementation, before calling it done, re-check the inventory against the actual result: every row still accurate, no layer/region collisions introduced, sizes match the spec at min/max, and nothing from Step 6's usability pass was skipped. Describe (or screenshot, if tooling allows) the final placement rather than asserting it's correct.
 
---
 
## Defers to
 
- `architecture-expert` — for structural/module decisions this skill's layer choices must live inside; this skill doesn't decide app architecture, only interface layout discipline within it.
- `senior-software-engineer` — for code-quality baseline once a component's inventory/layer/size spec is settled and implementation starts.
- `frontend-design` (public skill) — for aesthetic direction, typography, and visual style once layout/layer placement is locked in; don't let visual polish decisions leak back into layer allocation.
## Used by
 
- Any GUI work on [[universal-ai-bridge]]'s unified Electron/React shell or [[ximera]]'s single unified UI.
- [[igris-cli]]'s terminal/TUI surface and any other CLI agent output that renders structured panels rather than plain log lines.
- Any future `desktop-ui`/`tauri`-style skill — this is the layer/placement pass that should run before those get into framework-specific detail.
## Anti-patterns
 
- Writing UI code before the component inventory + layer map exists, "to save time."
- Ad-hoc z-index numbers (`999`, `9999`) instead of the shared layer scale.
- Adding a component "just in case it's useful later" without a necessity justification in Step 2.
- Designing for one window/terminal size only and hoping it scales.
- Two components silently sharing a layer/region with no defined stacking or focus order between them.
- Treating the CLI/TUI side as an afterthought of the GUI spec — terminal layout has its own region model above and needs its own pass, not a reused GUI answer.