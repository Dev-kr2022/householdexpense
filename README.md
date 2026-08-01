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
streamlit run app.py
```

Add an OpenAI key to `.env` only if you want AI report insights. Expense entry,
reports, and CSV download work without an API key. The app opens at
`http://localhost:8501` and stores data in the local `expenses.db` SQLite file.

## Features

- Record date, category, amount, and an optional note.
- Filter by dates and categories, name the report, view totals and a chart.
- Export the filtered report to CSV.
- Ask an AI agent about the selected report or choose common queries.

## Deployment note

SQLite is appropriate for local use. Before deploying a multi-user app, replace
it with a persistent hosted database such as Postgres; cloud containers can be
restarted and their local files lost.
