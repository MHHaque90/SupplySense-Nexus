import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { DataTable, Pagination, usePager } from "../components/DataTable";
import { FilterBar, Section, SelectInput, ShortId } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { SupplierPerformanceRow } from "../api/types";

/**
 * Suppliers — directory (GET /suppliers) + per-supplier descriptive fact sheet
 * (GET /suppliers/performance?supplier_id=…). Facts only; the API does not
 * rank, score or recommend suppliers and the UI reflects that.
 */
export function SuppliersPage() {
  return (
    <PageGate>
      <SuppliersBody />
    </PageGate>
  );
}

const SUPPLIERS_PAGE_SIZE = 5;

export function SuppliersBody() {
  /* Directory: paginated (page owned by the UI; page size 5 so pagination is active). */
  const [page, setPage] = usePager();
  const dir = useApiQuery(() => endpoints.suppliers(page, SUPPLIERS_PAGE_SIZE), [page]);
  const [supplierId, setSupplierId] = useState("");

  const selected =
    supplierId !== ""
      ? supplierId
      : dir.status === "ok"
        ? (dir.data.items[0]?.supplier_id ?? "")
        : "";

  const perf = useApiQuery(
    () => endpoints.supplierPerformance({ supplier_id: selected, page_size: 10 }),
    [selected],
    { enabled: selected !== "" },
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Suppliers</h1>
        <span className="muted">Directory and descriptive performance facts — no ranking or scoring is computed</span>
        <DataSourceLabelChip label="synthetic" />
      </div>

      <Section title="Supplier directory" subtitle="Deduplicated supplier parties observed in purchase orders">
        {dir.status === "loading" ? <LoadingState message="Loading suppliers…" /> : null}
        {dir.status === "error" ? <ErrorState error={dir.error} what="the supplier directory" /> : null}
        {dir.status === "empty" ? <EmptyState what="suppliers" /> : null}
        {dir.status === "ok" ? (
          <>
            <FilterBar>
              <SelectInput
                label="Supplier"
                value={selected || ""}
                options={[{ value: "", label: "— select supplier —" },
                  ...dir.data.items.map((s) => ({ value: s.supplier_id, label: `${s.supplier_name} (${s.country})` }))]}
                onChange={setSupplierId}
              />
              {selected ? <span className="muted small mono">{selected}</span> : (
                <span className="muted small">Select a supplier to load its performance facts.</span>
              )}
            </FilterBar>
            <DataTable
              columns={[
                { header: "Supplier", render: (s: (typeof dir.data.items)[0]) => <strong>{s.supplier_name}</strong> },
                { header: "ID", render: (s) => <ShortId id={s.supplier_id} /> },
                { header: "Country", render: (s) => s.country },
                { header: "Rating (recorded)", render: (s) => (s.rating === null ? "—" : s.rating.toFixed(2)) },
              ]}
              rows={dir.data.items}
            />
            <Pagination page={dir.data.page} pageSize={dir.data.page_size} total={dir.data.total} hasNext={dir.data.has_next} onPage={setPage} />
          </>
        ) : null}
      </Section>

      {selected !== "" ? (
        <Section title="Performance fact sheet" subtitle="Descriptive delivery and lead-time evidence at the analysis date. Facts only — the system never ranks suppliers.">
          {perf.status === "loading" ? <LoadingState message="Loading performance facts…" /> : null}
          {perf.status === "error" ? <ErrorState error={perf.error} what="supplier performance" /> : null}
          {perf.status === "empty" ? <EmptyState what="performance facts for the selected supplier" hint="The API returned no rows — the supplier may have no purchase-order history yet." /> : null}
          {perf.status === "ok" ? (
            <>
              <DataTable
                columns={[
                  { header: "Metric", render: (row: [string, string]) => <strong>{row[0]}</strong> },
                  { header: "Value", render: (row) => <span className="mono">{row[1]}</span> },
                ]}
                rows={factRows(perf.data.items)}
              />
              {perf.data.items[0]?.missing_evidence.length ? (
                <LimitationsWithRows items={perf.data.items[0]!.missing_evidence} />
              ) : null}
              <Limitations items={perf.meta.limitations} />
            </>
          ) : null}
        </Section>
      ) : null}
    </div>
  );
}

function LimitationsWithRows({ items }: { items: string[] }) {
  return (
    <div className="limitations-panel" style={{ marginTop: 10 }}>
      <p className="limitations-title">Missing evidence (from API)</p>
      <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

function factRows(rows: SupplierPerformanceRow[]): [string, string][] {
  if (rows.length === 0) return [];
  const r = rows[0]!;
  const variants: ([string, string] | null)[] = [
    ["Purchase orders", fmt(r.po_count, "")],
    ["Purchase-order lines", fmt(r.po_line_count, "")],
    ["Ordered quantity", fmt(r.ordered_quantity, "units")],
    ["Received quantity", fmt(r.received_quantity, "units")],
    ["Shipments", fmt(r.shipment_count, "")],
    ["Completed shipments", fmt(r.completed_shipments, "")],
    ["On-time shipments", fmt(r.on_time_shipments, "")],
    ["Late shipments", fmt(r.late_shipments, "")],
    ["On-time rate", fmt(r.on_time_rate, "share")],
    ["Average delay", fmt(r.average_delay_days, "days")],
    ["Median delay", fmt(r.median_delay_days, "days")],
    ["Max delay", fmt(r.max_delay_days, "days")],
    ["Average lead time", fmt(r.average_lead_time_days, "days")],
    ["Median lead time", fmt(r.median_lead_time_days, "days")],
    ["Lead-time range", `${r.min_lead_time_days ?? "?"}–${r.max_lead_time_days ?? "?"} days (std ${r.lead_time_std ?? "?"})`],
  ];
  return variants.filter((v): v is [string, string] => v !== null);
}

function fmt(value: unknown, unit: string): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") {
    const s = Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
    return unit ? `${s} ${unit}` : s;
  }
  return String(value);
}
