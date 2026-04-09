from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.errors import (
    SimulationInputError,
    build_api_error_response,
    build_validation_error_response,
)


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

app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    response = build_validation_error_response(exc)
    return JSONResponse(status_code=422, content=response.model_dump())


@app.exception_handler(SimulationInputError)
async def handle_simulation_input_error(_request: Request, exc: SimulationInputError) -> JSONResponse:
    response = build_api_error_response(
        error_type="simulation_input_error",
        code=exc.code,
        message=str(exc),
    )
    return JSONResponse(status_code=400, content=response.model_dump())


@app.exception_handler(Exception)
async def handle_unexpected_runtime_error(request: Request, exc: Exception) -> JSONResponse:
    logging.exception("Unhandled API exception on path %s", request.url.path, exc_info=exc)
    response = build_api_error_response(
        error_type="simulation_runtime_error",
        code="SIMULATION_RUNTIME_ERROR",
        message="Unexpected runtime error while executing simulation.",
    )
    return JSONResponse(status_code=500, content=response.model_dump())
