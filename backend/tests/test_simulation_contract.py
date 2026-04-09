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

    def test_burn_ticks_decay_and_only_reduce_health_with_shield_mitigation(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 0.5
        payload["players"][0]["stats"] = {
            "max_health": 100,
            "start_shield": 10,
        }
        payload["players"][0]["board"]["placements"] = []
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["initial_statuses"] = [{"type": "burn", "value": 10}]
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.duration_seconds, 0.5)
        self.assertEqual(run.players[0].health, 95.0)
        self.assertEqual(run.players[0].shield, 10.0)
        self.assertEqual(run.players[0].burn, 9.0)
        self.assertEqual(run.combat_log[0].event_type, "burn_tick")
        self.assertEqual(run.combat_log[0].state_deltas[0].health_delta, -5.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].shield_delta, 0.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].burn_delta, -1.0)

    def test_poison_ticks_ignore_shield_and_do_not_decay(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 1.0
        payload["players"][0]["stats"] = {
            "max_health": 100,
            "start_shield": 10,
        }
        payload["players"][0]["board"]["placements"] = []
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["initial_statuses"] = [{"type": "poison", "value": 4}]
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.duration_seconds, 1.0)
        self.assertEqual(run.players[0].health, 96.0)
        self.assertEqual(run.players[0].shield, 10.0)
        self.assertEqual(run.players[0].poison, 4.0)
        self.assertEqual(run.combat_log[0].event_type, "poison_tick")
        self.assertEqual(run.combat_log[0].state_deltas[0].health_delta, -4.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].shield_delta, 0.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].poison_delta, 0.0)

    def test_healing_reduces_statuses_but_regen_does_not(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 1.0
        payload["item_definitions"] = [
            {
                "id": "medic",
                "name": "Medic",
                "size": 1,
                "cooldown_seconds": 99,
                "initial_delay_seconds": 0,
                "effects": [
                    {
                        "type": "heal",
                        "target": "self",
                        "magnitude": 20,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {
            "max_health": 100,
            "start_health": 50,
            "regeneration_per_second": 10,
        }
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a-medic",
                "item_definition_id": "medic",
                "start_slot": 0,
            }
        ]
        payload["players"][0]["initial_statuses"] = [
            {"type": "burn", "value": 10},
            {"type": "poison", "value": 10},
        ]
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(run.players[0].health, 54.0)
        self.assertEqual(run.players[0].burn, 7.0)
        self.assertEqual(run.players[0].poison, 9.0)
        self.assertEqual(run.metrics.player_a.regen_ticks, 1)
        self.assertEqual(run.metrics.player_a.item_uses, 1)
        self.assertEqual(run.combat_log[0].event_type, "item_use")
        self.assertEqual(run.combat_log[0].state_deltas[0].health_delta, 20.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].burn_delta, -1.0)
        self.assertEqual(run.combat_log[0].state_deltas[0].poison_delta, -1.0)
        self.assertEqual(run.combat_log[1].event_type, "burn_tick")
        self.assertEqual(run.combat_log[2].event_type, "burn_tick")
        self.assertEqual(run.combat_log[3].event_type, "poison_tick")
        self.assertEqual(run.combat_log[4].event_type, "regen_tick")
        self.assertEqual(run.combat_log[4].state_deltas[0].health_delta, 10.0)
        self.assertEqual(run.combat_log[4].state_deltas[0].burn_delta, 0.0)
        self.assertEqual(run.combat_log[4].state_deltas[0].poison_delta, 0.0)

    def test_combat_log_includes_ordered_entries_with_state_deltas(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 2
        payload["max_events"] = 100
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertGreater(len(run.combat_log), 0)
        self.assertEqual(run.combat_log_total_events, run.metrics.total_events_processed)
        self.assertFalse(run.combat_log_truncated)

        for index, entry in enumerate(run.combat_log):
            self.assertEqual(entry.event_index, index)
            self.assertIn(entry.event_type, ["item_use", "burn_tick", "poison_tick", "regen_tick"])
            self.assertIn(entry.source_player_id, ["player_a", "player_b"])

        first_entry = run.combat_log[0]
        self.assertEqual(first_entry.time_seconds, 1.0)
        self.assertEqual(first_entry.event_type, "item_use")
        self.assertEqual(first_entry.source_player_id, "player_a")
        self.assertEqual(first_entry.target_id, "player_b")
        self.assertTrue(any(delta.player_id == "player_b" for delta in first_entry.state_deltas))

        player_b_delta = next(delta for delta in first_entry.state_deltas if delta.player_id == "player_b")
        self.assertEqual(player_b_delta.health_delta, -3.0)
        self.assertEqual(player_b_delta.health_after, 27.0)

    def test_combat_log_limit_caps_entries_and_sets_truncation(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 4
        payload["max_events"] = 100
        payload["combat_log_limit"] = 2

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        self.assertEqual(len(run.combat_log), 2)
        self.assertGreater(run.combat_log_total_events, len(run.combat_log))
        self.assertTrue(run.combat_log_truncated)

    def test_combat_log_snapshot_fixed_payload(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 2
        payload["max_events"] = 100
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
        payload["players"][0]["stats"] = {"max_health": 30}
        payload["players"][1]["stats"] = {"max_health": 30}
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

        self.assertEqual(run.combat_log_total_events, 3)
        self.assertFalse(run.combat_log_truncated)
        self.assertEqual(len(run.combat_log), 3)

        snapshot = [
            {
                "event_index": entry.event_index,
                "time_seconds": entry.time_seconds,
                "event_type": entry.event_type,
                "source_player_id": entry.source_player_id,
                "source_item_instance_id": entry.source_item_instance_id,
                "target_id": entry.target_id,
                "state_deltas": [delta.model_dump() for delta in entry.state_deltas],
            }
            for entry in run.combat_log
        ]

        self.assertEqual(
            snapshot,
            [
                {
                    "event_index": 0,
                    "time_seconds": 0.0,
                    "event_type": "item_use",
                    "source_player_id": "player_a",
                    "source_item_instance_id": "a-burner",
                    "target_id": "player_b",
                    "state_deltas": [
                        {
                            "player_id": "player_b",
                            "health_delta": -3.0,
                            "shield_delta": 0.0,
                            "burn_delta": 2.0,
                            "poison_delta": 0.0,
                            "health_after": 27.0,
                            "shield_after": 0.0,
                            "burn_after": 2.0,
                            "poison_after": 0.0,
                        }
                    ],
                },
                {
                    "event_index": 1,
                    "time_seconds": 0.5,
                    "event_type": "burn_tick",
                    "source_player_id": "player_a",
                    "source_item_instance_id": "a-burner",
                    "target_id": "player_b",
                    "state_deltas": [
                        {
                            "player_id": "player_b",
                            "health_delta": -2.0,
                            "shield_delta": 0.0,
                            "burn_delta": -1.0,
                            "poison_delta": 0.0,
                            "health_after": 25.0,
                            "shield_after": 0.0,
                            "burn_after": 1.0,
                            "poison_after": 0.0,
                        }
                    ],
                },
                {
                    "event_index": 2,
                    "time_seconds": 1.0,
                    "event_type": "burn_tick",
                    "source_player_id": "player_a",
                    "source_item_instance_id": "a-burner",
                    "target_id": "player_b",
                    "state_deltas": [
                        {
                            "player_id": "player_b",
                            "health_delta": -1.0,
                            "shield_delta": 0.0,
                            "burn_delta": -1.0,
                            "poison_delta": 0.0,
                            "health_after": 24.0,
                            "shield_after": 0.0,
                            "burn_after": 0.0,
                            "poison_after": 0.0,
                        }
                    ],
                },
            ],
        )

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

    def test_adjacency_targeting_prefers_adjacent_enemy_anchor(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 1
        payload["max_events"] = 20
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a-source",
                "item_definition_id": "jab",
                "start_slot": 4,
            }
        ]
        payload["players"][1]["board"]["placements"] = [
            {
                "item_instance_id": "b-solo",
                "item_definition_id": "jab",
                "start_slot": 4,
            },
            {
                "item_instance_id": "b-pair-1",
                "item_definition_id": "jab",
                "start_slot": 1,
            },
            {
                "item_instance_id": "b-pair-2",
                "item_definition_id": "jab",
                "start_slot": 2,
            },
        ]

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        first_entry = run.combat_log[0]
        self.assertEqual(first_entry.event_type, "item_use")
        self.assertEqual(first_entry.source_item_instance_id, "a-source")
        self.assertEqual(first_entry.target_id, "player_b")

    def test_adjacency_targeting_tie_breaks_by_start_slot_then_item_id(self) -> None:
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 1
        payload["max_events"] = 20
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a-source",
                "item_definition_id": "jab",
                "start_slot": 4,
            }
        ]
        payload["players"][1]["board"]["placements"] = [
            {
                "item_instance_id": "b-left-adjacent",
                "item_definition_id": "jab",
                "start_slot": 3,
            },
            {
                "item_instance_id": "b-left-anchor",
                "item_definition_id": "jab",
                "start_slot": 2,
            },
            {
                "item_instance_id": "b-right-adjacent",
                "item_definition_id": "jab",
                "start_slot": 5,
            },
            {
                "item_instance_id": "b-right-anchor",
                "item_definition_id": "jab",
                "start_slot": 6,
            },
        ]

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        first_entry = run.combat_log[0]
        self.assertEqual(first_entry.event_type, "item_use")
        self.assertEqual(first_entry.target_id, "player_b")

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

    def test_simulation_input_error_code_on_duplicate_item_instance_id(self) -> None:
        payload = sample_request_payload()
        payload["players"][0]["board"]["placements"] = [
            {"item_instance_id": "dup", "item_definition_id": "jab", "start_slot": 0},
            {"item_instance_id": "dup", "item_definition_id": "jab", "start_slot": 1},
        ]

        request = SimulationRequest.model_validate(payload)
        with self.assertRaises(SimulationInputError) as ctx:
            run_simulation(request)

        self.assertEqual(ctx.exception.code, "DUPLICATE_ITEM_INSTANCE_ID")

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

    # M5 Regression Tests: Representative Combat Scenarios

    def test_stop_reason_natural_win_when_opponent_dies(self) -> None:
        """Verify natural_win stop reason when combat ends due to death."""
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 60
        payload["max_events"] = 10000
        payload["item_definitions"] = [
            {
                "id": "lethal",
                "name": "Lethal",
                "size": 1,
                "cooldown_seconds": 99,
                "initial_delay_seconds": 0,
                "effects": [
                    {
                        "type": "damage",
                        "target": "opponent",
                        "magnitude": 50,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 30}
        payload["players"][1]["stats"] = {"max_health": 30}
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a1",
                "item_definition_id": "lethal",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        from app.models.base_models import RunStopReason
        self.assertEqual(run.stop_reason, RunStopReason.NATURAL_WIN)
        self.assertEqual(run.winner_player_id, "player_a")
        self.assertEqual(run.duration_seconds, 0.0)

    def test_stop_reason_time_limit_exceeded(self) -> None:
        """Verify time_limit_exceeded stop reason when max_time_seconds is hit."""
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 0.5
        payload["max_events"] = 10000
        payload["item_definitions"] = [
            {
                "id": "slow_dot",
                "name": "Slow DoT",
                "size": 1,
                "cooldown_seconds": 99,
                "effects": [
                    {
                        "type": "apply_burn",
                        "target": "opponent",
                        "magnitude": 0.1,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 100}
        payload["players"][1]["stats"] = {"max_health": 100}
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a1",
                "item_definition_id": "slow_dot",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        from app.models.base_models import RunStopReason
        self.assertEqual(run.stop_reason, RunStopReason.TIME_LIMIT_EXCEEDED)
        self.assertEqual(run.duration_seconds, 0.5)

    def test_stop_reason_event_limit_exceeded(self) -> None:
        """Verify event_limit_exceeded stop reason when max_events is hit."""
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 60
        payload["max_events"] = 5
        payload["item_definitions"] = [
            {
                "id": "rapid_ticker",
                "name": "Rapid",
                "size": 1,
                "cooldown_seconds": 0.1,
                "effects": [
                    {
                        "type": "apply_burn",
                        "target": "opponent",
                        "magnitude": 1,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 100}
        payload["players"][1]["stats"] = {"max_health": 100}
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a1",
                "item_definition_id": "rapid_ticker",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = []
        payload["players"][0]["initial_statuses"] = []
        payload["players"][1]["initial_statuses"] = []

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        from app.models.base_models import RunStopReason
        self.assertEqual(run.stop_reason, RunStopReason.EVENT_LIMIT_EXCEEDED)
        self.assertEqual(run.metrics.total_events_processed, 5)

    def test_scenario_aggressive_damage_race(self) -> None:
        """Scenario: Both players deal damage with staggered timing."""
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 10
        payload["item_definitions"] = [
            {
                "id": "burst",
                "name": "Burst",
                "size": 1,
                "cooldown_seconds": 5.0,
                "initial_delay_seconds": 0.5,
                "effects": [
                    {
                        "type": "damage",
                        "target": "opponent",
                        "magnitude": 15,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 40}
        payload["players"][1]["stats"] = {"max_health": 40}
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

        from app.models.base_models import RunStopReason
        self.assertEqual(run.stop_reason, RunStopReason.NATURAL_WIN)
        self.assertIn(run.winner_player_id, ["player_a", "player_b", "draw"])
        # At least one player should take damage
        self.assertLess(run.players[0].health + run.players[1].health, 80.0)

    def test_scenario_defensive_healing_mirror(self) -> None:
        """Scenario: Both players have healing, mirror items, should reach time limit."""
        payload = sample_request_payload()
        payload["runs"] = 1
        payload["max_time_seconds"] = 2.0
        payload["max_events"] = 1000
        payload["item_definitions"] = [
            {
                "id": "medic",
                "name": "Medic",
                "size": 1,
                "cooldown_seconds": 0.5,
                "initial_delay_seconds": 0,
                "effects": [
                    {
                        "type": "heal",
                        "target": "self",
                        "magnitude": 5,
                    }
                ],
            }
        ]
        payload["players"][0]["stats"] = {"max_health": 50}
        payload["players"][1]["stats"] = {"max_health": 50}
        payload["players"][0]["board"]["placements"] = [
            {
                "item_instance_id": "a1",
                "item_definition_id": "medic",
                "start_slot": 0,
            }
        ]
        payload["players"][1]["board"]["placements"] = [
            {
                "item_instance_id": "b1",
                "item_definition_id": "medic",
                "start_slot": 0,
            }
        ]

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        from app.models.base_models import RunStopReason
        self.assertEqual(run.stop_reason, RunStopReason.TIME_LIMIT_EXCEEDED)
        self.assertEqual(run.winner_player_id, "draw")
        self.assertEqual(run.duration_seconds, 2.0)

    def test_scenario_multi_item_complexity(self) -> None:
        """Scenario: Multiple items with staggered delays and effects."""
        payload = {
            "seed": 42,
            "runs": 1,
            "max_time_seconds": 10,
            "max_events": 500,
            "item_definitions": [
                {
                    "id": "quick_jab",
                    "name": "Quick Jab",
                    "size": 1,
                    "cooldown_seconds": 1.0,
                    "initial_delay_seconds": 0.1,
                    "effects": [{"type": "damage", "target": "opponent", "magnitude": 5}],
                },
                {
                    "id": "burn_trap",
                    "name": "Burn Trap",
                    "size": 1,
                    "cooldown_seconds": 2.0,
                    "initial_delay_seconds": 0.5,
                    "effects": [
                        {"type": "apply_burn", "target": "opponent", "magnitude": 3}
                    ],
                },
                {
                    "id": "shield_up",
                    "name": "Shield Up",
                    "size": 1,
                    "cooldown_seconds": 3.0,
                    "initial_delay_seconds": 1.0,
                    "effects": [{"type": "shield", "target": "self", "magnitude": 10}],
                },
            ],
            "players": [
                {
                    "player_id": "player_a",
                    "stats": {
                        "max_health": 50,
                        "regeneration_per_second": 1,
                    },
                    "board": {
                        "width": 10,
                        "placements": [
                            {"item_instance_id": "a1", "item_definition_id": "quick_jab", "start_slot": 0},
                            {"item_instance_id": "a2", "item_definition_id": "burn_trap", "start_slot": 1},
                            {"item_instance_id": "a3", "item_definition_id": "shield_up", "start_slot": 2},
                        ],
                    },
                    "initial_statuses": [],
                },
                {
                    "player_id": "player_b",
                    "stats": {
                        "max_health": 50,
                        "regeneration_per_second": 0.5,
                    },
                    "board": {
                        "width": 10,
                        "placements": [
                            {"item_instance_id": "b1", "item_definition_id": "quick_jab", "start_slot": 0},
                            {"item_instance_id": "b2", "item_definition_id": "shield_up", "start_slot": 1},
                        ],
                    },
                    "initial_statuses": [],
                },
            ],
        }

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        from app.models.base_models import RunStopReason
        self.assertIn(run.stop_reason, [RunStopReason.NATURAL_WIN, RunStopReason.TIME_LIMIT_EXCEEDED])
        self.assertIn(run.winner_player_id, ["player_a", "player_b", "draw"])
        self.assertGreater(run.metrics.total_events_processed, 0)
        self.assertGreater(len(run.combat_log), 0)

    def test_batch_performance_100_runs_deterministic(self) -> None:
        """Performance: 100 runs complete quickly and produce consistent results."""
        payload = sample_request_payload()
        payload["runs"] = 100
        payload["seed"] = 999
        payload["max_time_seconds"] = 5

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)

        self.assertEqual(len(result.runs), 100)
        self.assertGreater(result.summary.run_count, 0)
        self.assertAlmostEqual(
            result.summary.player_a_win_rate + result.summary.player_b_win_rate + result.summary.draw_rate, 1.0, places=5
        )

        # Verify all runs have stop_reason set
        from app.models.base_models import RunStopReason
        for run in result.runs:
            self.assertIn(run.stop_reason, [RunStopReason.NATURAL_WIN, RunStopReason.TIME_LIMIT_EXCEEDED, RunStopReason.EVENT_LIMIT_EXCEEDED])

    def test_performance_metrics_populated_in_batch_summary(self) -> None:
        """Performance: Batch summary includes performance metrics and stop reason breakdown."""
        payload = sample_request_payload()
        payload["runs"] = 5
        payload["seed"] = 555

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)

        # Verify performance metrics exist and are reasonable
        self.assertIsNotNone(result.summary.performance)
        self.assertGreater(result.summary.performance.total_events_across_batch, 0)
        self.assertGreater(result.summary.performance.average_events_per_run, 0)
        
        # Verify stop_reason_breakdown is populated
        self.assertGreater(len(result.summary.performance.stop_reason_breakdown), 0)
        total_stops = sum(result.summary.performance.stop_reason_breakdown.values())
        self.assertEqual(total_stops, 5)


if __name__ == "__main__":
    unittest.main()
