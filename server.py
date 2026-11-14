from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

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
    amount_paid,
    metric_value,
    orders_delivered,
    orders_pending,
    payment_pending,
    product_performance,
    sales_growth,
    total_profit,
    total_orders,
    total_revenue,
    total_units_sold,
)
from src.data_cleaning import clean_dataframe, data_quality_summary, duplicate_count
from src.data_loader import MOCK_CUSTOMER_SEGMENTS, STOCK_LOW_THRESHOLD, load_project_data

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "frontend"
app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-development-secret")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
DEPARTMENTS = {"Healthcare B2B", "Distribution B2B", "Corporate B2B", "Consumer"}
ORDER_STORE = ROOT / "mock_orders.json"
ORDER_LOCK = Lock()


def _load_local_orders() -> list[dict]:
    if not ORDER_STORE.exists():
        return []
    with ORDER_STORE.open(encoding="utf-8") as file:
        orders = json.load(file)
    if not isinstance(orders, list) or not all(isinstance(order, dict) for order in orders):
        raise RuntimeError("The local order store must contain a list of order records.")
    return orders


LOCAL_ORDERS = _load_local_orders()
DEMO_USERS = {
    f"user{index}": customer_id
    for index, customer_id in enumerate(MOCK_CUSTOMER_SEGMENTS, start=1)
}


@app.after_request
def disable_dashboard_caching(response):
    if request.path.startswith("/api/") or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


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
    with ORDER_LOCK:
        if LOCAL_ORDERS:
            _repair_local_orders(bundle.sales)
            local_orders = pd.DataFrame(LOCAL_ORDERS).dropna(axis=1, how="all")
            bundle.sales = pd.concat([local_orders, bundle.sales], ignore_index=True, sort=False)
    bundle.sales = clean_dataframe(bundle.sales)
    bundle.products = clean_dataframe(bundle.products)
    bundle.customers = clean_dataframe(bundle.customers)
    user = _user()
    if user and user.get("role") != "admin":
        if user.get("customer_id") and "customer_id" in bundle.sales.columns:
            bundle.sales = bundle.sales.loc[bundle.sales["customer_id"] == user["customer_id"]].copy()
        elif user.get("department") and "segment" in bundle.sales.columns:
            bundle.sales = bundle.sales.loc[bundle.sales["segment"] == user["department"]].copy()
        else:
            raise RuntimeError("This user has no valid data scope assigned.")
        if "sku" in bundle.products.columns and "sku" in bundle.sales.columns:
            bundle.products = bundle.products.loc[bundle.products["sku"].isin(bundle.sales["sku"])].copy()
        if "customer_id" in bundle.customers.columns and "customer_id" in bundle.sales.columns:
            bundle.customers = bundle.customers.loc[
                bundle.customers["customer_id"].isin(bundle.sales["customer_id"])
            ].copy()
    return bundle


def _save_local_orders() -> None:
    temporary = ORDER_STORE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(LOCAL_ORDERS, file, indent=2)
    temporary.replace(ORDER_STORE)


def _repair_local_orders(sales: pd.DataFrame) -> None:
    changed = False
    for order in LOCAL_ORDERS:
        if "sku" not in order or "sku" not in sales.columns:
            continue
        matching = sales.loc[sales["sku"].eq(order["sku"])]
        if "customer_id" in sales.columns and order.get("customer_id"):
            customer_matching = matching.loc[matching["customer_id"].eq(order["customer_id"])]
            if not customer_matching.empty:
                matching = customer_matching
        if matching.empty:
            continue
        source = matching.iloc[0].to_dict()
        for key, value in source.items():
            current = order.get(key)
            missing = current is None or current == "" or (isinstance(current, float) and pd.isna(current))
            if missing and key != "_record_id":
                order[key] = _json_value(value)
                changed = True
    if changed:
        _save_local_orders()


def _order_status_summary(sales: pd.DataFrame) -> list[dict]:
    if "order_status" not in sales.columns or "order_id" not in sales.columns:
        return []
    statuses = sales.assign(
        order_status=sales["order_status"].fillna("Unknown").astype(str).str.strip().str.title()
    ).loc[sales["order_id"].notna()]
    summary = (
        statuses.groupby("order_status")["order_id"]
        .nunique()
        .sort_values(ascending=False)
        .rename("orders")
        .reset_index()
    )
    return _records(summary)


def _stock_alerts(sales: pd.DataFrame) -> dict:
    required = {"sku", "stock_available_units"}
    if not required.issubset(sales.columns):
        return {"out_of_stock": 0, "low_stock": 0, "units_in_stock": None, "products": []}
    working = sales.copy()
    working["stock_available_units"] = pd.to_numeric(working["stock_available_units"], errors="coerce")
    working = working.dropna(subset=["sku", "stock_available_units"])
    if working.empty:
        return {"out_of_stock": 0, "low_stock": 0, "units_in_stock": None, "products": []}
    latest = (
        working.sort_values("date" if "date" in working.columns else "sku")
        .drop_duplicates("sku", keep="last")
    )
    latest["product"] = latest.get("product_name", latest["sku"]).fillna(latest["sku"]).astype(str)
    latest["stock"] = latest["stock_available_units"].astype(float)
    alerts = latest.loc[latest["stock"] <= STOCK_LOW_THRESHOLD].sort_values("stock")
    return {
        "out_of_stock": int((latest["stock"] <= 0).sum()),
        "low_stock": int(
            ((latest["stock"] > 0) & (latest["stock"] <= STOCK_LOW_THRESHOLD)).sum()
        ),
        "units_in_stock": int(latest["stock"].sum()),
        "products": _records(alerts[["sku", "product", "stock"]].head(8)),
    }


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
        "customer_id": account.get("customer_id"),
    }
    return jsonify(session["user"])


