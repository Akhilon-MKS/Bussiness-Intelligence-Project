# NutriFuel Bar Business Insights

## Business problem

NutriFuel needs a repeatable way to understand its B2B and B2C sales dimensions, customers, product packs, and data readiness before operational reporting is introduced.

## Project objectives

- Inspect and document the supplied synthetic data.
- Provide reusable cleaning, validation, KPI, and visualization code.
- Give users an interactive Streamlit dashboard with honest empty states.

## Dataset description

`NutriFuel_Bar_BI_Dataset.xlsx` contains `README`, `Products`, `Customers`, and `Sales_Data` sheets. The workbook README describes Orders, Production_Data, and Inventory_Snapshots, but those sheets are not present in the supplied workbook. `NutriFuel_Sales_Data.csv` is a matching flat sales-dimension export.

The supplied Sales_Data contains 65,760 rows dated from 2022-01-01 through 2024-12-31. It includes NutriFuel Bar pack, channel, segment, region, state, and customer identifiers, 50 customer accounts, 3 SKUs, and 63,323 populated price observations. The columns for units, revenue, costs, stock, delivery, and promotion are empty in the supplied files. No order identifier is present.

All records, prices, accounts, and descriptions are synthetic sample data. They are not actual business transactions and must not be used as live financial reporting.

## Data cleaning

- Work on copies; source CSV and Excel files are preserved.
- Normalize column names and trim text values.
- Parse available date columns with invalid values becoming missing.
- Coerce known numeric columns to numeric values.
- Report missing values, duplicate rows, uniqueness, and negative-value warnings.
- Do not delete rows or fill missing business measures automatically.

## KPI definitions and availability

Revenue is the sum of populated `revenue_inr`; units are the sum of `units_sold`; orders are distinct `order_id`, `order_number`, or `invoice_id`; average order value is revenue divided by unique orders. These KPIs are **not calculable** from the supplied data because the relevant measures and order key are missing. Dimension-level counts and date coverage remain available.

## Main analytical findings

1. The dataset covers three calendar years and has no invalid dates in the supplied CSV.
2. The product identity is consistently NutriFuel Bar, with Single Bar, Box of 12, and Carton of 48 packs.
3. The customer model includes Healthcare B2B, Distribution B2B, Corporate B2B, and Consumer dimensions.
4. The Sales_Data table has no duplicate full rows and contains useful dimensions and prices, but its operational measures are 100% missing.
5. The workbook lacks the Orders, Production_Data, and Inventory_Snapshots sheets described in its README.

## Recommendations

- Populate a governed sales fact table with an order/invoice identifier, quantity, actual revenue, status, and transaction date.
- Supply inventory snapshots and production output with their own dates and keys.
- Confirm whether prices are list prices or realized selling prices before using them for revenue.
- Add automated completeness checks before publishing financial or inventory KPIs.

## Limitations

This is synthetic sample data, not a live database. It cannot support revenue, order, unit, stock, production, profitability, growth, or actual customer-performance conclusions until the missing measures are supplied.
