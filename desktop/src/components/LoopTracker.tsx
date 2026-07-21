import type { StageEvent } from "../lib/types";

interface LoopTrackerProps {
  events: StageEvent[];
  running: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  snapshot: "Snapshot",
  intent: "Intent",
  clarify: "Clarify",
  complexity: "Complexity",
  loop_plan: "Loop Plan",
  skills: "Skills",
  gather: "Gather",
  spec: "Spec",
  multi_agent: "Multi-agent",
  review_1: "Review",
  review_2: "Review (retry)",
};

function labelFor(stage: string): string {
  if (STAGE_LABELS[stage]) return STAGE_LABELS[stage];
  if (stage.startsWith("attempt_")) return `Attempt ${stage.split("_")[1]}`;
  if (stage.startsWith("review_")) return `Review ${stage.split("_")[1]}`;
  return stage;
}

export default function LoopTracker({ events, running }: LoopTrackerProps) {
  return (
    <div className="px-3 py-3">
      <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-ink-faint">
        Loop
      </h3>
      {events.length === 0 && !running && (
        <p className="text-xs text-ink-faint">
          Send a task to watch the reprompt loop run stage by stage.
        </p>
      )}
      <ol className="relative">
        {events.map((event, i) => {
          const isLast = i === events.length - 1;
          const isActive = isLast && running;
          return (
            <li key={`${event.stage}-${i}`} className="relative flex gap-2.5 pb-4 last:pb-0">
              {!isLast && (
                <span className="absolute left-[5px] top-3 h-full w-px bg-border" aria-hidden />
              )}
              <span
                className={`relative mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2 ${
                  isActive
                    ? "animate-pulse-soft border-green bg-green"
                    : "border-green-dark bg-green-dark"
                }`}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-medium text-ink">{labelFor(event.stage)}</div>
                <div
                  className="truncate font-mono text-2xs text-ink-muted"
                  title={event.detail}
                >
                  {event.detail}
                </div>
              </div>
            </li>
          );
        })}
        {running && (
          <li className="flex items-center gap-2.5 pt-1">
            <span className="h-2.5 w-2.5 animate-pulse-soft rounded-full bg-blue" aria-hidden />
            <span className="text-xs text-ink-muted">running&hellip;</span>
          </li>
        )}
      </ol>
    </div>
  );
}
