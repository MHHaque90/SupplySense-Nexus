import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { DistributionChart } from "../components/Charts";
import { PageGate, PlannerGate } from "../components/PageGate";
import { ScenarioForm, defaultScenarioForm, toScenarioBody, type ScenarioFormState } from "../components/ScenarioForm";
import { DataTable } from "../components/DataTable";
import { KpiCard, Section, ShortId } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import { ApiError } from "../api/client";
import type { SimulationReport } from "../api/types";

/**
 * Simulation — GET /simulation/events for vocabulary/bounds and
 * POST /simulation/run for the Monte Carlo report (planner+).
 * Output is simulated: conditional scenario modelling, never a forecast.
 */
export function SimulationPage() {
  return (
    <PageGate>
      <PlannerGate action="Scenario simulation">
        <SimulationBody />
      </PlannerGate>
    </PageGate>
  );
}

function SimulationBody() {
  const meta = useApiQuery(() => endpoints.simulationEvents(), []);
  const [form, setForm] = useState<ScenarioFormState | null>(null);
  const [report, setReport] = useState<SimulationReport | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<ApiError | null>(null);

  if (meta.status === "loading") {
    return <div className="page"><LoadingState message="Loading event vocabulary and bounds…" /></div>;
  }
  if (meta.status === "error") {
    return <div className="page"><ErrorState error={meta.error} what="the simulation event vocabulary" /></div>;
  }
  if (meta.status === "empty") {
    return <div className="page"><EmptyState what="simulation event metadata" /></div>;
  }

  const state0 = form ?? defaultScenarioForm(meta.data);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Simulation</h1>
        <span className="muted">Monte Carlo disruption scenarios — conditional outcomes, never predictions</span>
        <DataSourceLabelChip label="simulated" />
      </div>

      <div className="sim-banner" role="note">
        Simulated scenario analysis. Figures describe what the models project <em>if</em> the declared event
        occurs under the stated assumptions — not expectations of what will happen.
      </div>

      <Section title="Scenario inputs" subtitle={`${meta.data.probability_modes.join(" / ")} probability modes · horizon ${meta.data.bounds.horizon_days.min}–${meta.data.bounds.horizon_days.max} days · ${meta.data.bounds.simulation_count.min}–${meta.data.bounds.simulation_count.max} simulations`}>
        <ScenarioForm meta={meta.data} value={state0} onChange={setForm} />
        <div className="center-row" style={{ justifyContent: "flex-start", gap: 10 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={running}
            onClick={async () => {
              setRunning(true);
              setRunError(null);
              setReport(null);
              try {
                const ok = await endpoints.simulationRun(toScenarioBody(state0));
                setReport(ok.data);
              } catch (err) {
                setRunError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN", String(err)));
              } finally {
                setRunning(false);
              }
            }}
          >
            {running ? "Simulating…" : "Run simulation"}
          </button>
          <span className="muted small">Same inputs + same seed reproduce the same report (documented determinism).</span>
        </div>
        {running ? <LoadingState message="Running Monte Carlo simulation — this can take several seconds…" /> : null}
        {runError ? (
          <ErrorState error={runError} what="the simulation run" />
        ) : null}
      </Section>

      <Section title="Event vocabulary" subtitle="From GET /simulation/events — the locked contract for scenario definition">
        <EventTemplatesVocabulary templates={meta.data.templates} types={meta.data.event_types} />
        <Limitations items={meta.data.notes} />
      </Section>

      {report ? <RunReport report={report} /> : null}
    </div>
  );
}

function EventTemplatesVocabulary({
  templates,
  types,
}: {
  templates: Record<string, { event_type: string; description: string; duration_days: number }>;
  types: string[];
}) {
  return (
    <>
      <p className="muted small">Event types: {types.join(", ")}</p>
      <DataTable
        columns={[
          { header: "Template", render: (t: [string, { event_type: string; description: string; duration_days: number }]) => <strong>{t[0]}</strong> },
          { header: "Event type", render: (t) => <span className="mono small">{t[1].event_type}</span> },
          { header: "Default duration", render: (t) => `${t[1].duration_days} days` },
          { header: "Description", render: (t) => <span className="small">{t[1].description}</span> },
        ]}
        rows={Object.entries(templates)}
      />
    </>
  );
}

function RunReport({ report }: { report: SimulationReport }) {
  const { scenario_definition: scenario } = report;
  return (
    <>
      <div className="sim-banner" role="note">
        Report {report.scenario_definition.scenario_id} — entirely simulated on the synthetic dataset.
      </div>

      <Section title="Declared scenario" subtitle={`event ${report.event_type} · probability mode ${report.probability_mode} (${report.probability_provenance.source}) · seed ${report.simulation_configuration.random_seed}`}>
        <div className="table-wrap">
          <table className="data-table">
            <tbody>
              <tr><td>Event</td><td><span className="mono">{scenario.event.event_type}</span> — {scenario.event.description}</td></tr>
              <tr><td>Duration</td><td>{scenario.event.duration_days} days starting {scenario.event.start_date ?? report.scenario_definition.analysis_date}</td></tr>
              <tr><td>Scope</td><td><span className="mono small">{scenario.event.affected_suppliers.length} suppliers · {scenario.event.affected_products.length} products · {scenario.event.affected_warehouses.length} warehouses</span></td></tr>
              <tr><td>Event parameters</td><td><span className="mono small">supply_reduction={scenario.event.supply_reduction} · lead_time_delay={scenario.event.lead_time_delay_days}d · demand_multiplier={scenario.event.demand_multiplier}</span></td></tr>
              <tr><td>Severity</td><td>{scenario.event.severity}</td></tr>
            </tbody>
          </table>
        </div>
        {report.event_assumptions.length > 0 ? (
          <ul className="evidence-list">{report.event_assumptions.map((a, i) => <li key={`${i}:${a}`}>{a}</li>)}</ul>
        ) : null}
      </Section>

      <Section title="Baseline vs scenario (expected outcomes)" subtitle={`From ${report.simulation_configuration.simulation_count} seeded Monte Carlo draws over a ${report.simulation_configuration.horizon_days}-day horizon`}>
        <div className="kpi-grid">
          <KpiCard title="Stockout probability (baseline)" value={report.baseline_outcome.stockout_probability} unit="share" note={`scenario_outcome: ${report.scenario_outcome.stockout_probability}`} />
          <KpiCard title="Expected unmet demand (baseline)" value={report.baseline_outcome.expected_unmet_demand} unit="units" note={`scenario outcome: ${report.scenario_outcome.expected_unmet_demand}`} />
          <KpiCard title="Expected min inventory (baseline)" value={report.baseline_outcome.expected_min_inventory} unit="units" note={`scenario outcome: ${report.scenario_outcome.expected_min_inventory}`} />
          <KpiCard title="Expected ending inventory (baseline)" value={report.baseline_outcome.expected_ending_inventory} unit="units" note={`scenario outcome: ${report.scenario_outcome.expected_ending_inventory}`} />
          <KpiCard title="Service exposure (baseline)" value={report.baseline_outcome.service_exposure_probability} unit="share" note={`scenario outcome: ${report.scenario_outcome.service_exposure_probability}`} />
          <KpiCard
            title="Delta stockout probability (scenario vs baseline)"
            value={report.delta.delta_stockout_probability}
            unit="+pp"
            note={`delta unmet demand: ${report.delta.delta_unmet_demand} units; other deltas reported in the table below`}
          />
        </div>
        <DataTable
          columns={[
            { header: "Delta", render: (d: [string, number]) => <strong>{labelOf(d[0])}</strong> },
            { header: "Value", render: (d) => <SpanDelta v={d[1] as number} /> },
          ]}
          rows={Object.entries(report.delta)}
        />
        <h3 className="panel-subtitle" style={{ marginTop: 12 }}>Unmet-demand distribution across draws (simulated)</h3>
        <DistributionChart title="Expected unmet demand" dist={report.scenario_outcome.distributions.unmet_demand} />
        <h3 className="panel-subtitle" style={{ marginTop: 12 }}>Ending-inventory distribution</h3>
        <DistributionChart title="Ending inventory" dist={report.scenario_outcome.distributions.ending_inventory} />
      </Section>

      <Section title="Stockout timing" subtitle="Probability of at least one stockout day within the horizon windows (simulated)">
        <DataTable
          columns={[
            { header: "Within", render: (d: [string, number | null]) => <strong>{d[0]}</strong> },
            { header: "Probability", render: (d) => (d[1] === null ? <span className="muted">beyond horizon</span> : <SpanDelta v={d[1] as number} />) },
          ]}
          rows={Object.entries(report.inventory_outcomes.stockout_by_day)}
        />
      </Section>

      <Section title="Traceability (per affected product-warehouse series)" subtitle="Provenance chain for every simulated entity">
        <DataTable
          columns={[
            { header: "Product", render: (t: Record<string, unknown>) => <ShortId id={String(t.product_id)} /> },
            { header: "Warehouse", render: (t) => <ShortId id={String(t.warehouse_id)} /> },
            { header: "Baseline on hand", render: (t) => String(t.baseline_on_hand) },
            { header: "Forecast model", render: (t) => <span className="mono small">{String(t.forecast_model)} ({String(t.forecast_origin)})</span> },
            { header: "Probability", render: (t) => <span className="mono small">{String(t.probability_mode)} / {String(t.probability_source)}</span> },
          ]}
          rows={report.traceability.slice(0, 25)}
        />
      </Section>

      <Limitations items={[...report.limitations]} />
    </>
  );
}

function labelOf(key: string): string {
  const names: Record<string, string> = {
    delta_stockout_probability: "Δ stockout probability",
    delta_unmet_demand: "Δ expected unmet demand (units)",
    delta_min_inventory: "Δ expected min inventory (units)",
    delta_ending_inventory: "Δ expected ending inventory (units)",
    delta_stockout_days: "Δ expected stockout days",
    delta_service_exposure: "Δ service exposure",
  };
  return names[key] ?? key;
}

export function SpanDelta({ v }: { v: number }) {
  const positive = v > 1e-12;
  const negative = v < -1e-12;
  return (
    <span className={positive ? "delta-positive" : negative ? "delta-negative" : "delta-neutral"}>
      {positive ? "+" : ""}{v.toLocaleString(undefined, { maximumFractionDigits: 4 })}
    </span>
  );
}
