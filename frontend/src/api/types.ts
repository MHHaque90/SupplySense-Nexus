/**
 * Shared API types derived from the live Phase 12A OpenAPI schema and
 * captured response samples (never invented).
 */

export type DataSourceLabel = "derived" | "forecast" | "synthetic" | "simulated";

export interface Meta {
  timestamp: string;
  data_source_label: DataSourceLabel;
  source?: string;
  analysis_date?: string;
  limitations?: string[];
  session_id?: string | null;
  conversation_id?: string | null;
  provider?: string;
  intent?: string;
  approval_ids?: string[];
  [key: string]: unknown;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: ApiErrorBody | null;
  meta?: Meta;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: { reason?: string; [key: string]: unknown };
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  /* Server-side context fields observed on paginated responses. */
  analysis_date?: string;
  horizon_days?: number;
  overview?: RiskOverview;
}

/* ---------- identity ---------- */

export interface AuthIdentity {
  user_id: string;
  email: string;
  role: string;
  organization_id: string;
  is_active: boolean;
}

/* ---------- KPI primitives ---------- */

export interface KpiMetric {
  metric_name: string;
  value: number | null;
  unit: string;
  numerator: number | null;
  denominator: number | null;
  time_start: string | null;
  time_end: string | null;
  grain: string;
  dimensions: Record<string, string>;
  source_tables: string[];
  synthetic: boolean;
  formula: string;
  notes: string;
}

/* ---------- dashboard ---------- */

export interface InventoryKpiGroups {
  current_on_hand: KpiMetric[];
  inventory_levels: KpiMetric[];
  stockout_stats: KpiMetric[];
  movement_summary: KpiMetric[];
  turnover_proxy: KpiMetric[];
  days_of_supply: KpiMetric[];
}

export interface ProcurementKpiGroups {
  procurement_summary: KpiMetric[];
  lead_time_stats: KpiMetric[];
  shipment_performance: KpiMetric[];
  moq_compliance: KpiMetric[];
  concentration: KpiMetric[];
}

export interface DashboardOverview {
  analysis_date: string;
  horizon_days: number;
  kpis: {
    demand: KpiMetric[];
    inventory: InventoryKpiGroups;
    service: KpiMetric[];
    procurement: ProcurementKpiGroups;
  };
  risk: RiskOverview;
  forecast_status: { persisted_forecast_rows: number };
  limitations: string[];
}

/* ---------- forecast ---------- */

export interface ForecastRow {
  series_id: string;
  product_id: string;
  warehouse_id: string;
  origin: string;
  forecast_dates: string[];
  horizon: number;
  point: number[];
  lower: number[];
  upper: number[];
  confidence_level: number;
  interval_method: string;
  model_name: string;
  model_version: string;
  demand_profile: string;
  validation_metric: string;
  validation_score: number | null;
  validation_folds: number;
  confidence: Record<string, unknown>;
  explanation: string;
  warnings: string[];
  source: string;
  missing: boolean;
}

export type ForecastQuery = {
  product_id?: string;
  warehouse_id?: string;
  horizon?: number;
  profile?: string;
  start_date?: string;
  end_date?: string;
  analysis_date?: string;
  page?: number;
  page_size?: number;
};

/* ---------- inventory ---------- */

export interface InventoryPositionRow {
  product_id: string;
  warehouse_id: string;
  analysis_date: string;
  current_on_hand: number;
  latest_snapshot_date: string;
  recent_average: number;
  recent_minimum: number;
  recent_maximum: number;
  recent_volatility: number;
  recent_inflow: number;
  recent_outflow: number;
  adjustment_count: number;
  stockout_observations: number;
  unknown: boolean;
}

export interface InventoryHealthRow {
  product_id: string;
  warehouse_id: string;
  health: string;
  reason: string;
  missing_evidence: string[];
}

export interface InventoryOverview {
  analysis_date: string;
  kpis: InventoryKpiGroups & { service: KpiMetric[] };
  limitations: string[];
}

/* ---------- suppliers ---------- */

export interface SupplierRow {
  supplier_id: string;
  supplier_name: string;
  country: string;
  rating: number;
}

export interface SupplierPerformanceRow {
  supplier_id: string;
  supplier_name: string;
  analysis_date: string;
  po_count: number;
  po_line_count: number;
  ordered_quantity: number;
  received_quantity: number;
  shipment_count: number;
  completed_shipments: number;
  on_time_shipments: number;
  late_shipments: number;
  on_time_rate: number;
  average_delay_days: number;
  median_delay_days: number;
  max_delay_days: number;
  average_lead_time_days: number;
  median_lead_time_days: number;
  min_lead_time_days: number;
  max_lead_time_days: number;
  lead_time_std: number;
  missing_evidence: string[];
}

