# Optimization Engine

**Phase:** 10
**Status:** Implementation complete
**Data classification:** All outputs produced by this module are **SYNTHETIC DATA / simulated planning outputs** (`data_source_label = "simulated"`). Nothing produced here is real procurement advice.

---

## 1. Purpose

The Optimization Engine builds and solves a deterministic, auditable procurement
optimization problem (MILP) over a user-selected scenario horizon. It consumes
**only public Phase 9 Decision Replay outputs** (no Phase 4-9 logic is modified)
and produces feasible, traceable order-quantity solutions under an
explicitly declared objective, constraint set, scenario, and solver.

It answers: *given this scenario, this forecast, and these supplier terms, what
order quantities are feasible, and what do they cost / deliver versus the
current plan and versus taking no action?*

Out of scope (documented, not implemented):

- Warehouse-to-warehouse transfer / network flow optimization (no transfer cost
  or transfer capacity data exists in the synthetic datasets).
- Multi-scenario stochastic or robust optimization (scenarios are single-event;
  only one scenario probability is disclosed, no scenario distribution).
- Pareto-front multi-objective generation (original roadmap idea; replaced by
  one explicit scalar objective per run — see `docs/roadmap.md` Phase 10 notes).
- Reinforcement learning, LLM/AI-solver assistance, cloud solvers.
- Recommendation language: outputs never state that a plan "should" be adopted;
  they state what is *optimal under the stated objective and constraints*.

---

## 2. Phase boundary

```
Phase 8 simulation        Phase 9 Decision Replay         Phase 10 Optimization
-----------------         ------------------------        ----------------------
supply_effects      -->   run_replay (public dict)  -->    build_optimization_inputs
demand_effects            build_shared_baseline     -->   build_milp_formulation
inventory_engine          public types/reports             OptimizationSolver.solve
                                                              -> result validation
                                                              -> comparison
                                                              -> JSON + Markdown report
```

- Phase 10 code lives **only** in `backend/app/analytics/optimization/`, the
  `optimization` CLI subcommand, `backend/app/tests/test_optimization_*.py`,
  and this document.
- No database tables, schemas, models, or migrations are added or changed.
- Phase 10 imports Phase 8/9 public functions; it never imports Phase 4-7
  internals directly.

---

## 3. Input contract (Phase 9 → Phase 10)

`build_optimization_inputs(replay_run, entities, supplier_links, ...)`
consumes exactly:

| Input | Source | Shape / meaning |
|---|---|---|
| `replay_run` | `replay.run_replay(...)` with at least the `NO_ACTION` control arm | dict with keys `replay_id`, `scenario`, `scenario_id`, `scenario_fingerprint`, `baseline_ref`, `baseline` (ScenarioOutcome dict), `results` (dict of ReplayResult dicts), `uncertainty`, `sample_fingerprint`, `configs`, `synthetic`, `analysis_date`, `horizon_days` |
| `entities` | `replay.build_shared_baseline(scenario, forecasts, snapshots, shipments, po_lines, supplier_links, analysis_date)` | per-entity dicts: `product_id`, `warehouse_id`, `demand_point` (list, len = horizon), `demand_lower`, `demand_upper`, `schedule` (list of baseline inbound), `on_hand` (float), `forecast_meta` (model_name, model_version, confidence_level, origin, validation fields) |
| `supplier_links` | `datasets.suppliers.load_suppliers` frame | columns include `supplier_id`, `product_id`, `unit_cost`, `lead_time_days`, `min_order_qty`, `capacity_units` (nullable) |
| `config` | CLI / caller (`OptimizationConfig`) | objective, optional budget / shortage penalty / minimum fulfillment, integrality mode, solver time limit |

Derived inside the adapter (documented derivations, no hidden inputs):

1. **Effective demand** per entity = Phase 9 point demand with Phase 8
   `demand_effects` applied when the scenario contains a `DEMAND_SHOCK`
   (point parameters of the event — not Monte Carlo samples).
2. **Effective inbound** per entity = Phase 9 `schedule` with Phase 8
   `supply_effects` dispatch applied (same window/clip semantics as
   `simulation.run_entity_once`, `parameters` omitted = point values).
3. **Availability mask** = `WAREHOUSE_DISRUPTION` windows (days masked = demand
   unmet, inbound dropped — mirrors `inventory_engine.run_days`).
4. **Order arrival under scenario** for supplier `s` with lead time `L`:
   unit arrival placed at day `L` is pushed through the same `supply_effects`
   dispatch; result is `(arrival_day, effective_factor)`; orders that arrive
   after the horizon or are fully eliminated by the scenario are excluded with
   a recorded reason.
