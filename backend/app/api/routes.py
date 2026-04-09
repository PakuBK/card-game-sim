from fastapi import APIRouter
from datetime import datetime, timezone

from app.core.simulation import run_simulation
from app.models.base_models import (
    ApiErrorResponse,
    HealthResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationSchemaResponse,
)

router = APIRouter()

@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", now=datetime.now(timezone.utc))


@router.get("/api/simulation/schema", response_model=SimulationSchemaResponse)
def simulation_schema() -> SimulationSchemaResponse:
    return SimulationSchemaResponse()


@router.post(
    "/api/simulate",
    response_model=SimulationResponse,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid simulation configuration."},
        422: {"model": ApiErrorResponse, "description": "Request validation failed."},
        500: {"model": ApiErrorResponse, "description": "Unexpected simulation runtime error."},
    },
)
def simulate(payload: SimulationRequest) -> SimulationResponse:
    return run_simulation(payload)
