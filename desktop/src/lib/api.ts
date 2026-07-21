import type {
  ChatResponse,
  McpToolsResponse,
  ModelsResponse,
  ProjectsResponse,
  ProviderTestResponse,
  ProvidersResponse,
  SettingsResponse,
  SettingsUpdatePayload,
  Skill,
  WsEvent,
} from "./types";

// The Python backend (igris/server.py) is spawned as a Tauri sidecar and
// always listens on localhost -- see src-tauri/src/main.rs for the port.
// Overridable via VITE_IGRIS_API_BASE for local `npm run dev` against a
// manually-started `uvicorn igris.server:app` instance.
const API_BASE = import.meta.env.VITE_IGRIS_API_BASE ?? "http://127.0.0.1:8765";
const WS_BASE = API_BASE.replace(/^http/, "ws");

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`GET ${path} failed: ${resp.status}`);
  return resp.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`POST ${path} failed: ${resp.status}`);
  return resp.json();
}

export const api = {
  health: () => getJson<{ status: string }>("/api/health"),
  listProjects: () => getJson<ProjectsResponse>("/api/projects"),
  createProject: (name: string) => postJson<{ name: string; path: string }>("/api/projects", { name }),
  activateProject: (name: string) => postJson<{ active: string }>(`/api/projects/${name}/activate`, {}),
  listSkills: (project: string) => getJson<{ skills: Skill[] }>(`/api/skills?project=${encodeURIComponent(project)}`),
  listMcpTools: (project: string) => getJson<McpToolsResponse>(`/api/mcp/tools?project=${encodeURIComponent(project)}`),
  listProviders: () => getJson<ProvidersResponse>("/api/providers"),
  selectProvider: (provider: string, project: string) =>
    postJson(`/api/providers/select?project=${encodeURIComponent(project)}`, { provider }),
  getSettings: (project: string) => getJson<SettingsResponse>(`/api/settings?project=${encodeURIComponent(project)}`),
  updateSettings: (project: string, payload: SettingsUpdatePayload) =>
    postJson<SettingsResponse>(`/api/settings?project=${encodeURIComponent(project)}`, payload),
  chatOnce: (message: string, project: string) =>
    postJson<ChatResponse>("/api/chat", { message, project }),
  fetchModels: (provider: string, host: string, apiKey?: string) =>
    postJson<ModelsResponse>("/api/providers/models", { provider, host, api_key: apiKey }),
  testProvider: (provider: string, host: string, model?: string, apiKey?: string) =>
    postJson<ProviderTestResponse>("/api/providers/test", { provider, host, model, api_key: apiKey }),
};

/**
 * Opens the streaming chat WebSocket. Call send() per message; onEvent
 * fires for every stage + the final event. Caller owns the socket
 * lifecycle (close() when the panel unmounts).
 */
export function openChatSocket(onEvent: (event: WsEvent) => void) {
  const socket = new WebSocket(`${WS_BASE}/ws/chat`);

  socket.onmessage = (raw) => {
    try {
      onEvent(JSON.parse(raw.data) as WsEvent);
    } catch {
      onEvent({ type: "error", detail: "Received malformed event from server" });
    }
  };

  return {
    send: (message: string, project: string) => {
      if (socket.readyState !== WebSocket.OPEN) {
        onEvent({ type: "error", detail: "Not connected to igris backend yet" });
        return;
      }
      socket.send(JSON.stringify({ message, project }));
    },
    close: () => socket.close(),
    raw: socket,
  };
}