/* ---------- procurement ---------- */

export interface ProcurementOverview {
  analysis_date: string;
  kpis: ProcurementKpiGroups;
  limitations: string[];
}

export interface OpenOrderRow {
  po_id: string;
  po_number: string;
  supplier_id: string;
  product_id: string;
  order_date: string;
  expected_arrival: string;
  ordered_quantity: number;
  received_quantity: number;
  remaining_quantity: number;
  overdue: boolean;
  days_outstanding: number;
  arrival_status: string;
}

export interface InboundCoverageRow {
  product_id: string;
  warehouse_id: string;
  state: string;
  known_inbound: number;
  uncovered_demand: number;
  reason: string;
}

export interface ProcurementRiskRow {
  supplier_id: string;
  product_id: string | null;
  signal: string;
  severity: string;
  reason: string;
  evidence: string[];
  metrics: {
    late_rate?: number;
    shipments?: number;
    at_risk_products?: number;
    stockout_products?: number;
    urgent_products?: number;
    [key: string]: unknown;
  };
  missing_evidence: string[];
}

/* ---------- risk ---------- */

export interface RiskOverview {
  records: number;
  domains: string[];
  severity_counts: Record<string, Record<string, number>>;
}

export interface RiskRecordRow {
  risk_id: string;
  domain: string;
  entity_type: string;
  entity_id: string;
  product_id: string;
  warehouse_id: string;
  supplier_id: string | null;
  analysis_date: string;
  state: string;
  severity: string;
  evidence: string[];
  metrics: Record<string, number>;
  supporting_records: string[];
  missing_evidence: string[];
  confidence: Record<string, unknown>;
  provenance: Record<string, unknown>;
  explanation: string;
  synthetic: boolean;
}

export type RiskQuery = {
  severity?: string;
  domain?: string;
  supplier_id?: string;
  product_id?: string;
  warehouse_id?: string;
  horizon_days?: number;
  analysis_date?: string;
  page?: number;
  page_size?: number;
};

/* ---------- simulation ---------- */

export interface BoundRange {
  min: number;
  max: number;
  default?: number;
}

export interface SimulationEventMeta {
  event_types: string[];
  templates: Record<string, { event_type: string; description: string; duration_days: number }>;
  probability_modes: string[];
  bounds: {
    horizon_days: BoundRange;
    simulation_count: BoundRange;
    duration_days: BoundRange;
    random_seed_default: number;
  };
  notes: string[];
}

export interface ScenarioEvent {
  event_id: string;
  event_type: string;
  name?: string;
  description: string;
  start_date?: string;
  duration_days: number;
  affected_suppliers: string[];
  affected_products: string[];
  affected_warehouses: string[];
  supply_reduction: number;
  lead_time_delay_days: number;
  demand_multiplier: number;
  warehouse_available: boolean;
  probability_mode: string;
  probability: number;
  probability_source: string;
  severity: string;
  assumptions: string[];
  source: string;
  data_source_label: string;
  distributions: unknown[];
  components: unknown[];
}

export interface ScenarioDefinition {
  scenario_id: string;
  name: string;
  description: string;
  analysis_date: string;
  horizon_days: number;
  event: ScenarioEvent;
  affected_entities: { entity_type: string; supplier_id?: string; product_id?: string; warehouse_id?: string }[];
  baseline_source: string;
  probability_mode: string;
  probability: number;
  probability_source: string;
  simulation_count: number;
  random_seed: number;
  assumptions: string[];
  source: string;
  data_source_label: string;
  selection_basis: string;
}

export interface OutcomeDistribution {
  mean: number;
  median: number;
  min: number;
  max: number;
  p05: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number | null;
}

export interface ScenarioOutcome {
  label: string;
  stockout_probability: number;
  stockout_count: number;
  expected_stockout_days: number;
  expected_min_inventory: number;
  expected_ending_inventory: number;
  inventory_depletion_probability: number;
  affected_product_count: number;
  affected_warehouse_count: number;
  service_exposure_probability: number;
  expected_unmet_demand: number;
  median_unmet_demand: number;
  p90_unmet_demand: number;
  p95_unmet_demand: number;
  affected_supplier_count: number;
  affected_supplier_product_count: number;
  affected_inbound_count: number;
  delayed_inbound_quantity: number;
  unavailable_inbound_quantity: number;
  stockout_by_day: {
    probability_stockout_by_7d: number;
    probability_stockout_by_14d: number | null;
    probability_stockout_by_28d: number | null;
  };
  first_stockout_dates: unknown[];
  distributions: { unmet_demand: OutcomeDistribution; ending_inventory: OutcomeDistribution };
}

