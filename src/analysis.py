from __future__ import annotations

from typing import Optional

import numpy as np
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


def product_performance(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize product performance using populated measures when available."""
    product_column = "product_name" if "product_name" in frame.columns else "sku"
    if product_column not in frame.columns:
        return pd.DataFrame()
    working = frame[[product_column]].copy()
    working["product"] = working[product_column].fillna("Unknown").astype(str)
    result = working.groupby("product", as_index=False).size().rename(columns={"size": "records"})
    measure = next(
        (column for column in ("revenue_inr", "units_sold") if column in frame.columns
         and pd.to_numeric(frame[column], errors="coerce").notna().any()),
        None,
    )
    if measure:
        values = pd.DataFrame({
            "product": frame[product_column].fillna("Unknown").astype(str),
            "value": pd.to_numeric(frame[measure], errors="coerce"),
        }).dropna(subset=["value"])
        result = result.merge(values.groupby("product", as_index=False)["value"].sum(), on="product", how="left")
    else:
        result["value"] = result["records"]
    if "price_unit_inr" in frame.columns:
        prices = pd.DataFrame({
            "product": frame[product_column].fillna("Unknown").astype(str),
            "price": pd.to_numeric(frame["price_unit_inr"], errors="coerce"),
        })
        average_prices = prices.groupby("product", as_index=False)["price"].mean()
        result = result.merge(average_prices, on="product", how="left")
        result = result.rename(columns={"price": "average_price"})
    return result.sort_values("records", ascending=False).reset_index(drop=True)


def dimension_performance(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Aggregate a dimension by real sales measures or row activity."""
    if column not in frame.columns:
        return pd.DataFrame()
    working = pd.DataFrame({"dimension": frame[column].fillna("Unknown").astype(str)})
    result = working.groupby("dimension", as_index=False).size().rename(columns={"size": "records"})
    measure = next(
        (name for name in ("revenue_inr", "units_sold") if name in frame.columns
         and pd.to_numeric(frame[name], errors="coerce").notna().any()),
        None,
    )
    if measure:
        values = pd.DataFrame({
            "dimension": frame[column].fillna("Unknown").astype(str),
            "value": pd.to_numeric(frame[measure], errors="coerce"),
        }).dropna(subset=["value"])
        result = result.merge(values.groupby("dimension", as_index=False)["value"].sum(), on="dimension", how="left")
    else:
        result["value"] = result["records"]
    return result.sort_values("value", ascending=False).reset_index(drop=True)


def monthly_activity_forecast(frame: pd.DataFrame, periods: int = 3) -> tuple[str, pd.DataFrame]:
    """Return actual monthly values and a simple transparent trend projection."""
    if "date" not in frame.columns:
        return "record_activity", pd.DataFrame()
    dates = pd.to_datetime(frame["date"], errors="coerce")
    measure = next(
        (column for column in ("revenue_inr", "units_sold") if column in frame.columns
         and pd.to_numeric(frame[column], errors="coerce").notna().any()),
        None,
    )
    working = pd.DataFrame({"date": dates})
    if measure:
        working["value"] = pd.to_numeric(frame[measure], errors="coerce")
        metric = measure
    else:
        working["value"] = 1
        metric = "record_activity"
    working = working.dropna(subset=["date", "value"])
    if working.empty:
        return metric, pd.DataFrame()
    working["month"] = working["date"].dt.to_period("M").dt.to_timestamp()
    actual = working.groupby("month", as_index=False)["value"].sum().sort_values("month")
    actual["actual"] = actual["value"].round(2)
    actual["predicted"] = None
    result = actual[["month", "actual", "predicted"]].copy()
    if periods <= 0:
        return metric, result
    values = actual["value"].to_numpy(dtype=float)
    x_values = np.arange(len(values), dtype=float)
    slope, intercept = np.polyfit(x_values, values, 1) if len(values) > 1 else (0.0, values[0])
    next_month = actual["month"].iloc[-1].to_period("M") + 1
    future = []
    for offset in range(periods):
        prediction = max(0.0, slope * (len(values) + offset) + intercept)
        future.append({
            "month": (next_month + offset).to_timestamp(),
            "actual": None,
            "predicted": round(float(prediction), 2),
        })
    combined = result[["month", "actual", "predicted"]].to_dict("records") + future
    return metric, pd.DataFrame(combined, columns=["month", "actual", "predicted"])


def filter_by_date(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    if "date" not in frame.columns:
        return frame.copy()
    dates = pd.to_datetime(frame["date"], errors="coerce")
    return frame.loc[dates.between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")].copy()
