import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatusBar from "../StatusBar";

const base = { provider: "ollama", model: "qwen3", lastIterations: null, promptTokens: 0, completionTokens: 0, costUsd: 0, running: false };

describe("StatusBar", () => {
  it("shows provider and model", () => {
    render(<StatusBar {...base} />);
    expect(screen.getByText("ollama")).toBeInTheDocument();
    expect(screen.getByText("qwen3")).toBeInTheDocument();
  });

  it("hides the last-run line until a run has happened", () => {
    render(<StatusBar {...base} />);
    expect(screen.queryByText(/last run/)).not.toBeInTheDocument();
  });

  it("shows iteration count with correct singular/plural after a run", () => {
    const { rerender } = render(<StatusBar {...base} lastIterations={1} />);
    expect(screen.getByText(/1 iteration\b/)).toBeInTheDocument();

    rerender(<StatusBar {...base} lastIterations={3} />);
    expect(screen.getByText(/3 iterations/)).toBeInTheDocument();
  });

  it("shows running vs idle", () => {
    const { rerender } = render(<StatusBar {...base} running={true} />);
    expect(screen.getByText("running")).toBeInTheDocument();

    rerender(<StatusBar {...base} running={false} />);
    expect(screen.getByText("idle")).toBeInTheDocument();
  });

  it("hides tokens/cost until any tokens have been used", () => {
    render(<StatusBar {...base} />);
    expect(screen.queryByText(/tokens:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/cost:/)).not.toBeInTheDocument();
  });

  it("shows total tokens (prompt + completion) once a run has happened", () => {
    render(<StatusBar {...base} promptTokens={200} completionTokens={40} />);
    expect(screen.getByText(/tokens:/)).toBeInTheDocument();
    expect(screen.getByText("240")).toBeInTheDocument();
  });

  it("shows $0.00 for a free local provider even with real token usage", () => {
    render(<StatusBar {...base} promptTokens={200} completionTokens={40} costUsd={0} />);
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  it("shows a formatted dollar cost for a paid provider", () => {
    render(<StatusBar {...base} provider="openrouter" promptTokens={1000} completionTokens={500} costUsd={0.0234} />);
    expect(screen.getByText("$0.02")).toBeInTheDocument();
  });

  it("shows <$0.01 instead of rounding a tiny nonzero cost down to $0.00", () => {
    render(<StatusBar {...base} provider="openrouter" promptTokens={100} completionTokens={20} costUsd={0.0004} />);
    expect(screen.getByText("<$0.01")).toBeInTheDocument();
  });
});
