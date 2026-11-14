from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from pymongo import MongoClient


MOCK_CUSTOMER_SEGMENTS = {
    "USER1": "Healthcare B2B",
    "USER2": "Healthcare B2B",
    "USER3": "Distribution B2B",
    "USER4": "Distribution B2B",
    "USER5": "Corporate B2B",
    "USER6": "Consumer",
}
STOCK_LOW_THRESHOLD = 20_000


@dataclass
class DataBundle:
    """Loaded project datasets and the selected sales source."""

    sales: pd.DataFrame = field(default_factory=pd.DataFrame)
    products: pd.DataFrame = field(default_factory=pd.DataFrame)
    customers: pd.DataFrame = field(default_factory=pd.DataFrame)
    readme: pd.DataFrame = field(default_factory=pd.DataFrame)
    source: Optional[str] = None
    available_sheets: list[str] = field(default_factory=list)


def _mock_sales_until_today(sales: pd.DataFrame) -> pd.DataFrame:
    """Append deterministic demo sales through today without changing source rows."""
    if sales.empty or "date" not in sales.columns or "segment" not in sales.columns:
        return sales
    dates = pd.to_datetime(sales["date"], errors="coerce")
    latest = dates.max()
    today = pd.Timestamp.today().normalize()
    if pd.isna(latest):
        return sales

    sales = sales.copy()
    sales["date"] = dates
    if "customer_id" not in sales.columns:
        sales["customer_id"] = pd.Series(pd.NA, index=sales.index, dtype="object")
    else:
        sales["customer_id"] = sales["customer_id"].astype("object")
    for segment, customer_ids in _customers_by_segment().items():
        segment_rows = sales["segment"].eq(segment)
        row_count = int(segment_rows.sum())
        sales.loc[segment_rows, "customer_id"] = [
            customer_ids[offset % len(customer_ids)] for offset in range(row_count)
        ]
    rows = []
    if latest < today:
        templates = sales.loc[sales["date"].eq(latest)].copy()
        if len(templates) < 30:
            templates = sales.sort_values("date").tail(60).copy()
        templates["date"] = pd.to_datetime(templates["date"], errors="coerce")
        templates = templates.dropna(subset=["segment", "pack_type"])
        template_rows = templates.to_dict("records")
        for day_offset, date in enumerate(pd.date_range(latest + pd.Timedelta(days=1), today)):
            for template_index, template in enumerate(template_rows):
                row = template.copy()
                pack_price = pd.to_numeric(row.get("price_unit_inr"), errors="coerce")
                if pd.isna(pack_price):
                    pack_price = {
                        "Single Bar": 40,
                        "Box of 12": 420,
                        "Carton of 48": 1560,
                    }.get(row.get("pack_type"), 100)
                pack_price = float(pack_price)
                units = 4 + ((day_offset + template_index) % 9)
                invoice = round(pack_price * units, 2)
                received = (day_offset + template_index) % 4 != 0
                row.update({
                    "date": date,
                    "order_id": f"MOCK-{date:%Y%m%d}-{template_index:03d}-{row['customer_id']}",
                    "order_status": "Delivered" if received else "Pending",
                    "units_sold": units,
                    "delivered_units": units if received else 0,
                    "revenue_inr": invoice,
                    "invoice_amount_inr": invoice,
                    "amount_paid_inr": invoice if received else round(invoice * 0.4, 2),
                    "payment_pending_inr": 0.0 if received else round(invoice * 0.6, 2),
                    "estimated_cost_inr": round(invoice * 0.55, 2),
                    "estimated_profit_inr": round(invoice * 0.45, 2),
                    "stock_available_units": max(
                        0,
                        12 + ((day_offset * 3 + template_index * 11) % 42)
                        - (18 if (day_offset + template_index) % 17 == 0 else 0),
                    ) * 1_000,
                    "data_status": "mocked",
                })
                rows.append(row)
        sales = pd.concat([sales, pd.DataFrame(rows)], ignore_index=True)
    return _ensure_demo_measures(sales)


def _customers_by_segment() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for customer_id, segment in MOCK_CUSTOMER_SEGMENTS.items():
        result.setdefault(segment, []).append(customer_id)
    return result


