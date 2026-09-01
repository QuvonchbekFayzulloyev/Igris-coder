#!/usr/bin/env node
/**
 * PreToolUse hook for web-ai-bridge.
 * Runs before `browser_type` / `ask_web_ai` calls that would send text into a
 * third-party web AI chat session. If the text looks like it contains a
 * credential, escalate to a user confirmation instead of sending it silently.
 *
 * Cross-platform on purpose (pure Node, no shell dependency) so it works the
 * same way on native Windows, macOS, and Linux without WSL or Git Bash.
 */

const SECRET_PATTERNS = [
  { name: "AWS access key", re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "generic API key assignment", re: /\b(api[_-]?key|apikey|secret|token)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{16,}['"]?/i },
  { name: "OpenAI/Anthropic-style secret key", re: /\bsk-(ant-)?[A-Za-z0-9_\-]{20,}\b/ },
  { name: "Bearer token", re: /\bBearer\s+[A-Za-z0-9\-._~+/]{20,}=*\b/ },
  { name: "private key block", re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/ },
  { name: "password assignment", re: /\bpassword\s*[:=]\s*\S{6,}/i },
  { name: "US Social Security Number", re: /\b\d{3}-\d{2}-\d{4}\b/ },
];

// Checked separately (Luhn algorithm) rather than as a plain regex, since a
// bare "13-19 digits" pattern would false-positive constantly on order
// numbers, tracking numbers, phone numbers, etc. Luhn cuts that way down.
function luhnValid(digits) {
  let sum = 0;
  let alt = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = parseInt(digits[i], 10);
    if (alt) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return sum % 10 === 0;
}

function containsCreditCard(text) {
  const candidates = text.match(/\b(?:\d[ -]?){13,19}\b/g) || [];
  return candidates.some((c) => {
    const digits = c.replace(/[ -]/g, "");
    return digits.length >= 13 && digits.length <= 19 && luhnValid(digits);
  });
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function extractCandidateText(toolInput) {
  if (!toolInput || typeof toolInput !== "object") return "";
  const fields = ["text", "prompt", "value", "content"];
  return fields
    .map((f) => (typeof toolInput[f] === "string" ? toolInput[f] : ""))
    .join("\n");
}

(async () => {
  let input;
  try {
    input = JSON.parse(await readStdin());
  } catch {
    process.exit(0); // can't parse -> don't block, fail open
  }

  const text = extractCandidateText(input.tool_input);
  if (!text) process.exit(0);

  const hit = SECRET_PATTERNS.find((p) => p.re.test(text));
  const hitName = hit ? hit.name : containsCreditCard(text) ? "payment card number" : null;
  if (!hitName) process.exit(0);

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "ask",
        permissionDecisionReason:
          `web-ai-bridge: the text about to be sent to a third-party web AI looks like it contains a ${hitName}. ` +
          `Confirm this is intentional before it leaves your machine.`,
      },
    })
  );
  process.exit(0);
})();
