# Node verification: crud_operations
# Edge verification: returned Pydantic models match schema; 404 on unknown id
import pytest
from fastapi import HTTPException
from app import crud
from app.schemas import TodoCreate


def test_get_todos_empty(db):
    assert crud.get_todos(db) == []


def test_create_todo(db):
    todo = crud.create_todo(db, TodoCreate(title="buy milk"))
    assert todo.id is not None
    assert todo.title == "buy milk"
    assert todo.completed is False


def test_get_todos_returns_created(db):
    crud.create_todo(db, TodoCreate(title="a"))
    crud.create_todo(db, TodoCreate(title="b"))
    todos = crud.get_todos(db)
    assert len(todos) == 2
    assert {t.title for t in todos} == {"a", "b"}


def test_toggle_todo(db):
    todo = crud.create_todo(db, TodoCreate(title="buy milk"))
    toggled = crud.toggle_todo(db, todo.id, True)
    assert toggled.completed is True
    reopened = crud.toggle_todo(db, todo.id, False)
    assert reopened.completed is False


def test_toggle_todo_not_found(db):
    with pytest.raises(HTTPException) as exc:
        crud.toggle_todo(db, 999, True)
    assert exc.value.status_code == 404


def test_delete_todo(db):
    todo = crud.create_todo(db, TodoCreate(title="buy milk"))
    crud.delete_todo(db, todo.id)
    assert crud.get_todos(db) == []


def test_delete_todo_not_found(db):
    with pytest.raises(HTTPException) as exc:
        crud.delete_todo(db, 999)
    assert exc.value.status_code == 404