5. **Deterministic baseline reference** = `inventory_engine.run_days` with the
   entity's on-hand, effective inbound, mask, and demand (current plan,
   event-aware). The Phase 9 Monte Carlo baseline outcome is preserved
   separately as context, not recomputed.
6. **Scenario comparison** = Phase 9 `baseline` outcome vs the `NO_ACTION`
   arm outcome from the same replay run (factual event impact under Phase 9
   accounting). The optimized solution is **not** re-simulated — this is a
   documented limitation.

Malformed `replay_run` (missing `scenario` / `baseline` / `results`) raises
`ValueError` with an explicit message. Empty entity scope produces a
`NO_DATA` result rather than an exception.

---

## 4. Typed contracts (`optimization/types.py`)

Frozen dataclasses with `to_dict()` (mirrors Phase 9 conventions):

- `OptimizationConfig` — objective, shortage penalty, budget, min fulfillment,
  integrality mode, solver time limit.
- `DecisionVariable` — name, entity_type, entity_id (+ supplier/product/
  warehouse components), bounds, integrality, units, source, description.
  Only *order quantity* variables are exposed; MOQ binaries are auxiliary
  (documented in `problem.parameters`).
- `Constraint` — name, type, expression, bound, units, `hard_or_soft`, source,
  description.
- `Objective` — direction, components (name/weight/units), units, description.
- `Provenance` — source phase/module, replay/scenario ids, fingerprints,
  analysis date, forecast references (model name/version/confidence/validation
  metric), id scope lists, `synthetic=True`, `data_source_label="simulated"`.
- `OptimizationProblem` — problem_id, scenario_id, analysis date, horizon,
  objective, decision variables, constraints, parameters, assumptions,
  provenance, `source_phase`, `source_contract`.
- `ProblemFormulation` — problem metadata + MILP matrices (objective vector,
  bounds, integrality, named constraint rows). This is what the solver
  consumes; `OptimizationProblem` itself stays JSON-serializable.
- `OptimizationResult` — problem_id, scenario_id, status, feasible, solver,
  solver_version, objective_value, objective_breakdown, decision_values,
  binding_constraints, violated_constraints, slack, baseline_comparison,
  scenario_comparison, assumptions, provenance, warnings, limitations,
  analysis_date (+ `problem` echo, `synthetic`, `data_source_label`).

**Statuses:** `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNBOUNDED`, `ERROR`,
`NO_DATA` (exactly these six).

---

## 5. Objectives (exactly four, explicit, no silent weights)

| Objective | Direction | Meaning | Demand handling |
|---|---|---|---|
| `minimize_total_cost` | minimize | Σ unit_cost × order_qty | **hard** satisfaction — may return `INFEASIBLE` |
| `minimize_shortage` | minimize | Σ unmet demand units | cost ignored (orders free to solver) |
| `cost_shortage_tradeoff` | minimize | Σ cost + penalty × Σ unmet | requires explicit `shortage_penalty_per_unit` (`--shortage-penalty`); missing → clear error |
| `maximize_service_fulfillment` | maximize | Σ served demand units | cost ignored; tie-breaking by solver order (documented) |

Every objective states direction, components, weights, units, and description
in `OptimizationProblem.objective`.

---

## 6. Decision variables and constraints

**Variables**

- `order[supplier|product|warehouse]` ≥ 0 (integer by default; `continuous`
  mode allowed) — units of product ordered.
- Auxiliary binary `moq[supplier|product]` — whether the supplier-product pair
  is used (internal, reported in `parameters`, not in `decision_values`).

**Constraints**

| Type | Hard/soft | Expression |
|---|---|---|
| `demand_satisfaction` | hard for `minimize_total_cost`, soft otherwise (softness recorded) | per entity: Σ unmet over horizon = 0 (hard) or unmet left to objective (soft) |
| `daily_balance` | structural | balance dynamics per entity/day with event-adjusted arrivals, mask semantics identical to `run_days` |
| `supplier_capacity` | hard | per supplier-product: Σ_w order ≤ capacity_units (omitted when null — recorded as `UNCHECKED` note) |
| `minimum_order_quantity` | hard | Σ_w order ≥ MOQ × y, Σ_w order ≤ M × y (M = product procurement bound) |
| `over_purchase_bound` | hard | per product: Σ orders ≤ max(Σ gross demand, max MOQ among links) |
| `lead_time_horizon` | structural | offers with effective arrival outside horizon excluded at input stage (reason recorded) |
| `budget` | hard, only when `--budget` given | Σ known unit_cost × order ≤ budget (offers with unknown unit cost excluded while budget active, warning recorded) |
| `service_level_minimum` | hard, only when `--min-fulfillment` given | Σ served ≥ min_fulfillment × Σ demand |

