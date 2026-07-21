import { render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

// --- Fake WebSocket, per the ui-component-testing skill's pattern -----
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;

  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

// --- Fetch router: default routes cover App's mount-time calls --------
// Keys are either a bare path ("/api/projects", matches any method -- used
// for the common case) or "METHOD /path" for a specific method, which
// takes priority (e.g. "POST /api/projects" vs the GET list route that
// shares the same path).
type Routes = Record<string, unknown>;

function setupFetch(overrides: Routes = {}) {
  const routes: Routes = {
    "/api/health": { status: "ok" },
    "/api/providers": { providers: ["ollama", "lmstudio", "openrouter"] },
    "GET /api/projects": { projects: ["demo"], active: "demo" },
    "/api/skills": { skills: [] },
    "/api/mcp/tools": { tools: [] },
    "/api/settings": {
      gateway: { provider: "ollama" },
      ollama: { host: "http://localhost:11434", model: "qwen3" },
      lmstudio: { host: "http://localhost:1234/v1", model: "local-model" },
      openrouter: { host: "https://openrouter.ai/api/v1", model: "openrouter/auto", api_key_set: false },
    },
    "POST /api/projects": { name: "demo", path: "/projects/demo" },
    ...overrides,
  };

  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();

    const candidates = Object.keys(routes)
      .map((key) => {
        const [maybeMethod, ...rest] = key.split(" ");
        const hasMethod = rest.length > 0;
        const path = hasMethod ? rest.join(" ") : key;
        const methodMatches = hasMethod ? maybeMethod === method : true;
        return { key, path, hasMethod, methodMatches };
      })
      .filter((c) => c.methodMatches && url.includes(c.path))
      // prefer method-specific routes, then longest path match
      .sort((a, b) => Number(b.hasMethod) - Number(a.hasMethod) || b.path.length - a.path.length);

    const match = candidates[0];
    if (!match) {
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    }
    const body = routes[match.key];
    if (body instanceof Error) throw body;
    if (body && typeof body === "object" && "ok" in body) {
      return body as Response; // pre-shaped failure/response object, used as-is
    }
    return { ok: true, status: 200, json: async () => body } as Response;
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows the backend-unreachable screen when the health check fails", async () => {
    setupFetch({ "/api/health": new Error("connection refused") });
    render(<App />);
    await waitFor(() => expect(screen.getByText(/backend not reachable/i)).toBeInTheDocument());
  });

  it("loads the active project and shows it in the top bar and sidebar", async () => {
    setupFetch();
    render(<App />);
    // appears twice by design: TopBar breadcrumb + highlighted Sidebar entry
    await waitFor(() => expect(screen.getAllByText("demo")).toHaveLength(2));
    expect(screen.getByRole("button", { name: "demo" })).toBeInTheDocument();
  });

  it("sends a message over the socket scoped to the active project", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));

    const textbox = await screen.findByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "list files{Enter}");

    const socket = FakeWebSocket.instances[0];
    expect(socket.sent).toHaveLength(1);
    expect(JSON.parse(socket.sent[0])).toEqual({ message: "list files", project: "demo" });
  });

  it("renders stage events live and the final response when they arrive", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const textbox = await screen.findByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "list files{Enter}");

    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.emit({ type: "stage", stage: "intent", detail: "command (confidence=0.8)" });
    });
    await waitFor(() => expect(screen.getByText("command (confidence=0.8)")).toBeInTheDocument());

    act(() => {
      socket.emit({
        type: "final",
        response: "a.txt\nb.txt",
        needs_clarification: false,
        clarifying_question: "",
        iterations: 1,
      });
    });
    await waitFor(() => expect(screen.getByText(/a\.txt/)).toBeInTheDocument());
    expect(screen.getByText(/b\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/1 iteration\b/)).toBeInTheDocument();
  });

  it("renders a clarifying question distinctly from a normal answer", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const textbox = await screen.findByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "hmm{Enter}");

    const socket = FakeWebSocket.instances[0];
    act(() => {
      socket.emit({
        type: "final",
        response: "",
        needs_clarification: true,
        clarifying_question: "Which file did you mean?",
        iterations: 0,
      });
    });
    await waitFor(() => expect(screen.getByText("Clarification needed")).toBeInTheDocument());
    expect(screen.getByText("Which file did you mean?")).toBeInTheDocument();
  });

  it("stops the running indicator once the final event arrives", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const textbox = await screen.findByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "list files{Enter}");
    expect(screen.getByText("running")).toBeInTheDocument();

    act(() => {
      FakeWebSocket.instances[0].emit({
        type: "final",
        response: "done",
        needs_clarification: false,
        clarifying_question: "",
        iterations: 1,
      });
    });
    await waitFor(() => expect(screen.getByText("idle")).toBeInTheDocument());
  });

  it("shows connected once the socket opens", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    act(() => {
      FakeWebSocket.instances[0].onopen?.();
    });
    await waitFor(() => expect(screen.getByText("connected")).toBeInTheDocument());
  });

  it("disables the input instead of alerting when no project is active (no window.alert)", async () => {
    setupFetch({ "GET /api/projects": { projects: [], active: null } });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    render(<App />);
    await waitFor(() => expect(screen.getAllByText(/create or select a project/i).length).toBeGreaterThan(0));
    expect(screen.getByPlaceholderText(/create or select a project/i)).toBeDisabled();
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it("shows a dismissible error banner when creating a project fails, instead of failing silently", async () => {
    setupFetch({
      "GET /api/projects": { projects: [], active: null },
      "POST /api/projects": { ok: false, status: 400, json: async () => ({ detail: "name already exists" }) },
    });
    render(<App />);
    await waitFor(() => expect(screen.getAllByText(/create or select a project/i).length).toBeGreaterThan(0));

    vi.spyOn(window, "prompt").mockReturnValue("demo");
    await userEvent.click(screen.getByText("+ New project"));

    await waitFor(() => expect(screen.getByText(/couldn't create project/i)).toBeInTheDocument());

    await userEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByText(/couldn't create project/i)).not.toBeInTheDocument();
  });

  it("shows an error banner when switching projects fails", async () => {
    setupFetch({
      "GET /api/projects": { projects: ["demo", "other"], active: "demo" },
      "POST /api/projects/other/activate": { ok: false, status: 404, json: async () => ({}) },
    });
    render(<App />);
    await waitFor(() => expect(screen.getAllByText("demo")).toHaveLength(2));

    await userEvent.click(screen.getByRole("button", { name: "other" }));
    await waitFor(() => expect(screen.getByText(/couldn't switch to project/i)).toBeInTheDocument());
  });

  it("accumulates token usage and cost across the session and shows them in the status bar", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const textbox = await screen.findByPlaceholderText(/ask igris/i);

    await userEvent.type(textbox, "list files{Enter}");
    act(() => {
      FakeWebSocket.instances[0].emit({
        type: "final",
        response: "first response",
        needs_clarification: false,
        clarifying_question: "",
        iterations: 1,
        prompt_tokens: 200,
        completion_tokens: 40,
        cost_usd: 0,
      });
    });
    await waitFor(() => expect(screen.getByText("240")).toBeInTheDocument());

    // a second run should ADD to the running total, not replace it
    await userEvent.type(textbox, "list files again{Enter}");
    act(() => {
      FakeWebSocket.instances[0].emit({
        type: "final",
        response: "second response",
        needs_clarification: false,
        clarifying_question: "",
        iterations: 1,
        prompt_tokens: 100,
        completion_tokens: 20,
        cost_usd: 0,
      });
    });
    await waitFor(() => expect(screen.getByText("360")).toBeInTheDocument()); // 240 + 120
  });

  it("does not crash or show NaN if a final event is missing token fields", async () => {
    setupFetch();
    render(<App />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const textbox = await screen.findByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "list files{Enter}");

    act(() => {
      // simulates an older/mismatched server response missing the new fields
      FakeWebSocket.instances[0].emit({
        type: "final",
        response: "done",
        needs_clarification: false,
        clarifying_question: "",
        iterations: 1,
      });
    });

    await waitFor(() => expect(screen.getByText("done")).toBeInTheDocument());
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });
});
