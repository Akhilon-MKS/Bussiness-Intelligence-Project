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


def total_profit(frame: pd.DataFrame) -> Optional[float]:
    return metric_value(frame, "estimated_profit_inr")


def sales_growth(frame: pd.DataFrame, days: int = 30) -> Optional[float]:
    if "date" not in frame.columns or "revenue_inr" not in frame.columns:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce")
    revenue = pd.to_numeric(frame["revenue_inr"], errors="coerce")
    latest = dates.max()
    if pd.isna(latest):
        return None
    current_start = latest.normalize() - pd.Timedelta(days=days - 1)
    previous_start = current_start - pd.Timedelta(days=days)
    current = revenue[dates.between(current_start, latest)].sum(min_count=1)
    previous = revenue[dates.between(previous_start, current_start - pd.Timedelta(days=1))].sum(min_count=1)
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return None
    return round(float((current - previous) / previous * 100), 2)


def total_orders(frame: pd.DataFrame) -> Optional[int]:
    for column in ("order_id", "order_number", "invoice_id"):
        if column in frame.columns and frame[column].notna().any():
            return int(frame[column].nunique())
    return None


def orders_delivered(frame: pd.DataFrame) -> Optional[int]:
    """Count orders that have been delivered or completed."""
    for column in ("received_order_id", "received_order_number", "received_orders"):
        if column in frame.columns and frame[column].notna().any():
            return int(frame[column].nunique())
    order_column = next(
        (column for column in ("order_id", "order_number", "invoice_id") if column in frame.columns),
        None,
    )
    if not order_column or "order_status" not in frame.columns:
        return None
    statuses = frame["order_status"].astype(str).str.strip().str.lower()
    delivered = statuses.isin({"received", "delivered", "completed"})
    if not delivered.any():
        return None
    return int(frame.loc[delivered, order_column].nunique())


def orders_received(frame: pd.DataFrame) -> Optional[int]:
    """Backward-compatible alias for delivered-order counts."""
    return orders_delivered(frame)


def orders_pending(frame: pd.DataFrame) -> Optional[int]:
    order_column = next(
        (column for column in ("order_id", "order_number", "invoice_id") if column in frame.columns),
        None,
    )
    if not order_column or "order_status" not in frame.columns:
        return None
    pending = frame["order_status"].astype(str).str.strip().str.lower().eq("pending")
    return int(frame.loc[pending, order_column].nunique()) if pending.any() else 0


def amount_paid(frame: pd.DataFrame) -> Optional[float]:
    for column in ("amount_paid_inr", "paid_amount_inr", "payment_received_inr"):
        value = metric_value(frame, column)
        if value is not None:
            return value
    return None


def payment_pending(frame: pd.DataFrame) -> Optional[float]:
    """Sum an explicit pending-payment field, or derive it from due and paid amounts."""
    for column in (
        "payment_pending_inr",
        "pending_payment_inr",
        "amount_pending_inr",
        "payment_due_inr",
        "pending_amount_inr",
    ):
        value = metric_value(frame, column)
        if value is not None:
            return value
    due = next(
        (metric_value(frame, column) for column in ("invoice_amount_inr", "amount_due_inr", "total_amount_inr")
         if metric_value(frame, column) is not None),
        None,
    )
    paid = next(
        (metric_value(frame, column) for column in ("amount_paid_inr", "paid_amount_inr", "payment_received_inr")
         if metric_value(frame, column) is not None),
        None,
    )
    return max(0.0, due - paid) if due is not None and paid is not None else None


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
