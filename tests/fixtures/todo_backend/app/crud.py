from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import TodoModel
from app.schemas import Todo, TodoCreate


def get_todos(db: Session) -> list[Todo]:
    rows = db.query(TodoModel).all()
    return [Todo.model_validate(row) for row in rows]


def create_todo(db: Session, item: TodoCreate) -> Todo:
    row = TodoModel(title=item.title)
    db.add(row)
    db.commit()
    db.refresh(row)
    return Todo.model_validate(row)


def toggle_todo(db: Session, id: int, completed: bool) -> Todo:
    row = db.get(TodoModel, id)
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    row.completed = completed
    db.commit()
    db.refresh(row)
    return Todo.model_validate(row)


def delete_todo(db: Session, id: int) -> None:
    row = db.get(TodoModel, id)
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(row)
    db.commit()