"""Phase 9 common-random-number tests (shared sampling across arms)."""

from backend.app.analytics.replay import decisions
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.simulation.types import DistributionAssumption
from backend.app.tests.replay_support import make_inputs, make_scenario, run_replay_for

PARAMETER = DistributionAssumption(
    parameter="duration_days",
    distribution="triangular",
    minimum=5.0,
    mode=10.0,
    maximum=20.0,
    units="days",
)


def _uncertain_scenario(seed: int = 7, count: int = 12):
    scenario = make_scenario(random_seed=seed, simulation_count=count)
    scenario.event.distributions = [PARAMETER]
    return scenario


def _arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "PURCHASE_ORDER_ADJUSTMENT",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"order_units": 25.0},
            timing={"arrival_day": 3},
        ),
    ]


def test_same_seed_samples_identical_parameters():
    first = replay_mod.prepare_shared_samples(_uncertain_scenario())
    second = replay_mod.prepare_shared_samples(_uncertain_scenario())
    assert list(first) == ["duration_days"]
    assert first["duration_days"].tolist() == second["duration_days"].tolist()


def test_different_seed_may_vary_samples():
    first = replay_mod.prepare_shared_samples(_uncertain_scenario(seed=7))
    second = replay_mod.prepare_shared_samples(_uncertain_scenario(seed=99))
    assert first["duration_days"].tolist() != second["duration_days"].tolist()
    assert replay_mod.sample_fingerprint(first, _uncertain_scenario()) != (
        replay_mod.sample_fingerprint(second, _uncertain_scenario(seed=99))
    )


def test_every_arm_carries_the_same_sample_fingerprint():
    run = run_replay_for(_arms(), _uncertain_scenario())
    fingerprints = {result.sample_fingerprint for result in run["results"]}
    assert fingerprints == {run["sample_fingerprint"]}
    assert len(run["results"]) == 2


def test_shared_samples_are_sampled_once_per_run():
    run = run_replay_for(_arms(), _uncertain_scenario())
    assert set(run["shared_samples"]) == {"duration_days"}
    assert len(run["shared_samples"]["duration_days"]) == 12
    # One generator, one seed, one draw: the run exposes a single shared set.
    replay_again = run_replay_for(_arms(), _uncertain_scenario())
    assert replay_again["shared_samples"] == run["shared_samples"]
    assert replay_again["sample_fingerprint"] == run["sample_fingerprint"]


def test_deterministic_scenario_has_empty_sample_set():
    run = run_replay_for(_arms(), make_scenario())
    assert run["shared_samples"] == {}
    assert run["sample_fingerprint"] == replay_mod.sample_fingerprint({}, make_scenario())
    assert len(run["sample_fingerprint"]) == 16


def test_simulation_count_changes_sample_set():
    few = run_replay_for(_arms(), _uncertain_scenario(count=5))
    many = run_replay_for(_arms(), _uncertain_scenario(count=25))
    assert len(few["shared_samples"]["duration_days"]) == 5
    assert len(many["shared_samples"]["duration_days"]) == 25
    assert few["sample_fingerprint"] != many["sample_fingerprint"]


def test_inputs_are_not_consumed_by_sampling():
    inputs = make_inputs()
    scenario = _uncertain_scenario()
    run_replay_for(_arms(), scenario, inputs)
    first = replay_mod.prepare_shared_samples(_uncertain_scenario())
    second = replay_mod.prepare_shared_samples(_uncertain_scenario())
    assert first["duration_days"].tolist() == second["duration_days"].tolist()
