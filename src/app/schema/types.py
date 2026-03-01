from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TablePayload(BaseModel):
    title: str
    columns: list[str]
    rows: list[list[Any]]


class ToolResult(BaseModel):
    ok: bool = True
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    tables: list[TablePayload] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScenarioDiffResult(BaseModel):
    a: str
    b: str
    metrics: dict[str, dict[str, float | None]]
    improved: bool | None = None
