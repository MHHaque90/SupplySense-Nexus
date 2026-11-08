import { useState } from "react";
import { DataSourceLabelChip as Chip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { DataTable, Pagination, usePager } from "../components/DataTable";
import { FilterBar, KpiCard, Section, SeverityChip, ShortId, TextInput } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { KpiMetric } from "../api/types";

/**
 * Inventory — GET /inventory/overview (KPI summary),
 * GET /inventory/positions and GET /inventory/health (paginated tables).
 * All descriptive, data_source_label = synthetic.
 */
export function InventoryPage() {
  return (
    <PageGate>
      <InventoryBody />
    </PageGate>
  );
}

type Tab = "summary" | "positions" | "health";

function InventoryBody() {
  const [tab, setTab] = useState<Tab>("summary");
  return (
    <div className="page">
      <div className="page-header">
        <h1>Inventory</h1>
        <span className="muted">Descriptive positions, movement and rule-based health states</span>
        <Chip label="synthetic" />
      </div>
      <FilterBar>
        <SelectTab value={tab} onChange={setTab} />
      </FilterBar>
      {tab === "summary" ? <SummaryTab /> : null}
      {tab === "positions" ? <PositionsTab /> : null}
      {tab === "health" ? <HealthTab /> : null}
    </div>
  );
}

function SelectTab({ value, onChange }: { value: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "summary", label: "KPI summary" },
    { id: "positions", label: "Positions" },
    { id: "health", label: "Health states" },
  ];
  return (
    <>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`nav-item${value === t.id ? " active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </>
  );
}

/* ---------------- summary tab ---------------- */

const SUMMARY_GROUPS: { key: string; title: string; subtitle: string; cards?: boolean }[] = [
  { key: "inventory_levels", title: "Inventory levels", subtitle: "Position counts derived from generated snapshot levels", cards: true },
  { key: "stockout_stats", title: "Stockout statistics", subtitle: "Historical zero-on-hand observations in the snapshot window", cards: true },
  { key: "movement_summary", title: "Movement summary", subtitle: "Receipts / adjustments / shipments over the window" },
  { key: "turnover_proxy", title: "Turnover proxy", subtitle: "Unit-based proxy — not a financial turnover measure" },
  { key: "days_of_supply", title: "Days of supply", subtitle: "Coverage implied by generated levels and demand" },
  { key: "service", title: "Service", subtitle: "Availability proxy from snapshots and sales orders" },
];

function SummaryTab() {
  const state = useApiQuery(() => endpoints.inventoryOverview(), []);
  if (state.status === "loading") return <LoadingState message="Loading inventory KPI families…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="inventory overview" />;
  if (state.status === "empty") return <EmptyState what="inventory KPI data" />;

  const { data, meta } = state;
  return (
    <>
      <div className="meta-row">
        <Chip label={meta.data_source_label} />
        <span className="muted">analysis date {data.analysis_date}</span>
      </div>
      {SUMMARY_GROUPS.map((group) => {
        const metrics = data.kpis[group.key as keyof typeof data.kpis] as KpiMetric[];
        return (
          <Section key={group.key} title={group.title} subtitle={group.subtitle}>
            {group.cards ? (
              <div className="kpi-grid">
                {metrics.map((m, i) => (
                  <KpiCard key={i} title={m.metric_name} value={m.value} unit={m.unit} note={m.notes || undefined} />
                ))}
              </div>
            ) : (
              <DataTable
                columns={[
                  { header: "Metric", render: (m: KpiMetric) => m.metric_name },
                  { header: "Value", render: (m: KpiMetric) => (m.value === null ? "n/a" : String(m.value)) },
                  { header: "Unit", render: (m: KpiMetric) => m.unit },
                  { header: "Formula", render: (m: KpiMetric) => <span className="mono small">{m.formula}</span> },
                ]}
                rows={metrics}
              />
            )}
          </Section>
        );
      })}
      <Limitations items={[...data.limitations, ...(meta.limitations ?? [])]} />
    </>
  );
}

/* ---------------- positions tab ---------------- */

function PositionsTab() {
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [page, setPage] = usePager();

  const state = useApiQuery(
    () =>
      endpoints.inventoryPositions({
        product_id: productId || undefined,
        warehouse_id: warehouseId || undefined,
        page,
        page_size: 15,
      }),
    [productId, warehouseId, page],
  );

  if (state.status === "loading") return <LoadingState message="Loading positions…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="inventory positions" />;
  if (state.status === "empty")
    return <EmptyState what="inventory positions" hint="No position rows match the current filters." />;

  const { data, meta } = state;
  return (
    <Section title={`Positions — ${data.total} series with snapshot evidence at ${data.analysis_date}`}>
      <FilterBar>
        <TextInput label="Product ID" value={productId} onChange={(v) => { setProductId(v); setPage(1); }} placeholder="blank = all" />
        <TextInput label="Warehouse ID" value={warehouseId} onChange={(v) => { setWarehouseId(v); setPage(1); }} placeholder="blank = all" />
      </FilterBar>
      <DataTable
        columns={[
          { header: "Product", render: (r: (typeof data.items)[0]) => <ShortId id={r.product_id} /> },
          { header: "Warehouse", render: (r) => <ShortId id={r.warehouse_id} /> },
          { header: "On hand", render: (r) => r.current_on_hand.toLocaleString() },
          { header: "Recent avg", render: (r) => r.recent_average.toFixed(1) },
          { header: "Recent min", render: (r) => r.recent_minimum.toFixed(1) },
          { header: "Recent max", render: (r) => r.recent_maximum.toFixed(1) },
          { header: "Volatility", render: (r) => r.recent_volatility.toFixed(2) },
          { header: "Inflow", render: (r) => r.recent_inflow.toFixed(1) },
          { header: "Outflow", render: (r) => r.recent_outflow.toFixed(1) },
          { header: "Stockout obs.", render: (r) => String(r.stockout_observations) },
          { header: "Unknown", render: (r) => (r.unknown ? <span className="chip chip-warn">unknown</span> : "—") },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      <Limitations items={meta.limitations} />
    </Section>
  );
}

/* ---------------- health tab ---------------- */

function HealthTab() {
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [page, setPage] = usePager();

  const state = useApiQuery(
    () =>
      endpoints.inventoryHealth({
        product_id: productId || undefined,
        warehouse_id: warehouseId || undefined,
        page,
        page_size: 15,
      }),
    [productId, warehouseId, page],
  );

  if (state.status === "loading") return <LoadingState message="Loading health classifications…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="inventory health" />;
  if (state.status === "empty")
    return <EmptyState what="health classifications" hint="No health rows match the current filters." />;

  const { data, meta } = state;
  return (
    <Section title={`Health states — ${data.total} series (rule-based classifications, never predictions)`}>
      <FilterBar>
        <TextInput label="Product ID" value={productId} onChange={(v) => { setProductId(v); setPage(1); }} placeholder="blank = all" />
        <TextInput label="Warehouse ID" value={warehouseId} onChange={(v) => { setWarehouseId(v); setPage(1); }} placeholder="blank = all" />
      </FilterBar>
      <DataTable
        columns={[
          { header: "Product", render: (r: (typeof data.items)[0]) => <ShortId id={r.product_id} /> },
          { header: "Warehouse", render: (r) => <ShortId id={r.warehouse_id} /> },
          { header: "State", render: (r) => <SeverityChip severity={r.health} /> },
          { header: "Reason", render: (r) => <span className="small">{r.reason}</span> },
          {
            header: "Missing evidence",
            render: (r) =>
              r.missing_evidence.length === 0 ? (
                "—"
              ) : (
                <ul className="evidence-list">{r.missing_evidence.map((m) => <li key={m}>{m}</li>)}</ul>
              ),
          },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      <Limitations items={meta.limitations} />
    </Section>
  );
}
