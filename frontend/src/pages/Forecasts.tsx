import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { ForecastChart } from "../components/Charts";
import { PageGate } from "../components/PageGate";
import { DataTable, Pagination, usePager } from "../components/DataTable";
import { FilterBar, Section, ShortId, TextInput } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { ForecastRow } from "../api/types";

/**
 * Forecasts — GET /forecast (data_source_label = forecast).
 * Paginated series rows; each row expands to an interval-band chart.
 */
export function ForecastsPage() {
  return (
    <PageGate>
      <ForecastsBody />
    </PageGate>
  );
}

function ForecastsBody() {
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [horizon, setHorizon] = useState("");
  const [profile, setProfile] = useState("");
  const [page, setPage] = usePager();

  const state = useApiQuery(
    () =>
      endpoints.forecasts({
        product_id: productId || undefined,
        warehouse_id: warehouseId || undefined,
        horizon: horizon ? Number(horizon) : undefined,
        profile: profile || undefined,
        page,
        page_size: 10,
      }),
    [productId, warehouseId, horizon, profile, page],
  );

  if (state.status === "loading") {
    return <div className="page"><LoadingState message="Loading forecast series…" /></div>;
  }
  if (state.status === "error") {
    return <div className="page"><ErrorState error={state.error} what="forecast series" /></div>;
  }
  if (state.status === "empty") {
    return (
      <div className="page">
        <PageTitle />
        <EmptyState
          what="forecast series"
          hint="No persisted forecasts match the current filters for this organization."
        />
      </div>
    );
  }

  const { data, meta } = state;
  const items = data.items;

  return (
    <div className="page">
      <PageTitle />

      <Section
        title="Filters"
        subtitle="Query parameters pass straight through to the API. Data-source label and limitations come from the response meta."
      >
        <FilterBar>
          <TextInput label="Product ID" value={productId} onChange={(v) => { setProductId(v); setPage(1); }} placeholder="blank = all" />
          <TextInput label="Warehouse ID" value={warehouseId} onChange={(v) => { setWarehouseId(v); setPage(1); }} placeholder="blank = all" />
          <TextInput label="Horizon (days)" value={horizon} onChange={(v) => { setHorizon(v.replace(/\D/g, "")); setPage(1); }} placeholder="e.g. 28" />
          <TextInput label="Demand profile" value={profile} onChange={(v) => { setProfile(v); setPage(1); }} placeholder="e.g. steady" />
        </FilterBar>
        <div className="meta-row">
          <DataSourceLabelChip label={meta.data_source_label} />
          <span>Series in DB matching filters (report data): {data.total}</span>
          <span className="muted">analysis date {data.analysis_date}</span>
        </div>
      </Section>

      <Section title={`Forecast series (${items.length} shown)`}>
        <div className="kpi-grid" style={{ gridTemplateColumns: "1fr" }}>
          {items.map((row) => (
            <SeriesRow key={row.series_id} row={row} />
          ))}
        </div>
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} hasNext={data.has_next} onPage={setPage} />
      </Section>

      <Limitations items={[...(meta.limitations ?? [])]} />
    </div>
  );
}

function PageTitle() {
  return (
    <div className="page-header">
      <h1>Forecasts</h1>
      <span className="muted">Persisted Phase 4 model output with prediction intervals — estimates, never actuals</span>
      <DataSourceLabelChip label="forecast" />
    </div>
  );
}

function SeriesRow({ row }: { row: ForecastRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="panel" style={{ padding: 12 }}>
      <div className="panel-header">
        <div className="meta-row">
          <ShortId id={row.product_id} />
          <span className="muted">@</span>
          <ShortId id={row.warehouse_id} />
          <span className="muted small">h={row.horizon}d · {row.model_name} v{row.model_version}</span>
          {row.missing ? <span className="chip chip-bad">series missing</span> : null}
        </div>
        <button type="button" className="btn btn-sm" onClick={() => setOpen(!open)}>
          {open ? "Hide chart" : "Interval chart"}
        </button>
      </div>
      {open ? (
        <ForecastChart row={row} />
      ) : (
        <DataTable
          columns={[
            { header: "Origin", width: "110px", render: () => <span className="mono small">{row.origin}</span> },
            {
              header: "First forecast day",
              render: () => <span className="mono small">{row.forecast_dates[0]}</span>,
            },
            {
              header: "Point range",
              render: () => (
                <span className="mono small">
                  min {row.point ? `${Math.min(...row.point).toFixed(1)}` : "—"} · max {row.point ? `${Math.max(...row.point).toFixed(1)}` : "—"}
                </span>
              ),
            },
            {
              header: "Confidence",
              render: () => <span className="mono small">{(row.confidence_level * 100).toFixed(0)}% · {row.interval_method}</span>,
            },
            {
              header: "Validation",
              render: () => (
                <span className="mono small">
                  {row.validation_metric}
                  {row.validation_score === null ? <span className="muted"> (no fold output)</span> : ` = ${row.validation_score?.toFixed(3)}`}
                </span>
              ),
            },
            { header: "Explanation", render: () => <span className="small">{row.explanation}</span> },
          ]}
          rows={[row]}
        />
      )}
      {row.warnings.length > 0 ? (
        <ul className="evidence-list">
          {row.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      ) : null}
    </div>
  );
}
