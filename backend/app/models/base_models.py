from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    now: datetime


class CardSummary(BaseModel):
    id: str
    name: str
    cost: int = 0


class EchoRequest(BaseModel):
    message: str = Field(default="hello")
    payload: dict[str, Any] | None = None


class EchoResponse(BaseModel):
    received: EchoRequest
