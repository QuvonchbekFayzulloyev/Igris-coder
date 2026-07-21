import { useState } from "react";
import type { StageEvent } from "../lib/types";
import LoopTracker from "./LoopTracker";

interface RuntimePanelProps {
  events: StageEvent[];
  running: boolean;
}

function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-2xs font-semibold uppercase tracking-wide text-ink-faint hover:text-ink-muted"
      >
        {title}
        <span className="text-ink-faint">{open ? "\u2212" : "+"}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

export default function RuntimePanel({ events, running }: RuntimePanelProps) {
  const snapshotEvent = events.find((e) => e.stage === "snapshot");
  const gatherEvent = events.find((e) => e.stage === "gather");

  return (
    <aside className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-border bg-bg-subtle">
      <div className="border-b border-border">
        <LoopTracker events={events} running={running} />
      </div>

      <CollapsibleSection title="Context" defaultOpen={false}>
        <div className="space-y-2 font-mono text-2xs text-ink-muted">
          <div>
            <div className="text-ink-faint">snapshot</div>
            <div className="whitespace-pre-wrap">{snapshotEvent?.detail ?? "(none yet)"}</div>
          </div>
          <div>
            <div className="text-ink-faint">gathered</div>
            <div className="whitespace-pre-wrap">{gatherEvent?.detail ?? "(none yet)"}</div>
          </div>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Logs" defaultOpen={false}>
        <div className="max-h-64 space-y-1 overflow-y-auto font-mono text-2xs text-ink-muted">
          {events.length === 0 && <div className="text-ink-faint">(no output yet)</div>}
          {events.map((e, i) => (
            <div key={i}>
              <span className="text-green-dark">[{e.stage}]</span> {e.detail}
            </div>
          ))}
        </div>
      </CollapsibleSection>
    </aside>
  );
}
