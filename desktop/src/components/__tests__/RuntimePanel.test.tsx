import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import RuntimePanel from "../RuntimePanel";

describe("RuntimePanel", () => {
  it("renders the Loop tracker with events", () => {
    render(
      <RuntimePanel events={[{ stage: "intent", detail: "code_task (confidence=0.8)" }]} running={false} />
    );
    expect(screen.getByText("Intent")).toBeInTheDocument();
  });

  it("Context and Logs sections start collapsed", () => {
    render(
      <RuntimePanel events={[{ stage: "snapshot", detail: "cwd=/tmp/x" }]} running={false} />
    );
    // the LoopTracker at the top legitimately shows this detail already;
    // collapsed Context/Logs sections must not duplicate it a second time
    expect(screen.getAllByText("cwd=/tmp/x")).toHaveLength(1);
  });

  it("expands Context on click and shows the latest snapshot/gather detail", async () => {
    render(
      <RuntimePanel
        events={[
          { stage: "snapshot", detail: "cwd=/tmp/proj" },
          { stage: "gather", detail: "git_status (40 chars)" },
        ]}
        running={false}
      />
    );
    await userEvent.click(screen.getByText("Context"));
    // now appears twice: once in the LoopTracker, once in the expanded Context section
    expect(screen.getAllByText("cwd=/tmp/proj")).toHaveLength(2);
    expect(screen.getAllByText("git_status (40 chars)")).toHaveLength(2);
  });

  it("expands Logs on click and shows every stage event with a bracketed tag", async () => {
    render(
      <RuntimePanel
        events={[
          { stage: "intent", detail: "code_task" },
          { stage: "spec", detail: "2 acceptance criteria synthesized" },
        ]}
        running={false}
      />
    );
    await userEvent.click(screen.getByText("Logs"));
    expect(screen.getByText("[intent]", { exact: false })).toBeInTheDocument();
    // appears twice: once in the LoopTracker, once in the expanded Logs entry
    expect(screen.getAllByText(/2 acceptance criteria synthesized/)).toHaveLength(2);
  });

  it("Context section shows a placeholder when nothing has been gathered yet", async () => {
    render(<RuntimePanel events={[]} running={false} />);
    await userEvent.click(screen.getByText("Context"));
    expect(screen.getAllByText("(none yet)").length).toBe(2); // snapshot + gathered
  });
});
