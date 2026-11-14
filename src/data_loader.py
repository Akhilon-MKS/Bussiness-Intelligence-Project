from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from pymongo import MongoClient


@dataclass
class DataBundle:
    """Loaded project datasets and the selected sales source."""

    sales: pd.DataFrame = field(default_factory=pd.DataFrame)
    products: pd.DataFrame = field(default_factory=pd.DataFrame)
    customers: pd.DataFrame = field(default_factory=pd.DataFrame)
    readme: pd.DataFrame = field(default_factory=pd.DataFrame)
    source: Optional[str] = None
    available_sheets: list[str] = field(default_factory=list)


def _collection_frame(database, collection_name: str) -> pd.DataFrame:
    records = list(database[collection_name].find({}))
    for record in records:
        record["_record_id"] = str(record.pop("_id"))
    return pd.DataFrame(records)


def _load_local_data(root: Path) -> DataBundle:
    workbook = root / "NutriFuel_Bar_BI_Dataset.xlsx"
    csv_file = root / "NutriFuel_Sales_Data.csv"
    if workbook.exists():
        excel = pd.ExcelFile(workbook)
        return DataBundle(
            sales=pd.read_excel(workbook, sheet_name="Sales_Data") if "Sales_Data" in excel.sheet_names else pd.DataFrame(),
            products=pd.read_excel(workbook, sheet_name="Products") if "Products" in excel.sheet_names else pd.DataFrame(),
            customers=pd.read_excel(workbook, sheet_name="Customers") if "Customers" in excel.sheet_names else pd.DataFrame(),
            source=f"Local workbook: {workbook.name}",
            available_sheets=excel.sheet_names,
        )
    if csv_file.exists():
        return DataBundle(
            sales=pd.read_csv(csv_file, low_memory=False),
            source=f"Local CSV: {csv_file.name}",
            available_sheets=["sales"],
        )
    raise RuntimeError("No MongoDB connection or local dataset was found.")


def load_project_data() -> DataBundle:
    """Load dashboard datasets from MongoDB Atlas or local project files."""
    import os

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return _load_local_data(Path(__file__).resolve().parents[1])

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
