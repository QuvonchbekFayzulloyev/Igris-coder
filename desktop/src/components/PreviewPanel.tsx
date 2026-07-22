import type { PreviewData } from "../lib/types";

interface PreviewPanelProps {
  data: PreviewData | null;
}

function StatusBadge({ success }: { success: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-2xs font-semibold ${
        success
          ? "bg-green-dim text-green"
          : "bg-red-dim text-red"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${success ? "bg-green" : "bg-red"}`} />
      {success ? "ALL PASSED" : "SOME FAILED"}
    </span>
  );
}

export default function PreviewPanel({ data }: PreviewPanelProps) {
  if (!data) {
    return (
      <div className="flex min-w-0 flex-1 flex-col items-center justify-center text-center text-sm text-ink-faint">
        <div className="mb-3 text-4xl">&#9654;</div>
        <div>No test results yet</div>
        <div className="mt-1 text-xs">Run a task to see preview results here</div>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
      <div className="border-b border-border bg-bg-subtle px-6 py-4">
        <div className="mb-2 flex items-center gap-3">
          <h2 className="text-sm font-semibold text-ink">Test Results</h2>
          <StatusBadge success={data.success} />
        </div>
        <p className="text-xs text-ink-muted">{data.summary}</p>
      </div>

      <div className="flex-1 space-y-4 px-6 py-5">
        {data.details.length > 0 && (
          <section>
            <h3 className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-faint">
              Details
            </h3>
            <ul className="space-y-1">
              {data.details.map((d, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-ink-muted">
                  <span className="mt-0.5 shrink-0 text-green">&#10003;</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {data.errors.length > 0 && (
          <section>
            <h3 className="mb-2 text-2xs font-semibold uppercase tracking-wide text-red">
              Errors ({data.errors.length})
            </h3>
            <ul className="space-y-1">
              {data.errors.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-ink-muted">
                  <span className="mt-0.5 shrink-0 text-red">&#10007;</span>
                  <span className="font-mono">{e}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {data.artifacts.length > 0 && (
          <section>
            <h3 className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-faint">
              Artifacts
            </h3>
            <ul className="space-y-1">
              {data.artifacts.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-ink-muted">
                  <span className="mt-0.5 shrink-0 text-ink-faint">&#128206;</span>
                  <span className="font-mono">{a}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {data.details.length === 0 && data.errors.length === 0 && data.artifacts.length === 0 && (
          <div className="text-xs text-ink-faint">(no structured output)</div>
        )}
      </div>
    </div>
  );
}
