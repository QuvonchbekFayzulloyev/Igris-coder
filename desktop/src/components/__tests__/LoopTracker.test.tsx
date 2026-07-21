import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LoopTracker from "../LoopTracker";

describe("LoopTracker", () => {
  it("shows a hint when there are no events and nothing is running", () => {
    render(<LoopTracker events={[]} running={false} />);
    expect(screen.getByText(/watch the reprompt loop run/i)).toBeInTheDocument();
  });

  it("renders each stage event with its friendly label and detail", () => {
    render(
      <LoopTracker
        events={[
          { stage: "snapshot", detail: "cwd=/home/user/project" },
          { stage: "intent", detail: "code_task (confidence=0.8)" },
        ]}
        running={false}
      />
    );
    expect(screen.getByText("Snapshot")).toBeInTheDocument();
    expect(screen.getByText("cwd=/home/user/project")).toBeInTheDocument();
    expect(screen.getByText("Intent")).toBeInTheDocument();
    expect(screen.getByText("code_task (confidence=0.8)")).toBeInTheDocument();
  });

  it("maps attempt_N and review_N stages to friendly labels", () => {
    render(
      <LoopTracker
        events={[
          { stage: "attempt_1", detail: "120 chars" },
          { stage: "review_1", detail: "pass=false" },
          { stage: "attempt_2", detail: "180 chars" },
        ]}
        running={false}
      />
    );
    expect(screen.getByText("Attempt 1")).toBeInTheDocument();
    // review_1 has an explicit label mapping ("Review"); attempt_2 falls
    // through the generic "Attempt N" branch -- both should render.
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Attempt 2")).toBeInTheDocument();
  });

  it("shows a running indicator when running is true, even with no events yet", () => {
    render(<LoopTracker events={[]} running={true} />);
    expect(screen.getByText(/running/)).toBeInTheDocument();
  });

  it("does not show the empty-state hint once a run has started", () => {
    render(<LoopTracker events={[]} running={true} />);
    expect(screen.queryByText(/watch the reprompt loop run/i)).not.toBeInTheDocument();
  });
});
