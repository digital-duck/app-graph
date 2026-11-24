# Expense Tracker

A personal expense management application built with a Vue.js frontend and a FastAPI backend backed by SQLite. Users can log expenses with categories and amounts, browse and filter their history, and view spending summaries — all through a lightweight, self-hosted web UI that requires no external services.

## Status

| Application | Result | Duration |
|---|---|---|
| add_expense | PASS | 11.3 s |
| list_expenses | PASS | 17.2 s |
| filter_by_category | PASS | 19.1 s |
| delete_expense | PASS | 12.7 s |
| view_summary | PASS | 23.5 s |

## Architecture

The Vue.js frontend (`:5174`) communicates with the FastAPI backend (`:8001`) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for component-specific setup, run, and test instructions.

## Running the full system

**Build** (generates all component source from the blueprints):

```bash
appgraph build apps/expense/blueprint/main.graph.yaml --llm claude_cli
```

**Start the backend** (from `apps/expense/backend/`):

```bash
cd apps/expense/backend
# see backend/README.md for exact command
```

**Start the frontend** (from `apps/expense/frontend/`):

```bash
cd apps/expense/frontend
# see frontend/README.md for exact command
```

Open `http://localhost:5174` once both processes are running.

## Applications

- **add_expense** — record a new expense with description, amount, and category
- **list_expenses** — browse the full expense history in reverse-chronological order
- **filter_by_category** — narrow the expense list to a single category
- **delete_expense** — remove an expense record permanently
- **view_summary** — see total spending broken down by category
