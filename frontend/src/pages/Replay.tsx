import { useState, type ReactNode } from "react";
import { DataSourceLabelChip } from "../components/DataSourceLabel";
import { PageGate, PlannerGate } from "../components/PageGate";
import { ScenarioForm, defaultScenarioForm, toScenarioBody, type ScenarioFormState } from "../components/ScenarioForm";
import { DataTable } from "../components/DataTable";
import { Section } from "../components/Ui";
import { EmptyState, ErrorState, Limitations, LoadingState } from "../components/StateViews";
import { endpoints } from "../api/endpoints";
import { useApiQuery } from "../state/useApiQuery";
import { ApiError } from "../api/client";
import type { DecisionArm, DecisionType, ReplayReport, ReplayRunRequest } from "../api/types";
import { SpanDelta } from "./Simulation";

/**
 * Decision Replay — POST /replay/run with explicitly declared decision arms
 * vs the auto NO_ACTION control arm (planner+). The UI preserves the API's
 * no-ranking discipline: deltas are shown factually, never "better/worse
 * advised". Two structured arm builders are provided for the validated
 * parameter subsets; anything else must be declared in JSON.
 */
export function ReplayPage() {
  return (
    <PageGate>
      <PlannerGate action="Decision replay">
        <ReplayBody />
      </PlannerGate>
    </PageGate>
  );
}

const DECISION_LABELS: { value: DecisionType; label: string; note: string }[] = [
  { value: "EXPEDITE_INBOUND", label: "Expedite inbound", note: "quantities.expedite_units + timing.delay_reduction_days (>0)" },
  { value: "DEMAND_ADJUSTMENT", label: "Adjust demand", note: "quantities.demand_multiplier" },
  { value: "PURCHASE_ORDER_ADJUSTMENT", label: "Adjust purchase order", note: "quantities.order_units + timing.arrival_day (0 <= day < horizon)" },
  { value: "INVENTORY_TRANSFER", label: "Transfer inventory", note: "quantities.transfer_units + exactly one affected product ID" },
  { value: "ALTERNATIVE_SUPPLIER", label: "Use alternative supplier", note: "affected suppliers + products + allocation quantities (your explicit selection)" },
  { value: "SUPPLIER_ALLOCATION_CHANGE", label: "Change supplier allocation", note: "quantities = {supplier_id: units}; must sum > 0" },
  { value: "NO_ACTION", label: "No action (control)", note: "auto-added control arm — no need to declare" },
];

interface ArmDraft {
  decisionType: DecisionType;
  expediteUnits: number;
  delayReductionDays: number;
  demandMultiplier: number;
  orderUnits: number;
  arrivalDay: number;
  transferUnits: number;
  affectedProduct: string;
  altSupplier: string;
  altProduct: string;
  altUnits: number;
  customJson: string;
  useCustomJson: boolean;
}

const BASE_ARM: ArmDraft = {
  decisionType: "EXPEDITE_INBOUND",
  expediteUnits: 200,
  delayReductionDays: 3,
  demandMultiplier: 1.1,
  orderUnits: 0,
  arrivalDay: 0,
  transferUnits: 0,
  affectedProduct: "",
  altSupplier: "",
  altProduct: "",
  altUnits: 0,
  customJson: "",
  useCustomJson: false,
};

function armToRequest(arm: ArmDraft): DecisionArm | { error: string } {
  if (arm.useCustomJson) {
    try {
      return JSON.parse(arm.customJson) as DecisionArm;
    } catch (error) {
      return { error: `Decision JSON is not valid JSON: ${String(error)}` };
    }
  }
  if (arm.decisionType === "NO_ACTION") return { error: "NO_ACTION is added automatically as the control arm." };
  const base: DecisionArm = { decision_type: arm.decisionType };
  switch (arm.decisionType) {
    case "EXPEDITE_INBOUND":
      return {
        ...base,
        quantities: { expedite_units: arm.expediteUnits },
        timing: { delay_reduction_days: arm.delayReductionDays },
      };
    case "DEMAND_ADJUSTMENT":
      return { ...base, quantities: { demand_multiplier: arm.demandMultiplier } };
    case "PURCHASE_ORDER_ADJUSTMENT":
      return {
        ...base,
        quantities: { order_units: arm.orderUnits },
        timing: { arrival_day: arm.arrivalDay },
      };
    case "INVENTORY_TRANSFER":
      if (!arm.affectedProduct.trim()) return { error: "INVENTORY_TRANSFER requires exactly one affected product ID." };
      return { ...base, affected_products: [arm.affectedProduct.trim()], quantities: { transfer_units: arm.transferUnits } };
    case "ALTERNATIVE_SUPPLIER":
      if (!arm.altSupplier.trim() || !arm.altProduct.trim()) {
        return { error: "ALTERNATIVE_SUPPLIER requires affected supplier and product IDs (your explicit selection)." };
      }
      return {
        ...base,
        affected_suppliers: arm.altSupplier.split(",").map((s) => s.trim()).filter(Boolean),
        affected_products: arm.altProduct.split(",").map((s) => s.trim()).filter(Boolean),
        quantities: { alternative_units: arm.altUnits },
      };
    case "SUPPLIER_ALLOCATION_CHANGE": {
      const allocations: Record<string, number> = {};
      arm.altSupplier.split(",").map((s) => s.trim()).filter(Boolean).forEach((supplierId) => {
        allocations[supplierId] = arm.altUnits;
      });
      if (Object.keys(allocations).length === 0) return { error: "SUPPLIER_ALLOCATION_CHANGE requires supplier IDs (comma-separated)." };
      return { ...base, quantities: allocations };
    }
    default:
      return { error: "Use the JSON editor for COMBINED_ACTION." };
  }
}

