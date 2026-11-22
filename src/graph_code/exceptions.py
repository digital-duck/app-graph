"""Exceptions and diagnostic types for graph_lib validation."""

from __future__ import annotations


class ToolFailed(Exception):
    """Raised by graph_lib validators before any LLM call when graph is invalid."""


class ValidationWarning:
    """Non-fatal diagnostic returned (not raised) by validate_events."""

    def __init__(self, code: str, message: str, context: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.context: dict = context or {}

    def __repr__(self) -> str:
        return f"ValidationWarning({self.code!r}: {self.message!r})"

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
