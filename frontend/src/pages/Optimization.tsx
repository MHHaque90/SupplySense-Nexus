import { useState } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate, PlannerGate } from "../components/PageGate";
import { ScenarioForm, defaultScenarioForm, toScenarioBody, type ScenarioFormState } from "../components/ScenarioForm";
import { DataTable } from "../components/DataTable";
import { Section, ShortId } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import { ApiError } from "../api/client";
import type { Objective, OptimizationPlanSummary, OptimizationReport, OptimizationRunRequest } from "../api/types";

/**
 * Optimization — POST /optimization/run (planner+, Phase 10 MILP).
 * The solver status is reported verbatim; nothing is translated into advice.
 */
export function OptimizationPage() {
  return (
    <PageGate>
      <PlannerGate action="Optimization analysis">
        <OptimizationBody />
      </PlannerGate>
    </PageGate>
  );
}

const OBJECTIVE_LABELS: { value: Objective; label: string; note: string }[] = [
  { value: "minimize_total_cost", label: "minimize_total_cost", note: "hard demand satisfaction" },
  { value: "minimize_shortage", label: "minimize_shortage", note: "hard procurement budget where declared" },
  { value: "cost_shortage_tradeoff", label: "cost_shortage_tradeoff", note: "requires shortage_penalty > 0" },
  { value: "maximize_service_fulfillment", label: "maximize_service_fulfillment", note: "fulfillment rate maximization" },
];

interface OptFormState {
  objective: Objective;
  shortagePenalty: number;
  budget: number | null;
  minFulfillment: number | null;
  quantityIntegrality: "integer" | "continuous";
  timeLimitSeconds: number;
}

function OptimizationBody() {
  const scenarioMeta = useApiQuery(() => endpoints.simulationEvents(), []);
  const [form, setForm] = useState<ScenarioFormState | null>(null);
  const [opt, setOpt] = useState<OptFormState>({
    objective: "minimize_total_cost",
    shortagePenalty: 10,
    budget: null,
    minFulfillment: null,
    quantityIntegrality: "integer",
    timeLimitSeconds: 15,
  });
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<ApiError | null>(null);

  if (scenarioMeta.status === "loading") {
    return <div className="page"><LoadingState message="Loading scenario bounds…" /></div>;
  }
  if (scenarioMeta.status === "error") {
    return <div className="page"><ErrorState error={scenarioMeta.error} what="scenario bounds" /></div>;
  }
  if (scenarioMeta.status === "empty") {
    return <div className="page"><EmptyState what="optimization vocabulary" /></div>;
  }

  const state0 = form ?? defaultScenarioForm(scenarioMeta.data);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Optimization</h1>
        <span className="muted">Phase 10 MILP over one declared objective — solver status is reported, never interpreted</span>
        <DataSourceLabelChip label="simulated" />
      </div>

      <div className="sim-banner" role="note">
        "OPTIMAL" is the solver's status vocabulary only — a statement about the mathematical MILP, not an
        instruction to act on real operations.
      </div>

      <Section title="Objective & solver settings">
        <div className="filter-bar">
          <label className="field">
            <span>Objective</span>
            <select value={opt.objective} onChange={(e) => setOpt({ ...opt, objective: e.target.value as Objective })}>
              {OBJECTIVE_LABELS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label} — {o.note}
                </option>
              ))}
            </select>
          </label>
          {opt.objective === "cost_shortage_tradeoff" ? (
            <label className="field">
              <span>Shortage penalty per unit (&gt; 0)</span>
              <input type="number" min={0.01} step={0.5} value={opt.shortagePenalty} onChange={(e) => setOpt({ ...opt, shortagePenalty: Number(e.target.value) })} />
            </label>
          ) : null}
          <label className="field">
            <span>Budget (optional)</span>
            <input type="number" value={opt.budget ?? ""} onChange={(e) => setOpt({ ...opt, budget: e.target.value === "" ? null : Number(e.target.value) })} />
          </label>
          <label className="field">
            <span>Min fulfillment (optional 0–1)</span>
            <input type="number" min={0} max={1} step={0.05} value={opt.minFulfillment ?? ""} onChange={(e) => setOpt({ ...opt, minFulfillment: e.target.value === "" ? null : Number(e.target.value) })} />
          </label>
          <label className="field">
            <span>Quantity integrality</span>
            <select value={opt.quantityIntegrality} onChange={(e) => setOpt({ ...opt, quantityIntegrality: e.target.value as "integer" | "continuous" })}>
              <option value="integer">integer</option>
              <option value="continuous">continuous</option>
            </select>
          </label>
          <label className="field">
            <span>Time limit (seconds)</span>
            <input type="number" min={1} max={120} value={opt.timeLimitSeconds} onChange={(e) => setOpt({ ...opt, timeLimitSeconds: Number(e.target.value) || 15 })} />
          </label>
        </div>
      </Section>

      <Section title="Scenario inputs" subtitle="The MILP runs against the event-adjusted Phase 9 baseline for this scenario">
        <ScenarioForm meta={scenarioMeta.data} value={state0} onChange={setForm} />
        <div className="center-row" style={{ justifyContent: "flex-start" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={running}
            onClick={async () => {
              setRunning(true);
              setRunError(null);
              setReport(null);
              try {
                const body = toScenarioBody(state0) as OptimizationRunRequest;
                body.objective = opt.objective;
                if (opt.objective === "cost_shortage_tradeoff") {
                  if (!(opt.shortagePenalty > 0)) {
                    throw new ApiError(0, "VALIDATION_ERROR", "cost_shortage_tradeoff requires shortage_penalty > 0.", {
                      details: { reason: "Enter a shortage penalty greater than zero." },
                    });
                  }
                  body.shortage_penalty = opt.shortagePenalty;
                }
                if (opt.budget !== null) body.budget = opt.budget;
                if (opt.minFulfillment !== null) body.min_fulfillment = opt.minFulfillment;
                body.quantity_integrality = opt.quantityIntegrality;
                body.time_limit_seconds = opt.timeLimitSeconds;
                const ok = await endpoints.optimizationRun(body);
                setReport(ok.data);
              } catch (err) {
                setRunError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN", String(err)));
              } finally {
                setRunning(false);
              }
            }}
          >
            {running ? "Optimizing…" : "Run optimization"}
          </button>
        </div>
        {running ? <LoadingState message="Constructing and solving the MILP — this can take up to a minute…" /> : null}
        {runError ? <ErrorState error={runError} what="the optimization run" /> : null}
      </Section>

      {report ? <OptReportView report={report} /> : null}
    </div>
  );
}

