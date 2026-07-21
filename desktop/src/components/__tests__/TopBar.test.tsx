import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import TopBar from "../TopBar";

describe("TopBar", () => {
  it("shows the project name when one is active", () => {
    render(<TopBar projectName="my-app" connected={true} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("my-app")).toBeInTheDocument();
  });

  it("does not render a project segment when no project is active", () => {
    render(<TopBar projectName={null} connected={true} onOpenSettings={vi.fn()} />);
    expect(screen.queryByText("/")).not.toBeInTheDocument();
  });

  it("shows connected vs disconnected status text", () => {
    const { rerender } = render(<TopBar projectName="x" connected={true} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("connected")).toBeInTheDocument();

    rerender(<TopBar projectName="x" connected={false} onOpenSettings={vi.fn()} />);
    expect(screen.getByText("disconnected")).toBeInTheDocument();
  });

  it("calls onOpenSettings when the Settings button is clicked", async () => {
    const onOpenSettings = vi.fn();
    render(<TopBar projectName="x" connected={true} onOpenSettings={onOpenSettings} />);
    await userEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });
});
