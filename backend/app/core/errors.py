from __future__ import annotations

from typing import Literal

from fastapi.exceptions import RequestValidationError

from app.models.base_models import ApiErrorDetail, ApiErrorResponse


class SimulationInputError(Exception):
    def __init__(self, message: str, code: str = "SIMULATION_INPUT_ERROR") -> None:
        super().__init__(message)
        self.code = code


def build_validation_error_response(exc: RequestValidationError) -> ApiErrorResponse:
    details = [
        ApiErrorDetail(
            code=str(error.get("type", "validation_error")),
            message=str(error.get("msg", "Validation error")),
            location=list(error.get("loc", [])),
        )
        for error in exc.errors()
    ]
    return build_api_error_response(
        error_type="validation_error",
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed.",
        details=details,
    )


def build_api_error_response(
    *,
    error_type: Literal["validation_error", "simulation_input_error", "simulation_runtime_error"],
    code: str,
    message: str,
    details: list[ApiErrorDetail] | None = None,
) -> ApiErrorResponse:
    return ApiErrorResponse(
        error={
            "type": error_type,
            "code": code,
            "message": message,
            "details": details or [],
        }
    )
