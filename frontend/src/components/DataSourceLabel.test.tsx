import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataSourceLabelChip, LabelLegend } from "./DataSourceLabel";

describe("DataSourceLabelChip", () => {
  it("maps known labels to visible chips", () => {
    render(
      <div>
        <DataSourceLabelChip label="derived" />
        <DataSourceLabelChip label="forecast" />
        <DataSourceLabelChip label="synthetic" />
        <DataSourceLabelChip label="simulated" />
        <DataSourceLabelChip label="simulated/illustrative" />
      </div>,
    );
    expect(screen.getByText("derived")).toBeTruthy();
    expect(screen.getByText("forecast (estimated)")).toBeTruthy();
    expect(screen.getByText("synthetic data")).toBeTruthy();
    expect(screen.getByText("simulated")).toBeTruthy();
    expect(screen.getByText("simulated/illustrative")).toBeTruthy();
  });

  it("renders unknown labels honestly instead of inventing a mapping", () => {
    render(<DataSourceLabelChip label="user-provided" />);
    expect(screen.getByText("user-provided")).toBeTruthy();
  });
});

describe("LabelLegend", () => {
  it("renders the always-visible label legend", () => {
    render(<LabelLegend />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("Data labels:");
    expect(text).toContain("derived");
    expect(text).toContain("simulated");
  });
});
