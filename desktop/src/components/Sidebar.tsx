import type { Skill } from "../lib/types";

interface SidebarProps {
  projects: string[];
  projectsLoading?: boolean;
  activeProject: string | null;
  onSelectProject: (name: string) => void;
  onCreateProject: (name: string) => void;
  skills: Skill[];
  mcpTools: string[];
  providers: string[];
  selectedProvider: string;
  onSelectProvider: (provider: string) => void;
}

function SidebarSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border px-3 py-3">
      <h3 className="mb-2 text-2xs font-semibold uppercase tracking-wide text-ink-faint">
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function Sidebar({
  projects,
  projectsLoading = false,
  activeProject,
  onSelectProject,
  onCreateProject,
  skills,
  mcpTools,
  providers,
  selectedProvider,
  onSelectProvider,
}: SidebarProps) {
  return (
    <aside className="flex w-60 shrink-0 flex-col overflow-y-auto border-r border-border bg-bg-subtle">
      <SidebarSection title="Projects">
        <ul className="space-y-0.5">
          {projects.map((p) => (
            <li key={p}>
              <button
                onClick={() => onSelectProject(p)}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors ${
                  p === activeProject
                    ? "bg-blue-dim text-blue"
                    : "text-ink-muted hover:bg-bg-inset"
                }`}
              >
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-60" />
                {p}
              </button>
            </li>
          ))}
          {projects.length === 0 && projectsLoading && (
            <li className="px-2 py-1 text-xs text-ink-faint">Loading projects&hellip;</li>
          )}
          {projects.length === 0 && !projectsLoading && (
            <li className="px-2 py-1 text-xs text-ink-faint">No projects yet</li>
          )}
        </ul>
        <button
          onClick={() => {
            const name = window.prompt("New project name");
            if (name) onCreateProject(name);
          }}
          className="mt-2 w-full rounded-md border border-dashed border-border px-2 py-1 text-xs text-ink-muted hover:border-blue hover:text-blue"
        >
          + New project
        </button>
      </SidebarSection>

      <SidebarSection title="Provider">
        <select
          value={selectedProvider}
          onChange={(e) => onSelectProvider(e.target.value)}
          className="w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-ink"
        >
          {providers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </SidebarSection>

      <SidebarSection title={`Skills (${skills.length})`}>
        <ul className="space-y-1">
          {skills.map((s) => (
            <li key={s.name} className="group">
              <div className="flex items-center justify-between text-sm text-ink">
                <span className="truncate">{s.name}</span>
                <span className="ml-2 shrink-0 rounded bg-green-dim px-1.5 py-0.5 text-2xs text-green-dark">
                  {s.pipeline_stage}
                </span>
              </div>
            </li>
          ))}
          {skills.length === 0 && (
            <li className="text-xs text-ink-faint">No skills loaded</li>
          )}
        </ul>
      </SidebarSection>

      <SidebarSection title={`MCP Tools (${mcpTools.length})`}>
        <ul className="space-y-0.5 font-mono text-2xs text-ink-muted">
          {mcpTools.map((t) => (
            <li key={t} className="truncate">
              {t}
            </li>
          ))}
          {mcpTools.length === 0 && (
            <li className="text-xs text-ink-faint">No tools connected</li>
          )}
        </ul>
      </SidebarSection>

      <SidebarSection title="Memory">
        <p className="text-xs text-ink-faint">
          Session log + checkpoints persist under{" "}
          <code className="font-mono text-2xs">.igris/memory/</code> per project.
        </p>
      </SidebarSection>
    </aside>
  );
}
