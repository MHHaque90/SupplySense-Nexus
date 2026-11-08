# Decision Replay Lab: SupplySense Nexus (Phase 9)

**SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.** This analysis uses synthetic/simulated data. Decision assumptions, scenario assumptions, and simulated outcomes are hypothetical and are not evidence about real suppliers, real disruptions, or real business operations.

Phase 9 performs factual decision comparison only. It never ranks, never recommends, never scores, never selects a decision, and never optimizes. Ranking and optimization are Phase 10 scope.

## 1. Objective

Answer: "Given ONE frozen disruption scenario and a set of explicitly defined decisions, what does each decision do to inventory, service, inbound supply, timing, and modeled cost — versus the shared baseline and versus each other?" Every output is a labeled, reproducible, factual comparison handed to Phase 10.

## 2. Architecture

```
backend/app/analytics/replay/
    types.py          Decision, ReplayResult, ReplayConfig, DECISION_TYPES
    decisions.py      Deterministic IDs, builders, JSON decision parsing
    validation.py     Pre-simulation validation (raises with explicit messages)
    constraints.py    Descriptive PASS/UNCHECKED/FAIL checks (no solving)
    effects.py        Copy-on-write transforms per decision type
    outcomes.py       Thin Phase 8 aggregation wrappers + local scalars
    costs.py          Observed purchase cost + USER_ASSUMED_COST assembly
    comparison.py     Baseline deltas and pairwise deltas (factual arithmetic)
    traceability.py   Phase 8 chain + decision_id/type/assumptions/baseline_ref
    reports.py        Exactly 21 report sections, JSON + Markdown
    replay.py         Orchestration: validate → baseline once → sample once → arms
```

Phase 4–8 files are untouched; only public interfaces are consumed (`inventory.types.ForecastInput`, `simulation` public modules). No database access of any kind; no migration; no new dependencies.

## 3. Decision Contract

`Decision` carries deterministic `decision_id` (sha256 of replay_id + type + sorted targets), type, description, affected suppliers/products/warehouses, quantities, timing, cost assumptions, assumption notes, `source` (`user_defined` or `generated`), and nested components. Decisions are assumptions, never observed facts: every builder attaches "decision assumption" wording.

## 4. Decision Types (eight, closed set)

NO_ACTION (control arm, identity transform), EXPEDITE_INBOUND (arrivals shifted earlier), ALTERNATIVE_SUPPLIER (arrival attribution rewritten to an explicit user-selected supplier), SUPPLIER_ALLOCATION_CHANGE (inbound split proportionally to explicit per-supplier amounts), INVENTORY_TRANSFER (paired decrease/increase across two warehouses, conservation by construction), DEMAND_ADJUSTMENT (demand scaled over an explicit window; not a forecast), PURCHASE_ORDER_ADJUSTMENT (modeled inbound entry added; PostgreSQL untouched), COMBINED_ACTION (components applied in declared order; no nesting; INVENTORY_TRANSFER cannot nest).

## 5. Replay Contract

One frozen scenario → one shared baseline → copy-on-write decision transforms per arm → identical disruption mechanics and configuration → the SAME sampled parameter arrays for every arm → comparable simulated outcomes → baseline deltas + pairwise deltas. Scenario mechanics (event, probability, duration, reductions, horizon, seed, simulation count) are fingerprinted before and after the run; mutation aborts the replay. Validation and constraint checks run BEFORE any simulation work.

## 6. Validation and Constraints

Validation rejects unknown ids, non-positive quantities, timing outside the horizon, missing required parameters (EXPEDITE_INBOUND needs `delay_reduction_days`; PURCHASE_ORDER_ADJUSTMENT needs `arrival_day` or `start_day`), incomplete/unknown supplier allocations, missing supplier-product links, transfer rules (exactly one product, two warehouses, sufficient source inventory), and out-of-scope targets. With `require_validation=True` (default) any failure aborts; otherwise the decision is skipped with a recorded note. Constraint checks return descriptive PASS/UNCHECKED/FAIL notes: nullable capacity is UNCHECKED, never zero; a FAIL note rejects the decision. Nothing here searches, solves, or optimizes.

## 7. Shared Baseline

Built ONCE per replay from historical/observed synthetic data (latest on-hand ≤ analysis date, Phase 4 forecast consumed never retrained, known inbound schedule) and shared unchanged by every decision arm (`baseline_ref = baseline:<scenario_id>`). Arms never rebuild or mutate it (tested).

## 8. Common Random Numbers

