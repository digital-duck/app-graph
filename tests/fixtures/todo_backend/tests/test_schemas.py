# Node verification: todo_schema
import pytest
from pydantic import ValidationError
from app.schemas import Todo, TodoCreate


def test_todo_create_valid():
    t = TodoCreate(title="buy milk")
    assert t.title == "buy milk"


def test_todo_create_strips_whitespace():
    t = TodoCreate(title="  buy milk  ")
    assert t.title == "buy milk"


def test_todo_create_rejects_empty():
    with pytest.raises(ValidationError):
        TodoCreate(title="")


def test_todo_create_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        TodoCreate(title="   ")


def test_todo_output_shape():
    t = Todo(id=1, title="buy milk", completed=False)
    assert t.id == 1
    assert t.completed is False


# Edge verification: Todo schema field types match ORM column types
def test_todo_from_orm_attributes():
    class FakeRow:
        id = 1
        title = "buy milk"
        completed = False

    t = Todo.model_validate(FakeRow())
    assert t.id == 1
    assert t.title == "buy milk"
    assert t.completed is False
