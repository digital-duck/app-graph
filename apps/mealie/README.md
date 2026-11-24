# Mealie

Mealie is a self-hosted recipe manager: a Vue 3 / TypeScript frontend backed by a FastAPI + SQLite
REST API. Users browse a paginated recipe grid, view full recipe detail (ingredients, steps,
notes), create/update/delete recipes, and organize them with many-to-many tags and categories. It
is app-graph's largest reference app — first with pagination and a many-to-many
relationship.

## Status

Results from the most recent `appgraph build` integration run (2026-08-15): backend
and frontend both built clean (all nodes cache-hit, 53/53 pytest and 39/39 vitest respectively —
see [backend/README.md](backend/README.md)/[frontend/README.md](frontend/README.md)). System
acceptance tests:

| Application | Result |
|---|---|
| browse_recipes | FAIL |
| filter_by_organizer | FAIL |
| view_recipe | PASS |
| create_recipe | PASS |
| update_recipe | FAIL |
| delete_recipe | PASS |
| manage_organizers | PASS |

The three failures are generated-acceptance-test defects, not backend bugs (the backend's own 53
pytest tests assert the correct contract) — the same "fabricated acceptance-test" class already
documented for `dispatch`/`fastapi`/`kanban` in [`apps/README.md`](../README.md):

- **browse_recipes** — the generated test's "nonsense search returns 0 items" assertion found 1
  leftover recipe from an earlier test run in this same session (`create_recipe`'s fixture data);
  a known framework gap — the system acceptance run doesn't reset `mealie.db` between runs.
- **filter_by_organizer** — the generated test asserted `POST /tags` returns 200; the backend
  correctly returns 201 per the contract (creation endpoints in this API return 201, not 200).
- **update_recipe** — the generated test PUT a body missing the required `slug` field, so the
  backend correctly rejected it with 422 before ever reaching the "unknown slug" 404 path the test
  meant to exercise.

## Architecture

The frontend (`:5176`, Vue 3 + Vite) calls the backend (`:8003`, FastAPI) over REST with CORS
enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md)
for component-specific setup, run, and test instructions. Ports are defined once in
[blueprint/settings.yaml](blueprint/settings.yaml) and referenced from every `*.graph.yaml` as
`${{ settings.KEY }}`.

## Running the full system

**1. Build** — generate and install both components from the graph:

```bash
appgraph build apps/mealie/blueprint/main.graph.yaml \
    --llm claude_cli
```

**2. Start the backend:**

```bash
cd apps/mealie/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8003
```

**3. Start the frontend** (separate terminal):

```bash
cd apps/mealie/frontend
npm install
npm run dev
```

The app is then available at <http://localhost:5176>.

## How to verify

```bash
cd apps/mealie/backend && pytest tests/        # expect 53 passed
cd apps/mealie/frontend && npm test            # expect 39 passed
```

For a live end-to-end check, start both servers as above, then exercise the API directly:

```bash
curl http://localhost:8003/docs      # OpenAPI schema
curl http://localhost:8003/recipes   # paginated recipe list
```

## Applications

- **browse_recipes** — see all recipes in a paginated grid on page load, with keyword search
- **filter_by_organizer** — list recipes belonging to a specific tag or category
- **view_recipe** — view full detail of a single recipe (ingredients, steps, notes)
- **create_recipe** — submit a new recipe with name, description, tags, and category
- **update_recipe** — edit an existing recipe's fields, including nested sub-entities
- **delete_recipe** — permanently remove a recipe by slug
- **manage_organizers** — create, rename, and delete tags/categories used to organize recipes