Scenario distributions are sampled ONCE with one seeded generator; the identical sampled arrays feed every arm. A deterministic `sample_fingerprint` (seed + count + parameter bytes) identifies the shared sample set and is recorded on every `ReplayResult` — provenance only, not a score.

## 9. Comparison Semantics

Baseline deltas: arm minus shared baseline. Pairwise deltas: right minus left, in declared arm order. Delta keys are exactly `delta_stockout_probability`, `delta_unmet_demand`, `delta_min_inventory`, `delta_ending_inventory`, `delta_stockout_days`, `delta_service_exposure`. No sorting by metric, no scores, no tiers, no better/worse markers, no selection.

## 10. Cost Model

Only two cost kinds: observed purchase cost (quantity × SupplierProduct.unit_cost) and explicit USER_ASSUMED_COST values declared on the decision. Missing costs stay `None` — never zero, never fabricated. `disruption_cost_per_unmet_unit` (if user-assumed) × unmet demand models disruption cost without double counting. No best/minimum/optimal cost is ever computed (tested).

## 11. Uncertainty Separation

Four categories, each a documented note, never merged into one score: forecast uncertainty (Phase 4 intervals, inherited, not recalculated), scenario uncertainty (event parameters, probability, distributions), simulation variability (seed, count, shared-sample fingerprint), decision uncertainty (decision quantities, timing, cost and selection assumptions — a decision-assumption layer).

## 12. Traceability

Each entity trace keeps the full Phase 8 provenance chain and adds `decision_id`, `decision_type`, `decision_assumptions`, `decision_source`, `baseline_ref`, and the ordered chain: scenario → event → decision → supplier/product/warehouse → baseline → decision_effect → simulation → outcome. Phase 8 traceability is never modified.

## 13. Point-in-Time Rules

Replay inputs use records at or before the analysis date only (loaders filter; `_latest_on_hand` selects ≤ analysis date). Future-dated snapshots, POs, and shipments are excluded — tested by injecting post-analysis records and asserting byte-identical baselines, arms, and reports.

## 14. Synthetic-Data Rules

Reports carry `data_source_label: simulated`, the synthetic-data disclaimer, `DECISION_ASSUMPTION` labels on decision definitions, `USER_ASSUMED_COST` / `OBSERVED_PURCHASE_COST` provenance on costs, and PASS constraint notes. Test-enforced language bans: no ranking/recommendation/scoring fields or headings anywhere in the run, report, or Markdown.

## 15. Report Contract

Exactly 21 sections (synthetic_data_disclaimer → phase_10_handoff), no recommendations section. Markdown renders the same 21 sections in fixed order. Missing costs render as `None`. Reproducible: identical inputs + seed → byte-identical report (tested).

## 16. Limitations

- Outcomes are conditional on the configured scenario; zero-effect arms are honest mechanics (deep synthetic inventory), not errors.
- Constraint evidence (MOQ, capacity, lead time) is only as complete as the observed data; missing evidence is UNCHECKED, never assumed satisfied.
- Cost totals are partial whenever costs are undeclared: `None` means unknown, not free.
- Decision quantity/timing effects are user-declared assumptions; the system applies them faithfully but never validates them as business-wise sensible.
- No decision history persistence: replays are computed in memory from supplied inputs (CLI writes only its requested JSON/Markdown outputs).

## 17. Examples

```bash
python scripts/analyze_supply_chain.py decision-replay \
  --scenario-json scenario.json --product-id <uuid> \
  --decision-file decision1.json --decision-file decision2.json \
  --output-json replay.json --output-markdown replay.md

python scripts/analyze_supply_chain.py decision-replay \
  --scenario SUPPLIER_OUTAGE --supplier-id <uuid> \
  --decision '{"decision_type": "DEMAND_ADJUSTMENT", ...}' \
  --horizon-days 28 --simulation-count 200 --random-seed 42
```

The control arm (NO_ACTION) is always present so every replay is comparable.

## 18. Phase 10 Handoff

Phase 10 can consume: the decision contract (deterministic ids, explicit assumptions), `ReplayResult` objects (outcomes, baseline deltas, modeled costs with `None` for missing), validated constraint notes (PASS/UNCHECKED), pairwise factual delta tables, frozen scenario assumptions with fingerprint, shared-sample provenance, four separated uncertainty categories, and traceability chains. No optimization API is defined here; Phase 10 defines optimization scope.

**Phase 10 status (addendum):** implemented. The optimization engine consumes this handoff exactly as described — `run_replay` with the NO_ACTION control arm supplies the run context and shared baseline, and the comparison layer records `optimization_not_resimulated` (the optimized plan is never re-simulated through Phase 9). See [docs/optimization-engine.md](optimization-engine.md).
