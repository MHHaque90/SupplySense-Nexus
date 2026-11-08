# Disruption Simulation: SupplySense Nexus (Phase 8)

**SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.** This analysis uses synthetic/simulated data. Scenario assumptions and simulation outcomes are hypothetical and are not evidence about real suppliers, real disruptions, or real business operations.

Phase 8 compares BASELINE vs DISRUPTED SCENARIO only. It never compares ACTION A vs ACTION B (Phase 9), never optimizes, never prescribes, and never simulates beyond the configured event.

## 1. Objective

Answer: "Given a clearly defined disruption event and explicit assumptions, what could happen to inventory, service, inbound supply, and supplier exposure over the selected horizon?" Every result is conditional, hypothetical, and labeled.

## 2. Architecture

```
backend/app/analytics/simulation/
    types.py          DisruptionEvent, SimulationScenario, ScenarioOutcome, config
    events.py         7 event types, validation, templates
    probability.py    deterministic/explicit/empirical/distribution handling
    scenarios.py      Scenario assembly + validation
    targets.py        Explicit, supplier-expansion, and risk-record targeting
    baseline.py       One-time baseline state per scenario
    demand_effects.py Demand multiplier application (copies only)
    supply_effects.py Inbound zeroing/scaling/shifting (copies only)
    inventory_engine.py  Deterministic daily engine (NumPy)
    monte_carlo.py    Seeded sampling + distribution statistics
    simulation.py     Inbound schedules + per-entity deterministic passes
    runner.py         Orchestration: baseline once, runs, aggregation
    outcomes.py       Inventory/service/supply/timing aggregation
    comparison.py     Scenario-minus-baseline deltas
    traceability.py   Provenance chains
    reports.py        JSON + Markdown reporting
```

Phase 4 forecasting, Phase 5 inventory, Phase 6 procurement, and Phase 7 risk files are untouched; only public interfaces are consumed. No database writes; no migration.

## 3. Event Types

SUPPLIER_DISRUPTION (targeted arrivals scaled by 1−reduction), SHIPMENT_DELAY and LEAD_TIME_DELAY (arrivals shifted, clipped at horizon), SUPPLY_REDUCTION (in-window arrivals scaled), WAREHOUSE_DISRUPTION (inventory inaccessible during window; balance preserved, demand unmet), DEMAND_SHOCK (baseline demand scaled; forecast model untouched), COMBINED_DISRUPTION (explicit components applied in fixed order: supplier, reduction, delay; demand; warehouse mask; no nesting).

## 4. Scenario Contract

`SimulationScenario` carries id, name, analysis date, horizon (1–180), event, affected entities, baseline source, probability mode/source/value, simulation count, seed, assumptions, selection basis (`explicit_user_selection` or `risk_record:<id>`), and simulated labeling. Scenario IDs are deterministic from inputs (CLI default derives from event type).

## 5. Probability Modes

- deterministic → 1.0 / DETERMINISTIC, labeled DETERMINISTIC_SCENARIO (never a real-world 100%).
- explicit → user value in [0, 1] / USER_ASSUMED ("20% user-assumed scenario probability", never predicted/validated).
- empirical → contract present but UNAVAILABLE (no validated historical disruption-frequency data exists; the `disruptions` table holds synthetic scenario definitions, not frequencies).
- distribution → triangular (duration) / uniform (supply reduction) sampled with explicit seeded generators; every distribution records type, parameters, units, source, and assumption status.

Phase 7 risk severity is never converted into probability.

## 6. Probability Provenance

Every probability carries mode, value, and source from {DETERMINISTIC, USER_ASSUMED, EMPIRICAL, DISTRIBUTION_ASSUMPTION}. Never PREDICTED/OBSERVED/LEARNED/VALIDATED.

## 7. Assumptions

Every event parameter and the horizon/seed/count travel in `assumptions` with "scenario assumption, not an observed historical fact" wording. Reports separate HISTORICAL OBSERVATION, SCENARIO ASSUMPTION, and SIMULATED OUTCOME sections.

## 8. Baseline Methodology

Built ONCE per scenario per series: current on-hand (latest snapshot ≤ analysis date), Phase 4 forecast point/lower/upper (consumed, never retrained; short forecasts transparently extended by last value with a trace note), known inbound schedule with supplier attribution (one contribution per open PO/product at earliest in-window arrival). Baseline carries no disruption parameters (tested).

## 9. Simulation Mechanics

Daily: ending = max(0, beginning + inbound − demand); unmet = max(0, demand − available); stockout_flag = (ending ≤ 0 and demand > 0). Unmet demand tracked separately; negative inventory never stored. Warehouse disruption makes inventory inaccessible (unmet accrues, balance preserved).

## 10. Monte Carlo Methodology

`np.random.default_rng(seed)`; only configured distributions sampled; deterministic engine underneath. Same inputs + seed reproduce results (tested); different seeds may vary. Percentiles gated: p05–p95 need ≥20 runs, p99 needs ≥100.

## 11. Outcome Definitions

Inventory: stockout probability/count, expected stockout days/min/ending inventory, depletion probability. Service: exposure probability, unmet mean/median/p90/p95. Supply: affected supplier/supplier-product/inbound counts, delayed/unavailable quantities. Timing: by-7/14/28-day probabilities only when the horizon covers them, plus first-stockout date lists.

## 12. Uncertainty Separation

Forecast uncertainty (Phase 4 intervals, inherited), scenario uncertainty (event params, probability, distributions), and simulation variability (seed, count) are separate report sections and never merged into one score.

## 13. Traceability

Per entity: scenario → event → product/warehouse → suppliers → on-hand → forecast (model/origin/horizon) → inbound POs → probability → seed/count/selection basis, labeled simulated.

## 14. Point-in-Time Rules

Baseline uses records ≤ analysis date only (loaders filter; tested with future-record injection across inventory, demand, POs, shipments, supplier links). Analysis date defaults to latest available data.

## 15. Synthetic-Data Rules

Every report carries the disclaimer; every row/object is simulated-labeled; language bans (predictions, guarantees, prescriptions, Replay decisions, optimization) are test-enforced.

## 16. Limitations

- No future inbound exists beyond dataset end for some suppliers (zero-effect scenarios are honest mechanics, not errors).
- Deep inventory in the synthetic data means many scenarios show no stockouts; deltas still quantify depletion.
- Received quantities inherit Phase 6 inference limits; split-shipment partials use earliest-arrival allocation.
- Empirical probability unavailable (no frequency data).
- No historical backtesting of simulated vs actual (simulations project beyond observed history by design).

## 17. Examples

```bash
python scripts/analyze_supply_chain.py disruption-simulation \
  --scenario SUPPLIER_OUTAGE --supplier-id <uuid> --horizon-days 28 \
  --output-json sim.json --output-markdown sim.md

python scripts/analyze_supply_chain.py disruption-simulation \
  --event-type SUPPLY_REDUCTION --supply-reduction 0.6 --duration-days 21 \
  --supplier-id <uuid> --horizon-days 28 --simulation-count 200 \
  --random-seed 42 --duration-min 14 --duration-mode 21 --duration-max 30 \
  --probability-mode explicit --probability 0.2 \
  --output-json sim_mc.json
```

## 18. Phase 9 Handoff

Phase 9 (Decision Replay Lab) can consume: scenario definitions, event assumptions, baselines, simulated outcomes, stockout probabilities, service impact, unmet demand, inventory impact, supplier exposure, affected products/warehouses, uncertainty sections, probability provenance, seeds, counts, and traceability. Documented interface only; no decision comparison implemented.
