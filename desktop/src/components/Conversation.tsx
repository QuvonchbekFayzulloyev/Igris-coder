import { useEffect, useRef, useState } from "react";
import type { ConversationMessage } from "../lib/types";

interface ConversationProps {
  messages: ConversationMessage[];
  onSend: (text: string) => void;
  running: boolean;
  /** When set, the input is disabled and this hint is shown instead of a submit-time alert. */
  disabledReason?: string | null;
}

function Bubble({ message }: { message: ConversationMessage }) {
  const isUser = message.role === "user";
  const isClarify = message.role === "clarify";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[70ch] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-blue text-white"
            : isClarify
              ? "border border-amber/40 bg-amber-dim text-ink"
              : "border border-border bg-bg-subtle text-ink"
        }`}
      >
        {isClarify && (
          <div className="mb-1 flex items-center gap-1 text-2xs font-semibold uppercase tracking-wide text-amber">
            Clarification needed
          </div>
        )}
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}

export default function Conversation({ messages, onSend, running, disabledReason = null }: ConversationProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const disabled = running || Boolean(disabledReason);

  useEffect(() => {
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = () => {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-6 py-5">
        {messages.length === 0 && !disabledReason && (
          <div className="mx-auto max-w-md pt-16 text-center text-sm text-ink-faint">
            Describe a task. igris will resolve intent, gather context, and
            reprompt itself before touching the model -- watch it happen in
            the Loop panel on the right.
          </div>
        )}
        {messages.length === 0 && disabledReason && (
          <div className="mx-auto max-w-md pt-16 text-center text-sm text-ink-faint">
            {disabledReason}
          </div>
        )}
        {messages.map((m) => (
          <Bubble key={m.id} message={m} />
        ))}
        {running && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-lg border border-border bg-bg-subtle px-3.5 py-2.5 text-sm text-ink-muted">
              <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-green" />
              <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-green [animation-delay:0.2s]" />
              <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-green [animation-delay:0.4s]" />
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-border bg-bg px-6 py-4">
        {disabledReason && (
          <div className="mb-2 text-2xs text-ink-faint">{disabledReason}</div>
        )}
        <div className="flex items-end gap-2 rounded-lg border border-border bg-bg-subtle p-2 focus-within:border-blue">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            disabled={disabled}
            placeholder={disabledReason ?? "Ask igris to do something in this project..."}
            rows={2}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1 text-sm text-ink placeholder:text-ink-faint focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={submit}
            disabled={disabled || !draft.trim()}
            className="shrink-0 rounded-md bg-blue px-3 py-1.5 text-sm font-medium text-white transition-opacity disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
