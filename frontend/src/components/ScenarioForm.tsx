import { NumberInput, SelectInput, TextInput, FilterBar } from "./Ui";
import type { SimulationEventMeta } from "../api/types";

/**
 * Shared scenario-composition form for the three compute endpoints
 * (Simulation, Decision Replay, Optimization). Mirrors the shared
 * ScenarioRequest body contract:
 * - exactly one of event_template / event_type;
 * - probability_mode / probability;
 * - optional entity scope;
 * - horizon/simulation bounds live in GET /simulation/events.
 */

export interface ScenarioFormState {
  useTemplate: boolean;
  template: string;
  eventType: string;
  durationDays: number | null;
  supplyReduction: number | null;
  leadTimeDelayDays: number | null;
  demandMultiplier: number | null;
  probabilityMode: "deterministic" | "explicit" | "empirical";
  probability: number | null;
  productId: string;
  warehouseId: string;
  supplierId: string;
  horizonDays: number;
  simulationCount: number;
  randomSeed: number;
  analysisDate: string;
  assumptions: string;
}

export type ScenarioRequestBody = {
  event_template?: string;
  event_type?: string;
  duration_days?: number;
  supply_reduction?: number;
  lead_time_delay_days?: number;
  demand_multiplier?: number;
  probability_mode?: "deterministic" | "explicit" | "empirical";
  probability?: number;
  assumptions?: string[];
  product_id?: string;
  warehouse_id?: string;
  supplier_id?: string;
  analysis_date?: string;
  horizon_days?: number;
  simulation_count?: number;
  random_seed?: number;
};

export function toScenarioBody(state: ScenarioFormState): ScenarioRequestBody {
  const body: ScenarioRequestBody = {};
  if (state.useTemplate) body.event_template = state.template;
  else body.event_type = state.eventType;
  if (state.durationDays !== null) body.duration_days = state.durationDays;
  if (!state.useTemplate) {
    if (state.supplyReduction !== null) body.supply_reduction = state.supplyReduction;
    if (state.leadTimeDelayDays !== null) body.lead_time_delay_days = state.leadTimeDelayDays;
    if (state.demandMultiplier !== null) body.demand_multiplier = state.demandMultiplier;
  }
  if (state.probabilityMode !== "deterministic") {
    body.probability_mode = state.probabilityMode;
    if (state.probabilityMode === "explicit" && state.probability !== null) {
      body.probability = state.probability;
    }
  }
  if (state.productId.trim()) body.product_id = state.productId.trim();
  if (state.warehouseId.trim()) body.warehouse_id = state.warehouseId.trim();
  if (state.supplierId.trim()) body.supplier_id = state.supplierId.trim();
  if (state.analysisDate.trim()) body.analysis_date = state.analysisDate.trim();
  const assumptions = state.assumptions.split("\n").map((s) => s.trim()).filter(Boolean);
  if (assumptions.length > 0) body.assumptions = assumptions;
  body.horizon_days = state.horizonDays;
  body.simulation_count = state.simulationCount;
  body.random_seed = state.randomSeed;
  return body;
}

export function defaultScenarioForm(meta: SimulationEventMeta | undefined): ScenarioFormState {
  const firstTemplate = Object.keys(meta?.templates ?? {})[0] ?? "SUPPLIER_OUTAGE";
  return {
    useTemplate: true,
    template: firstTemplate,
    eventType: meta?.event_types[0] ?? "SUPPLIER_OUTAGE",
    durationDays: null,
    supplyReduction: null,
    leadTimeDelayDays: null,
    demandMultiplier: null,
    probabilityMode: "deterministic",
    probability: null,
    productId: "",
    warehouseId: "",
    supplierId: "",
    horizonDays: meta?.bounds.horizon_days.default ?? 28,
    simulationCount: meta?.bounds.simulation_count.default ?? 20,
    randomSeed: meta?.bounds.random_seed_default ?? 42,
    analysisDate: "",
    assumptions: "",
  };
}

