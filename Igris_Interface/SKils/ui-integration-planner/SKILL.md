---
name: ui-integration-planner
description: 'Use whenever a UI component is added, moved, resized, or restructured inside an EXISTING interface or codebase — not a fresh one-off mockup. Framework-agnostic: web, desktop (Tauri/Electron/Qt), mobile, or CLI/TUI. Runs a pre-build check before code is written: confirms the component is actually needed and not a duplicate of something already there, inventories the current UI to find what is genuinely missing, maps which spatial region and stacking/z-layer the new piece belongs to and checks it against existing components there for collisions, pins down shape/size/behavior before coding, and allocates every UI slot a feature touches up front so each gets filled deliberately instead of ad hoc. Investigates the codebase first and only asks the person when something genuinely cannot be determined by inspection. Trigger for "add a panel/button/modal to X", "extend the sidebar with Y", "where should this go", "will this break the layout", or any change to an interface that already has other components in it.'
---

# UI Integration Planner

## Why this exists

Most UI bugs in a real, growing codebase aren't rendering bugs — they're
*integration* bugs: a second component that does the same thing as one that
already existed under a different name, a modal that sits at the same
z-layer as a toast and swallows its clicks, a new sidebar item that nobody
wired the "empty state" or "loading state" for, a panel that looks fine at
1440px and covers the save button at 1024px. None of these show up by
looking at the new component in isolation — they only show up by checking it
against what's already there.

This skill is a pre-build discipline: a short investigation before writing
any UI code, so integration problems get caught while they're a five-minute
fix instead of after they ship.

## Before you start: investigate, don't guess

Default to finding the answer yourself over asking the person. Read the
actual layout code, the component tree, the existing style tokens/theme
file, and search the codebase for anything that sounds similar to what's
being requested. A surprising number of "I'll need to ask the user where
this goes" situations resolve themselves the moment you actually open the
relevant file. See `references/investigation-techniques.md` for concrete
search patterns (grep strategies, where to look for layout structure and
design tokens, how to find naming conventions already in use).

Ask the person only when the answer is genuinely undeterminable by
inspection — a product/business decision, an ambiguity the codebase itself
doesn't resolve, or a case where two equally valid placements exist and the
choice matters (see "When to actually ask" below). Reflexively asking "where
should I put this?" for something the existing code already answers isn't
carefulness, it's outsourcing work the investigation should have done.

## The checklist

Run these in order. For a one-line change (copy edit, color tweak) this
collapses to seconds; for a new feature touching several screens, actually
write the checklist out (see `references/preflight-checklist-template.md`)
rather than holding it in your head — the template exists because the step
most often skipped under time pressure is the one written down.

### 0. Is this actually needed?

Before creating anything new, search for a component that already does this
or something close to it — under a different name, in a different folder,
built for a slightly different original purpose. Building a second
`ConfirmDialog` because the first one wasn't found costs far more later
(two things to maintain, inconsistent behavior between them) than the extra
two minutes of searching now. If something close exists, the answer is
usually to extend or parameterize it, not duplicate it.

If the request itself is redundant — asking for a component that
functionally duplicates one already on screen — say so and point at the
existing one, rather than building the duplicate as asked.

### 1. Inventory the current interface

Before deciding where anything goes, know what's actually there:
- The spatial regions that exist (header, sidebar, main, right panel,
  footer/status bar, or their equivalents in a non-web shell).
- The stacking layers in use (inline content, dropdowns, overlays, modals,
  toasts) — see `references/layer-taxonomy.md` for a framework-agnostic
  reference scale.
- The conventions already established: spacing scale, naming pattern for
  similar components, how similar existing components handle their states.

Skipping this step is what produces a technically-working component that
still looks bolted on — right pixels, wrong conventions.

### 2. Gap analysis

Compare the request against the inventory from step 1: what genuinely
doesn't exist yet, what exists but needs extending, what exists and fully
covers the request already (in which case building anything is the wrong
answer — wire up the existing thing instead).

### 3. Placement and collision check

For the new/changed piece, pin down two independent things:

