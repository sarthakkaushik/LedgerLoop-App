from typing import Literal

from pydantic import BaseModel, Field


class AnalysisAskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class AnalysisAskE2EPostgresRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    postgres_url: str = Field(min_length=1, max_length=4000)


class AnalysisPoint(BaseModel):
    label: str
    value: float


class AnalysisChart(BaseModel):
    chart_type: Literal["bar", "line"]
    title: str
    points: list[AnalysisPoint] = Field(default_factory=list)


class AnalysisTable(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str | float | int]] = Field(default_factory=list)


class AnalysisAskResponse(BaseModel):
    mode: Literal["analytics", "chat"] = "analytics"
    route: Literal["fixed", "agent", "chat"] = "fixed"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tool: str
    tool_trace: list[str] = Field(default_factory=list)
    sql: str | None = None
    answer: str
    chart: AnalysisChart | None = None
    table: AnalysisTable | None = None
