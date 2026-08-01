# Project Documentation

## Overview

Household Expense Tracker is a Streamlit-based web application for recording shared household expenses, reviewing filtered reports, and exporting data. It is designed for everyday household use, but it also supports optional cloud-based persistence through PostgreSQL/Supabase.

The app combines a simple user interface with a small database layer, optional AI insights, and report generation features.

## Project Goals

The main goals of this project are to:

- Let users record expenses easily
- Keep spending organized by date, category, and person
- Generate summaries and reports for shared households
- Support local use with SQLite and cloud use with PostgreSQL/Supabase
- Offer optional AI-generated insights for expense reports

## Architecture Overview

The project is intentionally lightweight and centered around a single main entry point:

- app.py: contains the UI, app logic, database access, and report generation
- requirements.txt: lists the Python dependencies
- .env / .env.example: local environment configuration
- README.md: user-facing setup and usage guide
- tests/: regression tests for database-related behavior

## Core Components

### 1. Streamlit UI

The app uses Streamlit for the front end. Streamlit makes it simple to build a dashboard-style interface with forms, filters, charts, and tables.

The main UI responsibilities are:

- login screen
- expense entry form
- report filtering controls
- summary tables and chart display
- export and AI-related actions

### 2. Database Layer

The application supports two database modes:

- SQLite for local development and simple single-machine use
- PostgreSQL/Supabase for persistent cloud deployment

The database layer is abstracted through a small set of helper functions so the rest of the app does not need to care which backend is in use.

### 3. Expense Data Model

Each expense record contains:

- id: unique identifier
- transaction_date: the date of the expense
- category: the expense category
- expense_user: the person the expense belongs to
- amount: numeric value of the expense
- note: optional description
- created_at: timestamp of creation

### 4. Report Generation

The application builds report data from stored expense records by:

- filtering between start and end dates
- filtering by selected categories
- filtering by selected users
- summarizing totals by category and user
- creating a simple settlement-style summary

### 5. Optional AI Insights

The app can optionally use OpenAI to generate insights about the selected report. This is not required for basic app usage.

The AI feature uses only a limited report snapshot rather than the full database, which helps keep the approach safer and simpler.

## Code Concepts and Logic

### Entry Point

The main file is app.py. When the app starts, it:

1. loads environment variables
2. configures Streamlit page settings
3. sets up constants such as categories, users, and password
4. initializes the database connection
5. renders the login screen if needed
6. loads the main app interface

### Authentication Flow

The app uses a simple password-based login to protect access:

- the default password is stored in the code as ADMIN_PASSWORD
- users enter the password in a Streamlit form
- if the password matches, the session is marked as logged in

This is a lightweight approach suitable for a personal or small household app.

### Database Connection Logic

The app uses a helper function to decide whether to use PostgreSQL or SQLite:

- If DATABASE_URL is present, the app attempts to connect to PostgreSQL/Supabase
- If that connection fails, it falls back to SQLite
- Otherwise it uses SQLite directly

This makes the app flexible and resilient for local and hosted environments.

### Query Building

Expense queries are built dynamically depending on the active database type.

Key ideas:

- SQLite uses question-mark placeholders
- PostgreSQL uses percent-style placeholders
- the app translates the query placeholders so the same logic can work across both systems

### Data Handling

The app uses pandas for working with tabular data and report generation. It loads SQL results into DataFrames, which makes filtering, grouping, and summarizing much easier.

## File Structure

```text
household_expense_tracker/
├── app.py
├── README.md
├── requirements.txt
├── .env.example
├── .env
├── tests/
│   └── test_db_config.py
└── PROJECT_DOCUMENTATION.md
```

## Main Functions

### Database helpers

- get_database_url(): reads the database connection string from environment variables or Streamlit secrets
- get_database_kind(): decides whether the current setup is PostgreSQL or SQLite
- get_connection(): creates and returns the appropriate database connection

### Expense operations

- add_expense(): inserts a new expense record
- update_expense(): edits an existing expense
- delete_expense(): removes an expense record
- flush_expenses(): clears expenses within a date range

### Reporting helpers

- build_expense_query(): constructs the SQL query used to retrieve filtered expenses
- load_expenses(): retrieves expense rows for the selected date range and filters
- load_latest_expenses(): loads recent expense records
- get_default_report_start(): finds the earliest stored expense date
- get_default_report_end(): finds the latest stored expense date

### AI helpers

- report_context(): builds a compact text summary for AI analysis
- get_api_key(): retrieves the OpenAI API key from environment or secrets

## Deployment Considerations

### Local deployment

The app runs locally with SQLite and does not require a database server.

### Cloud deployment

For hosting services such as Streamlit Cloud, the app can be configured to use a hosted PostgreSQL database via DATABASE_URL. This allows data to persist beyond the lifecycle of a container or local machine.

## Testing Strategy

The project includes basic regression tests focused on database behavior:

- database type detection
- PostgreSQL placeholder compatibility
- connection fallback behavior

These tests help prevent regressions when changing how database queries are handled.

## Developer Guide

### Environment setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment example file and adjust values if needed:

```bash
cp .env.example .env
```

### Running the app locally

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

### Running tests

```bash
python -m unittest -q tests.test_db_config
```

### Suggested workflow for changes

- Make small, focused changes
- Keep database logic consistent across SQLite and PostgreSQL
- Test database behavior after touching query logic
- Update the documentation if user-facing behavior changes
- Prefer clear variable names and simple helpers over overly clever abstractions

