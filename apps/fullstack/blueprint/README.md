# Fullstack App

A full-stack web application with a Vue 3 frontend and a FastAPI backend backed by SQLite. It supports user self-registration and JWT-authenticated login, personal item management (full CRUD), a superuser-controlled user administration panel, and a token-based password reset flow. All item and user management operations are protected by JWT bearer authentication issued at login or registration.

## Status

| Application | Result | Duration |
|---|---|---|
| user_registers | PASS | 29.3s |
| user_logs_in | PASS | 17.3s |
| user_manages_items | PASS | 27.8s |
| superuser_manages_users | PASS | 29.1s |
| user_resets_password | PASS | 120.1s |

## Architecture

The Vue frontend (port 5177) communicates with the FastAPI backend (port 8004) over REST under `/api/v1`, with CORS enabled and JWT bearer tokens used for all authenticated endpoints — see [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for each component's own setup, run, and test instructions.

## Running the full system

Build the app with the SPL runner:

```bash
spl3 run spl/build_app.spl apps/fullstack/blueprint/main.graph.yaml
```

Then start the backend and frontend in separate terminals:

```bash
# Terminal 1 — backend
cd apps/fullstack/backend
uvicorn app.main:app --port 8004 --reload

# Terminal 2 — frontend
cd apps/fullstack/frontend
npm run dev
```

Open http://localhost:5177 in your browser.

## Default login

On first startup the backend's lifespan handler automatically creates an admin account:

- **Email:** `admin@example.com`
- **Password:** `adminpassword`

## Applications

- **user_registers** — A new user self-registers via `POST /api/v1/users/signup` with an email and password; the backend returns a `UserPublic`, and the user can then log in.
- **user_logs_in** — A registered user logs in with email and password via `POST /api/v1/login/access-token` to receive a JWT bearer token.
- **user_manages_items** — An authenticated user creates, views, edits, and deletes their own items through the item dashboard; regular users see only their own items, superusers see all.
- **superuser_manages_users** — Backend-only: a superuser lists, creates, updates, and deletes any user account (no frontend admin panel in this app's scope).
- **user_resets_password** — Backend-only: a user who forgot their password requests a reset via `POST /api/v1/password-recovery/{email}`, then completes the reset with the returned token via `POST /api/v1/reset-password/` (no frontend UI in this app's scope; no real email is sent in this prototype).
- **manage_items_authenticated** — The capstone: the full golden path — register, log in, create an item, list it, update it, delete it, and confirm it's gone — using the bearer token acquired at login.
