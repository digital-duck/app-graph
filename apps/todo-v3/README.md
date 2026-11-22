Let me look at the graph.yaml and directory structure to get accurate details.

<function_calls>
<invoke name="mcp__claude-code-filesystem__list_directory">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps/todo-v3</parameter>
</invoke>
<invoke name="mcp__claude-code-filesystem__list_directory">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps</parameter>
</invoke>
</function_calls>
<function_calls>
<invoke name="mcp__claude-code-filesystem__read_file">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps/todo-v3</parameter>
</invoke>
</function_calls>
<function_calls>
<invoke name="mcp__claude-code-filesystem__directory_tree">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps/todo-v3</parameter>
</invoke>
</function_calls>
<function_calls>
<invoke name="mcp__claude-code-filesystem__read_file">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps/todo-v3/todo.graph.yaml</parameter>
</invoke>
</function_calls>
<function_calls>
<invoke name="mcp__claude-code-filesystem__read_file">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/docs/DEV/BUILD/README.md</parameter>
</invoke>
</function_calls>
<function_calls>
<invoke name="mcp__claude-code-filesystem__directory_tree">
<parameter name="path">/home/gongai/projects/digital-duck/graph-code/apps/compiled</parameter>
</invoke>
</function_calls>

# Todo App

A full-stack todo application built with a Vue.js frontend and a FastAPI backend, backed by SQLite for persistence. The app lets users create, list, toggle completion, and delete todo items through a clean browser interface — supporting the full todo list management lifecycle from a single-page app that communicates with a lightweight REST API.

## Status

Acceptance tests run against the just-completed integration build:

| Application | Result |
|---|---|
| create_todo | PASS (11.5s) |
| list_todos | **FAIL** — `test_empty_state` received a non-empty list when the database had not been reset between runs |
| toggle_todo | PASS (12.4s) |
| delete_todo | PASS (12.0s) |

`list_todos` failure is a test-isolation issue (leftover rows from a prior run), not a functional defect in the list endpoint itself.

## Architecture

The Vue.js frontend (port 5173) communicates with the FastAPI backend (port 8000) over REST, with CORS enabled; see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

**Build** — compile and wire all components from the graph blueprint:

```bash
spl3 run spl/build_app.spl --graph apps/todo-v3/todo.graph.yaml
```

See [docs/DEV/BUILD/README.md §12.1](docs/DEV/BUILD/README.md) for build options (custom output directory via `--output_dir`, §12.4).

**Start** — once built, launch backend and frontend in separate terminals:

```bash
# Terminal 1 — backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in a browser.

## Applications

- **create_todo** — add a new named todo item to the list
- **list_todos** — retrieve all current todo items
- **toggle_todo** — flip a todo item between completed and not completed
- **delete_todo** — permanently remove a todo item
- **manage_todo_list** — end-to-end todo list management combining create, list, toggle, and delete into a coherent workflow