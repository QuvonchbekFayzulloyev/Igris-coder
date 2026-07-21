import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Sidebar from "../Sidebar";

const baseProps = {
  projects: ["alpha", "beta"],
  activeProject: "alpha",
  onSelectProject: vi.fn(),
  onCreateProject: vi.fn(),
  skills: [
    { name: "intent-resolver", description: "", pipeline_stage: "Planning", triggers: [] },
  ],
  mcpTools: ["filesystem.read_file", "terminal.run_command"],
  providers: ["ollama", "lmstudio", "openrouter"],
  selectedProvider: "ollama",
  onSelectProvider: vi.fn(),
};

describe("Sidebar", () => {
  it("lists all projects and highlights the active one", () => {
    render(<Sidebar {...baseProps} />);
    const alphaBtn = screen.getByRole("button", { name: "alpha" });
    const betaBtn = screen.getByRole("button", { name: "beta" });
    expect(alphaBtn).toBeInTheDocument();
    expect(betaBtn).toBeInTheDocument();
    // active project gets the highlighted class; inactive doesn't
    expect(alphaBtn.className).toMatch(/text-blue/);
    expect(betaBtn.className).not.toMatch(/text-blue/);
  });

  it("calls onSelectProject when a project button is clicked", async () => {
    const onSelectProject = vi.fn();
    render(<Sidebar {...baseProps} onSelectProject={onSelectProject} />);
    await userEvent.click(screen.getByRole("button", { name: "beta" }));
    expect(onSelectProject).toHaveBeenCalledWith("beta");
  });

  it("shows a placeholder when there are no projects", () => {
    render(<Sidebar {...baseProps} projects={[]} activeProject={null} />);
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
  });

  it("shows a loading placeholder instead of 'No projects yet' during the initial fetch", () => {
    render(<Sidebar {...baseProps} projects={[]} activeProject={null} projectsLoading={true} />);
    expect(screen.getByText("Loading projects\u2026")).toBeInTheDocument();
    expect(screen.queryByText("No projects yet")).not.toBeInTheDocument();
  });

  it("prefers the real project list over the loading placeholder once data arrives", () => {
    render(<Sidebar {...baseProps} projectsLoading={true} />);
    expect(screen.queryByText("Loading projects\u2026")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "alpha" })).toBeInTheDocument();
  });

  it("prompts for a name and calls onCreateProject when confirmed", async () => {
    const onCreateProject = vi.fn();
    vi.spyOn(window, "prompt").mockReturnValue("gamma");
    render(<Sidebar {...baseProps} onCreateProject={onCreateProject} />);
    await userEvent.click(screen.getByText("+ New project"));
    expect(onCreateProject).toHaveBeenCalledWith("gamma");
  });

  it("does not call onCreateProject if the prompt is cancelled", async () => {
    const onCreateProject = vi.fn();
    vi.spyOn(window, "prompt").mockReturnValue(null);
    render(<Sidebar {...baseProps} onCreateProject={onCreateProject} />);
    await userEvent.click(screen.getByText("+ New project"));
    expect(onCreateProject).not.toHaveBeenCalled();
  });

  it("renders skills with their pipeline stage badge", () => {
    render(<Sidebar {...baseProps} />);
    expect(screen.getByText("intent-resolver")).toBeInTheDocument();
    expect(screen.getByText("Planning")).toBeInTheDocument();
  });

  it("renders MCP tool names", () => {
    render(<Sidebar {...baseProps} />);
    expect(screen.getByText("filesystem.read_file")).toBeInTheDocument();
    expect(screen.getByText("terminal.run_command")).toBeInTheDocument();
  });

  it("calls onSelectProvider when the provider dropdown changes", async () => {
    const onSelectProvider = vi.fn();
    render(<Sidebar {...baseProps} onSelectProvider={onSelectProvider} />);
    await userEvent.selectOptions(screen.getByDisplayValue("ollama"), "lmstudio");
    expect(onSelectProvider).toHaveBeenCalledWith("lmstudio");
  });
});
