import server


def test_user_order_updates_user_and_admin_dashboards(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ORDER_STORE", tmp_path / "orders.json")
    server.LOCAL_ORDERS.clear()


def test_dashboard_exposes_admin_kpis():
    client = server.app.test_client()
    client.post("/api/demo-login", json={"username": "admin", "password": "anything"})
    metrics = client.get("/api/dashboard").get_json()["metrics"]
    for key in (
        "revenue",
        "amount_billed",
        "amount_paid",
        "payment_pending",
        "orders_made",
        "orders_received",
        "orders_pending",
        "units",
        "average_order_value",
        "profit",
        "sales_growth_pct",
    ):
        assert metrics[key] is not None
    assert metrics["amount_billed"] >= metrics["amount_paid"]
    assert metrics["amount_billed"] >= metrics["payment_pending"]
    dashboard = client.get("/api/dashboard").get_json()
    assert dashboard["order_status"]
    assert "low_stock" in dashboard["stock_alerts"]
    assert dashboard["stock_alerts"]["units_in_stock"] >= 1_000
    client = server.app.test_client()

    client.post("/api/demo-login", json={"username": "user1", "password": "anything"})
    before = client.get("/api/dashboard").get_json()
    options = client.get("/api/order-options").get_json()
    response = client.post(
        "/api/orders",
        json={"sku": options["products"][0]["sku"], "quantity": 2},
    )
    assert response.status_code == 201
    order = response.get_json()["order"]
    assert order["brand"] == "NutriFuel"
    assert order["category"] == "Energy/Nutrition Bar"
    assert order["channel"] == "Hospital"
    assert order["customer_id"] == "USER1"
    assert order["sku"] == options["products"][0]["sku"]
    after = client.get("/api/dashboard").get_json()
    assert after["metrics"]["orders_made"] == before["metrics"]["orders_made"] + 1
    assert after["metrics"]["orders_pending"] == before["metrics"]["orders_pending"] + 1

    client.post("/api/demo-login", json={"username": "admin", "password": "anything"})
    admin = client.get("/api/dashboard").get_json()
    assert admin["metrics"]["orders_made"] >= after["metrics"]["orders_made"]
    server.LOCAL_ORDERS.clear()
