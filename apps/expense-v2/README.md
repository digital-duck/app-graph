# Expense Tracker

A full-stack expense-tracking application that lets users add expenses with an amount, category, and description; browse and filter the full expense list by category; delete individual entries; and view a summary of total spending broken down by category. The system is assembled from a REST backend (FastAPI + SQLite) and a reactive single-page frontend (React + Vite).

## Status

| Application | Result | Time |
|---|---|---|
| add_expense | PASS | 11.4s |
| list_expenses | PASS | 16.6s |
| filter_by_category | PASS | 18.9s |
| delete_expense | PASS | 10.1s |
| view_summary | PASS | 18.8s |

## Architecture

The frontend (React + Vite, port 5174) calls the backend (FastAPI, port 8001) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for component-specific setup, run, and test instructions.

## Running the full system

**Build** the application (generates backend and frontend source):

```bash
appgraph build apps/expense/blueprint/main.graph.yaml --llm claude_cli
```

Then start each component in its own terminal — refer to each component's README for the exact commands:

- **Backend** — see [backend/README.md](backend/README.md)
- **Frontend** — see [frontend/README.md](frontend/README.md)

Once both are running, open [http://localhost:5174](http://localhost:5174) in your browser.

## Applications

| Application | Description |
|---|---|
| add_expense | Add a new expense entry with amount, category, and description. |
| list_expenses | Browse the full list of expense entries. |
| filter_by_category | Filter the expense list to show only entries matching a selected category. |
| delete_expense | Delete an individual expense entry. |
| view_summary | View a summary of total spending broken down by category. |
