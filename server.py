from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from src.analysis import average_order_value, total_orders, total_revenue, total_units_sold
from src.data_cleaning import clean_dataframe, data_quality_summary, duplicate_count
from src.data_loader import load_project_data

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "frontend"
app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")


def _json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    return value.item() if hasattr(value, "item") else value


def _records(frame: pd.DataFrame, limit: int | None = None) -> list[dict]:
    selected = frame.head(limit) if limit else frame
    return [{str(k): _json_value(v) for k, v in row.items()} for row in selected.to_dict("records")]


def _bundle():
    bundle = load_project_data()
    bundle.sales = clean_dataframe(bundle.sales)
    bundle.products = clean_dataframe(bundle.products)
    bundle.customers = clean_dataframe(bundle.customers)
    return bundle


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/api/dashboard")
def dashboard():
    bundle = _bundle()
    sales = bundle.sales
    if "date" in sales:
        start = request.args.get("start")
        end = request.args.get("end")
        if start and end:
            dates = pd.to_datetime(sales["date"], errors="coerce")
            sales = sales.loc[dates.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    price = pd.to_numeric(sales.get("price_unit_inr"), errors="coerce") if "price_unit_inr" in sales else pd.Series(dtype=float)
    return jsonify({
        "source": bundle.source,
        "sheets": bundle.available_sheets,
        "rows": len(sales),
        "date_start": sales["date"].min().strftime("%Y-%m-%d") if len(sales) and sales["date"].notna().any() else None,
        "date_end": sales["date"].max().strftime("%Y-%m-%d") if len(sales) and sales["date"].notna().any() else None,
        "duplicates": duplicate_count(sales),
        "catalog_value": float(price.mean()) if price.notna().any() else None,
        "customers": int(sales["customer_id"].nunique()) if "customer_id" in sales else None,
        "packs": int(sales["sku"].nunique()) if "sku" in sales else None,
        "metrics": {
            "revenue": total_revenue(sales),
            "orders": total_orders(sales),
            "units": total_units_sold(sales),
            "average_order_value": average_order_value(sales),
        },
        "segments": _records(sales["segment"].value_counts().rename_axis("segment").reset_index(name="rows")),
        "channels": _records(sales["channel"].value_counts().rename_axis("channel").reset_index(name="rows")),
        "products": _records(sales["product_name"].value_counts().rename_axis("product").reset_index(name="rows")),
    })


@app.get("/api/quality")
def quality():
    bundle = _bundle()
    return jsonify({
        "sales": _records(data_quality_summary(bundle.sales, "Sales_Data")),
        "products": _records(data_quality_summary(bundle.products, "Products")),
        "customers": _records(data_quality_summary(bundle.customers, "Customers")),
    })


@app.get("/api/sales")
def sales():
    bundle = _bundle()
    return jsonify({"columns": list(bundle.sales.columns), "rows": _records(bundle.sales, 200)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
