/**
 * web-ai-bridge — Safety / Sanitization
 * ======================================
 * Mirrors Igris_brain/safety.py (N2/N3 fix): before web page text reaches the
 * LLM, prompt-injection patterns ("ignore previous instructions", "system:",
 * "you are now ...", etc.) are masked out.
 *
 * The Python brain ALSO sanitizes at its own choke point (mcp_bridge.py), so
 * this is defense-in-depth: the bridge itself never ships raw injection text,
 * and even if a future tool forgets to sanitize, the Python layer still catches
 * it. Keeping the pattern list identical to safety.py means one source of
 * truth in two languages.
 */

const SUSPICIOUS_PATTERNS = [
  /ignore\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?)/i,
  /ignore\s+all\s+previous\s+(instructions?|rules?|prompts?)/i,
  /you\s+are\s+now\s+(a|an)\s+/i,
  /forget\s+(everything|all|previous)/i,
  /system\s*:\s*/i,
  /<\s*(script|instruction)\s*>/i,
  /override\s+(safety|rules?|instructions?)/i,
  /jailbreak/i,
  /DAN\s+mode/i,
  /developer\s+mode/i,
  /admin\s+access/i,
  /bypass\s+(all|security|rules?)/i,
  /disregard\s+(previous|all)\s+instructions?/i,
  /pretend\s+(you\s+are|to\s+be)\s+/i,
  /repeat\s+(after\s+me|the\s+above)/i,
  /new\s+instructions?\s*:/i,
];

export function hasSuspicious(text) {
  if (!text) return false;
  return SUSPICIOUS_PATTERNS.some((p) => p.test(text));
}

/**
 * Masks only the matched spans (not whole lines): web page text is usually one
 * long collapsed string, so whole-line masking would wipe legitimate content.
 *
 * Replaces ALL occurrences of each pattern (Python `re.sub` bilan bir xil):
 * the literals intentionally have no `g` flag so `hasSuspicious().test()` stays
 * stateless, so here we rebuild each pattern with `g` added for the replace.
 */
export function sanitize(text, replace = "[filtered: suspicious content]") {
  if (!text) return text;
  let out = String(text);
  for (const p of SUSPICIOUS_PATTERNS) {
    out = out.replace(new RegExp(p.source, p.flags.includes("g") ? p.flags : p.flags + "g"), replace);
  }
  return out;
}

/** Convenience: if suspicious, sanitize; else return unchanged. */
export function sanitizeIfNeeded(text) {
  if (hasSuspicious(text)) return sanitize(text);
  return text;
}
