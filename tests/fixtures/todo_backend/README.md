# Todo Backend

A lightweight REST API for managing a todo list, built with FastAPI and SQLite. It exposes four endpoints for listing, creating, toggling, and deleting todos. The database is created automatically on startup — no migration step required.

## Prerequisites

- Python 3.11+
- Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` should include: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`.

## Running the server

```bash
uvicorn app.main:app --reload
```

- Base URL: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

## Running tests

```bash
pytest tests/
```

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/todos` | Return all todos |
| `POST` | `/todos` | Create a new todo |
| `PUT` | `/todos/{id}` | Toggle the completed state of a todo |
| `DELETE` | `/todos/{id}` | Delete a todo by ID |