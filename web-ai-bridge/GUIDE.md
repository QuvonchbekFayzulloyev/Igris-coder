# web-ai-bridge: usage, button, and validation reference

Everything the plugin does automatically, or refuses to do without your
say-so, in one place. `README.md` covers install; `skills/web-ai-bridge/
SKILL.md` is the version Claude itself reads. This one is for you.

## 1. Which tool for which task

| You want to... | Tool |
|---|---|
| Open a URL and see what's there | `browser_navigate` |
| Check what a link even *is*, without leaving your current tab | `browser_check_link` |
| Look at the page yourself | `browser_screenshot` |
| Read the page's text (ads/clutter stripped) | `browser_get_text` |
| Click something | `browser_click` |
| Fill in a field | `browser_type` |
| Choose a dropdown option | `browser_select_option` |
| Attach a local file | `browser_upload_file` |
| Press a shortcut (Escape, Ctrl+A, ...) | `browser_press_key` |
| Scroll / reveal something off-screen | `browser_scroll` |
| Wait for something to actually load | `browser_wait_for` |
| Work with more than one tab | `browser_list_tabs`, `browser_new_tab`, `browser_switch_tab`, `browser_close_tab` |
| See what's been downloaded | `browser_list_downloads` |
| Confirm which browser is actually running | `browser_info` |
| Clear a cookie banner / popup that's in the way | `browser_dismiss_overlays` |
| Run a whole adaptive task (survives UI redesigns — picks elements by text/label from the live page) | `browser_ai_task` |
| Ask ChatGPT / Gemini / Claude.ai / DeepSeek something (normal length) | `ask_web_ai` |
| Ask something that could take a while (deep research) | `web_ai_start_research` then `web_ai_check_research` |
| Start that provider's conversation over | `web_ai_new_chat` |
| Interrupt a reply that's generating | `web_ai_stop_generating` |
| Read the full on-screen conversation | `web_ai_get_conversation` |

## 2. When which button gets pressed

Not every button is treated the same way. Three tiers:

**Pressed automatically, no question asked** -- routine, reversible UI:
navigation, tabs, dropdowns, scrolling, ordinary form fields, the
provider's own New Chat / Stop Generating buttons (`web_ai_new_chat`,
`web_ai_stop_generating` click the *real* button; only fall back to a bare
URL change if no such button exists on the page).

**Pressed automatically, but only after checking for clutter first** --
cookie-consent banners: `browser_dismiss_overlays` clicks **Accept**, never
Reject, because that's the one reliable way to unblock a page
programmatically. It does not touch a site's actual privacy/tracking
settings -- if those matter to you, review them yourself. Generic popups
(newsletter modals, etc.) get their **Close/Dismiss/No thanks** button
clicked the same way.

**Never pressed without your explicit go-ahead** -- anything
`browser_click` finds reading like a real-world, often irreversible
consequence: *Buy Now, Place Order, Confirm Payment, Pay Now, Proceed to
Checkout, Delete My Account, Deactivate/Remove Account, Cancel
Subscription*, and similar. The tool call is refused outright until it's
retried with `confirm: true` -- and the instruction to Claude is explicit:
that flag only gets set after you've been told exactly what the button does
and you've said yes. `Add to Cart` and ordinary navigation are *not* in this
tier -- they're not final/irreversible, so they go through normally.

## 3. How data gets checked

**Every navigation** (`browser_navigate`, `browser_check_link`) is
classified, not just attempted:
- real HTTP status and Content-Type decide **page / image / media / text /
  file** -- never guessed from the URL's file extension
- a failed navigation is checked against known network-error patterns (DNS
  failure, connection refused, timeout, TLS error, too many redirects, no
  connection) and reported in plain language, not a raw Chromium error string
- if the "failure" was actually a file download starting, that's detected
  and the file is saved (see `browser_list_downloads`) instead of being
  reported as an error
- the loaded page's text is scanned for CAPTCHA/bot-check wording first; if
  that matches, the result is reported as **blocked** and nothing else is
  checked. Only if no CAPTCHA is detected does a second, separate scan run
  for cookie-banner / newsletter-popup wording -- so a page is reported as
  either blocked, or (optionally) obstructed, never both at once

**Text about to be sent to a third-party AI chat** (`browser_type`,
`ask_web_ai`) is scanned by a `PreToolUse` hook before it ever leaves your
machine, for:
- AWS access keys, `api_key=`/`token=`-style assignments, OpenAI/
  Anthropic-style `sk-...` keys, Bearer tokens, PEM private-key blocks,
  `password=` assignments
- US Social Security numbers (`###-##-####`)
- payment card numbers -- checked with the **Luhn algorithm**, not just "is
  this 13-19 digits", specifically so order numbers, tracking numbers, and
  phone numbers don't constantly false-trigger it

A hit doesn't silently block -- it escalates to a confirmation prompt so you
decide whether it's actually fine to send.

**Reply-time degradation** (`ask_web_ai`) is judged by a written rule, not a
gut feeling:
1. Needs at least 3 timed replies in the current conversation before judging
   anything -- one or two data points can't show a trend.
2. Baseline = the average of the first two replies.
3. A reply only counts as "slow" if it clears **both** 2x the baseline and
   baseline+15s -- so neither a naturally-fast provider (2s -> 4s) nor a
   naturally-slow one (10s -> 13s) false-triggers.
4. Only **two slow replies in a row** raise the signal. One slow reply is
   treated as noise and gets no reaction.

Separately, if the provider's own UI says outright that the conversation is
getting long, that's treated as an immediate, one-time signal -- no pattern
required, because the provider is saying so directly rather than it being
inferred from timing.

## 4. Long-running research: submit, then poll -- never block-wait

Normal chat replies use `ask_web_ai`, which blocks until the reply is ready
(up to `wait_timeout_ms`, default 60s). Deep research is a different shape of
problem -- it can take many minutes -- so it uses two calls instead of one:

1. `web_ai_start_research(provider, prompt)` submits the prompt and returns
   right away, without waiting for a reply.
2. Claude is expected to do its own useful work in the meantime rather than
   idling -- researching the same question itself, or handling another part
   of the task.
3. `web_ai_check_research(provider)` is called periodically afterward. It
   reports one of three states:
   - **still working** -- normal, not an error, keep going and check later
   - **complete** -- the reply text, plus how long it actually took
   - **hard failure** -- the tab stopped responding at all (crashed, closed,
     or the connection was lost). This is checked directly (a live probe of
     the page, with its own timeout so a hung connection can't hang the
     check itself) and reported immediately and explicitly -- it is never
     confused with "still working," and it is never silently retried.
4. A job still "generating" past a configurable sanity ceiling (30 minutes by
   default) gets flagged as possibly stuck, rather than being trusted forever.