Unknown `unit_cost` / missing supplier terms follow the Phase 9 convention:
**excluded and honestly noted — never silently invented**. For cost-bearing
objectives, offers with unknown `unit_cost` are excluded from the optimization
with a warning; their exclusion is listed in the report.

---

## 7. Solver

- Interface: `OptimizationSolver.solve(formulation) -> OptimizationResult`
  (Protocol).
- Implementation: `ScipyHiGHSSolver` using `scipy.optimize.milp`
  (HiGHS branch & bound) — already present in the environment as a declared
  transitive dependency (via scikit-learn/statsmodels). **No new dependency
  is installed.**
- **Roadmap deviation (documented):** `docs/roadmap.md` originally named
  OR-Tools; OR-Tools is *not* installed (optional `oracle` extra only), and
  installing dependencies in this phase is prohibited. The solver backend is
  abstracted so OR-Tools can be added behind the same interface later.
- Options: presolve on, `mip_rel_gap = 0`, time limit from config
  (default 30 s). Determinism verified empirically (two consecutive runs on
  identical inputs must produce byte-identical decision values).
- Status mapping: scipy `0 → OPTIMAL`, `1 → FEASIBLE` (incumbent found,
  else `ERROR`), `2 → INFEASIBLE`, `3 → UNBOUNDED`, `4/exception → ERROR`.
- `NO_DATA` is set by the orchestration layer when entity scope or eligible
  offers are empty (solver never called).

---

## 8. Feasibility, diagnostics, validation

- Every result states: status, feasibility, objective value and breakdown
  (procurement cost, unmet demand, served demand, fulfillment rate, penalty
  component where applicable), binding constraints, violated constraints
  (empty unless a validation cross-check fails), and slack/utilization.
- `INFEASIBLE` results still carry the full problem definition plus structural
  diagnostics (capacity shortfall, lead-time exclusions, MOQ/bound conflicts,
  budget insufficiency). A full IIS conflict set is not available from this
  backend — stated honestly in `limitations`.
- Result validation (`validation.py`) re-checks bounds, integrality, and
  constraint satisfaction from the extracted solution, and cross-checks
  served/unmet totals against `inventory_engine.run_days` re-evaluation of the
  extracted order plan (greedy serve-early policy equals the LP-optimal total
  for fixed arrivals).

---

## 9. Baseline and scenario comparison

- `baseline_comparison`: deterministic current plan (event-aware `run_days`
  totals) vs current plan + optimized orders, same accounting basis. Shows
  shortage delta, served delta, fulfillment delta, new procurement cost.
- `scenario_comparison`: Phase 9 Monte Carlo `baseline` outcome vs `NO_ACTION`
  arm outcome — factual event impact under Phase 9 accounting; the optimized
  solution is not re-simulated (stated limitation).
- Baseline data is never mutated (inputs are frozen dataclasses; comparisons
  build fresh dicts).

---

## 10. Provenance and uncertainty

- `Provenance` records replay id, scenario id/fingerprint, baseline ref,
  sample fingerprint, analysis date, forecast model references (name, version,
  confidence level, validation metric/score, origin), and id scope.
- Uncertainty disclosed: forecast prediction intervals (lower/upper,
  confidence level), replay uncertainty block, scenario probability, and
  explicit statements where point parameters were used instead of samples.
- No probabilities, distributions, costs, or capacities are invented.

---

## 11. Reporting contract

JSON + Markdown reports built by `reports.build_report(run)` /
`render_markdown(report)` with **exactly these 21 sections** (also exported as
`REPORT_SECTIONS`):

1. `synthetic_data_disclaimer`
2. `optimization_run_metadata`
3. `source_scenario`
4. `problem_definition`
5. `objective`
6. `decision_variables`
7. `constraints`
8. `assumptions`
9. `solver_information`
10. `feasibility_status`
11. `objective_value`
12. `objective_breakdown`
13. `decision_values`
14. `baseline_comparison`
15. `scenario_comparison`
16. `binding_constraints`
17. `slack_utilization`
18. `provenance`
19. `uncertainty`
20. `warnings`
21. `limitations`

Language rules enforced by tests: no "best", "recommend", "should", "ideal",
or "perfect" wording in optimization outputs; feasibility and solver status
always explicit.