export interface DeltaSet {
  delta_stockout_probability: number;
  delta_unmet_demand: number;
  delta_min_inventory: number;
  delta_ending_inventory: number;
  delta_stockout_days: number;
  delta_service_exposure: number;
}

export interface SimulationRunRequest {
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
}

export interface SimulationReport {
  disclaimer: string;
  synthetic: boolean;
  scenario_definition: ScenarioDefinition;
  event_type: string;
  event_assumptions: string[];
  probability_mode: string;
  probability_provenance: { mode: string; probability: number; source: string };
  baseline_definition: { source: string; note: string };
  simulation_configuration: { horizon_days: number; simulation_count: number; random_seed: number };
  inventory_outcomes: ScenarioOutcome;
  service_outcomes: Pick<ScenarioOutcome, "service_exposure_probability" | "expected_unmet_demand" | "median_unmet_demand" | "p90_unmet_demand" | "p95_unmet_demand" | "affected_product_count" | "affected_warehouse_count">;
  supply_outcomes: Pick<ScenarioOutcome, "affected_supplier_count" | "affected_supplier_product_count" | "affected_inbound_count" | "delayed_inbound_quantity" | "unavailable_inbound_quantity">;
  stockout_distribution: {
    stockout_by_day: ScenarioOutcome["stockout_by_day"];
    first_stockout_dates: unknown[];
    expected_stockout_days: number;
  };
  unmet_demand_distribution: OutcomeDistribution;
  baseline_outcome: ScenarioOutcome;
  scenario_outcome: ScenarioOutcome;
  delta: DeltaSet;
  forecast_uncertainty: { note: string };
  scenario_uncertainty: { distributions: unknown[]; note: string };
  simulation_variability: { random_seed: number; simulation_count: number; note: string };
  traceability: Record<string, unknown>[];
  limitations: string[];
  data_source_label: string;
}

/* ---------- replay ---------- */

export const DECISION_TYPES = [
  "NO_ACTION",
  "EXPEDITE_INBOUND",
  "ALTERNATIVE_SUPPLIER",
  "SUPPLIER_ALLOCATION_CHANGE",
  "INVENTORY_TRANSFER",
  "DEMAND_ADJUSTMENT",
  "PURCHASE_ORDER_ADJUSTMENT",
  "COMBINED_ACTION",
] as const;

export type DecisionType = (typeof DECISION_TYPES)[number];

export interface ReplayDecisionMeta {
  decision_types: string[];
  max_decisions: number;
  notes: string[];
}

export interface DecisionArm {
  decision_type: DecisionType;
  description?: string;
  affected_suppliers?: string[];
  affected_products?: string[];
  affected_warehouses?: string[];
  quantities?: Record<string, number | Record<string, number>>;
  timing?: Record<string, number>;
  cost_assumptions?: Record<string, number>;
  assumptions?: string[];
  components?: DecisionArm[];
}

export interface ReplayRunRequest {
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
  decisions?: DecisionArm[];
}

export interface ReplayReport {
  synthetic_data_disclaimer: string;
  replay_metadata: {
    replay_id: string;
    scenario_id: string;
    baseline_ref: string;
    decision_count: number;
    decisions: { decision_id: string; decision_type: string; synthetic: boolean; sample_fingerprint: string }[];
    skipped_decisions: unknown[];
    synthetic: boolean;
    data_source_label: string;
  };
  disruption_scenario: ScenarioDefinition;
  scenario_assumptions: {
    assumptions: string[];
    event_assumptions: string[];
    probability: { mode: string; value: number; source: string };
    fingerprint: Record<string, unknown>;
    note: string;
  };
  shared_baseline: { baseline_ref: string; outcome: ScenarioOutcome; note: string };
  decision_definitions: {
    decision_id: string;
    decision_type: string;
    description: string;
    affected_suppliers: string[];
    affected_products: string[];
    affected_warehouses: string[];
    quantities: Record<string, unknown>;
    timing: Record<string, unknown>;
    cost_assumptions: Record<string, unknown>;
    source: string;
    data_label: string;
  }[];
  inventory_outcomes: Record<string, Pick<ScenarioOutcome, "stockout_probability" | "expected_stockout_days" | "expected_min_inventory" | "expected_ending_inventory" | "inventory_depletion_probability">>;
  service_outcomes: Record<string, Pick<ScenarioOutcome, "expected_unmet_demand" | "service_exposure_probability" | "affected_product_count" | "affected_warehouse_count">>;
  supply_outcomes: Record<string, Pick<ScenarioOutcome, "affected_supplier_count" | "affected_inbound_count" | "delayed_inbound_quantity" | "unavailable_inbound_quantity">>;
  baseline_comparison: {
    semantics: string;
    deltas: Record<string, DeltaSet>;
  };
  decision_to_decision_comparison: {
    semantics: string;
    pairs: {
      left_decision_id: string;
      left_decision_type: string;
      right_decision_id: string;
      right_decision_type: string;
      deltas: DeltaSet;
      semantics: string;
    }[];
  };
  limitations: string[];
  phase_10_handoff: string[];
  data_source_label: string;
}

