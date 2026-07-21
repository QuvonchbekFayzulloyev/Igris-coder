# desktop/src/components (frontend.components)

The presentation layer. Every file here renders something; none of them
decide anything the backend should be deciding.

## Purpose

Render igris's state (projects, skills, MCP tools, conversation, the
live loop trace, settings) and turn user interaction into calls to the
callbacks `App.tsx` passes down -- nothing here owns state beyond local
UI state (an input draft, a collapsed/expanded flag).

## Boundary

- **No direct `fetch`/`WebSocket` calls** -- see `../README.md`'s
  boundary section. `SettingsPanel.tsx` calls `api.getSettings()`/
  `api.updateSettings()`, never a raw `fetch`.
- **Every interactive control needs a keyboard path and a clear disabled
  state with a stated reason.** A disabled button with no explanation is
  a usability gap, not acceptable polish debt -- see
  `Conversation.tsx`'s `disabledReason` prop and `SettingsPanel.tsx`'s
  Escape-to-close handler (both added after a `desktop-ux-usability-
  audit` pass found their absence).
- **Errors surface visibly, never silently.** `App.tsx`'s dismissible
  error banner exists because `handleCreateProject`/`handleSelectProject`
  originally failed with `.catch(() => {})` -- a real gap the same audit
  found and fixed.

## Key files

| File | Role |
|---|---|
| `TopBar.tsx` | search / workspace / settings entry point, connection status |
| `Sidebar.tsx` | projects, provider selector, skills, MCP tools |
| `Conversation.tsx` | message thread + prompt editor; owns the disabled/hint state when no project is active |
| `LoopTracker.tsx` | the product's signature element -- live, ordered stage timeline as `RepromptLoop` emits events |
| `RuntimePanel.tsx` | wraps `LoopTracker` plus collapsible Context/Logs sections |
| `StatusBar.tsx` | provider, model, run status, accumulated token usage and cost |
| `SettingsPanel.tsx` | manual provider/model/host/API-key editing, persisted through to `.igris/config.yaml` |

## Testing

One `__tests__/*.test.tsx` per component, `@testing-library/react`
queries by role/text/placeholder (never by CSS class or test-id), every
conditional render branch and user interaction covered as its own test
-- see `ui-component-testing` for the full convention this follows.

## How this compares

Keeping components free of network calls and business logic is standard
React practice; the specific discipline worth calling out is that this
project's usability fixes (error banners, keyboard support, loading
states) came from applying a written checklist (`desktop-ux-usability-
audit`) against the actual rendered/tested behavior, not from a general
sense that the UI "could be nicer."
