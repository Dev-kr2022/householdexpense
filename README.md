# Household Expense Tracker

Household Expense Tracker is a simple web app for recording shared household spending, reviewing reports, and exporting data. It is built with Streamlit and can work with either a local SQLite database or a hosted PostgreSQL/Supabase database.

## What the app does

You can use it to:

- Add new expenses with a date, category, amount, and note
- Choose the user associated with each expense
- Filter expenses by date, category, and user
- Create named reports and view totals and charts
- Export reports to CSV
- Ask for optional AI-generated insights about a report

## Quick start

### 1. Install the project

```bash
cd /path/to/household_expense_tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run the app locally

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Then open:

- http://localhost:8501

### 3. Sign in

The app is protected by an admin password. Set `ADMIN_PASSWORD` in your local
`.env` file or in Streamlit secrets before starting the app.

```env
ADMIN_PASSWORD=choose_a_secure_password
```

## Optional setup

### Use AI features

Add your OpenAI key to the .env file if you want AI report insights.

```env
OPENAI_API_KEY=your-openai-key
```

AI features are optional. Expense entry, filtering, reports, and CSV export still work without an API key.

### Use a persistent database

By default, the app uses SQLite for local testing. This is fine for personal use.

If you want shared or production-style storage, set a PostgreSQL/Supabase connection string:

```env
DATABASE_URL=postgresql://user:password@host:5432/postgres
```

The app will automatically use PostgreSQL when DATABASE_URL is available.

## How to use the app

1. Open the app and sign in.
2. Add an expense using the form.
3. Choose a category and user.
4. Filter and review your data in the reports section.
5. Export a report to CSV when needed.

## Deployment

### Local use

Use the steps above. SQLite is the easiest option for a single machine.

### Streamlit Cloud

For hosted deployment, add your secrets in Streamlit Cloud:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/postgres"
OPENAI_API_KEY = "your-openai-key"
```

If you are using Supabase, copy the connection string from your Supabase project database settings.

## Troubleshooting

- If the app says a port is already in use, try a different port such as 8502 or 8503.
- If the app cannot connect to PostgreSQL, it will fall back to SQLite automatically.
- If you want a custom SQLite file location, set:

```bash
export SQLITE_PATH="/path/to/expenses.db"
```

## Notes

Common expense categories include Grocery, Internet, Electricity, Gas, Petrol, Maintenance, Cooper, Cooper Doctor, Car Servicing, Car Wash, Alcohol, Parking, Festival, Misc, Medical, and FTH.
