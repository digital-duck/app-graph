from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TodoModel(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str]
    completed: Mapped[bool] = mapped_column(default=False)