# Todo App

A full-stack task-management application built with a Vue 3 frontend and a FastAPI backend backed by SQLite. The app lets users maintain personal to-do lists — creating tasks, viewing them, marking them complete or incomplete, deleting them, and managing the overall list — through a clean browser interface. The system is code-generated from graph blueprints using the SPL build pipeline.

## Architecture

The Vue 3 frontend (port 5173) communicates with the FastAPI backend (port 8000) over REST, with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

**Build** the app from the graph blueprints:

```bash
spl3 run spl/build_app.spl --tools spl/tools.py --llm claude_cli \
  -p system_yaml=apps/todo/blueprint/main.graph.yaml \
  -p output_dir=apps/todo-v6
```

**Start** both services (each in its own terminal, or via a process manager):

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

Open `http://localhost:5173` in a browser once both services are running.

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/todos` | List all todo items |
| `POST` | `/todos` | Create a new todo item |
| `PUT` | `/todos/{id}` | Toggle the completed state of a todo |
| `DELETE` | `/todos/{id}` | Delete a todo item by ID |
