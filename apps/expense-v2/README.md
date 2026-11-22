Let me read the relevant files to understand this system.

**Tool calls: 1**
- Read: apps/expense/blueprint/main.graph.yaml

**Tool calls: 2**
- Read: apps/expense/blueprint/backend.graph.yaml
- Read: apps/expense/blueprint/frontend.graph.yaml

**Tool results: 1**
```
domain: apps/expense
domain_type: integrated
name: Expense Tracker
description: >
  A full-stack expense-tracking application. Users can add expenses with amount,
  category, and description; browse and filter the expense list by category; delete
  individual entries; and view a summary of totals broken down by category.
  The system is assembled from a REST backend (FastAPI + SQLite) and a reactive
  frontend (React + Vite).

applications:
  - name: add_expense
    description: Add a new expense entry with amount, category, and description.
  - name: list_expenses
    description: Browse the full list of expense entries.
  - name: filter_by_category
    description: Filter the expense list to show only entries matching a selected category.
  - name: delete_expense
    description: Delete an individual expense entry.
  - name: view_summary
    description: View a summary of total spending broken down by category.

imports:
  - path: backend.graph.yaml
    as: backend
  - path: frontend.graph.yaml
    as: frontend
```

**Tool results: 2**
```
domain: apps/expense/backend
domain_type: software
name: Expense Backend
description: >
  FastAPI backend for the Expense Tracker. Exposes a REST API on port 8001 for
  creating, listing, filtering, and deleting expenses, and serving a category-level
  spending summary. Persistence is handled by SQLite via SQLAlchemy.

target_languages:
  - python

form:
  primitives:
    - name: expense_record
      description: >
        A single expense entry stored in the database: amount (float), category
        (string), description (string), and auto-generated id and created_at timestamp.

  nodes:
    - name: expense_store
      description: >
        SQLAlchemy model + session factory backed by a SQLite file. Provides the
        persistence layer for expense_record objects.
      composed_of:
        - expense_record

    - name: expense_api
      description: >
        FastAPI application (CORS enabled, port 8001). Implements endpoints:
        POST /expenses, GET /expenses, GET /expenses?category=<cat>,
        DELETE /expenses/{id}, GET /expenses/summary.
      composed_of:
        - expense_store

function:
  nodes:
    - name: add_expense
      description: >
        POST /expenses — accepts {amount, category, description}, persists a new
        expense_record, returns the created record as JSON.
      depends_on:
        - expense_api

    - name: list_expenses
      description: >
        GET /expenses — returns all expense records as a JSON array, ordered by
        created_at descending.
      depends_on:
        - expense_api

    - name: filter_expenses_by_category
      description: >
        GET /expenses?category=<cat> — returns expense records filtered to the given
        category, ordered by created_at descending.
      depends_on:
        - expense_api

    - name: delete_expense
      description: >
        DELETE /expenses/{id} — removes the expense record with the given id; returns
        404 if not found.
      depends_on:
        - expense_api

    - name: get_summary
      description: >
        GET /expenses/summary — returns a JSON object mapping each category to the
        total amount spent in that category.
      depends_on:
        - expense_api
```

```
domain: apps/expense/frontend
domain_type: software
name: Expense Frontend
description: >
  React + Vite frontend for the Expense Tracker, served on port 5174. Provides a
  single-page interface for adding expenses, browsing and filtering the expense list
  by category, deleting entries, and viewing a category-level spending summary.

target_languages:
  - typescript

form:
  primitives:
    - name: expense_item
      description: >
        Client-side representation of a single expense: id, amount, category,
        description, created_at.

  nodes:
    - name: expense_store
      description: >
        React state (useState/useEffect) holding the current list of expense_item
        objects and the active category filter.
      composed_of:
        - expense_item

    - name: expense_api_client
      description: >
        Fetch-based API client. Calls the backend at http://localhost:8001 for all
        CRUD and summary operations.
      composed_of:
        - expense_item

    - name: add_expense_form
      description: >
        Controlled form component for submitting a new expense (amount, category,
        description).
      composed_of:
        - expense_store
        - expense_api_client

    - name: expense_list
      description: >
        Renders the list of expense_item objects, with per-item delete buttons.
      composed_of:
        - expense_store
        - expense_api_client

    - name: category_filter
      description: >
        Dropdown or button group that sets the active category filter and triggers a
        filtered fetch.
      composed_of:
        - expense_store
        - expense_api_client

    - name: summary_view
      description: >
        Displays the category-level spending totals returned by the backend summary
        endpoint.
      composed_of:
        - expense_api_client

    - name: expense_app
      description: >
        Root application component. Composes add_expense_form, expense_list,
        category_filter, and summary_view into the full single-page layout.
      composed_of:
        - add_expense_form
        - expense_list
        - category_filter
        - summary_view

function:
  nodes:
    - name: add_expense
      description: >
        User fills the add_expense_form and submits; the frontend POSTs to
        /expenses and refreshes the expense_list.
      depends_on:
        - add_expense_form

    - name: list_expenses
      description: >
        On load and after mutations, the frontend GETs /expenses and renders the
        result in expense_list.
      depends_on:
        - expense_list

    - name: filter_by_category
      description: >
        User selects a category in category_filter; the frontend GETs
        /expenses?category=<cat> and updates expense_list.
      depends_on:
        - category_filter

    - name: delete_expense
      description: >
        User clicks delete on an expense_item; the frontend DELETEs /expenses/{id}
        and removes the item from expense_list.
      depends_on:
        - expense_list

    - name: view_summary
      description: >
        User navigates to the summary panel; the frontend GETs /expenses/summary and
        renders totals in summary_view.
      depends_on:
        - summary_view
```

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
spl3 run spl/build_app.spl apps/expense/blueprint/main.graph.yaml
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