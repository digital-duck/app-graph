# Todo App

A full-stack todo application built with a Vue.js frontend and a FastAPI backend backed by SQLite. It supports the full lifecycle of todo management: creating tasks, listing them, toggling completion status, and deleting items — suitable for personal productivity, team task tracking, or as a reference integration for the graph-code SPL workflow system.

## Status

| Application | Result | Duration |
|---|---|---|
| create_todo | PASS | 10.7s |
| list_todos | PASS | 19.0s |
| toggle_todo | PASS | 13.3s |
| delete_todo | PASS | 22.5s |

## Architecture

The Vue.js frontend (`:5173`) communicates with the FastAPI backend (`:8000`) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's setup, run, and test instructions.

## Running the Full System

Build the integrated system first, then start the backend and frontend:

```bash
# Build (see docs/DEV/BUILD/README.md §12.1 and §12.4 for options)
spl3 run spl/build_app.spl

# Start the backend (from backend/)
cd backend && uvicorn main:app --reload --port 8000

# Start the frontend (from frontend/, in a separate terminal)
cd frontend && npm run dev
```

The app will be available at `http://localhost:5173`.

## Applications

- **create_todo** — Add a new todo item with a title to the list.
- **list_todos** — Retrieve and display all current todo items.
- **toggle_todo** — Mark a todo item as complete or incomplete.
- **delete_todo** — Permanently remove a todo item from the list.
- **manage_todo_list** — Full end-to-end lifecycle management of the todo list (create, list, toggle, delete).