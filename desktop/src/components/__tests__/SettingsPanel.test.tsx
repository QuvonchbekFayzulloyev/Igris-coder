import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import SettingsPanel from "../SettingsPanel";
import { api } from "../../lib/api";
import type { SettingsResponse } from "../../lib/types";

vi.mock("../../lib/api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
}));

const SETTINGS: SettingsResponse = {
  gateway: { provider: "ollama" },
  ollama: { host: "http://localhost:11434", model: "qwen3", temperature: 0.4 },
  lmstudio: { host: "http://localhost:1234/v1", model: "local-model" },
  openrouter: { host: "https://openrouter.ai/api/v1", model: "openrouter/auto", api_key_set: false },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSettings).mockResolvedValue(SETTINGS);
  vi.mocked(api.updateSettings).mockResolvedValue(SETTINGS);
});

describe("SettingsPanel", () => {
  it("shows a loading state, then the loaded values", async () => {
    render(<SettingsPanel project="demo" onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    expect(screen.getByDisplayValue("http://localhost:11434")).toBeInTheDocument();
  });

  it("marks the currently active provider", async () => {
    render(<SettingsPanel project="demo" onClose={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("active")).toBeInTheDocument());
    // "active" badge should be inside the Ollama card specifically
    const ollamaHeading = screen.getByText("Ollama");
    expect(ollamaHeading.parentElement).toHaveTextContent("active");
  });

  it("saves with the edited model and calls onSaved + onClose", async () => {
    const onClose = vi.fn();
    const onSaved = vi.fn();
    render(<SettingsPanel project="demo" onClose={onClose} onSaved={onSaved} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());

    const modelField = screen.getByDisplayValue("qwen3");
    await userEvent.clear(modelField);
    await userEvent.type(modelField, "qwen2.5-coder:7b");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateSettings).toHaveBeenCalled());
    const payload = vi.mocked(api.updateSettings).mock.calls.at(-1)![1];
    expect(payload.ollama?.model).toBe("qwen2.5-coder:7b");
    expect(onSaved).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("does not include api_key in the payload when the field is left blank", async () => {
    render(<SettingsPanel project="demo" onClose={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateSettings).toHaveBeenCalled());
    const payload = vi.mocked(api.updateSettings).mock.calls.at(-1)![1];
    expect(payload.openrouter).not.toHaveProperty("api_key");
  });

  it("includes api_key in the payload when the user types one", async () => {
    render(<SettingsPanel project="demo" onClose={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());

    const keyField = screen.getByPlaceholderText("sk-or-...");
    await userEvent.type(keyField, "sk-test-abc");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateSettings).toHaveBeenCalled());
    const payload = vi.mocked(api.updateSettings).mock.calls.at(-1)![1];
    expect(payload.openrouter?.api_key).toBe("sk-test-abc");
  });

  it("shows 'saved' wording and a masked placeholder when a key is already set", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      ...SETTINGS,
      openrouter: { ...SETTINGS.openrouter, api_key_set: true },
    });
    render(<SettingsPanel project="demo" onClose={vi.fn()} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/saved.*leave blank/i)).toBeInTheDocument());
  });

  it("shows an error and does not close when saving fails", async () => {
    vi.mocked(api.updateSettings).mockRejectedValue(new Error("network error"));
    const onClose = vi.fn();
    render(<SettingsPanel project="demo" onClose={onClose} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText(/network error/)).toBeInTheDocument());
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose when Cancel is clicked without saving", async () => {
    const onClose = vi.fn();
    render(<SettingsPanel project="demo" onClose={onClose} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(api.updateSettings).not.toHaveBeenCalled();
  });

  it("calls onClose when Escape is pressed", async () => {
    const onClose = vi.fn();
    render(<SettingsPanel project="demo" onClose={onClose} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("removes its Escape listener on unmount (doesn't leak across re-renders)", async () => {
    const onClose = vi.fn();
    const { unmount } = render(<SettingsPanel project="demo" onClose={onClose} onSaved={vi.fn()} />);
    await waitFor(() => expect(screen.getByDisplayValue("qwen3")).toBeInTheDocument());
    unmount();
    await userEvent.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });
});
