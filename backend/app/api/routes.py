from fastapi import APIRouter
from ..models.base_models import CardSummary, EchoRequest, EchoResponse, HealthResponse
from datetime import datetime, timezone

router = APIRouter()

@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", now=datetime.now(timezone.utc))


@router.get("/api/cards", response_model=list[CardSummary])
def list_cards() -> list[CardSummary]:
    return [
        CardSummary(id="strike", name="Strike", cost=1),
        CardSummary(id="guard", name="Guard", cost=1),
        CardSummary(id="fireball", name="Fireball", cost=2),
    ]


@router.post("/api/echo", response_model=EchoResponse)
def echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(received=payload)
