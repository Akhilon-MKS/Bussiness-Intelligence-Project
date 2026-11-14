from __future__ import annotations

from typing import Iterable

import pandas as pd


DATE_COLUMNS = ("date", "order_date", "snapshot_date", "production_date")
NUMERIC_COLUMNS = (
    "price_unit_inr", "list_price_inr", "unit_cost_inr", "units_per_pack",
    "promotion", "delivery_days", "stock_available_units", "delivered_units",
    "units_sold", "revenue_inr", "estimated_cost_inr", "estimated_profit_inr",
    "quantity", "production_quantity", "invoice_amount_inr", "amount_paid_inr",
    "payment_pending_inr",
)


def clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Clean a working copy while preserving source records and columns."""
    df = frame.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    for column in df.select_dtypes(include="object").columns:
        df[column] = df[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    for column in DATE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", format="mixed", dayfirst=True)
    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def data_quality_summary(frame: pd.DataFrame, name: str = "dataset") -> pd.DataFrame:
    """Return one row per column with completeness, type, and validation information."""
    df = clean_dataframe(frame)
    rows = []
    for column in df.columns:
        series = df[column]
        warning = ""
        if column in {"units_sold", "delivered_units", "quantity", "production_quantity"}:
            invalid = int((series.dropna() < 0).sum())
            if invalid:
                warning = f"{invalid} negative value(s)"
        if column in {"price_unit_inr", "revenue_inr", "estimated_cost_inr", "estimated_profit_inr"}:
            invalid = int((series.dropna() < 0).sum())
            if invalid:
                warning = f"{invalid} negative value(s)"
        rows.append({
            "dataset": name,
            "column": column,
            "dtype": str(series.dtype),
            "rows": len(df),
            "missing": int(series.isna().sum()),
            "missing_pct": round(float(series.isna().mean() * 100), 2) if len(df) else 0.0,
            "unique_values": int(series.nunique(dropna=True)),
            "warning": warning,
        })
    return pd.DataFrame(rows)


def duplicate_count(frame: pd.DataFrame) -> int:
    return int(frame.duplicated().sum())


def validate_required_columns(frame: pd.DataFrame, required: Iterable[str]) -> list[str]:
    columns = {str(column).strip().lower() for column in frame.columns}
    return [column for column in required if column.lower() not in columns]
