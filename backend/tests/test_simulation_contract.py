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

    def test_simultaneous_lethal_item_uses_resolve_to_draw(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["item_definitions"] = [
            {
                "id": "burst",
                "name": "Burst",
                "size": 1,
                "cooldown_seconds": 1.0,
                "effects": [
                    {
                        "type": "damage",
                        "target": "opponent",
                        "magnitude": 10,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 10}
        payload["players"][1]["stats"] = {"max_health": 10}
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a1",
                "item_definition_id": "burst",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = [
            {
                "item_instance_id": "b1",
                "item_definition_id": "burst",
                "start_slot": 0,
            }
        ]

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.winner_player_id, "draw")
        self.assertEqual(run.duration_seconds, 1.0)
        self.assertEqual(run.players[0].health, 0.0)
        self.assertEqual(run.players[1].health, 0.0)
        self.assertEqual(run.metrics.player_a.item_uses, 1)
        self.assertEqual(run.metrics.player_b.item_uses, 1)

    def test_same_time_poison_tick_is_processed_before_regen_tick(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 3
        payload["item_definitions"] = [
            {
                "id": "placeholder",
                "name": "Placeholder",
                "size": 1,
                "cooldown_seconds": 99,
                "effects": [
                    {
                        "type": "heal",
                        "target": "self",
                        "magnitude": 1,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {
            "max_health": 1,
            "regeneration_per_second": 1,
        }
        payload["players"][1]["stats"] = {"max_health": 10}
        payload["players"][0]["initial_statuses"] = [{"type": "poison", "value": 1}]
        payload["players"][1]["initial_statuses"] = []
        payload["players"][0]["board"]["placements"] = []
        payload["players"][1]["board"]["placements"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.winner_player_id, "player_b")
        self.assertEqual(run.duration_seconds, 1.0)
        self.assertEqual(run.players[0].health, 0.0)
        self.assertEqual(run.metrics.player_a.poison_ticks, 1)
        self.assertEqual(run.metrics.player_a.regen_ticks, 1)
        self.assertEqual(run.metrics.player_b.poison_ticks, 0)
        self.assertEqual(run.metrics.player_b.regen_ticks, 0)

    def test_metrics_include_item_event_status_and_damage_breakdowns(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 1.0
        payload["item_definitions"] = [
            {
                "id": "burner",
                "name": "Burner",
                "size": 1,
                "cooldown_seconds": 99,
                "initial_delay_seconds": 0,
                "effects": [
                    {
                        "type": "damage",
                        "target": "opponent",
                        "magnitude": 3,
                    },
                    {
                        "type": "apply_burn",
                        "target": "opponent",
                        "magnitude": 2,
                    },
                ],
            }
        ]
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a-burner",
                "item_definition_id": "burner",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.metrics.player_a.item_uses, 1)
        self.assertEqual(run.metrics.player_a.damage_to_opponent.direct, 3.0)
        self.assertEqual(run.metrics.player_a.damage_to_opponent.burn, 3.0)
        self.assertEqual(run.metrics.player_a.damage_to_opponent.total, 6.0)
        self.assertEqual(run.metrics.player_a.status_effects_applied.burn.applications, 1)
        self.assertEqual(run.metrics.player_a.status_effects_applied.burn.total_value, 2.0)
        self.assertEqual(run.metrics.player_b.status_effects_received.burn.applications, 1)
        self.assertEqual(run.metrics.player_b.status_effects_received.burn.total_value, 2.0)

        item_metric = run.metrics.player_a.item_metrics[0]
        self.assertEqual(item_metric.item_instance_id, "a-burner")
        self.assertEqual(item_metric.damage_done.direct, 3.0)
        self.assertEqual(item_metric.damage_done.burn, 3.0)
        self.assertEqual(item_metric.damage_done.total, 6.0)
        self.assertEqual(item_metric.events_triggered["used"], 1)
        self.assertEqual(item_metric.events_triggered["damage"], 1)
        self.assertEqual(item_metric.events_triggered["apply_burn"], 1)
        self.assertEqual(item_metric.events_triggered["burn_tick"], 2)

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
