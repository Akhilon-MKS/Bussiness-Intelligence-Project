import pandas as pd

from src.data_loader import _mock_sales_until_today
from src.analysis import (
    average_order_value,
    amount_paid,
    filter_by_date,
    monthly_activity_forecast,
    orders_received,
    orders_pending,
    payment_pending,
    product_performance,
    total_orders,
    total_revenue,
)
from src.data_cleaning import clean_dataframe, data_quality_summary, validate_required_columns


def test_cleaning_parses_dates_and_numbers():
    result = clean_dataframe(pd.DataFrame({"date": ["01-01-2024"], "revenue_inr": ["12.5"]}))
    assert str(result["date"].dtype).startswith("datetime")
    assert result.loc[0, "revenue_inr"] == 12.5


def test_revenue_and_unique_orders():
    data = pd.DataFrame({"revenue_inr": [10, 20, 5], "order_id": ["A", "A", "B"]})
    assert total_revenue(data) == 35
    assert total_orders(data) == 2
    assert average_order_value(data) == 17.5


def test_empty_measure_returns_none():
    assert total_revenue(pd.DataFrame({"revenue_inr": [None]})) is None
    assert total_orders(pd.DataFrame({"revenue_inr": [1]})) is None


def test_order_and_payment_account_metrics():
    data = pd.DataFrame({
        "order_id": ["A", "A", "B"],
        "order_status": ["Delivered", "Delivered", "Pending"],
        "invoice_amount_inr": [100, 50, 80],
        "amount_paid_inr": [100, 50, 20],
    })
    assert orders_received(data) == 1
    assert payment_pending(data) == 60
    assert amount_paid(data) == 170
    assert orders_pending(data) == 1


def test_date_filtering():
    data = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-02-01"]), "x": [1, 2]})
    assert len(filter_by_date(data, "2024-01-15", "2024-02-15")) == 1


def test_quality_and_required_columns():
    data = pd.DataFrame({"a": [1, None], "b": [2, 3]})
    quality = data_quality_summary(data)
    assert quality.loc[quality["column"] == "a", "missing"].item() == 1
    assert validate_required_columns(data, ["a", "missing"]) == ["missing"]


def test_product_performance_uses_records_when_sales_measures_are_empty():
    data = pd.DataFrame({
        "product_name": ["Classic", "Classic", "Berry"],
        "price_unit_inr": [100, 120, 80],
    })
    result = product_performance(data)
    assert result.loc[0, "product"] == "Classic"
    assert result.loc[0, "records"] == 2
    assert result.loc[0, "value"] == 2
    assert result.loc[0, "average_price"] == 110


def test_monthly_activity_forecast_returns_actual_and_projection():
    data = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-02-15"]),
    })
    metric, result = monthly_activity_forecast(data, periods=1)
    assert metric == "record_activity"
    assert result["actual"].notna().sum() == 2
    assert result["predicted"].notna().sum() == 1


def test_mock_sales_are_added_through_today():
    source = pd.DataFrame({
        "date": ["2024-12-31"],
        "segment": ["Consumer"],
        "pack_type": ["Single Bar"],
        "price_unit_inr": [40],
        "sku": ["NF-SINGLE"],
    })
    result = _mock_sales_until_today(source)
    assert len(result) > len(source)
    assert result["date"].max() == pd.Timestamp.today().normalize()
    assert result["data_status"].dropna().eq("mocked").all()
    assert result["order_id"].notna().any()
    assert result["payment_pending_inr"].notna().any()
    assert result["stock_available_units"].max() >= 1_000
