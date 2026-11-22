Based on the specification and everything I can gather, I'll write the README now.

# Todo App

A full-stack todo application built with a Vue.js frontend and FastAPI backend, persisting data in SQLite. It supports the complete lifecycle of todo items: creating, listing, toggling completion, and deleting — assembled as an integrated system from independently deployable frontend and backend components.

## Status

| Application | Result | Duration |
|---|---|---|
| create\_todo | PASS | 11.1 s |
| list\_todos | PASS | 13.1 s |
| toggle\_todo | PASS | 10.8 s |
| delete\_todo | PASS | 12.2 s |

## Architecture

The Vue.js frontend (`:5173`) communicates with the FastAPI backend (`:8000`) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

Build the system first (see [docs/DEV/BUILD/README.md §12.1](../../docs/DEV/BUILD/README.md) for full options):

```bash
spl3 run spl/build_app.spl apps/todo/blueprint/main.graph.yaml
```

Then start the backend and frontend together:

```bash
# terminal 1 — backend
cd backend && uvicorn main:app --reload

# terminal 2 — frontend
cd frontend && npm run dev
```

The app is available at http://localhost:5173.

## Applications

- **create\_todo** — add a new todo item with a title
- **list\_todos** — retrieve all todo items with their completion status
- **toggle\_todo** — mark a todo item complete or incomplete
- **delete\_todo** — remove a todo item permanently
- **manage\_todo\_list** — end-to-end workflow combining create, list, toggle, and delete operations