---

## 12. CLI usage

```bash
python scripts/analyze_supply_chain.py optimization \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --scenario SUPPLY_REDUCTION --supplier-id <uuid> \
  --objective minimize_total_cost \
  [--horizon-days 28] [--product-id P1] [--warehouse-id W1] \
  [--duration-days 30] [--supply-reduction 0.4] \
  [--budget 5000] [--shortage-penalty 25] [--min-fulfillment 0.95] \
  [--output-json out.json] [--output-markdown out.md]
```

- Exactly one scenario source: `--scenario <TEMPLATE>` (Phase 8 template:
  `SUPPLIER_OUTAGE`, `SUPPLIER_DELAY`, `SHIPMENT_DELAY`, `SUPPLY_REDUCTION`,
  `WAREHOUSE_DISRUPTION`, `DEMAND_SPIKE`, `COMBINED_DISRUPTION`) or
  `--scenario-json <file|inline>`; template parameters can be overridden with
  `--duration-days`, `--supply-reduction`, `--lead-time-delay-days`,
  `--demand-multiplier`. `--scenario-id` labels the run but never supplies
  the event itself.

- Scenario construction reuses the same Phase 9 scenario-shape conventions
  (JSON file or inline args, simulator/event templates) in a Phase 10-owned
  code block — no Phase 9 code is refactored.
- Forecasts: persisted-first (`load_persisted_forecasts`), generated fallback
  (same as replay CLI).
- Runs `run_replay` in-process with the `NO_ACTION` control arm to obtain the
  Phase 9 run context, then builds and solves the optimization.
- Exit codes: `0` = analysis completed (any solver status incl. `INFEASIBLE`
  or `NO_DATA`, reported in payload), `1` = no data / cannot build inputs,
  `2` = invalid arguments.

---

## 13. Data labeling

- Report disclaimer states all values are synthetic/simulated planning outputs.
- Result payload carries `synthetic: true` and `data_source_label: "simulated"`.
- Forecast references carry their real (synthetic-dataset) origin labels
  (`persisted` / `generated_for_analysis`).
- Prose never presents simulated numbers as actual company performance.

---

## 14. Testing

Implemented as **130 tests in 11 files** (`backend/app/tests/test_optimization_*.py`
plus `optimization_support.py` fixtures). Full suite: **665 passed**
(535 baseline before Phase 10 + 130 new), zero failures, zero regressions.

| File | Tests | Coverage focus |
|---|---|---|
| `test_optimization_inputs.py` | 18 | Malformed-input errors, arrival day `L−1`, exclusion reasons, scope filters, warehouse mask (mirrors unconditional `run_entity_once` dispatch), demand-shock window, inbound pass-through, point-parameter assumptions, baseline parity vs `inventory_engine.run_days`, provenance/forecast refs |
| `test_optimization_problem.py` | 21 | Config validation, objective metadata, problem-id stability/scoping, orders-only decision variables, hard/soft demand rows per objective, MOQ/capacity/budget/service rows, unit-cost-missing offer exclusion, zero-column NO_DATA formulation, matrix shapes |
| `test_optimization_solve.py` | 18 | Six solver statuses, INFEASIBLE structural diagnostics, OPTIMAL short-outage breakdown, shortage/tradeoff/maximize objectives, budget and service-floor enforcement, NO_DATA, continuous integrality mode, solver identity, timings + labeling (total < 5 s) |
| `test_optimization_scenarios.py` | 10 | Warehouse mask, demand shock, supply reduction factor, lead-time delay, delay clip to horizon−1, combined events, MC settings excluded from problem id, scenario change included |
| `test_optimization_comparison.py` | 7 | Baseline comparison arithmetic, unavailable-solution note, evaluate-plan by entity, Phase 9 deltas + `optimization_not_resimulated`, JSON serializability |
| `test_optimization_determinism.py` | 6 | Runs identical excluding timings, stable problem id and decision ordering, byte-identical reports after timing normalization |
| `test_optimization_leakage.py` | 5 | Future-poisoned snapshots/POs/shipments produce identical inputs/problem id/decisions/report; analysis date and forecast-origin bounds recorded |
| `test_optimization_provenance.py` | 9 | Phase 9 lineage, forecast refs, simulated labeling, report/problem provenance equality, OR-Tools deviation disclosure, warning dedup, capacity disclosure, uncertainty intervals |
| `test_optimization_nodb.py` | 5 | No DB imports/SQL anywhere in the package, payload-only signature, clean module namespace, session factory untouched |
| `test_optimization_reports.py` | 15 | Exactly 21 ordered sections, numbered Markdown headings, banned-word scan (`best`/`should`/`recommend`/`ideal`/`perfect`), status/objective/check language, decision-value shape, binding grouping, all-four-objectives report loop |
| `test_optimization_cli.py` | 16 | End-to-end CLI (JSON + Markdown + stdout, exit 0), exit-2 argument paths, exit-1 empty datasets, DB-offline path, shortage objective e2e, banned-word Markdown scan |

