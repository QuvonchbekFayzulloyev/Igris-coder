interface TopBarProps {
  projectName: string | null;
  connected: boolean;
  view: "chat" | "preview";
  onToggleView: () => void;
  onOpenSettings: () => void;
}

export default function TopBar({ projectName, connected, view, onToggleView, onOpenSettings }: TopBarProps) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-bg px-4">
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-green-dark text-[11px] font-semibold text-white">
          ig
        </div>
        <span className="text-sm font-medium text-ink">igris</span>
        {projectName && (
          <>
            <span className="text-ink-faint">/</span>
            <span className="text-sm text-ink-muted">{projectName}</span>
          </>
        )}
      </div>

      <div className="flex flex-1 justify-center px-8">
        <div className="w-full max-w-md rounded-md border border-border bg-bg-subtle px-3 py-1 text-xs text-ink-faint">
          Search this project&hellip;
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={onToggleView}
          className={`rounded-md px-2 py-1 text-xs transition-colors ${
            view === "preview"
              ? "bg-green-dark text-white"
              : "text-ink-muted hover:bg-bg-inset"
          }`}
          title={view === "chat" ? "Show test results" : "Show chat"}
        >
          {view === "chat" ? "Preview" : "Chat"}
        </button>
        <div className="flex items-center gap-1.5 text-2xs text-ink-muted">
          <span
            className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-green" : "bg-red"}`}
            aria-hidden
          />
          {connected ? "connected" : "disconnected"}
        </div>
        <button
          onClick={onOpenSettings}
          className="rounded-md px-2 py-1 text-xs text-ink-muted hover:bg-bg-inset"
        >
          Settings
        </button>
      </div>
    </header>
  );
}
