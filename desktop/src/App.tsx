import { useCallback, useEffect, useRef, useState } from "react";
import TopBar from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import Conversation from "./components/Conversation";
import RuntimePanel from "./components/RuntimePanel";
import StatusBar from "./components/StatusBar";
import SettingsPanel from "./components/SettingsPanel";
import PreviewPanel from "./components/PreviewPanel";
import { api, openChatSocket } from "./lib/api";
import type { ConversationMessage, PreviewData, Skill, StageEvent, WsEvent } from "./lib/types";

let idCounter = 0;
const nextId = () => `msg-${++idCounter}-${Date.now()}`;

export default function App() {
  const [projects, setProjects] = useState<string[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [mcpTools, setMcpTools] = useState<string[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("ollama");
  const [activeModel, setActiveModel] = useState<string>("-");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [stageEvents, setStageEvents] = useState<StageEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [lastIterations, setLastIterations] = useState<number | null>(null);
  const [promptTokens, setPromptTokens] = useState(0);
  const [completionTokens, setCompletionTokens] = useState(0);
  const [costUsd, setCostUsd] = useState(0);
  const [backendReachable, setBackendReachable] = useState(true);
  const [view, setView] = useState<"chat" | "preview">("chat");
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);

  const socketRef = useRef<ReturnType<typeof openChatSocket> | null>(null);

  const handleEvent = useCallback((event: WsEvent) => {
    if (event.type === "stage") {
      setStageEvents((prev) => [...prev, { stage: event.stage, detail: event.detail }]);
      return;
    }
    if (event.type === "final") {
      setRunning(false);
      setLastIterations(event.iterations);
      setPromptTokens((prev) => prev + (event.prompt_tokens ?? 0));
      setCompletionTokens((prev) => prev + (event.completion_tokens ?? 0));
      setCostUsd((prev) => prev + (event.cost_usd ?? 0));
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: event.needs_clarification ? "clarify" : "assistant",
          content: event.needs_clarification ? event.clarifying_question : event.response,
          timestamp: Date.now(),
        },
      ]);
      return;
    }
    if (event.type === "error") {
      setRunning(false);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: `Error: ${event.detail}`, timestamp: Date.now() },
      ]);
    }
    if (event.type === "preview") {
      setPreviewData({
        tester_name: event.tester_name,
        success: event.success,
        summary: event.summary,
        details: event.details,
        errors: event.errors,
        artifacts: event.artifacts,
      });
    }
  }, []);

  // Load project list + provider list once; probe backend reachability.
  useEffect(() => {
    let cancelled = false;

    api
      .health()
      .then(() => { if (!cancelled) setBackendReachable(true); })
      .catch(() => { if (!cancelled) setBackendReachable(false); });

    api.listProviders()
      .then((r) => { if (!cancelled) setProviders(r.providers); })
      .catch(() => {});

    api.listProjects()
      .then((r) => {
        if (cancelled) return;
        setProjects(r.projects);
        if (r.active) setActiveProject(r.active);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setProjectsLoading(false); });

    return () => { cancelled = true; };
  }, []);

  // (Re)load project-scoped state whenever the active project changes.
  useEffect(() => {
    if (!activeProject) return;
    let cancelled = false;

    api.listSkills(activeProject)
      .then((r) => { if (!cancelled) setSkills(r.skills); })
      .catch(() => { if (!cancelled) setSkills([]); });
    api.listMcpTools(activeProject)
      .then((r) => { if (!cancelled) setMcpTools(r.tools); })
      .catch(() => { if (!cancelled) setMcpTools([]); });
    refreshSettings(activeProject, () => cancelled);

    return () => { cancelled = true; };
  }, [activeProject]);

  const refreshSettings = (project: string, isCancelled: () => boolean = () => false) => {
    api
      .getSettings(project)
      .then((s) => {
        if (isCancelled()) return;
        setSelectedProvider(s.gateway.provider);
        const modelBySection: Record<string, string | undefined> = {
          ollama: s.ollama.model,
          lmstudio: s.lmstudio.model,
          openrouter: s.openrouter.model,
        };
        setActiveModel(modelBySection[s.gateway.provider] ?? "-");
      })
      .catch(() => {});
  };

  // Open the chat WebSocket once; RepromptLoop instances are created
  // per-message server-side, scoped by the `project` field in each send.
  useEffect(() => {
    let active = true;
    const socket = openChatSocket((event) => {
      if (active) handleEvent(event);
    });
    socket.raw.onopen = () => { if (active) setConnected(true); };
    socket.raw.onclose = () => { if (active) setConnected(false); };
    socketRef.current = socket;
    return () => {
      active = false;
      socket.close();
    };
  }, [handleEvent]);

  const handleSend = (text: string) => {
    if (!activeProject) return; // Conversation is disabled in this state; defensive no-op only
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: text, timestamp: Date.now() }]);
    setStageEvents([]);
    setRunning(true);
    socketRef.current?.send(text, activeProject);
  };

  const handleCreateProject = async (name: string) => {
    try {
      await api.createProject(name);
      const r = await api.listProjects();
      setProjects(r.projects);
      setActiveProject(name);
      setActionError(null);
    } catch (e) {
      setActionError(`Couldn't create project "${name}": ${String(e)}`);
    }
  };

  const handleSelectProject = async (name: string) => {
    try {
      await api.activateProject(name);
      setActiveProject(name);
      setMessages([]);
      setStageEvents([]);
      setPromptTokens(0);
      setCompletionTokens(0);
      setCostUsd(0);
      setLastIterations(null);
      setActionError(null);
    } catch (e) {
      setActionError(`Couldn't switch to project "${name}": ${String(e)}`);
    }
  };

  const handleSelectProvider = async (provider: string) => {
    if (!activeProject) {
      setSelectedProvider(provider);
      return;
    }
    try {
      await api.selectProvider(provider, activeProject);
      refreshSettings(activeProject);
      setActionError(null);
    } catch (e) {
      setActionError(`Couldn't switch provider to "${provider}": ${String(e)}`);
    }
  };

  if (!backendReachable) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg px-6 text-center">
        <div className="max-w-sm">
          <div className="mx-auto mb-3 h-8 w-8 rounded-md bg-green-dark" />
          <h1 className="mb-1 text-sm font-medium text-ink">igris backend not reachable</h1>
          <p className="text-xs text-ink-muted">
            Start it with{" "}
            <code className="rounded bg-bg-inset px-1 py-0.5 font-mono">
              uvicorn igris.server:app --port 8765
            </code>{" "}
            from the igris-cli directory, then reload.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col">
      <TopBar
        projectName={activeProject}
        connected={connected}
        view={view}
        onToggleView={() => setView((v) => (v === "chat" ? "preview" : "chat"))}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      {actionError && (
        <div className="flex items-center justify-between border-b border-red/30 bg-red-dim px-4 py-1.5 text-xs text-red">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="ml-3 shrink-0 hover:opacity-70">
            Dismiss
          </button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Sidebar
          projects={projects}
          projectsLoading={projectsLoading}
          activeProject={activeProject}
          onSelectProject={handleSelectProject}
          onCreateProject={handleCreateProject}
          skills={skills}
          mcpTools={mcpTools}
          providers={providers}
          selectedProvider={selectedProvider}
          onSelectProvider={handleSelectProvider}
        />
        {view === "chat" ? (
          <Conversation
            messages={messages}
            onSend={handleSend}
            running={running}
            disabledReason={activeProject ? null : "Create or select a project to start."}
          />
        ) : (
          <PreviewPanel data={previewData} />
        )}
        <RuntimePanel events={stageEvents} running={running} />
      </div>
      <StatusBar
        provider={selectedProvider}
        model={activeModel}
        lastIterations={lastIterations}
        promptTokens={promptTokens}
        completionTokens={completionTokens}
        costUsd={costUsd}
        running={running}
      />
      {settingsOpen && activeProject && (
        <SettingsPanel
          project={activeProject}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => refreshSettings(activeProject)}
        />
      )}
    </div>
  );
}
