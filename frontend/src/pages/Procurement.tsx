import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { DataTable, Pagination, usePager } from "../components/DataTable";
import { FilterBar, KpiCard, Section, SeverityChip, ShortId, TextInput, formatNumber } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { KpiMetric } from "../api/types";

/**
 * Procurement — overview KPIs, open orders, inbound coverage states and
 * supplier risk signals (all descriptive; data_source_label = synthetic).
 */
export function ProcurementPage() {
  return (
    <PageGate>
      <ProcurementBody />
    </PageGate>
  );
}

type Tab = "summary" | "orders" | "inbound" | "risk";

const TABS: { id: Tab; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "orders", label: "Open orders" },
  { id: "inbound", label: "Inbound coverage" },
  { id: "risk", label: "Risk signals" },
];

function ProcurementBody() {
  const [tab, setTab] = useState<Tab>("summary");
  return (
    <div className="page">
      <div className="page-header">
        <h1>Procurement</h1>
        <span className="muted">Purchase orders, inbound coverage and supplier risk descriptions</span>
        <DataSourceLabelChip label="synthetic" />
      </div>
      <FilterBar>
        {TABS.map((t) => (
          <button key={t.id} type="button" className={`nav-item${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </FilterBar>
      {tab === "summary" ? <SummaryTab /> : null}
      {tab === "orders" ? <OrdersTab /> : null}
      {tab === "inbound" ? <InboundTab /> : null}
      {tab === "risk" ? <RiskTab /> : null}
    </div>
  );
}

function SummaryTab() {
  const state = useApiQuery(() => endpoints.procurementOverview(), []);
  if (state.status === "loading") return <LoadingState message="Loading procurement KPIs…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="procurement overview" />;
  if (state.status === "empty") return <EmptyState what="procurement KPI data" />;

  const { data, meta } = state;
  const groups = data.kpis;
  return (
    <>
      <div className="meta-row">
        <DataSourceLabelChip label={meta.data_source_label} />
        <span className="muted">analysis date {data.analysis_date}</span>
      </div>
      <Section title="Procurement summary" subtitle="Open purchase order volume and status mix">
        <div className="kpi-grid">
          {groups.procurement_summary.map((m, i) => <KpiCard key={i} title={m.metric_name} value={m.value} unit={m.unit} note={m.notes || undefined} />)}
        </div>
      </Section>
      <Section title="Lead times" subtitle="Contracted terms recorded on the synthetic supplier records">
        <DataTable
          columns={[
            { header: "Metric", render: (m: KpiMetric) => m.metric_name },
            { header: "Value", render: (m) => (m.value === null ? "n/a" : formatNumber(m.value)) },
            { header: "Unit", render: (m) => m.unit },
            { header: "Notes", render: (m) => <span className="small">{m.notes}</span> },
          ]}
          rows={groups.lead_time_stats}
        />
      </Section>
      <Section title="Shipment performance" subtitle="Completed vs late shipments over the window">
        <div className="kpi-grid">
          {groups.shipment_performance.map((m, i) => <KpiCard key={i} title={m.metric_name} value={m.value} unit={m.unit} note={m.notes || undefined} />)}
        </div>
      </Section>
      <Section title="MOQ compliance & market concentration" subtitle="Descriptive compliance shares and spend concentration">
        <DataTable
          columns={[
            { header: "Metric", render: (m: KpiMetric) => m.metric_name },
            { header: "Value", render: (m) => (m.value === null ? "n/a" : formatNumber(m.value)) },
            { header: "Numerator", render: (m) => (m.numerator === null ? "n/a" : formatNumber(m.numerator)) },
            { header: "Denominator", render: (m) => (m.denominator === null ? "n/a" : formatNumber(m.denominator)) },
            { header: "Notes", render: (m) => <span className="small">{m.notes}</span> },
          ]}
          rows={[...groups.moq_compliance, ...groups.concentration]}
        />
      </Section>
      <Limitations items={[...data.limitations, ...(meta.limitations ?? [])]} />
    </>
  );
}

function OrdersTab() {
  const [supplierId, setSupplierId] = useState("");
  const [page, setPage] = usePager();
  const state = useApiQuery(
    () => endpoints.openOrders({ supplier_id: supplierId || undefined, page, page_size: 15 }),
    [supplierId, page],
  );
  if (state.status === "loading") return <LoadingState message="Loading open purchase orders…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="open purchase orders" />;
  if (state.status === "empty") return <EmptyState what="open purchase orders" hint="No open orders match the current filters." />;

  const { data, meta } = state;
  return (
    <Section title={`Open purchase orders — ${data.total} lines open at ${data.analysis_date}`}>
      <FilterBar>
        <TextInput label="Supplier ID" value={supplierId} onChange={(v) => { setSupplierId(v); setPage(1); }} placeholder="blank = all" />
      </FilterBar>
      <DataTable
        columns={[
          { header: "PO number", render: (r: (typeof data.items)[0]) => <span className="mono small">{r.po_number}</span> },
          { header: "Supplier", render: (r) => <ShortId id={r.supplier_id} /> },
          { header: "Product", render: (r) => <ShortId id={r.product_id} /> },
          { header: "Order date", render: (r) => <span className="mono small">{r.order_date}</span> },
          { header: "Expected arrival", render: (r) => <span className="mono small">{r.expected_arrival}</span> },
          { header: "Ordered", render: (r) => r.ordered_quantity.toLocaleString() },
          { header: "Received", render: (r) => r.received_quantity.toLocaleString() },
          { header: "Remaining", render: (r) => r.remaining_quantity.toLocaleString() },
          { header: "Status", render: (r) => <span className="chip chip-neutral">{r.arrival_status}</span> },
          { header: "Overdue", render: (r) => (r.overdue ? <span className="chip chip-bad">overdue ({r.days_outstanding}d)</span> : "—") },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      <Limitations items={meta.limitations} />
    </Section>
  );
}

function InboundTab() {
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [horizonDays, setHorizonDays] = useState("");
  const [page, setPage] = usePager();
  const state = useApiQuery(
    () =>
      endpoints.inboundCoverage({
        product_id: productId || undefined,
        warehouse_id: warehouseId || undefined,
        horizon_days: horizonDays ? Number(horizonDays) : undefined,
        page,
        page_size: 15,
      }),
    [productId, warehouseId, horizonDays, page],
  );
  if (state.status === "loading") return <LoadingState message="Loading inbound coverage…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="inbound coverage" />;
  if (state.status === "empty") return <EmptyState what="inbound coverage rows" hint="No coverage rows match the current filters." />;

  const { data, meta } = state;
  return (
    <Section title={`Inbound coverage — ${data.total} series over a ${data.horizon_days}-day horizon`}>
      <FilterBar>
        <TextInput label="Product ID" value={productId} onChange={(v) => { setProductId(v); setPage(1); }} placeholder="blank = all" />
        <TextInput label="Warehouse ID" value={warehouseId} onChange={(v) => { setWarehouseId(v); setPage(1); }} placeholder="blank = all" />
        <TextInput label="Horizon (days)" value={horizonDays} onChange={(v) => { setHorizonDays(v.replace(/\D/g, "")); setPage(1); }} placeholder="default" />
      </FilterBar>
      <DataTable
        columns={[
          { header: "Product", render: (r: (typeof data.items)[0]) => <ShortId id={r.product_id} /> },
          { header: "Warehouse", render: (r) => <ShortId id={r.warehouse_id} /> },
          { header: "State", render: (r) => <CoverageState state={r.state} /> },
          { header: "Known inbound", render: (r) => r.known_inbound.toLocaleString() },
          { header: "Uncovered demand", render: (r) => r.uncovered_demand.toLocaleString() },
          { header: "Reason", render: (r) => <span className="small">{r.reason}</span> },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      <Limitations items={meta.limitations} />
    </Section>
  );
}

function CoverageState({ state }: { state: string }) {
  const tone =
    state === "INBOUND_SUPPORTED" ? "chip-good"
    : state === "INBOUND_PARTIAL" ? "chip-warn"
    : ["INBOUND_INSUFFICIENT", "NO_KNOWN_INBOUND"].includes(state) ? "chip-bad"
    : "chip-neutral";
  return <span className={`chip ${tone}`}>{state}</span>;
}

function RiskTab() {
  const [supplierId, setSupplierId] = useState("");
  const [page, setPage] = usePager();
  const state = useApiQuery(
    () => endpoints.procurementRisk({ supplier_id: supplierId || undefined, page, page_size: 15 }),
    [supplierId, page],
  );
  if (state.status === "loading") return <LoadingState message="Loading supplier risk signals…" />;
  if (state.status === "error") return <ErrorState error={state.error} what="procurement risk signals" />;
  if (state.status === "empty") return <EmptyState what="risk signals" hint="No risk signals match the current filters." />;

  const { data, meta } = state;
  return (
    <Section title={`Supplier risk signals — ${data.total} rows (descriptive categories, never ranked advice)`}>
      <FilterBar>
        <TextInput label="Supplier ID" value={supplierId} onChange={(v) => { setSupplierId(v); setPage(1); }} placeholder="blank = all" />
      </FilterBar>
      <DataTable
        columns={[
          { header: "Supplier", render: (r: (typeof data.items)[0]) => <ShortId id={r.supplier_id} /> },
          { header: "Signal", render: (r) => <strong>{r.signal}</strong> },
          { header: "Severity", render: (r) => <SeverityChip severity={r.severity} /> },
          { header: "Product", render: (r) => (r.product_id ? <ShortId id={r.product_id} /> : "—") },
          { header: "Reason", render: (r) => <span className="small">{r.reason}</span> },
          {
            header: "Metrics",
            render: (r) => (
              <span className="mono small">
                {Object.entries(r.metrics).map(([k, v]) => `${k}=${v}`).join(" · ")}
              </span>
            ),
          },
          {
            header: "Evidence",
            render: (r) =>
              r.evidence.length === 0 ? (
                "—"
              ) : (
                <ul className="evidence-list">{r.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
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
