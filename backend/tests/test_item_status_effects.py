from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.simulation import run_simulation
from app.models.base_models import SimulationRequest


def build_request_payload(item_definitions: list[dict], players: list[dict]) -> dict:
    return {
        "seed": 123,
        "runs": 1,
        "max_time_seconds": 12,
        "max_events": 2000,
        "combat_log_limit": 2000,
        "item_definitions": item_definitions,
        "players": players,
    }


def base_player(player_id: str, placements: list[dict]) -> dict:
    return {
        "player_id": player_id,
        "stats": {
            "max_health": 50,
        },
        "board": {
            "width": 10,
            "placements": placements,
        },
        "initial_statuses": [],
    }


class ItemStatusEffectTests(unittest.TestCase):
    def test_apply_item_slow_delays_target_cooldown(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "slow_caster",
                    "name": "Slow Caster",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_slow",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "target",
                    "name": "Target",
                    "size": 1,
                    "cooldown_seconds": 2.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "damage",
                            "target": "opponent",
                            "magnitude": 1.0,
                        }
                    ],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-slow",
                            "item_definition_id": "slow_caster",
                            "start_slot": 0,
                        }
                    ],
                ),
                base_player(
                    "player_b",
                    [
                        {
                            "item_instance_id": "b-target",
                            "item_definition_id": "target",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        target_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-target"
        ]
        self.assertGreaterEqual(len(target_uses), 1)
        self.assertEqual(target_uses[0], 5.0)

    def test_apply_item_charge_reduces_remaining_cooldown(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "charger",
                    "name": "Charger",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_charge",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "target",
                    "name": "Target",
                    "size": 1,
                    "cooldown_seconds": 5.0,
                    "initial_delay_seconds": 5.0,
                    "effects": [
                        {
                            "type": "damage",
                            "target": "opponent",
                            "magnitude": 1.0,
                        }
                    ],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-charge",
                            "item_definition_id": "charger",
                            "start_slot": 0,
                        }
                    ],
                ),
                base_player(
                    "player_b",
                    [
                        {
                            "item_instance_id": "b-target",
                            "item_definition_id": "target",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        target_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-target"
        ]
        self.assertGreaterEqual(len(target_uses), 1)
        self.assertEqual(target_uses[0], 3.0)

    def test_apply_item_freeze_pauses_and_resumes_cooldown(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "freezer",
                    "name": "Freezer",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_freeze",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "target",
                    "name": "Target",
                    "size": 1,
                    "cooldown_seconds": 2.0,
                    "initial_delay_seconds": 1.0,
                    "effects": [
                        {
                            "type": "damage",
                            "target": "opponent",
                            "magnitude": 1.0,
                        }
                    ],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-freeze",
                            "item_definition_id": "freezer",
                            "start_slot": 0,
                        }
                    ],
                ),
                base_player(
                    "player_b",
                    [
                        {
                            "item_instance_id": "b-target",
                            "item_definition_id": "target",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        target_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-target"
        ]
        self.assertGreaterEqual(len(target_uses), 1)
        self.assertEqual(target_uses[0], 3.0)

    def test_apply_item_flight_halves_modifier_duration(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "flight",
                    "name": "Flight",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_flight",
                            "target": "opponent_item",
                            "magnitude": 4.0,
                        }
                    ],
                },
                {
                    "id": "slow",
                    "name": "Slow",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 1.0,
                    "effects": [
                        {
                            "type": "apply_item_slow",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "target",
                    "name": "Target",
                    "size": 1,
                    "cooldown_seconds": 4.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "damage",
                            "target": "opponent",
                            "magnitude": 1.0,
                        }
                    ],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-flight",
                            "item_definition_id": "flight",
                            "start_slot": 0,
                        },
                        {
                            "item_instance_id": "a-slow",
                            "item_definition_id": "slow",
                            "start_slot": 1,
                        },
                    ],
                ),
                base_player(
                    "player_b",
                    [
                        {
                            "item_instance_id": "b-target",
                            "item_definition_id": "target",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        target_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-target"
        ]
        self.assertGreaterEqual(len(target_uses), 1)
        self.assertEqual(target_uses[0], 4.5)


if __name__ == "__main__":
    unittest.main()
