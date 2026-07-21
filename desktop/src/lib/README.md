# desktop/src/lib (frontend.lib)

The data-access/integration layer for the frontend: the only files that
know the backend's actual REST/WebSocket shapes.

## Purpose

Give every component the same typed, mockable interface to the backend,
so a component test never needs to know an HTTP status code or a
WebSocket frame format -- it mocks `api.ts`'s exported functions (or
props derived from them) instead.

## Boundary

- **`api.ts` is the only file that constructs a `fetch()` call or opens
  a `WebSocket`.** Every REST endpoint the backend exposes gets one
  corresponding function here; every field the backend can return gets a
  type in `types.ts`.
- **`openChatSocket()` exposes only `send()`/`close()`/`raw`** -- callers
  drive it via an `onEvent` callback dispatching on the `WsEvent`
  discriminated union (`stage` | `final` | `error`), never by inspecting
  `raw.readyState` directly outside this file.
- **Types here must stay in sync with the backend's actual response
  shape** -- when `server.py` adds a field (e.g. `prompt_tokens`/
  `cost_usd` were added to the `final` WebSocket event), `types.ts` and
  every caller that should read it need updating in the same change, not
  as a follow-up. A missed field here fails silently at runtime (an
  `undefined` value), not at compile time, since JSON parsing doesn't
  enforce the TypeScript type -- see `App.tsx`'s `?? 0` defensive
  fallback on the token fields for exactly this reason.

## Key files

| File | Role |
|---|---|
| `api.ts` | every REST call + the WebSocket wrapper |
| `types.ts` | shared types matching the backend's actual request/response shapes |

## Testing

`App.test.tsx` and `SettingsPanel.test.tsx` mock `globalThis.fetch` (a
small method-aware router, not a blanket stub) and a `FakeWebSocket`
class rather than mocking `lib/api.ts` itself where possible, so the
tests exercise `api.ts`'s real parsing logic -- `SettingsPanel.test.tsx`
mocks `api.ts` directly instead, since its concern is the component's
payload-construction logic, not `api.ts`'s own request building.

## How this compares

A single client module per backend, rather than scattering endpoint
knowledge across components, is the same pattern most React apps
converge on once they have more than a handful of API calls; the
specific payoff realized here is that the token/cost field additions
(`prompt_tokens`, `completion_tokens`, `cost_usd`) touched exactly one
file (`types.ts`) plus the one component that displays them
(`StatusBar.tsx`), not every component that happens to receive a `final`
event.