def _ensure_demo_measures(sales: pd.DataFrame) -> pd.DataFrame:
    """Fill missing operational fields so the demo exposes complete KPIs."""
    df = sales.copy()
    def column(name: str) -> pd.Series:
        return df[name] if name in df.columns else pd.Series(index=df.index, dtype="object")

    row_index = pd.Series(range(len(df)), index=df.index)
    prices = pd.to_numeric(column("price_unit_inr"), errors="coerce")
    pack_prices = column("pack_type").map({
        "Single Bar": 40,
        "Box of 12": 420,
        "Carton of 48": 1560,
    })
    prices = prices.fillna(pack_prices).fillna(100)
    units = pd.to_numeric(column("units_sold"), errors="coerce")
    units = units.fillna(4 + (row_index % 9))
    invoice = pd.to_numeric(column("invoice_amount_inr"), errors="coerce")
    invoice = invoice.fillna((prices * units).round(2))
    statuses = column("order_status")
    statuses = statuses.where(statuses.notna() & statuses.astype(str).str.strip().ne(""), "Delivered")
    missing_status = statuses.eq("Delivered") & column("order_id").isna()
    statuses.loc[missing_status] = row_index.loc[missing_status].map(
        lambda value: "Pending" if int(value) % 4 == 0 else "Delivered"
    )
    order_ids = column("order_id")
    order_ids = order_ids.where(order_ids.notna() & order_ids.astype(str).str.strip().ne(""))
    order_ids = order_ids.fillna("DATA-" + row_index.map(lambda value: f"{int(value):06d}"))
    received = statuses.astype(str).str.lower().isin({"received", "delivered", "completed"})
    paid = pd.to_numeric(column("amount_paid_inr"), errors="coerce")
    paid = paid.fillna(invoice.where(received, (invoice * 0.4).round(2)))
    pending = pd.to_numeric(column("payment_pending_inr"), errors="coerce")
    pending = pending.fillna((invoice - paid).clip(lower=0).round(2))
    profit = pd.to_numeric(column("estimated_profit_inr"), errors="coerce")
    profit = profit.fillna((invoice * 0.45).round(2))
    delivered = pd.to_numeric(column("delivered_units"), errors="coerce")
    delivered = delivered.fillna(units.where(received, 0))
    stock = pd.to_numeric(column("stock_available_units"), errors="coerce")
    stock = stock.fillna(
        (12 + (row_index % 42) - (18 * (row_index % 17 == 0))).clip(lower=0) * 1_000
    )
    stock = stock.mask(stock.gt(0) & stock.lt(1_000), stock * 1_000)
    df["order_id"] = order_ids
    df["order_status"] = statuses
    df["units_sold"] = units
    df["delivered_units"] = delivered
    df["revenue_inr"] = pd.to_numeric(column("revenue_inr"), errors="coerce").fillna(invoice)
    df["invoice_amount_inr"] = invoice
    df["amount_paid_inr"] = paid
    df["payment_pending_inr"] = pending
    df["estimated_cost_inr"] = pd.to_numeric(column("estimated_cost_inr"), errors="coerce").fillna((invoice * 0.55).round(2))
    df["estimated_profit_inr"] = profit
    df["stock_available_units"] = stock
    data_status = column("data_status")
    df["data_status"] = data_status.where(
        data_status.notna() & data_status.astype(str).str.strip().ne(""),
        "mocked",
    )
    return df


def _collection_frame(database, collection_name: str) -> pd.DataFrame:
    records = list(database[collection_name].find({}))
    for record in records:
        record["_record_id"] = str(record.pop("_id"))
    return pd.DataFrame(records)


@lru_cache(maxsize=1)
def _load_local_data(root: Path) -> DataBundle:
    workbook = root / "NutriFuel_Bar_BI_Dataset.xlsx"
    csv_file = root / "NutriFuel_Sales_Data.csv"
    if workbook.exists():
        excel = pd.ExcelFile(workbook)
        sales = pd.read_excel(workbook, sheet_name="Sales_Data") if "Sales_Data" in excel.sheet_names else pd.DataFrame()
        sales = _mock_sales_until_today(sales)
        return DataBundle(
            sales=sales,
            products=pd.read_excel(workbook, sheet_name="Products") if "Products" in excel.sheet_names else pd.DataFrame(),
            customers=pd.read_excel(workbook, sheet_name="Customers") if "Customers" in excel.sheet_names else pd.DataFrame(),
            source=f"Local workbook with mocked data through {pd.Timestamp.today():%Y-%m-%d}: {workbook.name}",
            available_sheets=excel.sheet_names,
        )
    if csv_file.exists():
        sales = _mock_sales_until_today(pd.read_csv(csv_file, low_memory=False))
        return DataBundle(
            sales=sales,
            source=f"Local CSV with mocked data through {pd.Timestamp.today():%Y-%m-%d}: {csv_file.name}",
            available_sheets=["sales"],
        )
    raise RuntimeError("No MongoDB connection or local dataset was found.")


def load_project_data() -> DataBundle:
    """Load local project files unless MongoDB is explicitly enabled."""
    import os

    use_mongodb = os.environ.get("USE_MONGODB", "").lower() in {"1", "true", "yes"}
    uri = os.environ.get("MONGODB_URI")
    if not use_mongodb:
        return copy.deepcopy(_load_local_data(Path(__file__).resolve().parents[1]))
    if not uri:
        raise RuntimeError("MONGODB_URI is required when USE_MONGODB is enabled.")

    database_name = os.environ.get("MONGODB_DATABASE", "nutrifuel")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        database = client[database_name]
        return DataBundle(
            sales=_collection_frame(database, "sales"),
            products=_collection_frame(database, "products"),
            customers=_collection_frame(database, "customers"),
            source=f"MongoDB Atlas: {database_name}",
            available_sheets=["sales", "products", "customers"],
        )
    except Exception as error:
        raise RuntimeError("Could not connect to MongoDB Atlas.") from error
    finally:
        client.close()
