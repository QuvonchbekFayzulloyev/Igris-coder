import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Conversation from "../Conversation";
import type { ConversationMessage } from "../../lib/types";

const msg = (role: ConversationMessage["role"], content: string): ConversationMessage => ({
  id: `${role}-${content}`,
  role,
  content,
  timestamp: Date.now(),
});

describe("Conversation", () => {
  it("shows an empty-state hint with no messages", () => {
    render(<Conversation messages={[]} onSend={vi.fn()} running={false} />);
    expect(screen.getByText(/describe a task/i)).toBeInTheDocument();
  });

  it("renders user and assistant messages", () => {
    render(
      <Conversation
        messages={[msg("user", "list files"), msg("assistant", "a.txt, b.txt")]}
        onSend={vi.fn()}
        running={false}
      />
    );
    expect(screen.getByText("list files")).toBeInTheDocument();
    expect(screen.getByText("a.txt, b.txt")).toBeInTheDocument();
  });

  it("labels clarify messages distinctly", () => {
    render(
      <Conversation messages={[msg("clarify", "Which file did you mean?")]} onSend={vi.fn()} running={false} />
    );
    expect(screen.getByText("Clarification needed")).toBeInTheDocument();
    expect(screen.getByText("Which file did you mean?")).toBeInTheDocument();
  });

  it("sends the draft and clears the input on Send click", async () => {
    const onSend = vi.fn();
    render(<Conversation messages={[]} onSend={onSend} running={false} />);
    const textbox = screen.getByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "hello igris");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("hello igris");
    expect(textbox).toHaveValue("");
  });

  it("sends on Enter but not on Shift+Enter", async () => {
    const onSend = vi.fn();
    render(<Conversation messages={[]} onSend={onSend} running={false} />);
    const textbox = screen.getByPlaceholderText(/ask igris/i);

    await userEvent.type(textbox, "line one{Shift>}{Enter}{/Shift}line two");
    expect(onSend).not.toHaveBeenCalled();
    expect(textbox).toHaveValue("line one\nline two");

    await userEvent.type(textbox, "{Enter}");
    expect(onSend).toHaveBeenCalledWith("line one\nline two");
  });

  it("does not send an empty or whitespace-only draft", async () => {
    const onSend = vi.fn();
    render(<Conversation messages={[]} onSend={onSend} running={false} />);
    const textbox = screen.getByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "   ");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the Send button while running", () => {
    render(<Conversation messages={[]} onSend={vi.fn()} running={true} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("does not call onSend on Enter while running", async () => {
    const onSend = vi.fn();
    const { rerender } = render(<Conversation messages={[]} onSend={onSend} running={false} />);
    const textbox = screen.getByPlaceholderText(/ask igris/i);
    await userEvent.type(textbox, "hello");
    rerender(<Conversation messages={[]} onSend={onSend} running={true} />);
    await userEvent.type(textbox, "{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows the disabled reason as a hint and placeholder, and disables input/button", () => {
    render(
      <Conversation messages={[]} onSend={vi.fn()} running={false} disabledReason="Create or select a project to start." />
    );
    // shown twice by design: once as the empty-state body, once as the input-area hint
    expect(screen.getAllByText("Create or select a project to start.")).toHaveLength(2);
    expect(screen.getByPlaceholderText("Create or select a project to start.")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("never calls onSend while disabledReason is set, even via Enter", async () => {
    const onSend = vi.fn();
    render(
      <Conversation messages={[]} onSend={onSend} running={false} disabledReason="Create or select a project to start." />
    );
    const textbox = screen.getByPlaceholderText("Create or select a project to start.");
    // disabled textareas don't accept typed input in a real browser, but
    // guard the handler itself too in case a caller drives it programmatically
    await userEvent.type(textbox, "hello{Enter}", { skipClick: true }).catch(() => {});
    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows the disabled reason instead of the normal empty-state hint when there are no messages", () => {
    render(
      <Conversation messages={[]} onSend={vi.fn()} running={false} disabledReason="Create or select a project to start." />
    );
    expect(screen.queryByText(/describe a task/i)).not.toBeInTheDocument();
  });
});
