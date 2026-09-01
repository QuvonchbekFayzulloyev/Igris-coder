/**
 * Turns a raw Playwright navigation result (or error) into something Claude
 * can actually reason about: is this a page, an image, a file download, a
 * blocked/CAPTCHA wall, or a real failure -- and why.
 */

const CAPTCHA_PATTERN =
  /verify you (are|'re) human|checking your browser|unusual traffic|complete the captcha|are you a robot|attention required.*cloudflare|access denied.*cloudflare|please enable javascript and cookies/i;

const COOKIE_BANNER_PATTERN =
  /we use cookies|this (site|website) uses cookies|accept (all )?cookies|cookie (policy|consent|preferences)|manage (cookie|privacy) (settings|preferences)/i;

const NEWSLETTER_MODAL_PATTERN =
  /subscribe to our newsletter|sign up for (our )?(newsletter|updates)|join our mailing list|get .*(delivered|sent) to your inbox/i;

/** Button/link text that signals a real-world, often irreversible
 *  consequence -- money moving, an account or data being destroyed, a
 *  purchase being finalized. Used to require an explicit confirm before
 *  browser_click fires on something matching this, not to detect page state. */
export const RISKY_ACTION_PATTERN =
  /\b(buy now|place( your)? order|complete (the )?purchase|confirm (payment|order|purchase)|pay now|proceed to checkout|checkout now|send money|transfer funds|wire transfer|delete (my )?account|permanently delete|deactivate (my )?account|remove (my )?account|confirm delete|unsubscribe permanently|cancel subscription)\b/i;

export function classifyContentType(contentType) {
  if (!contentType) return "unknown";
  const ct = contentType.split(";")[0].trim().toLowerCase();
  if (ct.startsWith("text/html")) return "page";
  if (ct.startsWith("image/")) return "image";
  if (ct === "application/pdf") return "file";
  if (ct.startsWith("video/") || ct.startsWith("audio/")) return "media";
  if (ct.startsWith("text/") || ct === "application/json" || ct === "application/xml") return "text";
  return "file";
}

export function classifyNetError(message) {
  const m = String(message || "");
  if (/ERR_NAME_NOT_RESOLVED/.test(m)) return { reason: "DNS lookup failed -- domain doesn't resolve", code: "dns" };
  if (/ERR_CONNECTION_REFUSED/.test(m)) return { reason: "Connection refused -- nothing answering at that address", code: "refused" };
  if (/ERR_CONNECTION_TIMED_OUT|Timeout.*exceeded/.test(m)) return { reason: "Connection timed out", code: "timeout" };
  if (/ERR_CERT|SSL/.test(m)) return { reason: "TLS/certificate error", code: "tls" };
  if (/ERR_TOO_MANY_REDIRECTS/.test(m)) return { reason: "Too many redirects", code: "redirects" };
  if (/ERR_INTERNET_DISCONNECTED/.test(m)) return { reason: "No internet connection", code: "offline" };
  if (/ERR_ABORTED/.test(m)) return { reason: "Navigation aborted -- often means the link triggered a file download instead of loading a page", code: "aborted_maybe_download" };
  return { reason: m.split("\n")[0].slice(0, 200), code: "unknown" };
}

export async function detectCaptchaWall(page) {
  try {
    const [title, body] = await Promise.all([
      page.title().catch(() => ""),
      page.evaluate(() => document.body.innerText.slice(0, 2000)).catch(() => ""),
    ]);
    return CAPTCHA_PATTERN.test(title) || CAPTCHA_PATTERN.test(body);
  } catch {
    return false;
  }
}

/** Cheap, text-pattern-based detection of common page clutter that isn't a
 *  CAPTCHA but still blocks or distracts from the real content -- cookie
 *  consent banners and newsletter/subscribe popups being the two that show
 *  up almost everywhere. Best-effort, same spirit as CAPTCHA detection: a
 *  hint to act on, not a guarantee. */
export async function detectObstruction(page) {
  try {
    const body = await page.evaluate(() => document.body.innerText.slice(0, 3000)).catch(() => "");
    if (COOKIE_BANNER_PATTERN.test(body)) {
      return { type: "cookie_banner", note: "A cookie-consent banner is likely visible" };
    }
    if (NEWSLETTER_MODAL_PATTERN.test(body)) {
      return { type: "newsletter_modal", note: "A newsletter/subscribe popup is likely visible" };
    }
    return null;
  } catch {
    return null;
  }
}
