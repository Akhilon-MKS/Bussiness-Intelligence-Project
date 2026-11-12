import pandas as pd

from src.analysis import average_order_value, filter_by_date, total_orders, total_revenue
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


def test_date_filtering():
    data = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-02-01"]), "x": [1, 2]})
    assert len(filter_by_date(data, "2024-01-15", "2024-02-15")) == 1


def test_quality_and_required_columns():
    data = pd.DataFrame({"a": [1, None], "b": [2, 3]})
    quality = data_quality_summary(data)
    assert quality.loc[quality["column"] == "a", "missing"].item() == 1
    assert validate_required_columns(data, ["a", "missing"]) == ["missing"]
