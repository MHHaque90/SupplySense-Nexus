import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { DataTable, Pagination, usePager } from "../components/DataTable";
import { FilterBar, Section, SeverityChip, ShortId, SelectInput, TextInput } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { RiskOverview, RiskRecordRow } from "../api/types";

/**
 * Risk — Phase 7 descriptive register (GET /risk). Filters map directly to
 * response; severity filter narrows items without changing the full-register
 * overview counts (per API contract).
 */
export function RiskPage() {
  return (
    <PageGate>
      <RiskBody />
    </PageGate>
  );
}

function RiskBody() {
  const [severity, setSeverity] = useState("");
  const [domain, setDomain] = useState("");
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [horizonDays, setHorizonDays] = useState("");
  const [page, setPage] = usePager();

  const state = useApiQuery(
    () =>
      endpoints.riskRegister({
        severity: severity || undefined,
        domain: domain || undefined,
        product_id: productId || undefined,
        warehouse_id: warehouseId || undefined,
        supplier_id: supplierId || undefined,
        horizon_days: horizonDays ? Number(horizonDays) : undefined,
        page,
        page_size: 15,
      }),
    [severity, domain, productId, warehouseId, supplierId, horizonDays, page],
  );

  if (state.status === "loading") {
    return <div className="page"><LoadingState message="Loading risk register…" /></div>;
  }
  if (state.status === "error") {
    return <div className="page"><ErrorState error={state.error} what="the risk register" /></div>;
  }
  if (state.status === "empty") {
    return (
      <div className="page">
        <EmptyState
          what="risk records"
          hint="No records match the current filters. Reset filters or widen the horizon window."
        />
      </div>
    );
  }

  const { data, meta } = state;
  return (
    <>
      <div className="page-header">
        <h1>Risk</h1>
        <span className="muted">Descriptive register — observations with evidence, not scores or predictions</span>
        <DataSourceLabelChip label={meta.data_source_label} />
      </div>

      <Section title="Full-register overview" subtitle={`All ${data.overview?.records ?? 0} records regardless of item filters (API behavior: severity filter narrows the items list only)`}>
        <OverviewCounts overview={data.overview ?? { records: 0, domains: [], severity_counts: {} }} />
      </Section>

      <Section title={`Records (${data.total} match filters)`}>
        <FilterBar>
          <SelectInput label="Severity" value={severity || ""} options={["", "LOW", "MODERATE", "HIGH", "UNKNOWN"].map((v) => ({ value: v, label: v || "— any —" }))} onChange={(v) => { setSeverity(v); setPage(1); }} />
          <SelectInput label="Domain" value={domain || ""} options={["", ...((data.overview?.domains ?? []) as string[])].map((v) => ({ value: v, label: v || "— any —" }))} onChange={(v) => { setDomain(v); setPage(1); }} />
          <TextInput label="Product ID" value={productId} onChange={(v) => { setProductId(v); setPage(1); }} placeholder="blank = any" />
          <TextInput label="Warehouse ID" value={warehouseId} onChange={(v) => { setWarehouseId(v); setPage(1); }} placeholder="blank = any" />
          <TextInput label="Supplier ID" value={supplierId} onChange={(v) => { setSupplierId(v); setPage(1); }} placeholder="blank = any" />
          <TextInput label="Horizon (days)" value={horizonDays} onChange={(v) => { setHorizonDays(v.replace(/\D/g, "")); setPage(1); }} placeholder="default" />
        </FilterBar>
        <DataTable
          columns={[
            { header: "Domain", render: (r: RiskRecordRow) => <strong>{r.domain}</strong> },
            { header: "State", render: (r) => <SeverityChip severity={r.state} /> },
            { header: "Severity", render: (r) => <SeverityChip severity={r.severity} /> },
            { header: "Entity", render: (r) => <ShortId id={r.entity_id} /> },
            { header: "Product", render: (r) => (r.product_id ? <ShortId id={r.product_id} /> : "—") },
            { header: "Warehouse", render: (r) => (r.warehouse_id ? <ShortId id={r.warehouse_id} /> : "—") },
            { header: "Supplier", render: (r) => (r.supplier_id ? <ShortId id={r.supplier_id} /> : "—") },
            { header: "Metrics", render: (r) => <span className="mono small">{Object.entries(r.metrics).map(([k, v]) => `${k}=${v}`).join(" · ")}</span> },
            { header: "Explanation", render: (r) => <span className="small">{r.explanation}</span> },
            {
              header: "Evidence",
              render: (r) =>
                r.evidence.length === 0 ? (
                  <span className="muted small">none {r.missing_evidence.length > 0 ? `· missing: ${r.missing_evidence.join(", ")}` : ""}</span>
                ) : (
                  <ul className="evidence-list">{r.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
                ),
            },
          ]}
          rows={data.items}
        />
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      </Section>

      <Limitations items={[...(meta.limitations ?? [])]} />
    </>
  );
}

function OverviewCounts({ overview }: { overview: RiskOverview }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>Severity distribution</th>
          </tr>
        </thead>
        <tbody>
          {overview.domains.map((domain) => {
            const counts = overview.severity_counts[domain] ?? {};
            return (
              <tr key={domain}>
                <td>{domain}</td>
                <td>
                  {Object.entries(counts).map(([severity, count]) => (
                    <span key={severity} style={{ marginRight: 10, display: "inline-flex", gap: 4, alignItems: "center" }}>
                      <SeverityChip severity={severity} />
                      <span className="muted small">×{count}</span>
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