export function ScenarioForm({
  meta,
  value,
  onChange,
}: {
  meta: SimulationEventMeta | undefined;
  value: ScenarioFormState;
  onChange: (next: ScenarioFormState) => void;
}) {
  const templates = Object.keys(meta?.templates ?? {});
  const template = meta?.templates[value.template];
  const bounds = meta?.bounds;

  return (
    <div className="scenario-form">
      <FilterBar>
        <SelectInput
          label="Define event via"
          value={value.useTemplate ? "template" : "direct"}
          options={[
            { value: "template", label: "Locked template" },
            { value: "direct", label: "Direct event type" },
          ]}
          onChange={(v) => onChange({ ...value, useTemplate: v === "template" })}
        />
        {value.useTemplate ? (
          <SelectInput
            label="Event template"
            value={value.template}
            options={templates}
            onChange={(template) => onChange({ ...value, template })}
          />
        ) : (
          <SelectInput
            label="Event type"
            value={value.eventType}
            options={meta?.event_types ?? ["SUPPLIER_OUTAGE"]}
            onChange={(eventType) => onChange({ ...value, eventType })}
          />
        )}
        <SelectInput
          label="Probability mode"
          value={value.probabilityMode}
          options={(meta?.probability_modes ?? ["deterministic", "explicit", "empirical"]) as ScenarioFormState["probabilityMode"][]}
          onChange={(probabilityMode) => onChange({ ...value, probabilityMode })}
        />
        {value.probabilityMode === "explicit" ? (
          <NumberInput
            label="Probability (0–1)"
            value={value.probability ?? 0.5}
            min={0}
            max={1}
            step={0.05}
            onChange={(probability) => onChange({ ...value, probability })}
          />
        ) : null}
      </FilterBar>

      {value.useTemplate && template ? (
        <p className="muted small">
          <strong>{value.template}:</strong> {template.description} (default duration {template.duration_days} days)
        </p>
      ) : null}
      {!value.useTemplate ? (
        <FilterBar>
          <NumberInput
            label="Duration (days)"
            value={value.durationDays ?? 14}
            min={bounds?.duration_days.min ?? 1}
            max={bounds?.duration_days.max ?? 90}
            onChange={(durationDays) => onChange({ ...value, durationDays })}
          />
          <NumberInput
            label="Supply reduction (0–1)"
            value={value.supplyReduction ?? 0}
            min={0}
            max={1}
            step={0.05}
            onChange={(supplyReduction) => onChange({ ...value, supplyReduction })}
          />
          <NumberInput
            label="Lead-time delay (days)"
            value={value.leadTimeDelayDays ?? 0}
            min={0}
            max={60}
            onChange={(leadTimeDelayDays) => onChange({ ...value, leadTimeDelayDays })}
          />
          <NumberInput
            label="Demand multiplier"
            value={value.demandMultiplier ?? 1}
            min={0}
            max={5}
            step={0.1}
            onChange={(demandMultiplier) => onChange({ ...value, demandMultiplier })}
          />
        </FilterBar>
      ) : null}

      <FilterBar>
        <NumberInput
          label="Horizon (days)"
          value={value.horizonDays}
          min={bounds?.horizon_days.min ?? 1}
          max={bounds?.horizon_days.max ?? 180}
          onChange={(horizonDays) => onChange({ ...value, horizonDays })}
        />
        <NumberInput
          label="Simulations"
          value={value.simulationCount}
          min={bounds?.simulation_count.min ?? 1}
          max={bounds?.simulation_count.max ?? 500}
          onChange={(simulationCount) => onChange({ ...value, simulationCount })}
        />
        <NumberInput
          label="Random seed"
          value={value.randomSeed}
          min={0}
          onChange={(randomSeed) => onChange({ ...value, randomSeed })}
        />
        <TextInput
          label="Analysis date (optional, YYYY-MM-DD)"
          value={value.analysisDate}
          onChange={(analysisDate) => onChange({ ...value, analysisDate })}
          placeholder="blank = engine default"
        />
      </FilterBar>

      <FilterBar>
        <TextInput
          label="Product scope (optional ID)"
          value={value.productId}
          onChange={(productId) => onChange({ ...value, productId })}
          placeholder="blank = all products"
        />
        <TextInput
          label="Warehouse scope (optional ID)"
          value={value.warehouseId}
          onChange={(warehouseId) => onChange({ ...value, warehouseId })}
          placeholder="blank = all warehouses"
        />
        <TextInput
          label="Supplier scope (optional ID)"
          value={value.supplierId}
          onChange={(supplierId) => onChange({ ...value, supplierId })}
          placeholder="blank = all suppliers"
        />
      </FilterBar>

      <label className="field field-wide">
        <span>Assumptions (one per line, optional — recorded verbatim in the report)</span>
        <textarea
          rows={2}
          value={value.assumptions}
          onChange={(e) => onChange({ ...value, assumptions: e.target.value })}
          placeholder="e.g. supplier confirms 10 percent recovery"
        />
      </label>

      <p className="muted small">
        Scope fields take raw entity IDs (no lookup endpoint exists in this phase). Blank = engine
        default scope. The exact request body is shown under the results for traceability.
      </p>
    </div>
  );
}
