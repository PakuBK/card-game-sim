from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import CardSummary, EchoRequest, EchoResponse, HealthResponse

app = FastAPI(title="card-game-sim API", version="0.1.0")

# In dev, the Vite server will proxy `/api/*` to this backend, so CORS is usually
# not involved. This is still useful if you hit the backend directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", now=datetime.now(timezone.utc))


@app.get("/api/cards", response_model=list[CardSummary])
def list_cards() -> list[CardSummary]:
    return [
        CardSummary(id="strike", name="Strike", cost=1),
        CardSummary(id="guard", name="Guard", cost=1),
        CardSummary(id="fireball", name="Fireball", cost=2),
    ]


@app.post("/api/echo", response_model=EchoResponse)
def echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(received=payload)
