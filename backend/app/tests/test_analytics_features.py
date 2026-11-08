"""Phase 3 feature engineering tests, including leakage prevention."""

from datetime import date, timedelta

import pandas as pd

from backend.app.analytics.features import calendar_features, demand_features, inventory_features

START = date(2026, 1, 1)


def _demand_frame(values, product="P1", warehouse="W1"):
    return pd.DataFrame({
        "product_id": [product] * len(values),
        "warehouse_id": [warehouse] * len(values),
        "date": [START + timedelta(days=i) for i in range(len(values))],
        "quantity": [float(v) for v in values],
    })


def test_lag_features_use_history_only():
    frame = _demand_frame(list(range(1, 36)))
    featured = demand_features.add_lag_features(frame)
    assert featured.loc[0, "lag_1"] != featured.loc[0, "lag_1"]  # NaN at start
    assert featured.loc[7, "lag_7"] == 1.0
    assert featured.loc[10, "lag_1"] == 10.0


def test_rolling_features_exclude_current_day():
    frame = _demand_frame([10.0] * 30)
    featured = demand_features.add_rolling_features(frame)
    # Rolling mean over prior days only: still 10, current-day spike excluded.
    assert featured.loc[15, "rolling_mean_7"] == 10.0
    spiked = frame.copy()
    spiked.loc[15, "quantity"] = 1000.0
    featured_spiked = demand_features.add_rolling_features(spiked)
    assert featured_spiked.loc[15, "rolling_mean_7"] == 10.0
    assert featured_spiked.loc[16, "rolling_mean_7"] > 10.0


def test_future_values_cannot_change_past_features():
    values = [float(i) for i in range(1, 21)]
    before = demand_features.build_feature_frame(_demand_frame(values))
    tampered = values.copy()
    tampered[-1] = 9999.0
    after = demand_features.build_feature_frame(_demand_frame(tampered))
    for column in after.columns:
        if column in ("quantity", "date"):
            continue
        pd.testing.assert_series_equal(
            before.loc[:15, column], after.loc[:15, column], check_names=False
        )


def test_calendar_features():
    frame = _demand_frame([1.0, 2.0, 3.0])
    featured = calendar_features.add_calendar_attributes(frame)
    assert featured.loc[0, "day_of_week"] == 3  # 2026-01-01 is a Thursday
    assert featured.loc[0, "month"] == 1
    assert featured.loc[0, "quarter"] == 1
    assert featured.loc[0, "year"] == 2026


def test_intermittent_gap_feature():
    frame = _demand_frame([5.0, 0.0, 0.0, 3.0, 0.0])
    featured = demand_features.add_intermittent_features(frame)
    assert featured.loc[3, "days_since_nonzero"] == 3.0
    assert featured.loc[4, "days_since_nonzero"] == 1.0
    assert featured.loc[4, "zero_ratio_28"] > 0


def test_missing_dates_documented_zero_fill():
    frame = _demand_frame([4.0, 4.0, 4.0]).iloc[[0, 2]]
    continuous = demand_features.ensure_daily_continuity(frame)
    assert len(continuous) == 3
    assert continuous.loc[1, "was_imputed_zero"] == 1
    assert continuous.loc[1, "quantity"] == 0.0
    assert continuous.loc[0, "was_imputed_zero"] == 0


def test_constant_and_zero_series_features():
    constant = demand_features.build_feature_frame(_demand_frame([7.0] * 35))
    assert constant["rolling_std_7"].fillna(0.0).max() == 0.0
    assert constant["trend_slope_28"].fillna(0.0).abs().max() == 0.0
    zeros = demand_features.build_feature_frame(_demand_frame([0.0] * 35))
    assert zeros["quantity"].sum() == 0.0
    assert zeros["coefficient_of_variation"].isna().all()


def test_insufficient_history_yields_nan_not_crash():
    frame = _demand_frame([3.0, 4.0])
    featured = demand_features.build_feature_frame(frame)
    assert featured.loc[0, "lag_7"] != featured.loc[0, "lag_7"]
    assert featured.loc[1, "rolling_mean_28"] == 3.0  # min_periods=1


def test_inventory_movement_signs():
    frame = pd.DataFrame({
        "product_id": ["P1"] * 3,
        "warehouse_id": ["W1"] * 3,
        "timestamp": [START] * 3,
        "transaction_type": ["RECEIPT", "SALE", "ADJUSTMENT"],
        "quantity": [10.0, 4.0, 1.0],
    })
    movement = inventory_features.daily_movement(frame)
    assert movement.loc[0, "inflow"] == 11.0
    assert movement.loc[0, "outflow"] == 4.0
    assert movement.loc[0, "net"] == 7.0
