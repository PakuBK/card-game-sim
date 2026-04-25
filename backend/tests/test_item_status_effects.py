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
    def test_enemy_left_most_targets_left_edge_item(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "left-lock",
                    "name": "Left Lock",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_slow",
                            "target": "enemy_left_most",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "small",
                    "name": "Small",
                    "size": 1,
                    "cooldown_seconds": 8.0,
                    "effects": [{"type": "damage", "target": "opponent", "magnitude": 1.0}],
                },
                {
                    "id": "large",
                    "name": "Large",
                    "size": 3,
                    "cooldown_seconds": 8.0,
                    "effects": [{"type": "damage", "target": "opponent", "magnitude": 1.0}],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [{"item_instance_id": "a-lock", "item_definition_id": "left-lock", "start_slot": 0}],
                ),
                base_player(
                    "player_b",
                    [
                        {"item_instance_id": "b-left", "item_definition_id": "small", "start_slot": 0},
                        {"item_instance_id": "b-right", "item_definition_id": "large", "start_slot": 4},
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        slow_events = [entry for entry in run.combat_log if entry.event_type == "item_slow_start"]
        self.assertGreaterEqual(len(slow_events), 1)
        self.assertEqual(slow_events[0].target_id, "b-left")

    def test_enemy_small_item_targets_only_size_one_items(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "small-lock",
                    "name": "Small Lock",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 0.0,
                    "effects": [
                        {
                            "type": "apply_item_haste",
                            "target": "enemy_small_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "small",
                    "name": "Small",
                    "size": 1,
                    "cooldown_seconds": 8.0,
                    "effects": [{"type": "damage", "target": "opponent", "magnitude": 1.0}],
                },
                {
                    "id": "medium",
                    "name": "Medium",
                    "size": 2,
                    "cooldown_seconds": 8.0,
                    "effects": [{"type": "damage", "target": "opponent", "magnitude": 1.0}],
                },
            ],
            players=[
                base_player(
                    "player_a",
                    [{"item_instance_id": "a-lock", "item_definition_id": "small-lock", "start_slot": 0}],
                ),
                base_player(
                    "player_b",
                    [
                        {"item_instance_id": "b-small", "item_definition_id": "small", "start_slot": 0},
                        {"item_instance_id": "b-medium", "item_definition_id": "medium", "start_slot": 3},
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        haste_events = [entry for entry in run.combat_log if entry.event_type == "item_haste_start"]
        self.assertGreaterEqual(len(haste_events), 1)
        self.assertEqual(haste_events[0].target_id, "b-small")

    def test_slow_and_haste_overlap_cancel_to_normal_speed(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "slow_caster",
                    "name": "Slow Caster",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "apply_item_slow",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "engine",
                    "name": "Engine",
                    "size": 1,
                    "cooldown_seconds": 4.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "apply_item_haste",
                            "target": "self_item",
                            "magnitude": 2.0,
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
                            "item_instance_id": "b-engine",
                            "item_definition_id": "engine",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        engine_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-engine"
        ]
        self.assertGreaterEqual(len(engine_uses), 2)
        self.assertEqual(engine_uses[0], 4.0)
        self.assertEqual(engine_uses[1], 8.0)

    def test_freeze_and_haste_overlap_keeps_item_paused(self) -> None:
        payload = build_request_payload(
            item_definitions=[
                {
                    "id": "freeze_caster",
                    "name": "Freeze Caster",
                    "size": 1,
                    "cooldown_seconds": 99.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "apply_item_freeze",
                            "target": "opponent_item",
                            "magnitude": 2.0,
                        }
                    ],
                },
                {
                    "id": "engine",
                    "name": "Engine",
                    "size": 1,
                    "cooldown_seconds": 4.0,
                    "initial_delay_seconds": 4.0,
                    "effects": [
                        {
                            "type": "apply_item_haste",
                            "target": "self_item",
                            "magnitude": 2.0,
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
                            "item_definition_id": "freeze_caster",
                            "start_slot": 0,
                        }
                    ],
                ),
                base_player(
                    "player_b",
                    [
                        {
                            "item_instance_id": "b-engine",
                            "item_definition_id": "engine",
                            "start_slot": 0,
                        }
                    ],
                ),
            ],
        )

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request)
        run = result.runs[0]

        engine_uses = [
            entry.time_seconds
            for entry in run.combat_log
            if entry.event_type == "item_use" and entry.source_item_instance_id == "b-engine"
        ]
        self.assertGreaterEqual(len(engine_uses), 2)
        self.assertEqual(engine_uses[0], 4.0)
        self.assertEqual(engine_uses[1], 10.0)

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
