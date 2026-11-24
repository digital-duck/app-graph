# FastAPI Item CRUD API

A backend REST API for managing items with full CRUD operations. Each item has an integer primary key and a unique name, and can be looked up either by numeric `id` or by `name` — both routes are first-class. The API enforces the unique-name constraint at the database layer and surfaces clean 404 / 409 responses for missing or duplicate items. There is no frontend; all interaction is through the HTTP API.

## Status

| Test | Result | Duration |
|---|---|---|
| user_creates_item | PASS | 9.0s |
| user_lists_items | PASS | 16.1s |
| user_reads_item_by_id | PASS | 10.3s |
| user_reads_item_by_name | PASS | 11.4s |
| user_updates_item | PASS | 11.1s |
| user_deletes_item | PASS | 8.8s |

## Architecture

Single FastAPI backend running at `:8005`, no frontend — see [backend/README.md](backend/README.md) for setup, run, and test instructions.

## Running the full system

**Build** (generate and install the backend from the blueprint):

```bash
appgraph build apps/fastapi/blueprint/main.graph.yaml
```

**Start the backend:**

```bash
cd apps/fastapi/backend
uvicorn app.main:app --port 8005
```

## Applications

- **backend** — FastAPI service at `:8005`; Item CRUD with integer PK, unique-name constraint, and dual lookup by `id` or `name`