- **Spatial region** — which layout area it lives in, and whether that area
  has room for it without pushing out or cramping what's already there at
  every viewport/window size the interface supports, not just the default one.
- **Stacking layer** — which z-layer it belongs to (see
  `references/layer-taxonomy.md`), and whether anything already in that
  layer would now overlap it, steal its clicks, or get hidden behind it.

Then actually check it against every existing component that shares that
region or layer — not just the one or two that come to mind first. A
sidebar with six items already in it is exactly the case where a new,
seventh item is most likely to silently push something off-screen or behind
a scroll boundary that nobody noticed.

### 4. Lock the spec before writing code

Write down, briefly, before touching implementation:
- Shape and size — fixed or fluid, min/max bounds, how it behaves when its
  content is longer/shorter than expected.
- Which existing design tokens it inherits (color, spacing, radius,
  motion) rather than introducing new one-off values — a new component
  that invents its own spacing scale is itself a future integration bug.
- Its interaction states, at least the ones that apply (default, hover,
  focus, disabled, loading, error, empty — see the `ux-design-system` skill
  if it's loaded, for the full state matrix and accessibility pass).

Skipping straight to code without this tends to produce a component that's
internally fine but externally inconsistent — a button with its own
one-off padding value next to five buttons that all share the standard one.

### 5. Allocate every slot the feature touches, then fill each one

For anything bigger than a single component (a new feature, a new flow),
enumerate every UI slot it touches *before* building any of them: the nav
entry, the main view, the empty state, the error state, any settings/config
surface, any confirmation/undo path. Write it as a checklist and work
through it in order — this is what prevents the common half-shipped result
where the main view is polished but the empty state was never designed, or
the feature works but nothing links to it from navigation. See
`references/preflight-checklist-template.md` for the worksheet format.

### 6. Verify after building, against the plan — not against a fresh look

Re-check the checklist from steps 0–5 against what actually got built, not
just a general "does this look okay" glance:
- Every allocated slot from step 5 actually filled, not just the main one?
- Placement/collision check from step 3 still holds now that real content
  (not placeholder text) is in it — long strings, empty arrays, many items?
- Anything that turned out to need a decision mid-build that never got
  locked down per step 4?

If any answer is "not quite," that's the next fix — not a caveat to
mention and move past.

## When to actually ask

Ask the person when, after actually inspecting the code, you're left with
one of these — not before:

- **A genuine product decision**, not a technical one — e.g. two
  reasonable places to put a feature that imply different information
  architecture, and the codebase gives no precedent either way.
- **A visual/brand decision with no existing precedent** — the first modal
  in an app that has none yet, where you'd otherwise be inventing the
  convention everything after it copies.
- **Conflicting existing patterns** — two different existing components
  solve similar problems in incompatible ways, and picking one sets
  precedent you can't easily undo later.

Don't ask about things the inspection already answered — which spacing
scale to use, which folder a component goes in, what an existing similar
component's states look like. Make the call, state the assumption in one
line, and proceed; that's what the investigation step was for.

## Quality bar before calling it done

- Did you search for an existing equivalent before building a new one, and
  can you say what you found (even if "nothing")?
- Can you name the exact spatial region and stacking layer this lives in,
  and confirm nothing else already occupies that combination?
- Does the spec (shape/size/tokens/states) trace back to existing
  conventions rather than inventing new ones?
- If this is a multi-slot feature, is there a written list of every slot it
  touches, with each one's status — not just the one that was top of mind?
- Did you re-verify placement with realistic content (long text, empty
  data, many items), not just the placeholder version?

## Reference files

- `references/investigation-techniques.md` — concrete ways to self-answer
  placement/naming/convention questions by reading the codebase, before
  considering whether to ask.
- `references/layer-taxonomy.md` — a framework-agnostic spatial-region and
  z-layer reference, with notes for web, desktop (Tauri/Electron/Qt),
  mobile, and CLI/TUI contexts.
- `references/preflight-checklist-template.md` — the literal checklist and
  slot-allocation worksheet to fill out for anything beyond a trivial change.