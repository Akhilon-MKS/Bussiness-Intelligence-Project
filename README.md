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

## Dashboard access

For the local demonstration, the login page provides five role buttons:
Admin, Healthcare B2B, Distribution B2B, Corporate B2B, and Consumer. No
credentials are required after selecting a role. This role selector is for
demonstration only and must not be used as production authentication.

The application has two role-based dashboards:

- `/admin`: administrator view of all departments, with sales-record editing.
- `/`: user view, filtered server-side to the user's assigned `segment`.

Set the first administrator before starting the server:

```powershell
$env:FLASK_SECRET_KEY = "use-a-long-random-value"
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = "use-a-strong-password"
python server.py
```

The administrator account is created in the `users` collection on first startup.
If you change `ADMIN_USERNAME` or `ADMIN_PASSWORD`, restart the server; the
configured administrator account is synchronized on the next sign-in.
After signing in at `/admin`, open **User accounts** in the sidebar to create
department users. Each user sees only sales rows for the assigned department;
related products, customers, and data-quality results are scoped to those rows.
Administrators see all departments and can edit sales records. The same user
creation action is also available through the API:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/admin/users" -Method Post `
  -ContentType "application/json" `
  -Body '{"username":"health-user","password":"strong-password","department":"Healthcare B2B"}'
```

PowerShell requests do not automatically share the browser's login session.
Use the browser while signed in as admin to create users, or create a PowerShell
session and log in first:

```powershell
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/login" -Method Post `
  -WebSession $session -ContentType "application/json" `
  -Body '{"username":"admin","password":"your-admin-password"}'
Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/admin/users" -Method Post `
  -WebSession $session -ContentType "application/json" `
  -Body '{"username":"health-user","password":"strong-password","department":"Healthcare B2B"}'
```

Valid departments are `Healthcare B2B`, `Distribution B2B`, `Corporate B2B`,
and `Consumer`. Keep the connection string, passwords, and Flask secret in
environment variables; never commit them.

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
