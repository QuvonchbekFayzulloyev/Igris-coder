/**
 * Best-effort selector config for each web AI chat UI.
 *
 * These front ends change their markup often, so every selector is a list of
 * candidates tried in order -- the first one present in the page wins. If a
 * provider redesigns their UI and every candidate stops matching, ask_web_ai
 * returns a clear error telling Claude to fall back to the low-level
 * browser_screenshot / browser_get_text / browser_click / browser_type tools
 * and re-run with an explicit selector instead of guessing blindly.
 *
 * Edit this file directly if a site changes and you've found the new
 * selector in devtools -- no need to touch index.js.
 */

export const PROVIDERS = {
  chatgpt: {
    label: "ChatGPT",
    url: "https://chatgpt.com/",
    inputCandidates: [
      "#prompt-textarea",
      "div[contenteditable='true'][id='prompt-textarea']",
      "textarea[data-testid='prompt-textarea']",
    ],
    submitCandidates: [
      "button[data-testid='send-button']",
      "button[aria-label='Send prompt']",
    ],
    responseCandidates: [
      "div[data-message-author-role='assistant']:last-of-type",
      "article:last-of-type div.markdown",
    ],
    streamingIndicator: "button[data-testid='stop-button']",
    newChatCandidates: [
      "a[data-testid='create-new-chat-button']",
      "button[aria-label='New chat']",
      "a[aria-label='New chat']",
    ],
  },
  gemini: {
    label: "Gemini",
    url: "https://gemini.google.com/app",
    inputCandidates: [
      "div.ql-editor[contenteditable='true']",
      "rich-textarea div[contenteditable='true']",
    ],
    submitCandidates: [
      "button.send-button",
      "button[aria-label='Send message']",
    ],
    responseCandidates: [
      "message-content.model-response-text:last-of-type",
      "div.response-container:last-of-type",
    ],
    streamingIndicator: "button.stop-icon, button[aria-label='Stop response']",
    newChatCandidates: [
      "button[aria-label='New chat']",
      "a[aria-label='New chat']",
      "expandable-button[data-test-id='new-chat-button']",
    ],
  },
  claude_web: {
    label: "Claude.ai",
    url: "https://claude.ai/new",
    inputCandidates: [
      "div[contenteditable='true'].ProseMirror",
      "div[aria-label='Write your prompt to Claude']",
    ],
    submitCandidates: [
      "button[aria-label='Send Message']",
      "button[data-testid='send-message-button']",
    ],
    responseCandidates: [
      "div[data-testid='message-content']:last-of-type",
    ],
    streamingIndicator: "button[aria-label='Stop Response']",
    newChatCandidates: [
      "a[href='/new']",
      "button[aria-label='New chat']",
      "a[data-testid='new-chat-button']",
    ],
  },
  deepseek: {
    label: "DeepSeek",
    url: "https://chat.deepseek.com/",
    inputCandidates: [
      "textarea#chat-input",
      "textarea[placeholder*='Message']",
    ],
    submitCandidates: [
      "div[role='button'][aria-disabled='false']",
      "button[type='submit']",
    ],
    responseCandidates: [
      "div.ds-markdown:last-of-type",
    ],
    streamingIndicator: "div.ds-loading, svg.animate-spin",
    newChatCandidates: [
      "div[aria-label='New chat']",
      "button[aria-label='New chat']",
      "div._217e214",
    ],
  },
};

export function getProvider(name) {
  const key = String(name || "").toLowerCase().trim();
  const provider = PROVIDERS[key];
  if (!provider) {
    const known = Object.keys(PROVIDERS).join(", ");
    throw new Error(`Unknown provider "${name}". Known providers: ${known}`);
  }
  return provider;
}
