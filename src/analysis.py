from __future__ import annotations

from typing import Optional

import pandas as pd


def _numeric(frame: pd.DataFrame, column: str) -> Optional[pd.Series]:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return values if not values.empty else None


def metric_value(frame: pd.DataFrame, column: str, operation: str = "sum") -> Optional[float]:
    values = _numeric(frame, column)
    if values is None:
        return None
    if operation == "mean":
        return float(values.mean())
    return float(values.sum())


def total_revenue(frame: pd.DataFrame) -> Optional[float]:
    return metric_value(frame, "revenue_inr")


def total_units_sold(frame: pd.DataFrame) -> Optional[float]:
    return metric_value(frame, "units_sold")


def total_orders(frame: pd.DataFrame) -> Optional[int]:
    for column in ("order_id", "order_number", "invoice_id"):
        if column in frame.columns and frame[column].notna().any():
            return int(frame[column].nunique())
    return None


def average_order_value(frame: pd.DataFrame) -> Optional[float]:
    revenue = total_revenue(frame)
    orders = total_orders(frame)
    return revenue / orders if revenue is not None and orders else None


def aggregate_by(frame: pd.DataFrame, group: str, value: str = "revenue_inr") -> pd.DataFrame:
    if group not in frame.columns or value not in frame.columns:
        return pd.DataFrame()
    working = frame[[group, value]].copy()
    working[value] = pd.to_numeric(working[value], errors="coerce")
    working = working.dropna(subset=[value])
    if working.empty:
        return pd.DataFrame()
    return working.groupby(group, dropna=False, as_index=False)[value].sum().sort_values(value, ascending=False)


def monthly_revenue(frame: pd.DataFrame) -> pd.DataFrame:
    if "date" not in frame.columns or "revenue_inr" not in frame.columns:
        return pd.DataFrame()
    working = frame[["date", "revenue_inr"]].copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["revenue_inr"] = pd.to_numeric(working["revenue_inr"], errors="coerce")
    working = working.dropna()
    if working.empty:
        return pd.DataFrame()
    working["month"] = working["date"].dt.to_period("M").dt.to_timestamp()
    return working.groupby("month", as_index=False)["revenue_inr"].sum().sort_values("month")


def filter_by_date(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    if "date" not in frame.columns:
        return frame.copy()
    dates = pd.to_datetime(frame["date"], errors="coerce")
    return frame.loc[dates.between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")].copy()