function OptReportView({ report }: { report: OptimizationReport }) {
  const run = report.optimization_run_metadata;
  const feasibility = report.feasibility_status;
  return (
    <>
      <div className="sim-banner">
        Run {run.solver_status} · solver {run.solver} ({report.solver_information.solver_version}) · objective {run.objective_key} · MILP-in-simulated-context only
      </div>

      <Section title="Solver & run metadata" subtitle="Facts from the API — verbatim vocabulary">
        <DataTable
          columns={[
            { header: "Field", render: (r: [string, string]) => <strong>{r[0]}</strong> },
            { header: "Value", render: (r) => <span className="mono">{r[1]}</span> },
          ]}
          rows={runRows(report)}
        />
      </Section>

      <Section title="Feasibility status" subtitle={feasibility.note}>
        <div className="meta-row" style={{ marginBottom: 8 }}>
          <span className={`chip ${feasibility.status === "OPTIMAL" ? "chip-good" : feasibility.status === "INFEASIBLE" ? "chip-bad" : "chip-warn"}`}>
            {feasibility.status}
          </span>
          <span className="muted small">feasible={String(feasibility.feasible)}</span>
        </div>
        <DataTable
          columns={[
            { header: "Validation check", render: (c: (typeof feasibility.validation_checks)[0]) => <strong>{c.name}</strong> },
            { header: "Status", render: (c) => c.status },
            { header: "Detail", render: (c) => <span className="small">{c.detail}</span> },
          ]}
          rows={feasibility.validation_checks}
        />
      </Section>

      <Section title="Objective value & breakdown" subtitle={report.objective_value.statement}>
        <div className="table-wrap">
          <table className="data-table">
            <tbody>
              <tr><td>Objective value</td><td><strong className="mono">{report.objective_value.value}</strong> {report.objective_value.units} (direction: {report.objective_value.direction})</td></tr>
              <tr><td>Total procurement cost</td><td className="mono">{report.objective_breakdown.total_procurement_cost}</td></tr>
              <tr><td>Total unmet demand</td><td className="mono">{report.objective_breakdown.total_unmet_demand} units</td></tr>
              <tr><td>Total served demand</td><td className="mono">{report.objective_breakdown.total_served_demand} units</td></tr>
              <tr><td>Fulfillment rate</td><td className="mono">{report.objective_breakdown.fulfillment_rate}</td></tr>
            </tbody>
          </table>
        </div>
        <p className="muted small">{report.objective.description}</p>
      </Section>

      <Section title="Baseline comparison" subtitle={report.baseline_comparison?.note ?? ""}>
        <DataTable
          columns={[
            { header: "Plan", render: (row: [string, string]) => <strong>{row[0]}</strong> },
            { header: "Value", render: (row) => <span className="mono">{row[1]}</span> },
          ]}
          rows={comparisonRows(report)}
        />
        <h3 className="panel-subtitle" style={{ marginTop: 10 }}>Per-entity deltas (served/unmet by product-warehouse)</h3>
        {(report.baseline_comparison?.current_plan_plus_optimized_orders?.by_entity?.length ?? 0) > 0 ? (
          <DataTable
            columns={[
              { header: "Product", render: (e: NonNullable<OptimizationPlanSummary["by_entity"]>[0]) => <ShortId id={e.product_id} /> },
              { header: "Warehouse", render: (e) => <ShortId id={e.warehouse_id} /> },
              { header: "Served delta", render: (e) => e.served_demand_units.toLocaleString() },
              { header: "Unmet after", render: (e) => e.unmet_demand_units.toLocaleString() },
            ]}
            rows={report.baseline_comparison!.current_plan_plus_optimized_orders!.by_entity!.slice(0, 25)}
          />
        ) : (
          <p className="muted small">Per-entity plan rows were not reported by the API for this run.</p>
        )}
      </Section>

      <Section title="Declared constraints & assumptions">
        <p className="muted small">
          {report.problem_definition.declared_constraint_count} declared constraints over {report.problem_definition.decision_variable_count} decision variables;{" "}
          {report.problem_definition.excluded_offers.length} offers excluded from the eligible set.
        </p>
        <Limitations items={report.limitations} />
        <Limitations items={report.warnings.map((w) => `Warning: ${w}`)} />
      </Section>
    </>
  );
}

