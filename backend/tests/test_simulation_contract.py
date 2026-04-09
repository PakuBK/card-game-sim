from __future__ import annotations

from pathlib import Path
import sys
import unittest

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes import simulate, simulation_schema
from app.core.errors import (
    SimulationInputError,
    build_api_error_response,
    build_validation_error_response,
)
from app.main import app
from app.models.base_models import SimulationRequest, SimulationSchemaResponse
from app.core.simulation import run_simulation


def sample_request_payload() -> dict:
    return {
        "seed": 123,
        "runs": 2,
        "max_time_seconds": 12,
        "max_events": 2000,
        "item_definitions": [
            {
                "id": "jab",
                "name": "Jab",
                "size": 1,
                "cooldown_seconds": 1.0,
                "effects": [
                    {
                        "type": "damage",
                        "target": "opponent",
                        "magnitude": 3,
                    }
                ],
            }
        ],
        "players": [
            {
                "player_id": "player_a",
                "stats": {
                    "max_health": 30,
                    "regeneration_per_second": 0.5,
                },
                "board": {
                    "width": 10,
                    "placements": [
                        {
                            "item_instance_id": "a1",
                            "item_definition_id": "jab",
                            "start_slot": 0,
                        }
                    ],
                },
                "initial_statuses": [{"type": "burn", "value": 1}],
            },
            {
                "player_id": "player_b",
                "stats": {
                    "max_health": 30,
                },
                "board": {
                    "width": 10,
                    "placements": [
                        {
                            "item_instance_id": "b1",
                            "item_definition_id": "jab",
                            "start_slot": 0,
                        }
                    ],
                },
                "initial_statuses": [{"type": "poison", "value": 1}],
            },
        ],
    }


class SimulationContractTests(unittest.TestCase):
    def test_scope_contract_limits(self) -> None:
        schema = SimulationSchemaResponse()
        self.assertEqual([s.value for s in schema.scope.statuses], ["burn", "poison"])
        self.assertEqual(schema.scope.trigger_modes, ["timed_use_only"])
        self.assertEqual(schema.scope.percentile_set, [50, 90, 95])

    def test_request_validation_requires_player_a_and_player_b(self) -> None:
        payload = sample_request_payload()
        payload["players"] = [payload["players"][0], payload["players"][0]]

        with self.assertRaises(ValidationError):
            SimulationRequest.model_validate(payload)

    def test_simulation_determinism_same_input_same_output(self) -> None:
        payload = sample_request_payload()
        request = SimulationRequest.model_validate(payload)

        result_1 = run_simulation(request)
        result_2 = run_simulation(request)

        self.assertEqual(result_1.model_dump(), result_2.model_dump())

    def test_api_route_contracts_and_openapi(self) -> None:
        scope_response = simulation_schema()
        self.assertEqual(scope_response.scope.trigger_modes, ["timed_use_only"])

        request = SimulationRequest.model_validate(sample_request_payload())
        result = simulate(request)
        self.assertEqual(result.summary.run_count, 2)
        self.assertIsNotNone(result.summary.duration_seconds.p50)
        self.assertIsNotNone(result.summary.duration_seconds.p90)
        self.assertIsNotNone(result.summary.duration_seconds.p95)

        openapi_paths = app.openapi().get("paths", {})
        self.assertIn("/api/simulation/schema", openapi_paths)
        self.assertIn("/api/simulate", openapi_paths)

    def test_simulation_input_error_code_on_invalid_board_layout(self) -> None:
        payload = sample_request_payload()
        payload["players"][0]["board"]["placements"] = [
            {"item_instance_id": "a1", "item_definition_id": "jab", "start_slot": 0},
            {"item_instance_id": "a2", "item_definition_id": "jab", "start_slot": 0},
        ]

        request = SimulationRequest.model_validate(payload)
        with self.assertRaises(SimulationInputError) as ctx:
            run_simulation(request)

        self.assertEqual(ctx.exception.code, "OVERLAPPING_ITEM_PLACEMENTS")

    def test_validation_error_envelope_builder(self) -> None:
        exc = RequestValidationError(
            [
                {
                    "type": "string_too_short",
                    "loc": ("body", "players", 0, "player_id"),
                    "msg": "String should have at least 1 character",
                    "input": "",
                }
            ]
        )
        response = build_validation_error_response(exc)
        self.assertEqual(response.error.type, "validation_error")
        self.assertEqual(response.error.code, "REQUEST_VALIDATION_ERROR")
        self.assertEqual(response.error.details[0].location, ["body", "players", 0, "player_id"])

    def test_runtime_error_envelope_builder(self) -> None:
        response = build_api_error_response(
            error_type="simulation_runtime_error",
            code="SIMULATION_RUNTIME_ERROR",
            message="Unexpected runtime error while executing simulation.",
        )
        self.assertEqual(response.error.type, "simulation_runtime_error")
        self.assertEqual(response.error.code, "SIMULATION_RUNTIME_ERROR")


if __name__ == "__main__":
    unittest.main()
