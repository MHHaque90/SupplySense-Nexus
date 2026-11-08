import { render, screen } from "@testing-library/react";
import { ApiError } from "../api/client";
import { describe, expect, it } from "vitest";
import { EmptyState, ErrorState, Limitations, LoadingState, UnavailableState } from "./StateViews";

describe("honest state views", () => {
  it("loading explains what is being fetched", () => {
    render(<LoadingState message="Loading dashboard overview (KPI families + risk snapshot)…" />);
    expect(screen.getByText(/Loading dashboard overview/i)).toBeTruthy();
  });

  it("empty states show the filter context instead of fake data", () => {
    render(<EmptyState what="risk records" hint="with filters active" />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("No risk records available from the API");
    expect(text).toContain("with filters active");
    expect(text).toContain("the UI never invents values");
  });

  it("error prefers the server-provided reason", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "validation failed", {
      details: { reason: "MIN_HORZ: horizon must be >= 1" },
    });
    render(<ErrorState error={error} what="the simulation" />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("MIN_HORZ: horizon must be >= 1");
    expect(text).toContain("VALIDATION_ERROR");
    expect(text).toContain("HTTP 422");
  });

  it("rate-limit errors surface Retry-After", () => {
    const error = new ApiError(429, "RATE_LIMIT_EXCEEDED", "rate limited", { retryAfter: 37 });
    render(<ErrorState error={error} what="the simulation" />);
    expect(document.body.textContent).toContain("Try again in 37 seconds");
  });

  it("unavailable capability keeps its reasons visible", () => {
    const reasons = ["No LLM provider is configured.", "The backend reports this feature as disabled."];
    render(<UnavailableState title="AI copilot reasoning" reasons={reasons} />);
    expect(document.body.textContent).toContain("AI copilot reasoning is not available");
    expect(screen.getByText(reasons[0]!)).toBeTruthy();
  });

  it("limitations render verbatim from the API", () => {
    render(<Limitations items={["Forecasts are simulated.", "No ranking is performed."]} />);
    expect(screen.getByText("Forecasts are simulated.")).toBeTruthy();
    expect(screen.getByText("No ranking is performed.")).toBeTruthy();
  });

  it("no limitations means no panel", () => {
    const { container } = render(<Limitations items={[]} />);
    expect(container.querySelector(".limitations-panel")).toBeNull();
  });
});
