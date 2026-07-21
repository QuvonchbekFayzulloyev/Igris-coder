interface StatusBarProps {
  provider: string;
  model: string;
  lastIterations: number | null;
  promptTokens: number;
  completionTokens: number;
  costUsd: number;
  running: boolean;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return "<$0.01";
  return `$${usd.toFixed(2)}`;
}

export default function StatusBar({
  provider,
  model,
  lastIterations,
  promptTokens,
  completionTokens,
  costUsd,
  running,
}: StatusBarProps) {
  const totalTokens = promptTokens + completionTokens;

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-bg-subtle px-4 font-mono text-2xs text-ink-muted">
      <div className="flex items-center gap-4">
        <span>
          provider: <span className="text-ink">{provider}</span>
        </span>
        <span>
          model: <span className="text-ink">{model}</span>
        </span>
        {lastIterations !== null && (
          <span>
            last run: <span className="text-ink">{lastIterations} iteration{lastIterations === 1 ? "" : "s"}</span>
          </span>
        )}
        {totalTokens > 0 && (
          <span title={`${promptTokens} prompt + ${completionTokens} completion`}>
            tokens: <span className="text-ink">{totalTokens.toLocaleString()}</span>
          </span>
        )}
        {totalTokens > 0 && (
          <span>
            cost: <span className="text-ink">{formatCost(costUsd)}</span>
          </span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${running ? "animate-pulse-soft bg-blue" : "bg-green"}`}
          aria-hidden
        />
        {running ? "running" : "idle"}
      </div>
    </footer>
  );
}