Verification commands:

```bash
pytest backend/app/tests/ -q                      # full suite (665)
pytest backend/app/tests/test_optimization_*.py   # Phase 10 only (130)
python -m ruff check backend/ scripts/            # lint (clean)
```

## 15. Performance

Every run payload carries `timings` with keys `input_preparation`,
`problem_construction`, `solver`, `result_validation`, `total` (seconds);
the CLI adds `reporting` (report build + Markdown render). Default solver
time limit is 30 s (`--time-limit`); `mip_rel_gap = 0.0` (proven optimal
required for `OPTIMAL`).

Measured on the synthetic dataset (2 entities × 28-day horizon,
2 supplier-product links, short-outage scenario; 3 consecutive runs, **simulated
benchmark — not a production guarantee**):

| Stage | Measured |
|---|---|
| Input preparation | 0.8–1.0 ms |
| Problem construction | 0.7–1.1 ms |
| Solver (HiGHS via `scipy.optimize.milp`) | 2.4–4.1 ms |
| Result validation | 0.3–0.4 ms |
| Full `run_optimization` | **39–43 ms** |
| `build_report` + `render_markdown` | < 1 ms (~17.6 KB Markdown) |

Tests enforce a loose ceiling (`total < 5.0 s`) so CI variance never masks
a real regression while the measured margin stays ~100×.

## 16. Known limitations

- Orders arriving after the horizon are out of scope (excluded with reason).
- Scenario effect on *future* orders uses point parameters of the event, not
  Monte Carlo samples.
- Optimized plan is not re-simulated through Phase 9; scenario comparison is
  factual (baseline vs no-action) only.
- `INFEASIBLE` diagnostics are structural checks, not a full IIS.
- Single scalar objective per run; no Pareto front generation.
- `capacity_units` is nullable; null capacity leaves the constraint
  `UNCHECKED` (recorded).

## 17. Phase 10 → Phase 11 handoff (AI Decision Copilot adapter)

Decision **C5** fixed the copilot/optimizer boundary: the AI Decision Copilot
calls the Phase 10 engine only through a **thin adapter** — it never
re-implements, re-weights, or re-ranks optimization results.

- **Adapter**: `backend/app/ai/tools/optimization_tools.py` →
  `run_optimization_analysis(context)`, registered as the
  `run_optimization_analysis` tool (category `optimization`,
  planning roles only).
- **Composition**: org scope + frames are loaded by the shared tool context,
  an optional Phase 8 scenario is prepared by `_scenario.prepare_scenario`,
  then the full Phase 9 → Phase 10 chain runs unchanged:
  `run_replay` (NO_ACTION control) → `build_shared_baseline` →
  `run_optimization` → `build_report`. Execution is CPU-bound and runs in the
  Starlette threadpool (`run_in_threadpool`).
- **Objectives**: exactly the `OBJECTIVES` registry of §5 (four, explicit).
  An unknown `objective` raises a validation error; `cost_shortage_tradeoff`
  without a positive `shortage_penalty` is rejected; `budget`,
  `min_fulfillment` (0..1), and `time_limit_seconds` (1..120, default 15) are
  validated before the config is built. No silent weights, no objective
  invention.
- **Output**: the same audited 21-section report the CLI produces, with
  `data_source_label` defaulted to `"simulated"`. The tool returns
  `source: "optimization_engine"` plus limitations that disclose the solver
  status vocabulary (`OPTIMAL`/`FEASIBLE`/... is feasibility language, "not
  an instruction to act"), the simulated nature of the outputs, and the
  objective/time limit used.
- **Scoping**: `product_id`/`warehouse_id`/`supplier_id`/`analysis_date` are
  org-checked (`ctx.require_scope`) — cross-organization ids are rejected.
- **Tests**: `test_ai_tools.py::test_optimization_tool_phase10_integration`
  and `::test_optimization_rejects_unknown_objective_and_tradeoff_without_penalty`
  assert the integration, label, and validation behavior; Phase 10's own
  banned-word report scan continues to guard wording.
