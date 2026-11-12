from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


def main() -> None:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not configured.")

    workbook = ROOT / "NutriFuel_Bar_BI_Dataset.xlsx"
    csv_file = ROOT / "NutriFuel_Sales_Data.csv"
    database_name = os.environ.get("MONGODB_DATABASE", "nutrifuel")

    if not workbook.exists() and not csv_file.exists():
        raise FileNotFoundError("No source CSV or Excel file was found.")

    if workbook.exists():
        excel = pd.ExcelFile(workbook)
        products = pd.read_excel(workbook, sheet_name="Products") if "Products" in excel.sheet_names else pd.DataFrame()
        customers = pd.read_excel(workbook, sheet_name="Customers") if "Customers" in excel.sheet_names else pd.DataFrame()
        sales = pd.read_excel(workbook, sheet_name="Sales_Data") if "Sales_Data" in excel.sheet_names else pd.DataFrame()
    else:
        products = pd.DataFrame()
        customers = pd.DataFrame()
        sales = pd.DataFrame()

    if sales.empty and csv_file.exists():
        sales = pd.read_csv(csv_file, low_memory=False)

    client = MongoClient(uri, serverSelectionTimeoutMS=5000, socketTimeoutMS=120000)
    try:
        client.admin.command("ping")
        database = client[database_name]
        for name, frame in (("sales", sales), ("products", products), ("customers", customers)):
            collection = database[name]
            collection.delete_many({})
            records = _records(frame)
            for start in range(0, len(records), 1000):
                collection.insert_many(records[start:start + 1000])
                print(f"{name}: imported {min(start + 1000, len(records))}/{len(records)} records", flush=True)
            if not records:
                print(f"{name}: imported 0 records", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
