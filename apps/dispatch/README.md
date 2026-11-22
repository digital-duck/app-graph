# Dispatch App

An incident management core built as a single FastAPI backend persisted to SQLite — no frontend component. It manages three reference-data resources (priorities, severities, incident types) and incidents themselves, which carry three foreign-key relationships to that reference data plus status-based filtering (Active/Stable/Closed). It is the first graph-code app to stress-test the schema on a wider/deeper `form.nodes` DAG than a single-entity CRUD app needs — 4 related entities, 3 FK-existence checks before insert, and a slug-generation primitive (`python-slugify`) none of the other apps use.

## Status

See [apps/README.md](../README.md)'s `dispatch` row for build/test history. This README's build/run instructions reflect the 2026-08-14 framework refactor (`docs/DEV/BUILD/refactoring-plan-v1.md`) — app-scoped `settings.yaml`, de-prefixed backend node ids (`data_schema`, `orm_model`) — which has not yet been verified against a real `spl3` build for this app.

## Architecture

A single FastAPI backend (port **8006**) with no frontend — CORS is left open (`allow_origins=["*"]`) since there's no fixed frontend origin to allow-list. See [backend/README.md](backend/README.md) for the backend's own setup, run, and test instructions. The port is defined once in [blueprint/settings.yaml](blueprint/settings.yaml) and referenced from every `*.graph.yaml` as `${{ settings.KEY }}`.

## Running the full system

**1. Build** — generate and install the backend from the graph:

```bash
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/dispatch/blueprint/main.graph.yaml \
    --llm claude_cli
```

To generate a fresh copy of the app into a new directory instead of overwriting
`apps/dispatch/backend` in place, add `-p output_dir=...`:

```bash
mkdir -p logs/console
spl3 run spl/build_app.spl \
    --tools spl/tools.py \
    -p system_yaml=apps/dispatch/blueprint/main.graph.yaml \
    -p output_dir=apps/dispatch-v2 \
    --llm claude_cli \
    2>&1 | tee "logs/console/build_app-$(date +%Y-%m-%d-%H-%M-%S).md"
```

The `tee` keeps the console output live while also capturing it to a
timestamped file under `logs/console/` — useful since a failed build's real
error (e.g. a `pytest`/SQLAlchemy traceback) often scrolls past the terminal
buffer before you can read it, and `spl3`'s own log (path printed as `Log:`
at the end of the run) captures the workflow trace but not the raw stdout.

The component is then written to `{output_dir}/backend/` — i.e.
`apps/dispatch-v2/backend/` for the command above — leaving the existing
`apps/dispatch/backend` untouched.

See [docs/DEV/BUILD/README.md](../../docs/DEV/BUILD/README.md) §12.1 for full build options and §12.4 for `--output_dir` usage.

**If a rebuild is needed after editing the blueprint** (e.g. iterating on a spec fix), clear the
cache and any stale runtime SQLite files first, so the fix is guaranteed to actually regenerate
rather than serve a stale cache hit:

```bash
rm -rf apps/dispatch-v2/backend/.spl_cache
rm -f apps/dispatch-v2/backend/*.db
```

**2. Start the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8006
```

The API is then available at <http://localhost:8006>, with OpenAPI docs at `/docs`.

## Applications

- **manage_priorities** — full CRUD lifecycle on incident priority reference data
- **manage_severities** — full CRUD lifecycle on incident severity reference data
- **manage_incident_types** — full CRUD lifecycle on incident type reference data, with auto-slugified names
- **browse_incidents** — list all incidents, or filter by status
- **create_incident** — open a new incident, referencing an existing type/priority/severity
- **update_incident** — move an incident through its lifecycle (Active → Stable → Closed)
- **manage_incidents** — full incident lifecycle: set up reference data, then open and manage an incident end to end
