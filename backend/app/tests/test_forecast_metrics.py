"""Phase 3 forecast metric tests, including zero handling."""

import math

import pytest

from backend.app.analytics.forecasting.metrics import bias, mae, mape, rmse, smape, wape


def test_normal_data():
    actual = [10.0, 20.0, 30.0]
    predicted = [12.0, 18.0, 33.0]
    assert mae(actual, predicted) == pytest.approx(7 / 3)
    assert rmse(actual, predicted) == pytest.approx(math.sqrt(17 / 3))
    assert bias(actual, predicted) == pytest.approx(1.0)


def test_perfect_forecast():
    actual = [5.0, 8.0, 13.0]
    assert mae(actual, actual) == 0.0
    assert rmse(actual, actual) == 0.0
    assert mape(actual, actual) == 0.0
    assert smape(actual, actual) == 0.0
    assert wape(actual, actual) == 0.0
    assert bias(actual, actual) == 0.0


def test_constant_forecast():
    actual = [10.0, 10.0, 10.0]
    predicted = [8.0, 8.0, 8.0]
    assert mae(actual, predicted) == 2.0
    assert mape(actual, predicted) == pytest.approx(0.2)


def test_zeros_masked_in_mape():
    actual = [0.0, 10.0, 20.0]
    predicted = [5.0, 10.0, 10.0]
    assert mape(actual, predicted) == pytest.approx(0.25)  # mean of 0 and 0.5
    assert wape(actual, predicted) == pytest.approx(15 / 30)


def test_all_zeros_return_nan():
    actual = [0.0, 0.0]
    predicted = [0.0, 1.0]
    assert math.isnan(mape(actual, predicted))
    assert math.isnan(wape(actual, predicted))
    assert smape([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_smape_bounded():
    assert 0.0 <= smape([0.0, 5.0], [10.0, 5.0]) <= 2.0


def test_length_mismatch_rejected():
    with pytest.raises(ValueError):
        mae([1.0, 2.0], [1.0])


def test_empty_and_nonfinite_rejected():
    with pytest.raises(ValueError):
        mae([], [])
    with pytest.raises(ValueError):
        mae([1.0, float("nan")], [1.0, 2.0])
    with pytest.raises(ValueError):
        rmse([1.0], [float("inf")])


def test_negative_inputs_allowed_numerically():
    # Returns are invalid business data but metrics stay numerically defined.
    assert mae([-5.0], [-3.0]) == 2.0
