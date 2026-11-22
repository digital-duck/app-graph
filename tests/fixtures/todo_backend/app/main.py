from __future__ import annotations

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import models
from app.config import FRONTEND_VITE_PORT
from app.crud import create_todo, delete_todo, get_todos, toggle_todo
from app.database import Base, engine, get_db
from app.schemas import Todo, TodoCreate, ToggleRequest

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{FRONTEND_VITE_PORT}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/todos", response_model=list[Todo])
def list_todos(db: Session = Depends(get_db)) -> list[Todo]:
    return get_todos(db)


@app.post("/todos", response_model=Todo, status_code=201)
def create(item: TodoCreate, db: Session = Depends(get_db)) -> Todo:
    return create_todo(db, item)


@app.put("/todos/{id}", response_model=Todo)
def update(id: int, body: ToggleRequest, db: Session = Depends(get_db)) -> Todo:
    return toggle_todo(db, id, body.completed)


@app.delete("/todos/{id}", status_code=204)
def delete(id: int, db: Session = Depends(get_db)) -> Response:
    delete_todo(db, id)
    return Response(status_code=204)