### Common development notes

- The app is intentionally single-file for simplicity, so changes to the UI and database logic often happen in the same place
- If you change SQL queries, verify both SQLite and PostgreSQL behavior
- If you add new categories or report features, update the documentation and user-facing labels

## Design Notes

This project favors simplicity over complex architecture. The app is intentionally built as a single-file Streamlit application so it is easy to run, modify, and understand.

That design makes it a good fit for:

- small household finance tracking
- personal budgeting tools
- lightweight shared expense management

## Detailed Implementation Notes for app.py

The main implementation file is app.py. It is written as a single Python script that combines the user interface, database access, report generation, and optional AI assistance in one place. This structure keeps the project simple and easy to understand while still supporting real-world usage.

### 1. File purpose and coding style

The file follows a lightweight, functional style. It uses:

- standard Python modules such as os, sqlite3, pathlib, and datetime
- Streamlit for the web application interface
- pandas for table handling and report summarization
- dotenv for environment-based configuration
- OpenAI for optional AI-powered report analysis

The code is organized around clearly named functions, which makes it easier to maintain and extend.

### 2. Initial setup and configuration

At the top of the file, the application:

- loads environment variables from .env
- sets page configuration for Streamlit
- defines the list of categories and users
- sets the default admin password
- defines the database path and SQL table creation statements

These definitions form the foundation of the app and are used throughout the script.

### 3. Database configuration logic

The app is designed to work in two environments:

- local mode using SQLite
- hosted mode using PostgreSQL/Supabase

The function get_database_url() looks for a connection string from environment variables or Streamlit secrets. The function get_database_kind() then decides whether the app should use PostgreSQL or SQLite.

This logic allows the same codebase to function both locally and in deployment environments without needing major changes.

### 4. Database abstraction and compatibility layer

A special adapter class, PostgresConnectionAdapter, is used to make PostgreSQL work smoothly with the same function calls used for SQLite.

Its main purpose is to:

- wrap a PostgreSQL connection object
- translate SQLite-style ? placeholders into PostgreSQL-style %s placeholders
- expose execute(), commit(), and close() methods that behave like a normal database connection

This makes the rest of the application easier to write and maintain because the CRUD operations do not need to be rewritten for each database type.

### 5. Connection handling

The get_connection() function is the central database access point. It:

- checks whether PostgreSQL is configured
- tries to connect to PostgreSQL if available
- creates the necessary table if it does not exist
- falls back to SQLite if the PostgreSQL connection fails
- creates the local SQLite database file if needed

This fallback behavior increases reliability and makes the app more user-friendly.

### 6. Authentication logic

The authenticate_app() function implements a basic login flow.

It works by:

- checking whether the user is already logged in through Streamlit session state
- showing a login form if not logged in
- validating the entered password against the stored admin password
- allowing the user to access the main app only after successful authentication

This is a simple but effective approach for a household or small-group application.

### 7. Expense management functions

The script contains several functions for data manipulation:

- add_expense(): inserts a new expense record
- update_expense(): modifies an existing record
- delete_expense(): removes a selected record
- flush_expenses(): deletes records inside a selected date range

Each of these functions obtains a connection, executes the relevant SQL command, and commits the changes. The logic is simple and direct, which fits the purpose of the project.

### 8. Report query construction

The build_expense_query() function dynamically constructs SQL queries based on the selected filters.

It creates a query that:

- selects expenses between a chosen start and end date
- filters by category
- filters by user
- sorts results in descending date order

This function also builds the correct parameter placeholders for SQLite or PostgreSQL, depending on the active database backend.

### 9. Data loading and summarization

The functions load_expenses() and load_latest_expenses() retrieve expense records from the database and convert them into pandas DataFrames.

This enables the application to:

- display transaction data in table form
- calculate totals and averages
- group expenses by category or user
- create charts and summaries for the report view

The report logic is therefore data-driven and easy to extend.

### 10. AI integration design

The application includes optional AI support through OpenAI.

The functions involved are:

- get_api_key(): reads the API key from environment variables or Streamlit secrets
- report_context(): prepares a compact summary of the filtered report
- agent_context(): combines the report summary with recent transactions for context
- ask_agent(): sends the report context and a user question to the OpenAI model

This design ensures that the AI only receives a focused summary rather than the full database, which keeps the feature manageable and safer.

### 11. Main application workflow

The main() function represents the main execution flow of the app. It performs the following actions:

1. loads environment variables
2. initializes the database connection
3. checks the login state
4. shows the sidebar forms for adding expenses and configuring report filters
5. loads the selected expense data
6. displays summary metrics and report tabs
7. allows users to edit or delete records
8. offers AI-based insights for the selected report

This function ties together all the smaller helper functions into a complete user experience.

### 12. Definition summary

In project-work terms, app.py can be described as a single-file full-stack prototype for household expense management. The script includes:

- front-end interface logic through Streamlit
- backend data handling through SQLite/PostgreSQL operations
- reporting and analytics logic through pandas
- optional AI assistance through OpenAI APIs
- simple authentication and session handling

This makes the project a practical example of a lightweight web application built with Python and Streamlit.

## Future Improvements

Possible enhancements include:

- a proper user authentication system
- multi-user role management
- richer charts and dashboards
- monthly expense insights
- recurring expense support
- improved backup and export options
