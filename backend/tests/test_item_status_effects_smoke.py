from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.simulation import run_simulation
from app.models.base_models import SimulationRequest


def _base_player(player_id: str, placements: list[dict]) -> dict:
    return {
        "player_id": player_id,
        "stats": {"max_health": 30},
        "board": {"width": 10, "placements": placements},
        "initial_statuses": [],
    }


class ItemStatusEffectSmokeTests(unittest.TestCase):
    def test_apply_item_slow_emits_modifier_event(self) -> None:
        payload = {
            "seed": 7,
            "runs": 1,
            "max_time_seconds": 1.1,
            "max_events": 200,
            "combat_log_limit": 200,
            "item_definitions": [
                {
                    "id": "slow",
                    "name": "Slow",
                    "size": 1,
                    "cooldown_seconds": 1.0,
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
                    "cooldown_seconds": 5.0,
                    "effects": [
                        {"type": "damage", "target": "opponent", "magnitude": 1.0}
                    ],
                },
            ],
            "players": [
                _base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-slow",
                            "item_definition_id": "slow",
                            "start_slot": 0,
                        }
                    ],
                ),
                _base_player(
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
        }

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request).runs[0]

        slow_events = [e for e in result.combat_log if e.event_type == "item_slow_start"]
        self.assertGreaterEqual(len(slow_events), 1)
        self.assertEqual(slow_events[0].target_id, "b-target")

    def test_apply_item_charge_emits_charge_event(self) -> None:
        payload = {
            "seed": 8,
            "runs": 1,
            "max_time_seconds": 1.1,
            "max_events": 200,
            "combat_log_limit": 200,
            "item_definitions": [
                {
                    "id": "charger",
                    "name": "Charger",
                    "size": 1,
                    "cooldown_seconds": 1.0,
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
                    "effects": [
                        {"type": "damage", "target": "opponent", "magnitude": 1.0}
                    ],
                },
            ],
            "players": [
                _base_player(
                    "player_a",
                    [
                        {
                            "item_instance_id": "a-charger",
                            "item_definition_id": "charger",
                            "start_slot": 0,
                        }
                    ],
                ),
                _base_player(
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
        }

        request = SimulationRequest.model_validate(payload)
        result = run_simulation(request).runs[0]

        charge_events = [e for e in result.combat_log if e.event_type == "item_charge"]
        self.assertGreaterEqual(len(charge_events), 1)
        self.assertEqual(charge_events[0].target_id, "b-target")


if __name__ == "__main__":
    unittest.main()
