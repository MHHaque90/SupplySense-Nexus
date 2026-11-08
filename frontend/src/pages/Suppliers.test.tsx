import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { endpoints } from "../api/endpoints";
import { SuppliersBody } from "./Suppliers";
import type { Paginated, SupplierRow } from "../api/types";

function mockSuppliers(page: number, pageSize: number): Paginated<SupplierRow> {
  const allSuppliers: SupplierRow[] = [
    { supplier_id: "sup-001", supplier_name: "Apex Global", country: "US", rating: 4.5 },
    { supplier_id: "sup-002", supplier_name: "Beacon Corp", country: "CA", rating: 4.2 },
    { supplier_id: "sup-003", supplier_name: "Crest Logistics", country: "MX", rating: 3.8 },
    { supplier_id: "sup-004", supplier_name: "Delta Dynamics", country: "DE", rating: 4.9 },
    { supplier_id: "sup-005", supplier_name: "Echo Enterprises", country: "JP", rating: 4.1 },
    { supplier_id: "sup-006", supplier_name: "Falcon Freight", country: "UK", rating: 3.9 },
    { supplier_id: "sup-007", supplier_name: "Giga Source", country: "SG", rating: 4.4 },
    { supplier_id: "sup-008", supplier_name: "Horizon Supplies", country: "KR", rating: 4.7 },
  ];
  const start = (page - 1) * pageSize;
  const items = allSuppliers.slice(start, start + pageSize);
  return {
    items,
    total: allSuppliers.length,
    page,
    page_size: pageSize,
    has_next: start + pageSize < allSuppliers.length,
  };
}

describe("Suppliers pagination", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads initial page with 5 items and active Next button", async () => {
    vi.spyOn(endpoints, "suppliers").mockImplementation(async (page = 1, pageSize = 5) => ({
      data: mockSuppliers(page, pageSize),
      meta: { timestamp: "2026-10-25T00:00:00Z", data_source_label: "synthetic" },
    }));

    vi.spyOn(endpoints, "supplierPerformance").mockResolvedValue({
      data: { items: [], total: 0, page: 1, page_size: 10, has_next: false },
      meta: { timestamp: "2026-10-25T00:00:00Z", data_source_label: "synthetic", limitations: [] },
    });

    render(<SuppliersBody />);

    expect(await screen.findByText("Apex Global")).toBeDefined();
    expect(screen.getByText("Echo Enterprises")).toBeDefined();
    expect(screen.queryByText("Falcon Freight")).toBeNull();

    const nextBtn = screen.getByRole("button", { name: "Next ›" });
    const prevBtn = screen.getByRole("button", { name: "‹ Prev" });
    expect((prevBtn as HTMLButtonElement).disabled).toBe(true);
    expect((nextBtn as HTMLButtonElement).disabled).toBe(false);

    // Click Next
    await act(async () => {
      nextBtn.click();
    });

    expect(await screen.findByText("Falcon Freight")).toBeDefined();
    expect(screen.getByText("Horizon Supplies")).toBeDefined();
    expect(screen.queryByText("Apex Global")).toBeNull();
    expect((prevBtn as HTMLButtonElement).disabled).toBe(false);
    expect((nextBtn as HTMLButtonElement).disabled).toBe(true);

    // Click Prev
    await act(async () => {
      prevBtn.click();
    });

    expect(await screen.findByText("Apex Global")).toBeDefined();
    expect((prevBtn as HTMLButtonElement).disabled).toBe(true);
    expect((nextBtn as HTMLButtonElement).disabled).toBe(false);
  });
});
