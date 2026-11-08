import { describe, expect, it } from "vitest";
import { defaultScenarioForm, toScenarioBody, type ScenarioFormState } from "./ScenarioForm";

function state(patch: Partial<ScenarioFormState> = {}): ScenarioFormState {
  return { ...defaultScenarioForm(undefined), ...patch };
}

describe("toScenarioBody (shared compute contract)", () => {
  it("uses event_template for locked templates", () => {
    const body = toScenarioBody(state());
    expect(body.event_template).toBe("SUPPLIER_OUTAGE");
    expect(body.event_type).toBeUndefined();
  });

  it("uses event_type and point parameters for direct definitions", () => {
    const body = toScenarioBody(
      state({
        useTemplate: false,
        eventType: "SUPPLY_REDUCTION",
        supplyReduction: 0.5,
        leadTimeDelayDays: 4,
        demandMultiplier: 1.5,
      }),
    );
    expect(body.event_type).toBe("SUPPLY_REDUCTION");
    expect(body.event_template).toBeUndefined();
    expect(body.supply_reduction).toBe(0.5);
    expect(body.lead_time_delay_days).toBe(4);
    expect(body.demand_multiplier).toBe(1.5);
  });

  it("sends probability only for explicit mode", () => {
    const deterministic = toScenarioBody(state());
    expect(deterministic.probability_mode).toBeUndefined();

    const explicit = toScenarioBody(state({ probabilityMode: "explicit", probability: 0.4 }));
    expect(explicit.probability_mode).toBe("explicit");
    expect(explicit.probability).toBe(0.4);
  });

  it("trims scopes and drops blank ones", () => {
    const body = toScenarioBody(state({ productId: "  prod-1  ", warehouseId: "", supplierId: "   " }));
    expect(body.product_id).toBe("prod-1");
    expect(body.warehouse_id).toBeUndefined();
    expect(body.supplier_id).toBeUndefined();
  });

  it("splits assumptions by line and skips blank lines", () => {
    const body = toScenarioBody(state({ assumptions: "supplier confirms recovery\n\nwith buffer stock" }));
    expect(body.assumptions).toEqual(["supplier confirms recovery", "with buffer stock"]);
  });

  it("always carries horizon, simulation count and seed", () => {
    const body = toScenarioBody(state({ horizonDays: 3, simulationCount: 5, randomSeed: 7 }));
    expect(body.horizon_days).toBe(3);
    expect(body.simulation_count).toBe(5);
    expect(body.random_seed).toBe(7);
  });

  it("never emits both template and event type simultaneously", () => {
    for (const useTemplate of [true, false]) {
      const body = toScenarioBody(state({ useTemplate }));
      expect(Boolean(body.event_template) && Boolean(body.event_type)).toBe(false);
    }
  });
});
