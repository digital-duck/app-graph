# Expense App

A full-stack expense tracker built with a Vue.js frontend and a FastAPI backend persisted to SQLite. The app lets users add, view, filter, and delete expenses, and see a running total plus a per-category breakdown — the first app-graph app exercising SQL `GROUP BY` aggregation (`report_aggregator`/`SummaryView`) and multi-parameter filtering (category + date range), neither of which `apps/todo/` needed. It is designed as a reference implementation of an `integrated` app-graph blueprint, assembling independently deployable backend and frontend software components into one working product.

## Status

See [apps/README.md](../README.md)'s `expense` row for build/test history. This README's build/run instructions reflect the 2026-08-14 framework refactor (`docs/DEV/BUILD/refactoring-plan-v1.md`) — app-scoped `settings.yaml`, de-prefixed backend node ids (`data_schema`, `orm_model`), and the `app/config.py`-based CORS wiring — which has not yet been verified against a real `appgraph build` for this app.

## Architecture

The Vue.js frontend (port **5174**) communicates with the FastAPI backend (port **8001**) over REST, with CORS enabled on the backend; see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions. Ports are defined once in [blueprint/settings.yaml](blueprint/settings.yaml) and referenced from every `*.graph.yaml` as `${{ settings.KEY }}`.

## Running the full system

**1. Build** — generate and install both components from the graph:

```bash
appgraph build apps/expense/blueprint/main.graph.yaml \
    --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/expense/backend`/`apps/expense/frontend` in place, add `--output-dir`:

```bash
appgraph build apps/expense/blueprint/main.graph.yaml \
    --output-dir apps/expense-v2 \
    --llm claude_cli \
    2>&1 | tee "build-$(date +%Y-%m-%d-%H-%M-%S).log"
```

The `tee` keeps the console output live while also capturing it to a
timestamped file — useful since a failed build's real
error (e.g. a `pytest`/SQLAlchemy traceback) often scrolls past the terminal
buffer before you can read it, and the run's own log (path printed as `[build] log:`
at the end) captures the recipe trace but not the raw stdout.

Each component is then written to `{output-dir}/{component_id}/` — i.e.
`apps/expense-v2/backend/` and `apps/expense-v2/frontend/` for the command above —
leaving the existing `apps/expense/backend`/`apps/expense/frontend` untouched.

Run `appgraph build -h` for all build options (`--max-llm-calls`, `--max-test-attempts`, `--no-cache`, ...); `appgraph validate expense/blueprint/main.graph.yaml` checks the blueprints first.

**Building to a redirected `--output-dir` location**: the build seeds each component's pre-authored
scaffold (`tests/`, and for the frontend also `package.json`/`package-lock.json`/`vite.config.ts`/
`tsconfig.json`/`index.html`/`.env`) into the new location automatically, but **deliberately does
not copy `node_modules/`** (copying a dependency tree risks silent drift from `package.json` —
reinstalling is safer). If the frontend build halts with `vitest: not found` (exit 127), run
`npm install` by hand in the redirected frontend directory once, then re-run the same
`appgraph build ...` command — it picks up where it left off (the backend and any
already-passing frontend nodes are cached, so only the remaining work re-runs).

**If a rebuild is needed after editing the blueprint** (e.g. iterating on a spec fix), clear that
component's cache and any stale runtime SQLite files first, so the fix is guaranteed to actually
regenerate rather than serve a stale cache hit:

```bash
rm -rf apps/expense-v2/backend/.agr_cache apps/expense-v2/frontend/.agr_cache
rm -f apps/expense-v2/backend/*.db
```

**2. Start the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

**3. Start the frontend** (separate terminal):

```bash
cd frontend
npm run dev
```

The app is then available at <http://localhost:5174>.

## Applications

- **add_expense** — record a new expense with amount, category, date, and description
- **list_expenses** — retrieve and display all current expenses
- **filter_by_category** — narrow the list and summary to a single category
- **delete_expense** — permanently remove an expense
- **view_summary** — see total spending and a per-category breakdown for the current filter
- **manage_expenses** — full lifecycle management: add, view, filter, and delete expenses, with the summary kept in sync at every step
