# NutriFuel Bar Business Intelligence and Sales Analytics Dashboard

This project is a Python and Flask dashboard for exploring NutriFuel Bar business dimensions across B2B and B2C channels. The dashboard never invents missing measures; unsupported KPIs show a clear availability message.

## Business problem and objectives

The application helps a business understand its product packs, customer segments, channels, regions, date coverage, and data readiness. It provides reusable loading, cleaning, validation, KPI, and visualization modules and an interactive dashboard with data-quality reporting.

## Technology stack

Python, Pandas, NumPy, OpenPyXL, Flask, Chart.js, pytest, Git, and GitHub.

## Project structure

```text
app.py
requirements.txt
data files (kept in the project root)
src/
  data_loader.py
  data_cleaning.py
  analysis.py
  visualizations.py
reports/business_insights.md
tests/test_data.py
```

## Supplied datasets

`NutriFuel_Bar_BI_Dataset.xlsx` contains `README`, `Products`, `Customers`, and `Sales_Data`. `NutriFuel_Sales_Data.csv` is a matching flat export. The workbook README mentions Orders, Production_Data, and Inventory_Snapshots, but those sheets are absent. The dataset is not empty: it contains 65,760 dated rows, 50 customer accounts, 3 product packs, channels, regions, states, and 63,323 populated price observations. However, sales measures such as `units_sold` and `revenue_inr` are empty, so revenue, orders, stock, production, and profitability KPIs cannot be calculated yet.

## Data source

The dashboard uses `NutriFuel_Bar_BI_Dataset.xlsx` locally and does not require
MongoDB for the demo. MongoDB support remains available only when
`USE_MONGODB=true` is explicitly configured.

## Windows PowerShell setup

```powershell
cd "E:\Nutri-Fuel Project"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal only.

## Run the application and tests

```powershell
python server.py
pytest -q
```

Open `http://127.0.0.1:5050` in your browser. The separate frontend has Overview, Sales Analytics, and Data Quality sections. It uses a Flask JSON API and Chart.js; it does not use Streamlit. Date filters update the dashboard data request.

## Dashboard access

For the local demonstration, start the server without MongoDB:

```powershell
$env:FLASK_SECRET_KEY = "use-a-long-random-value"
python server.py
```

The sign-in page provides seven local accounts: `admin`, `user1`, `user2`,
`user3`, `user4`, `user5`, and `user6`. Any non-empty password is accepted for
the demo accounts. Admin sees every category. Each user has a distinct customer
ID and is filtered server-side to only that customer's purchased items,
orders, received orders, pending orders, paid amount, pending payment,
products, channels, regions, states, and pack types. This is a demonstration
login and does not provide production authentication.

User views show items purchased, product categories, channels, regions, states,
pack types, and customer IDs for their assigned category. Admin sees all data.
The role selector is for demonstration only and does not provide production
authentication.

## KPI definitions

Revenue is the sum of populated `revenue_inr`; profit is the sum of
`estimated_profit_inr`; amount received and pending are based on the payment
fields; units sold is the sum of `units_sold`; orders use distinct order
identifiers; average order value is revenue divided by unique orders. Sales
growth compares the latest 30 days with the preceding 30 days. Stock alerts
use the latest available stock value per SKU, with zero as out of stock and
20,000 or fewer units as low stock. Demo inventory is generated in quantities
of thousands to reflect warehouse-scale stock levels. The application avoids line-item order
counting and duplicated joins. See `reports/business_insights.md` for the
full data-quality findings and recommendations.

## GitHub submission

Review the synthetic data licensing and size before committing datasets. Then:

```powershell
git add .
git commit -m "Build NutriFuel Bar BI dashboard"
git branch -M main
git remote add origin https://github.com/<your-account>/<your-repository>.git
git push -u origin main
```
