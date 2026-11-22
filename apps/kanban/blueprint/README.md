Let me read the relevant graph files to understand the system.

**Tool call: Read** (`apps/kanban/blueprint/main.graph.yaml`)

**Tool call: Read** (`apps/kanban/blueprint/backend.graph.yaml`)

**Tool call: Read** (`apps/kanban/blueprint/frontend.graph.yaml`)

**Results:**

<details>
<summary>main.graph.yaml</summary>

```yaml
meta:
  id: kanban
  label: Kanban Board
  version: "1.0"
  domain_type: integrated
  domain: productivity/project-management/kanban

applications:
  create_card: Create a new task card on the board, assigning it a title, optional description, and initial column.
  view_board: View the full three-column board with all cards organized by status column.
  move_card: Drag or move a card from one column to another to update its status.
  delete_card: Remove a card from the board permanently.
  manage_board: Manage board-level settings such as column configuration and board metadata.

imports:
  - path: backend.graph.yaml
    as: backend
  - path: frontend.graph.yaml
    as: frontend

integration:
  wiring:
    - from: frontend
      to: backend
      protocol: REST
      port: 8002
      cors: true
```

</details>

<details>
<summary>backend.graph.yaml (truncated)</summary>

Port 8002, FastAPI, SQLite confirmed.

</details>

<details>
<summary>frontend.graph.yaml (truncated)</summary>

Port 5175, Vue confirmed.

</details>

# Kanban Board

A three-column Kanban board application for tracking tasks through their lifecycle. Built with a Vue 3 frontend and a FastAPI backend backed by SQLite, the board supports the full task management workflow: creating cards with a title and description, viewing all cards organized by status column, moving cards between columns as work progresses, deleting cards when they're no longer needed, and managing board-level configuration. The system is designed for teams and individuals who want a lightweight, self-hosted project management tool with no external dependencies beyond the local runtime.

## Status

| Application | Result | Time |
|---|---|---|
| create_card | PASS | 16.1s |
| view_board | PASS | 21.8s |
| move_card | PASS | 17.5s |
| delete_card | PASS | 17.2s |

## Architecture

The Vue frontend (port 5175) communicates with the FastAPI backend (port 8002) over REST with CORS enabled — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

Build the application first, then start both components:

```bash
# Build
spl3 run spl/build_app.spl --app kanban

# Start backend (from apps/kanban/backend)
uvicorn app.main:app --port 8002

# Start frontend (from apps/kanban/frontend)
npm run dev
```

## Applications

- **create_card** — Create a new task card on the board, assigning it a title, optional description, and initial column.
- **view_board** — View the full three-column board with all cards organized by status column.
- **move_card** — Drag or move a card from one column to another to update its status.
- **delete_card** — Remove a card from the board permanently.
- **manage_board** — Manage board-level settings such as column configuration and board metadata.