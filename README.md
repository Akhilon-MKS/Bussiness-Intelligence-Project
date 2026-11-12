# NutriFuel Bar Business Intelligence and Sales Analytics Dashboard

This project is a beginner-friendly Python and Streamlit dashboard for exploring NutriFuel Bar business dimensions across B2B and B2C channels. **The supplied files contain synthetic sample data, not actual business transactions.** The dashboard never invents missing measures; unsupported KPIs show a clear availability message.

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

## MongoDB Atlas setup

The dashboard reads sales, products, and customers from MongoDB Atlas. It does not load
the CSV or Excel files at runtime. Set these environment variables in PowerShell:

```powershell
$env:MONGODB_URI = "mongodb+srv://akhilon24ad_db_user:<password>@nutrifuel-cluster.opihgfa.mongodb.net/nutrifuel?retryWrites=true&w=majority"
$env:MONGODB_DATABASE = "nutrifuel"
```

Replace `<password>` locally with the rotated database-user password. Do not commit
the URI or password.

Install dependencies and import the existing data once:

```powershell
pip install -r requirements.txt
python scripts/import_to_mongodb.py
```

The import replaces the contents of the `sales`, `products`, and `customers`
collections. After verifying the dashboard, the local CSV and Excel files can be
removed from the project folder.

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

## KPI definitions

Revenue is the sum of populated `revenue_inr`; units sold is the sum of `units_sold`; orders use distinct order identifiers; average order value is revenue divided by unique orders. The application avoids line-item order counting and duplicated joins. See `reports/business_insights.md` for the full data-quality findings and recommendations.

## GitHub submission

Review the synthetic data licensing and size before committing datasets. Then:

```powershell
git add .
git commit -m "Build NutriFuel Bar BI dashboard"
git branch -M main
git remote add origin https://github.com/<your-account>/<your-repository>.git
git push -u origin main
```
