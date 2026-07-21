# desktop/src (frontend)

The React+TypeScript application -- everything that runs in the Tauri
webview. This is a thin client deliberately: no business logic lives
here, only presentation and orchestration of calls to the backend.

## Purpose

Give the reprompt loop a visible, live face: the Loop panel renders
`RepromptLoop`'s stages as they happen over a WebSocket, instead of the
loop being invisible the way it is in a plain CLI run.

## Boundary

- **No component calls `fetch`/`WebSocket` directly.** Every network
  call goes through `lib/api.ts`. This is enforced by convention, not by
  code -- when reviewing a new component, check for a direct `fetch()`
  call as a layering violation (see `architecture-layer-classification`).
- **No business logic.** If a component needs to decide *what* the
  correct behavior is (not just *how* to render/dispatch it), that logic
  belongs in the backend, reachable through an API call -- not
  duplicated here.
- **Async effects that call `setState` must guard against firing after
  unmount** (a `cancelled`/`active` flag checked before every `setState`
  inside a `.then()`). Found as a real bug via React's `act()` warnings
  in the component test suite, not by inspection -- see `App.tsx`'s
  mount-time effects.

## Key files

| Path | Sub-module | Role |
|---|---|---|
| `App.tsx` | -- | state + layout composition, the only file that talks to both `lib/api.ts` and every top-level component |
| `components/` | frontend.components | presentation -- see [components/README.md](components/README.md) |
| `lib/` | frontend.lib | the API client and shared types -- see [lib/README.md](lib/README.md) |

## Design tokens

`tailwind.config.js`: `bg` #FFFFFF, `blue` #1D5FD6 (interactive accent),
`green`/`green-dark` #1FA463/#0B4D33 (state, methodology), Segoe UI for
UI text (Windows-first -- no web font fetch needed to render offline),
Cascadia Code for monospace/logs (ships with Windows Terminal).

## Testing

Vitest + jsdom + `@testing-library/react` + `user-event`. WebSocket-
driven components/integration tests use a hand-rolled `FakeWebSocket`
class (jsdom has no real `WebSocket`) -- see `App.test.tsx` for the
pattern (static `.OPEN`/`.CLOSED` constants matching the real API,
`.emit()` helper, and every simulated server event wrapped in React's
`act()` since it bypasses the DOM event loop React normally batches
around).

**Status**: verified by real execution (`npm run verify:bundle` in
`desktop/`), not just component tests -- the actual production `dist/`
bundle runs in a real JS engine and genuinely mounts, both with a live
backend and in the unreachable-backend fallback path. Never opened in an
actual browser tab or the real Tauri webview, since neither is available
in this environment -- see the root README's Status section and
`../README.md` for exactly what that gap does and doesn't mean.

## How this compares

Routing every network call through one client module rather than
letting components call `fetch` directly is the same pattern
`architecture-layer-classification` recommends generally; the payoff
here specifically is that every component test mocks props, never
`fetch`, which is most of why the suite runs in well under a second.
