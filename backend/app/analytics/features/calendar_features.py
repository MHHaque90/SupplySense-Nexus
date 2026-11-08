"""Calendar attributes for analytical frames (Phase 3)."""

import pandas as pd


def add_calendar_attributes(frame: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    """Add deterministic calendar attributes derived from a date column."""
    work = frame.copy()
    dates = pd.to_datetime(work[date_column])
    work["day_of_week"] = dates.dt.weekday.astype(int)
    work["is_weekend"] = (dates.dt.weekday >= 5).astype(int)
    work["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    work["month"] = dates.dt.month.astype(int)
    work["quarter"] = dates.dt.quarter.astype(int)
    work["year"] = dates.dt.year.astype(int)
    work["day_of_year"] = dates.dt.dayofyear.astype(int)
    return work