function ReplayBody() {
  const decisionMeta = useApiQuery(() => endpoints.replayDecisions(), []);
  const scenarioMeta = useApiQuery(() => endpoints.simulationEvents(), []);
  const [form, setForm] = useState<ScenarioFormState | null>(null);
  const [arms, setArms] = useState<ArmDraft[]>([]);
  const [report, setReport] = useState<ReplayReport | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<ApiError | null>(null);

  if (decisionMeta.status === "loading" || scenarioMeta.status === "loading") {
    return <div className="page"><LoadingState message="Loading decision vocabulary…" /></div>;
  }
  if (decisionMeta.status === "error") {
    return <div className="page"><ErrorState error={decisionMeta.error} what="the replay decision vocabulary" /></div>;
  }
  if (decisionMeta.status === "empty") {
    return <div className="page"><EmptyState what="replay decision metadata" /></div>;
  }

  const state0 = form ?? defaultScenarioForm(scenarioMeta.status === "ok" ? scenarioMeta.data : undefined);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Decision Replay</h1>
        <span className="muted">Declared decision arms vs NO_ACTION baseline — factual deltas only</span>
        <DataSourceLabelChip label="simulated" />
      </div>

      <div className="sim-banner" role="note">
        This system never ranks, never recommends, never scores. You declare the arms; the report states
        factual differences between them.
      </div>

      <Section title="Decision vocabulary" subtitle={`From GET /replay/decisions · max ${decisionMeta.data.max_decisions} declared arms per run`}>
        <DataTable
          columns={[
            { header: "Decision type", render: (d: { value: DecisionType; label: string; note: string }) => <strong>{d.value}</strong> },
            { header: "Required parameters (validated by API)", render: (d) => <span className="small">{d.note}</span> },
          ]}
          rows={DECISION_LABELS}
        />
        <Limitations items={decisionMeta.data.notes} />
      </Section>

      <Section title="Scenario inputs" subtitle="Same shared scenario contract as simulation">
        <ScenarioForm meta={scenarioMeta.status === "ok" ? scenarioMeta.data : undefined} value={state0} onChange={setForm} />
      </Section>

      <Section
        title={`Declared decision arms (${arms.length})`}
        subtitle="Each arm runs as declared; NO_ACTION is always included automatically as the control arm."
        actions={
          <button type="button" className="btn btn-sm" onClick={() => setArms([...arms, { ...BASE_ARM }])} disabled={arms.length >= decisionMeta.data.max_decisions}>
            + Add arm
          </button>
        }
      >
        {arms.length === 0 ? (
          <p className="muted small">No declared arms yet — a run with zero arms reports the NO_ACTION arm against baseline only.</p>
        ) : (
          arms.map((arm, index) => (
            <ArmEditor
              key={index}
              index={index}
              arm={arm}
              horizon={state0.horizonDays}
              onChange={(next) => setArms(arms.map((a, i) => (i === index ? next : a)))}
              onRemove={() => setArms(arms.filter((_, i) => i !== index))}
            />
          ))
        )}
        <div className="center-row" style={{ justifyContent: "flex-start", gap: 10, marginTop: 8 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={running}
            onClick={async () => {
              setRunning(true);
              setRunError(null);
              setReport(null);
              try {
                const body: ReplayRunRequest = { ...toScenarioBody(state0) };
                const decisions: DecisionArm[] = [];
                for (const arm of arms) {
                  const request = armToRequest(arm);
                  if ("error" in request) {
                    throw new ApiError(0, "VALIDATION_ERROR", request.error, { details: { reason: request.error } });
                  }
                  decisions.push(request);
                }
                if (decisions.length > 0) body.decisions = decisions;
                const ok = await endpoints.replayRun(body);
                setReport(ok.data);
              } catch (err) {
                setRunError(err instanceof ApiError ? err : new ApiError(0, "UNKNOWN", String(err)));
              } finally {
                setRunning(false);
              }
            }}
          >
            {running ? "Replaying…" : "Run replay comparison"}
          </button>
        </div>
        {running ? <LoadingState message="Replaying declared arms — this can take a minute…" /> : null}
        {runError ? <ErrorState error={runError} what="the replay run" /> : null}
      </Section>

      {report ? <ReplayReportView report={report} /> : null}
    </div>
  );
}

function ArmEditor({
  index,
  arm,
  horizon,
  onChange,
  onRemove,
}: {
  index: number;
  arm: ArmDraft;
  horizon: number;
  onChange: (arm: ArmDraft) => void;
  onRemove: () => void;
}) {
  return (
    <div className="panel" style={{ padding: 10, marginBottom: 8 }}>
      <div className="panel-header">
        <h3 style={{ margin: 0, fontSize: 13 }}>Arm #{index + 1}</h3>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <select
            aria-label="Decision type"
            className="field"
            style={{ minWidth: 220 }}
            value={arm.decisionType}
            onChange={(e) => onChange({ ...arm, decisionType: e.target.value as DecisionType })}
          >
            {DECISION_LABELS.filter((d) => d.value !== "NO_ACTION" && d.value !== "COMBINED_ACTION").map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
            <option value="COMBINED_ACTION">Combined (via JSON)</option>
          </select>
          <button type="button" className="btn btn-sm btn-danger" onClick={onRemove}>
            Remove
          </button>
        </div>
      </div>
      {arm.decisionType === "COMBINED_ACTION" || arm.useCustomJson ? (
        <label className="field field-wide">
          <span>Decision JSON (backend validates it; see the vocabulary table for required fields)</span>
          <textarea rows={4} value={arm.customJson} onChange={(e) => onChange({ ...arm, customJson: e.target.value })} />
        </label>
      ) : (
        <ArmFields arm={arm} horizon={horizon} onChange={onChange} />
      )}
    </div>
  );
}

function ArmFields({ arm, horizon, onChange }: { arm: ArmDraft; horizon: number; onChange: (arm: ArmDraft) => void }) {
  const num = (label: string, key: keyof ArmDraft, min?: number, max?: number, step?: number) => (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        value={String(arm[key])}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange({ ...arm, [key]: Number(e.target.value) })}
      />
    </label>
  );
  const text = (label: string, key: keyof ArmDraft, placeholder?: string) => (
    <label className="field">
      <span>{label}</span>
      <input value={String(arm[key])} placeholder={placeholder} onChange={(e) => onChange({ ...arm, [key]: e.target.value })} />
    </label>
  );
  switch (arm.decisionType) {
    case "EXPEDITE_INBOUND":
      return <FilterRow>{num("Expedite units", "expediteUnits")}{num("Delay reduction (days, >0)", "delayReductionDays", 1)}</FilterRow>;
    case "DEMAND_ADJUSTMENT":
      return <FilterRow>{num("Demand multiplier (0–5)", "demandMultiplier", 0, 5, 0.05)}</FilterRow>;
    case "PURCHASE_ORDER_ADJUSTMENT":
      return <FilterRow>{num("Order units", "orderUnits")}{num(`Arrival day (0–${horizon - 1})`, "arrivalDay", 0, horizon - 1)}</FilterRow>;
    case "INVENTORY_TRANSFER":
      return <FilterRow>{num("Transfer units", "transferUnits")}{text("Affected product ID (exactly one)", "affectedProduct")}</FilterRow>;
    case "ALTERNATIVE_SUPPLIER":
      return <FilterRow>{text("Affected supplier IDs (comma-separated)", "altSupplier")}{text("Affected product IDs (comma-separated)", "altProduct")}{num("Alternative units", "altUnits")}</FilterRow>;
    case "SUPPLIER_ALLOCATION_CHANGE":
      return <FilterRow>{text("Supplier IDs for allocation (comma-separated)", "altSupplier")}{num("Units per supplier", "altUnits")}</FilterRow>;
    default:
      return null;
  }
}

function FilterRow({ children }: { children: ReactNode }) {
  return <div className="filter-bar" style={{ margin: 0 }}>{children}</div>;
}

function ReplayReportView({ report }: { report: ReplayReport }) {
  const baseline = report.shared_baseline.outcome;
  const arms = report.replay_metadata.decisions;
  const baselineRef = report.shared_baseline.baseline_ref;

  // NO_ACTION arm uses the shared baseline outcome directly.
  const baselineRecord = baseline as unknown as Record<string, unknown>;
  const outcomeFor = (decisionId: string): Record<string, unknown> | null => {
    if (decisionId === baselineRef) return baselineRecord;
    const inventory = report.inventory_outcomes[decisionId];
    const service = report.service_outcomes[decisionId];
    if (!inventory || !service) return null;
    return { ...inventory, ...service };
  };

  return (
    <>
      <div className="sim-banner">
        Replay {report.replay_metadata.replay_id}: {arms.length} arm(s) incl. the NO_ACTION control. All figures are
        simulated over the shared baseline.
      </div>

      <Section title="Shared baseline outcome" subtitle={report.replay_metadata.baseline_ref}>
        <OutcomeTable outcome={baselineRecord} />
      </Section>

      <Section title="Arm outcomes vs shared baseline" subtitle={report.baseline_comparison.semantics}>
        <DataTable
          columns={[
            { header: "Decision", render: (d: (typeof arms)[0]) => <strong>{d.decision_type}</strong> },
            { header: "ID", render: (d) => <code className="short-id">{d.decision_id}</code> },
            { header: "Δ stockout probability", render: (d) => <DeltaCell id={d.decision_id} value={report.baseline_comparison.deltas[d.decision_id]?.delta_stockout_probability} /> },
            { header: "Δ unmet demand", render: (d) => <DeltaCell id={d.decision_id} value={report.baseline_comparison.deltas[d.decision_id]?.delta_unmet_demand} decimals={2} units="units" /> },
            { header: "Δ min inventory", render: (d) => <DeltaCell id={d.decision_id} value={report.baseline_comparison.deltas[d.decision_id]?.delta_min_inventory} decimals={2} units="units" /> },
            { header: "Δ ending inventory", render: (d) => <DeltaCell id={d.decision_id} value={report.baseline_comparison.deltas[d.decision_id]?.delta_ending_inventory} decimals={2} units="units" /> },
            { header: "Outcome", render: (d) => <OutcomePeek outcome={outcomeFor(d.decision_id)} /> },
          ]}
          rows={arms}
        />
      </Section>

      {report.decision_to_decision_comparison.pairs.length > 0 ? (
        <Section title="Decision-to-decision deltas" subtitle={report.decision_to_decision_comparison.semantics}>
          <DataTable
            columns={[
              { header: "Right decision", render: (p: (typeof report.decision_to_decision_comparison.pairs)[0]) => <strong>{p.right_decision_type}</strong> },
              { header: "Left decision", render: (p) => p.left_decision_type },
              { header: "Δ stockout prob.", render: (p) => <SpanDelta v={p.deltas.delta_stockout_probability} /> },
              { header: "Δ unmet demand", render: (p) => <SpanDelta v={p.deltas.delta_unmet_demand} /> },
              { header: "Δ stockout days", render: (p) => <SpanDelta v={p.deltas.delta_stockout_days} /> },
            ]}
            rows={report.decision_to_decision_comparison.pairs}
          />
        </Section>
      ) : null}

      <Section title="Scenario + decision assumptions" subtitle={report.scenario_assumptions.note}>
        <ul className="evidence-list">
          {[...report.scenario_assumptions.assumptions, ...report.scenario_assumptions.event_assumptions].map((a, i) => (
            <li key={`${i}-${a}`}>{a}</li>
          ))}
        </ul>
      </Section>

      <Limitations items={report.limitations} />
    </>
  );
}

function OutcomePeek({ outcome }: { outcome: unknown }) {
  if (!outcome) return <span className="muted small">not reported</span>;
  const record = outcome as Record<string, unknown>;
  return (
    <span className="mono small">
      P(stockout) {String(record.stockout_probability)} · unmet {String(record.expected_unmet_demand)}
    </span>
  );
}

function DeltaCell({ id, value, decimals = 6, units }: { id: string; value: number | undefined; decimals?: number; units?: string }) {
  if (value === undefined) return <span className="muted">—</span>;
  void id;
  const positive = value > 1e-12;
  const negative = value < -1e-12;
  return (
    <span className={`mono small ${positive ? "delta-positive" : negative ? "delta-negative" : "delta-neutral"}`}>
      {positive ? "+" : ""}{value.toFixed(decimals)}{units ? ` ${units}` : ""}
    </span>
  );
}

function OutcomeTable({ outcome }: { outcome: Record<string, unknown> }) {
  const rows = Object.entries(outcome).filter(([, v]) => typeof v !== "object");
  return (
    <DataTable
      columns={[
        { header: "Metric", render: (r: [string, unknown]) => <strong>{r[0]}</strong> },
        { header: "Value", render: (r) => <span className="mono">{String(r[1])}</span> },
      ]}
      rows={rows.slice(0, 14)}
    />
  );
}