/* ---------- optimization ---------- */

export const OBJECTIVES = [
  "minimize_total_cost",
  "minimize_shortage",
  "cost_shortage_tradeoff",
  "maximize_service_fulfillment",
] as const;

export type Objective = (typeof OBJECTIVES)[number];

/** Plan summary blocks may be omitted by the API in some configurations (legacy sample had note/by_entity variants). */
export interface OptimizationPlanSummary {
  served_demand_units?: number;
  unmet_demand_units?: number;
  fulfillment_rate?: number;
  procurement_cost?: number | null;
  note?: string;
  by_entity?: { product_id: string; warehouse_id: string; served_demand_units: number; unmet_demand_units: number }[];
  [key: string]: unknown;
}

export interface OptimizationRunRequest {
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
  objective?: Objective;
  shortage_penalty?: number;
  budget?: number;
  min_fulfillment?: number;
  quantity_integrality?: "integer" | "continuous";
  time_limit_seconds?: number;
}

export interface OptimizationReport {
  report_type: string;
  sections: string[];
  synthetic: boolean;
  data_source_label: string;
  synthetic_data_disclaimer: { disclaimer: string; data_source_label: string; statement: string };
  optimization_run_metadata: {
    optimization_id: string;
    replay_id: string;
    scenario_id: string;
    analysis_date: string;
    horizon_days: number;
    objective_key: string;
    solver: string;
    solver_status: string;
    timings_seconds: Record<string, number>;
    config: Record<string, unknown>;
    synthetic: boolean;
    data_source_label: string;
  };
  source_scenario: {
    scenario_id: string;
    name: string;
    analysis_date: string;
    horizon_days: number;
    event: { event_id: string; event_type: string; duration_days: number; probability: number; probability_mode: string };
    simulation_count: number;
    random_seed: number;
    affected_entity_count: number;
    data_source_label: string;
  };
  problem_definition: {
    problem_id: string;
    source_phase: string;
    horizon_days: number;
    decision_variable_count: number;
    declared_constraint_count: number;
    matrix_row_count: number;
    total_demand_units: number;
    eligible_offers: unknown[];
    excluded_offers: { supplier_id: string; product_id: string; reason: string }[];
  };
  objective: {
    name: string;
    direction: string;
    components: { name: string; weight: number; units: string }[];
    units: string;
    description: string;
    demand_satisfaction_hard: boolean;
    shortage_penalty_per_unit: number | null;
    budget: number | null;
    min_fulfillment: number | null;
  };
  solver_information: {
    solver: string;
    solver_version: string;
    options: { presolve: boolean; mip_rel_gap: number; time_limit_seconds: number };
    backend_note: string;
    determinism: string;
  };
  feasibility_status: {
    status: string;
    feasible: boolean;
    solver: string;
    solver_version: string;
    validation_checks: { name: string; status: string; detail: string }[];
    structural_diagnostics: unknown[];
    note: string;
  };
  objective_value: { value: number; units: string; direction: string; status: string; statement: string };
  objective_breakdown: {
    total_procurement_cost: number;
    total_unmet_demand: number;
    total_served_demand: number;
    fulfillment_rate: number;
    weighted_objective: number;
  };
  baseline_comparison?: {
    basis: string;
    current_plan: OptimizationPlanSummary | null;
    current_plan_plus_optimized_orders: OptimizationPlanSummary | null;
    deltas?: { unmet_delta: number; served_delta: number; added_procurement_cost: number; fulfillment_rate_delta: number };
    note: string;
  };
  scenario_comparison: {
    basis: string;
    deltas: DeltaSet;
    note: string;
    phase9_baseline_outcome: Record<string, number>;
    phase9_no_action_outcome: Record<string, number>;
    optimization_not_resimulated: boolean;
    limitation: string;
  };
  uncertainty: Record<string, { note?: string; [key: string]: unknown }>;
  warnings: string[];
  limitations: string[];
}

/* ---------- ai ---------- */

export interface ChatResponse {
  response: string;
  confidence: number;
  evidence: unknown[];
  limitations: string[];
  approved: boolean;
}

export interface AiTool {
  name: string;
  description: string;
  category: string;
  parameters: { type: string; properties: Record<string, unknown>; required: string[]; additionalProperties: boolean };
  executable: boolean;
  requires_approval: boolean;
}

export interface ApprovalResponse {
  approval_id: string;
  decision: string;
  decided_by: string;
  decided_at: string;
  status: string;
  [key: string]: unknown;
}
