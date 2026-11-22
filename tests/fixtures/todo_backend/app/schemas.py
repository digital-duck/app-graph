from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class TodoCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be empty")
        return stripped


class Todo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool = False


class ToggleRequest(BaseModel):
    completed: bool