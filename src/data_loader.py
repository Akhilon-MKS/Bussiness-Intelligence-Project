from __future__ import annotations

from dataclasses import dataclass, field
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
    records = list(database[collection_name].find({}, {"_id": False}))
    return pd.DataFrame(records)


def load_project_data() -> DataBundle:
    """Load all dashboard datasets from MongoDB Atlas."""
    import os

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not configured.")

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
