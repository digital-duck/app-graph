# FastAPI App

A FastAPI + SQLAlchemy 2.0 Item CRUD API — a single FastAPI backend persisted to SQLite, no frontend component. It manages one entity, Item, with an Integer autoincrement primary key and a DB-level unique constraint on `name`, exposed via a dual lookup axis (by id and by name) and 409-on-conflict checks on both create and update. This is the smallest of the ported reference apps, migrated from the `example-fastapi-sqlachemy-pytest` (Tim Hughes) example.

## Status

See [apps/README.md](../README.md)'s `fastapi` row for build/test history. This README's build/run instructions reflect the 2026-08-14 framework refactor (`docs/DEV/BUILD/refactoring-plan-v1.md`) — app-scoped `settings.yaml`, de-prefixed backend node ids (`item_schemas`→`data_schema`, `orm_models`→`orm_model`) — which has not yet been verified against a real `spl3` build for this app.

## Architecture

A single FastAPI backend (port **8005**) with no frontend — CORS is left open (`allow_origins=["*"]`) since there's no fixed frontend origin to allow-list. See [backend/README.md](backend/README.md) for the backend's own setup, run, and test instructions. The port is defined once in [blueprint/settings.yaml](blueprint/settings.yaml) and referenced from every `*.graph.yaml` as `${{ settings.KEY }}`.

## Running the full system

**1. Build** — generate and install the backend from the graph:

```bash
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/fastapi/blueprint/main.graph.yaml \
    --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/fastapi/backend` in place, add `-p output_dir=...`:

```bash
mkdir -p logs/console
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/fastapi/blueprint/main.graph.yaml \
    -p output_dir=apps/fastapi-v2 \
    --llm claude_cli \
    2>&1 | tee "logs/console/build_app-$(date +%Y-%m-%d-%H-%M-%S).md"
```

The `tee` keeps the console output live while also capturing it to a
timestamped file under `logs/console/` — useful since a failed build's real
error (e.g. a `pytest`/SQLAlchemy traceback) often scrolls past the terminal
buffer before you can read it, and `spl3`'s own log (path printed as `Log:`
at the end of the run) captures the workflow trace but not the raw stdout.

The component is then written to `{output_dir}/backend/` — i.e.
`apps/fastapi-v2/backend/` for the command above — leaving the existing
`apps/fastapi/backend` untouched.

See [docs/DEV/BUILD/README.md](../../docs/DEV/BUILD/README.md) §12.1 for full build options and §12.4 for `--output_dir` usage.

**If a rebuild is needed after editing the blueprint** (e.g. iterating on a spec fix), clear the
cache and any stale runtime SQLite files first, so the fix is guaranteed to actually regenerate
rather than serve a stale cache hit:

```bash
rm -rf apps/fastapi-v2/backend/.spl_cache
rm -f apps/fastapi-v2/backend/*.db
```

**2. Start the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8005
```

The API is then available at <http://localhost:8005>, with OpenAPI docs at `/docs`.

## Applications

- **user_creates_item** — `POST /api/v1/items/` creates a named item; 409 on duplicate name
- **user_lists_items** — `GET /api/v1/items/` returns a paginated list of items
- **user_reads_item_by_id** — `GET /api/v1/items/{item_id}` returns a single item by integer id
- **user_reads_item_by_name** — `GET /api/v1/items/by-name/{name}` returns a single item by unique name
- **user_updates_item** — `PUT /api/v1/items/{item_id}` updates name and/or description
- **user_deletes_item** — `DELETE /api/v1/items/{item_id}` removes an item
- **manage_items** — full item lifecycle: create → list → get by name → update → delete