@app.post("/api/demo-login")
def demo_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip().lower()
    if username == "admin":
        role = "admin"
        department = None
        customer_id = None
    elif username in DEMO_USERS:
        role = "user"
        customer_id = DEMO_USERS[username]
        department = MOCK_CUSTOMER_SEGMENTS[customer_id]
    else:
        return jsonify({"error": "Use admin or user1 through user6."}), 400
    session["user"] = {
        "username": username,
        "role": role,
        "department": department,
        "customer_id": customer_id,
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
            "orders_made": total_orders(sales),
            "orders_delivered": orders_delivered(sales),
            "orders_received": orders_delivered(sales),
            "orders_pending": orders_pending(sales),
            "amount_paid": amount_paid(sales),
            "amount_billed": metric_value(sales, "invoice_amount_inr"),
            "profit": total_profit(sales),
            "sales_growth_pct": sales_growth(sales),
            "payment_pending": payment_pending(sales),
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
        "order_status": _order_status_summary(sales),
        "stock_alerts": _stock_alerts(sales),
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
@_require_login
def sales():
    bundle = _bundle()
    return jsonify({"columns": list(bundle.sales.columns), "rows": _records(bundle.sales, 200)})


@app.get("/api/order-options")
@_require_login
def order_options():
    if _user().get("role") == "admin":
        return jsonify({"error": "Only customer accounts can place orders."}), 403
    bundle = _bundle()
    columns = ["sku", "product_name", "pack_type", "price_unit_inr"]
    available = [column for column in columns if column in bundle.sales.columns]
    options = bundle.sales[available].dropna(subset=["sku"]).drop_duplicates("sku")
    return jsonify({"products": _records(options.sort_values("sku"))})


@app.post("/api/orders")
@_require_login
def create_order():
    user = _user()
    if user.get("role") == "admin":
        return jsonify({"error": "Only customer accounts can place orders."}), 403
    payload = request.get_json(silent=True) or {}
    sku = str(payload.get("sku", "")).strip()
    try:
        quantity = int(payload.get("quantity", 0))
    except (TypeError, ValueError):
        quantity = 0
    if not sku or quantity < 1 or quantity > 1000:
        return jsonify({"error": "Choose a product and quantity between 1 and 1000."}), 400

    bundle = _bundle()
    if "sku" not in bundle.sales.columns:
        return jsonify({"error": "No products are available for ordering."}), 503
    matching = bundle.sales.loc[bundle.sales["sku"].eq(sku)]
    if matching.empty:
        return jsonify({"error": "That product is not available for your account."}), 400
    product = matching.iloc[0]
    price = pd.to_numeric(product.get("price_unit_inr"), errors="coerce")
    if pd.isna(price):
        return jsonify({"error": "The selected product has no valid price."}), 400

    invoice = round(float(price) * quantity, 2)
    today = pd.Timestamp.today().normalize()
    with ORDER_LOCK:
        order_id = f"USER-{today:%Y%m%d}-{len(LOCAL_ORDERS) + 1:05d}"
        order = {
            str(key): _json_value(value)
            for key, value in product.to_dict().items()
            if key != "_record_id"
        }
        order.update({
            "date": today.strftime("%Y-%m-%d"),
            "order_id": order_id,
            "order_status": "Pending",
            "customer_id": user["customer_id"],
            "segment": user["department"],
            "sku": sku,
            "product_name": product.get("product_name"),
            "pack_type": product.get("pack_type"),
            "price_unit_inr": float(price),
            "units_sold": quantity,
            "delivered_units": 0,
            "revenue_inr": invoice,
            "invoice_amount_inr": invoice,
            "amount_paid_inr": 0.0,
            "payment_pending_inr": invoice,
            "data_status": "user_order",
        })
        LOCAL_ORDERS.append(order)
        _save_local_orders()
    return jsonify({"created": True, "order": order}), 201


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
    customer_id = str(payload.get("customer_id", "")).strip()
    if not username or not password or not department or not customer_id:
        return jsonify({"error": "Username, password, department, and customer ID are required."}), 400
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
            "customer_id": customer_id,
            "active": True,
        })
    finally:
        client.close()
    return jsonify({
        "created": True,
        "username": username,
        "department": department,
        "customer_id": customer_id,
    }), 201


@app.get("/api/admin/users")
@_require_admin
def list_users():
    client, database = _database_client()
    try:
        accounts = database.users.find(
            {},
            {"_id": 0, "username": 1, "role": 1, "department": 1, "customer_id": 1, "active": 1},
        ).sort("username", 1)
        return jsonify({"users": list(accounts)})
    finally:
        client.close()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
