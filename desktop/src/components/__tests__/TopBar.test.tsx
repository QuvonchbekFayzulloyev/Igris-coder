import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import TopBar from "../TopBar";

describe("TopBar", () => {
  const defaults = { view: "chat" as const, onToggleView: vi.fn() };

  it("shows the project name when one is active", () => {
    render(<TopBar projectName="my-app" connected={true} {...defaults} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("my-app")).toBeInTheDocument();
  });

  it("does not render a project segment when no project is active", () => {
    render(<TopBar projectName={null} connected={true} {...defaults} onOpenSettings={vi.fn()} />);
    expect(screen.queryByText("/")).not.toBeInTheDocument();
  });

  it("shows connected vs disconnected status text", () => {
    const { rerender } = render(<TopBar projectName="x" connected={true} {...defaults} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("connected")).toBeInTheDocument();

    rerender(<TopBar projectName="x" connected={false} {...defaults} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("disconnected")).toBeInTheDocument();
  });

  it("calls onOpenSettings when the Settings button is clicked", async () => {
    const onOpenSettings = vi.fn();
    render(<TopBar projectName="x" connected={true} {...defaults} onOpenSettings={onOpenSettings} />);
    await userEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it("calls onToggleView when the toggle button is clicked", async () => {
    const onToggleView = vi.fn();
    render(<TopBar projectName="x" connected={true} view="chat" onToggleView={onToggleView} onOpenSettings={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(onToggleView).toHaveBeenCalledTimes(1);
  });

  it("shows Chat label when preview is active", () => {
    render(<TopBar projectName="x" connected={true} view="preview" onToggleView={vi.fn()} onOpenSettings={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Chat" })).toBeInTheDocument();
  });
});
