import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate } from "../components/PageGate";
import { KpiCard, Section, SeverityChip } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import type { KpiMetric } from "../api/types";

/**
 * Executive Overview — exclusively GET /dashboard/overview data
 * (data_source_label = derived). No KPI not present in the response is
 * displayed; anything missing renders as explicitly unavailable.
 */
export function OverviewPage() {
  return (
    <PageGate>
      <OverviewBody />
    </PageGate>
  );
}

function OverviewBody() {
  const state = useApiQuery(
    () => endpoints.dashboardOverview(),
    [],
  );

  if (state.status === "loading") {
    return <div className="page"><LoadingState message="Loading dashboard overview (KPI families + risk snapshot)…" /></div>;
  }
  if (state.status === "error") {
    return <div className="page"><ErrorState error={state.error} what="the dashboard overview" /></div>;
  }
  if (state.status === "empty") {
    return <div className="page"><EmptyState what="dashboard KPI data" /></div>;
  }

  const { data, meta } = state;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Overview</h1>
        <span className="muted">Analysis date {data.analysis_date} · horizon {data.horizon_days} days</span>
        <DataSourceLabelChip label={meta.data_source_label} />
        <span className="muted small">API response {meta.timestamp.slice(0, 19).replace("T", " ")}Z</span>
      </div>

      <Section title="Demand KPIs" subtitle="Derived from the organization's synthetic demand observations.">
        <div className="kpi-grid">
          {data.kpis.demand.map((metric, i) => <KpiCardFromMetricSafe key={i} metric={metric} />)}
        </div>
      </Section>

      <Section title="Inventory overview" subtitle="Headline inventory levels; the full Inventory page has positions and health detail.">
        <div className="kpi-grid">
          {data.kpis.inventory.inventory_levels.map((metric, i) => <KpiCardFromMetricSafe key={i} metric={metric} />)}
        </div>
      </Section>

      <Section title="Service level" subtitle="Availability proxy over sales-order fulfillment.">
        <div className="kpi-grid">
          {data.kpis.service.map((metric, i) => <KpiCardFromMetricSafe key={i} metric={metric} />)}
        </div>
      </Section>

      <Section title="Procurement exposure" subtitle="Open purchase orders, lead-time and shipment performance headline KPIs.">
        <div className="kpi-grid">
          {data.kpis.procurement.procurement_summary.map((metric, i) => <KpiCardFromMetricSafe key={i} metric={metric} />)}
        </div>
      </Section>

      <Section title="Risk snapshot" subtitle="Phase 7 risk register headline over all descriptive domains.">
        <RiskSummary data={data.risk} />
      </Section>

      <Section title="Model availability" subtitle="What the backend currently reports for forecasting and compute features.">
        <div className="kpi-grid">
          <KpiCard
            title="Persisted forecast rows"
            value={data.forecast_status.persisted_forecast_rows}
            unit="rows"
            note="Phase 4 forecasts stored in the organization's database."
          />
          <KpiCard
            title="Simulation / replay / optimization"
            value={null}
            unit=""
            note="Compute POSTs are available to planner+ roles on this API (rate limited). See their pages."
          />
          <KpiCard
            title="AI copilot"
            value={null}
            unit=""
            note="Available via the Phase 11 endpoints; provider is the offline mock when no LLM key is configured."
          />
        </div>
      </Section>

      <Limitations items={[...data.limitations, ...(meta.limitations ?? [])]} />
    </div>
  );
}

function KpiCardFromMetricSafe({ metric }: { metric: KpiMetric }) {
  return (
    <KpiCard
      title={metric.metric_name}
      value={metric.value}
      unit={metric.unit}
      note={metric.notes || undefined}
    />
  );
}

type RiskOverview = { records: number; domains: string[]; severity_counts: Record<string, Record<string, number>> };

function RiskSummary({ data }: { data: RiskOverview }) {
  return (
    <div>
      <p className="muted small">
        {data.records} risk records across {data.domains.length} domains (severity distribution per domain below).
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Domain</th>
              <th>Severity distribution</th>
            </tr>
          </thead>
          <tbody>
            {data.domains.map((domain) => {
              const counts = data.severity_counts[domain] ?? {};
              return (
                <tr key={domain}>
                  <td>{domain}</td>
                  <td>
                    {Object.entries(counts).map(([severity, count]) => (
                      <span key={severity} className="meta-row" style={{ marginRight: 10, display: "inline-flex" }}>
                        <SeverityChip severity={severity} /> <span className="muted small">×{count}</span>
                      </span>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
