"""Demand KPIs (Phase 3)."""

import pandas as pd

from backend.app.analytics.types import KPIResult

SOURCE = ["demand_observations"]


def _span(frame: pd.DataFrame) -> tuple[str, str]:
    dates = pd.to_datetime(frame["date"])
    return str(dates.min().date()), str(dates.max().date())


def demand_summary(frame: pd.DataFrame, grain: str = "dataset") -> list[KPIResult]:
    """Compute total, average daily, volatility, and zero-day share of demand."""
    if frame.empty:
        return []
    start, end = _span(frame)
    total = float(frame["quantity"].sum())
    days = max(1, (pd.to_datetime(end).date() - pd.to_datetime(start).date()).days + 1)
    mean_daily = total / days
    nonzero = frame[frame["quantity"] > 0]
    zero_share = 1.0 - len(nonzero) / max(1, len(frame))
    std_daily = float(frame.groupby(pd.to_datetime(frame["date"]).dt.date)["quantity"].sum().std(ddof=0) or 0.0)
    return [
        KPIResult("total_demand", total, "units", total, None, start, end, grain, {},
                  SOURCE, True, "formula=sum(quantity)",
                  "Observed generated demand in range."),
        KPIResult("average_daily_demand", mean_daily, "units/day", total, float(days),
                  start, end, grain, {}, SOURCE, True, "formula=total/days",
                  "Calendar-day average over the range."),
        KPIResult("daily_demand_std", std_daily, "units", None, None, start, end, grain, {},
                  SOURCE, True, "formula=std(daily totals)",
                  "Population std of daily totals."),
        KPIResult("zero_demand_share", zero_share, "ratio", float(len(frame) - len(nonzero)),
                  float(len(frame)), start, end, grain, {}, SOURCE, True,
                  "formula=zero_rows/total_rows",
                  "Share of product/warehouse/day rows with zero demand."),
    ]


def demand_by_dimension(frame: pd.DataFrame, dimension: str) -> list[KPIResult]:
    """Compute total demand per value of a dimension column."""
    if frame.empty or dimension not in frame.columns:
        return []
    start, end = _span(frame)
    results = []
    for value, group in frame.groupby(dimension):
        total = float(group["quantity"].sum())
        results.append(KPIResult(
            f"total_demand_by_{dimension}", total, "units", total, None,
            start, end, "dataset", {dimension: str(value)}, SOURCE, True,
            "formula=sum(quantity) grouped",
            "Observed generated demand for this dimension value.",
        ))
    return results
