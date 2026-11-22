domain: app/mealie
domain_type: integrated
description: >
  Mealie is a self-hosted recipe manager and meal planner with a REST API
  backend and a Vue.js frontend. It allows users to browse, create, update,
  and delete recipes; filter by organizer (category or tag); and manage
  organizers.

applications:
  - id: backend
    path: apps/mealie/blueprint/backend.graph.yaml
    readme: apps/mealie/backend/README.md
  - id: frontend
    path: apps/mealie/blueprint/frontend.graph.yaml
    readme: apps/mealie/frontend/README.md

```

# Mealie

Mealie is a self-hosted recipe manager and meal planner with a REST API backend and a Vue.js frontend. It allows users to browse, create, update, and delete recipes; filter recipes by organizer (category or tag); and manage organizers through a clean, responsive interface.

## Status

| Acceptance Test     | Result | Duration |
|---------------------|--------|----------|
| browse_recipes      | PASS   | 22.2s    |
| filter_by_organizer | PASS   | 31.6s    |
| view_recipe         | PASS   | 11.3s    |
| create_recipe       | PASS   | 9.6s     |
| update_recipe       | FAIL   | —        |
| delete_recipe       | PASS   | 12.6s    |
| manage_organizers   | PASS   | 12.3s    |

**update_recipe failure:**
```
AssertionError: Expected 201 on create, got 422: {'detail': [{'type': 'model_attributes_type',
'loc': ['body'], 'msg': 'Input should be a valid dictionary or object to extract fields from',
'input': 'Acceptance Test Recipe Original'}]}
```

## Architecture

The frontend (port 5176) communicates with the backend (port 8003) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for component-specific setup, run, and test instructions.

## Running the Full System

Build the app first, then start both services:

```bash
# Build
spl3 run spl/build_app.spl apps/mealie/blueprint/main.graph.yaml

# Start backend (port 8003)
cd apps/mealie/backend
uvicorn app.main:app --port 8003 --reload

# Start frontend (port 5176)
cd apps/mealie/frontend
npm run dev
```

## Applications

- **backend** — FastAPI REST API serving recipe and organizer data on port 8003. See [backend/README.md](backend/README.md).
- **frontend** — Vue.js single-page application on port 5176. See [frontend/README.md](frontend/README.md).