function runRows(report: OptimizationReport): [string, string][] {
  const run = report.optimization_run_metadata;
  return [
    ["Optimization ID", run.optimization_id],
    ["Scenario", run.scenario_id],
    ["Analysis date", run.analysis_date],
    ["Horizon", `${run.horizon_days} days`],
    ["Objective", run.objective_key],
    ["Solver", `${run.solver} ${report.solver_information.solver_version}`],
    ["Solver status", run.solver_status],
    ["Timings", Object.entries(run.timings_seconds).map(([k, v]) => `${k}=${(v as number).toFixed(2)}s`).join(", ")],
    ["Config", JSON.stringify(run.config)],
  ];
}

function comparisonRows(report: OptimizationReport): [string, string][] {
  const b = report.baseline_comparison;
  const d = b?.deltas;
  const num = (value: number | undefined | null, unit = ""): string =>
    value === undefined || value === null ? "(not reported)" : `${value}${unit}`;
  return [
    ["Current plan (event-aware deterministic)", fmtPlan(b?.current_plan ?? null)],
    ["Current plan + optimized orders", fmtPlan(b?.current_plan_plus_optimized_orders ?? null)],
    ["Δ unmet demand", d ? num(d.unmet_delta) : "deltas not reported"],
    ["Δ served demand", d ? num(d.served_delta) : "deltas not reported"],
    ["Δ added procurement cost", d ? num(d.added_procurement_cost) : "deltas not reported"],
    ["Δ fulfillment rate", d ? num(d.fulfillment_rate_delta) : "deltas not reported"],
    ["Basis", b?.basis ?? "(not reported)"],
  ];
}

function fmtPlan(plan: OptimizationPlanSummary | null): string {
  if (!plan) return "plan block not reported by the API";
  const num = (key: string): string => {
    const value = plan[key];
    return value === undefined || value === null ? "(not reported)" : String(value);
  };
  return [`served ${num("served_demand_units")}`, `unmet ${num("unmet_demand_units")}`, `fulfillment ${num("fulfillment_rate")}`, `procurement_cost ${plan.procurement_cost === undefined || plan.procurement_cost === null ? "not reported" : plan.procurement_cost}`].join(" · ");
}
