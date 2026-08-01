# Household Expense Tracker

A Streamlit app for recording household expenses and generating custom reports.
It includes Grocery, Internet, Electricity, Gas, Petrol, Maintenance, Cooper,
Cooper Doctor, Car Servicing, Alcohol, Parking, Festival, Misc, Medical, and FTH.

## Run locally

```bash
cd /path/to/household_expense_tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Add an OpenAI key to `.env` only if you want AI report insights. Expense entry,
reports, and CSV download work without an API key. The app opens at
`http://localhost:8501` on the Mac and can also be accessed from another
device on the same network at `http://192.168.68.58:8501` while the Mac is
running the app.

## Features

- Record date, category, amount, and an optional note.
- Filter by dates and categories, name the report, view totals and a chart.
- Export the filtered report to CSV.
- Ask an AI agent about the selected report or choose common queries.

## Deployment note

SQLite is appropriate for local use. Before deploying a multi-user app, replace
it with a persistent hosted database such as Postgres; cloud containers can be
restarted and their local files lost.

For Streamlit Cloud or any hosted environment, set `DATABASE_URL` in Streamlit
secrets or your environment so the app can connect to a persistent database.
If you use Postgres, also install the appropriate driver such as `psycopg[binary]`.

If you run the app locally on your Mac, you can optionally specify a custom
SQLite file path with `SQLITE_PATH`:

```bash
export SQLITE_PATH="/Users/yourname/Drive/expenses.db"
streamlit run app.py
```

Example Streamlit secrets configuration (`.streamlit/secrets.toml`):

```toml
DATABASE_URL = "postgresql://postgres:your-password@db.project-ref.supabase.co:5432/postgres"
OPENAI_API_KEY = "sk-..."
```

For Supabase, use the connection string from Project Settings → Database → Connection
string. In Streamlit Cloud, add `DATABASE_URL` under App settings → Secrets and
re-deploy. The app will automatically switch from SQLite to Postgres when that
value is present.
