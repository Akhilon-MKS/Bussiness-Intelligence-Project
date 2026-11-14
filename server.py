from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from bson import ObjectId
from flask import Flask, jsonify, redirect, request, send_from_directory, session
from functools import wraps
from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from src.analysis import (
    average_order_value,
    monthly_activity_forecast,
    dimension_performance,
    product_performance,
    total_orders,
    total_revenue,
    total_units_sold,
)
from src.data_cleaning import clean_dataframe, data_quality_summary, duplicate_count
from src.data_loader import load_project_data

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "frontend"
app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-development-secret")
DEPARTMENTS = {"Healthcare B2B", "Distribution B2B", "Corporate B2B", "Consumer"}
DEMO_ROLES = {
    "admin": None,
    "healthcare": "Healthcare B2B",
    "distribution": "Distribution B2B",
    "corporate": "Corporate B2B",
    "consumer": "Consumer",
}


def _json_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    return value.item() if hasattr(value, "item") else value


def _records(frame: pd.DataFrame, limit: int | None = None) -> list[dict]:
    selected = frame.head(limit) if limit else frame
    return [{str(k): _json_value(v) for k, v in row.items()} for row in selected.to_dict("records")]


def _client():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI is not configured.")
    from pymongo import MongoClient
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def _database_client():
    client = _client()
    return client, client[os.environ.get("MONGODB_DATABASE", "nutrifuel")]


def _ensure_admin():
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        return
    client, database = _database_client()
    try:
        database.users.update_one(
            {"username": username},
            {"$set": {
                "password_hash": generate_password_hash(password),
                "role": "admin",
                "department": None,
                "active": True,
            }},
            upsert=True,
        )
    finally:
        client.close()


def _user():
    return session.get("user")


def _require_login(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect("/login")
        return function(*args, **kwargs)
    return wrapped


def _require_admin(function):
    @wraps(function)
    @_require_login
    def wrapped(*args, **kwargs):
        if _user().get("role") != "admin":
            return jsonify({"error": "Administrator access required."}), 403
        return function(*args, **kwargs)
    return wrapped


def _bundle():
    bundle = load_project_data()
    bundle.sales = clean_dataframe(bundle.sales)
    bundle.products = clean_dataframe(bundle.products)
    bundle.customers = clean_dataframe(bundle.customers)
    user = _user()
    if user and user.get("role") != "admin":
        if not user.get("department"):
            raise RuntimeError("This user has no department assigned.")
        if "segment" not in bundle.sales.columns:
            raise RuntimeError("Sales data has no segment field for department filtering.")
        bundle.sales = bundle.sales.loc[bundle.sales["segment"] == user["department"]].copy()
        if "sku" in bundle.products.columns and "sku" in bundle.sales.columns:
            bundle.products = bundle.products.loc[bundle.products["sku"].isin(bundle.sales["sku"])].copy()
        if "customer_id" in bundle.customers.columns and "customer_id" in bundle.sales.columns:
            bundle.customers = bundle.customers.loc[
                bundle.customers["customer_id"].isin(bundle.sales["customer_id"])
            ].copy()
    return bundle


@app.get("/")
@_require_login
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/admin")
@_require_admin
def admin():
    return send_from_directory(WEB, "index.html")


@app.get("/login")
def login_page():
    if _user():
        return redirect("/admin" if _user().get("role") == "admin" else "/")
    return send_from_directory(WEB, "login.html")


@app.post("/api/login")
def login():
    try:
        _ensure_admin()
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except PyMongoError:
        return jsonify({"error": "Could not connect to MongoDB. Check MONGODB_URI and network access."}), 503
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    try:
        client, database = _database_client()
        try:
            account = database.users.find_one({"username": username, "active": True})
        finally:
            client.close()
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except PyMongoError:
        return jsonify({"error": "Could not connect to MongoDB. Check MONGODB_URI and network access."}), 503
    if not account or not check_password_hash(account["password_hash"], password):
        return jsonify({"error": "Invalid username or password."}), 401
    session["user"] = {
        "username": account["username"],
        "role": account["role"],
        "department": account.get("department"),
    }
    return jsonify(session["user"])


@app.post("/api/demo-login")
def demo_login():
    payload = request.get_json(silent=True) or {}
    role = str(payload.get("role", "")).strip()
    if role not in DEMO_ROLES:
        return jsonify({"error": "Select a dashboard role."}), 400
    session["user"] = {
        "username": f"Demo {role.title()}",
        "role": "admin" if role == "admin" else "user",
        "department": DEMO_ROLES[role],
    }
    return jsonify(session["user"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    if not _user():
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, **_user()})


@app.get("/api/dashboard")
@_require_login
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
    sales_metric, monthly_trend = monthly_activity_forecast(sales)
    products = product_performance(sales)
    regions = dimension_performance(sales, "region")
    customer_types = dimension_performance(sales, "channel")
    pack_types = dimension_performance(sales, "pack_type")
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
        "product_performance": _records(products),
        "trend_metric": sales_metric,
        "monthly_trend": _records(monthly_trend),
        "regions": _records(regions),
        "customer_types": _records(customer_types),
        "pack_types": _records(pack_types),
    })


@app.get("/api/quality")
@_require_admin
def quality():
    bundle = _bundle()
    return jsonify({
        "sales": _records(data_quality_summary(bundle.sales, "Sales_Data")),
        "products": _records(data_quality_summary(bundle.products, "Products")),
        "customers": _records(data_quality_summary(bundle.customers, "Customers")),
    })


@app.get("/api/sales")
@_require_admin
def sales():
    bundle = _bundle()
    return jsonify({"columns": list(bundle.sales.columns), "rows": _records(bundle.sales, 200)})


@app.patch("/api/admin/sales/<record_id>")
@_require_admin
def update_sale(record_id):
    payload = request.get_json(silent=True) or {}
    allowed = {
        "date", "segment", "channel", "region", "state", "customer_id",
        "sku", "product_name", "price_unit_inr", "units_sold", "revenue_inr",
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        return jsonify({"error": "No editable fields were provided."}), 400
    try:
        object_id = ObjectId(record_id)
    except Exception:
        return jsonify({"error": "Invalid record ID."}), 400
    client, database = _database_client()
    try:
        result = database.sales.update_one({"_id": object_id}, {"$set": updates})
    finally:
        client.close()
    if result.matched_count == 0:
        return jsonify({"error": "Sales record not found."}), 404
    return jsonify({"updated": True, "record_id": record_id})


@app.post("/api/admin/users")
@_require_admin
def create_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    department = str(payload.get("department", "")).strip()
    if not username or not password or not department:
        return jsonify({"error": "Username, password, and department are required."}), 400
    if department not in DEPARTMENTS:
        return jsonify({"error": "Invalid department."}), 400
    client, database = _database_client()
    try:
        if database.users.find_one({"username": username}):
            return jsonify({"error": "Username already exists."}), 409
        database.users.insert_one({
            "username": username,
            "password_hash": generate_password_hash(password),
            "role": "user",
            "department": department,
            "active": True,
        })
    finally:
        client.close()
    return jsonify({"created": True, "username": username, "department": department}), 201


@app.get("/api/admin/users")
@_require_admin
def list_users():
    client, database = _database_client()
    try:
        accounts = database.users.find(
            {},
            {"_id": 0, "username": 1, "role": 1, "department": 1, "active": 1},
        ).sort("username", 1)
        return jsonify({"users": list(accounts)})
    finally:
        client.close()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
