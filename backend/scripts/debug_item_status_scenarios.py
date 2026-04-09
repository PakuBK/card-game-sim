from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.simulation import run_simulation
from app.core.simulation_event_handlers import clear_modifier_timer_trace, get_modifier_timer_trace
from app.models.base_models import SimulationRequest

ITEM_STATUS_EVENT_TYPES = {
    "item_charge",
    "item_slow_start",
    "item_slow_end",
    "item_haste_start",
    "item_haste_end",
    "item_freeze_start",
    "item_freeze_end",
    "item_flight_start",
    "item_flight_end",
}


def _base_player(player_id: str, placements: list[dict[str, Any]]) -> dict[str, Any]:
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


def _request(item_definitions: list[dict[str, Any]], players: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "seed": 123,
        "runs": 1,
        "max_time_seconds": 12,
        "max_events": 2000,
        "combat_log_limit": 5000,
        "item_definitions": item_definitions,
        "players": players,
    }


def scenario_slow_basic() -> dict[str, Any]:
    return _request(
        item_definitions=[
            {
                "id": "slow_caster",
                "name": "Slow Caster",
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
            _base_player(
                "player_a",
                [
                    {
                        "item_instance_id": "a-slow",
                        "item_definition_id": "slow_caster",
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
    )


def scenario_charge_basic() -> dict[str, Any]:
    return _request(
        item_definitions=[
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
            _base_player(
                "player_a",
                [
                    {
                        "item_instance_id": "a-charge",
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
    )


def scenario_freeze_basic() -> dict[str, Any]:
    return _request(
        item_definitions=[
            {
                "id": "freezer",
                "name": "Freezer",
                "size": 1,
                "cooldown_seconds": 1.0,
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
            _base_player(
                "player_a",
                [
                    {
                        "item_instance_id": "a-freeze",
                        "item_definition_id": "freezer",
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
    )


def scenario_flight_halving() -> dict[str, Any]:
    return _request(
        item_definitions=[
            {
                "id": "flight",
                "name": "Flight",
                "size": 1,
                "cooldown_seconds": 1.0,
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
                "cooldown_seconds": 1.0,
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
            _base_player(
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
    )


SCENARIOS = {
    "slow_basic": scenario_slow_basic,
    "charge_basic": scenario_charge_basic,
    "freeze_basic": scenario_freeze_basic,
    "flight_halving": scenario_flight_halving,
}


def _print_header(name: str) -> None:
    print("=" * 80)
    print(f"Scenario: {name}")
    print("=" * 80)


def _print_summary(run_result: Any) -> None:
    print(
        f"winner={run_result.winner_player_id} "
        f"duration={run_result.duration_seconds} "
        f"stop_reason={run_result.stop_reason.value} "
        f"events={run_result.metrics.total_events_processed}"
    )


def _print_item_use_schedule(run_result: Any) -> None:
    uses_by_item: dict[str, list[float]] = defaultdict(list)
    for entry in run_result.combat_log:
        if entry.event_type != "item_use" or entry.source_item_instance_id is None:
            continue
        uses_by_item[entry.source_item_instance_id].append(entry.time_seconds)

    print("\nItem-use timeline:")
    if not uses_by_item:
        print("  (none)")
        return

    for item_id in sorted(uses_by_item.keys()):
        times = ", ".join(f"{t:.3f}" for t in uses_by_item[item_id])
        print(f"  {item_id}: [{times}]")


def _print_status_events(run_result: Any) -> None:
    print("\nItem status events:")
    found = False
    for entry in run_result.combat_log:
        if entry.event_type not in ITEM_STATUS_EVENT_TYPES:
            continue
        found = True
        print(
            f"  t={entry.time_seconds:>6.3f} "
            f"{entry.event_type:<18} "
            f"source_item={entry.source_item_instance_id or '-'} "
            f"target={entry.target_id or '-'}"
        )

    if not found:
        print("  (none)")


def _print_full_log(run_result: Any, event_limit: int) -> None:
    print("\nCombat log:")
    for index, entry in enumerate(run_result.combat_log[:event_limit]):
        print(
            f"  #{index:03d} t={entry.time_seconds:>6.3f} "
            f"{entry.event_type:<18} "
            f"source={entry.source_player_id:<8} "
            f"source_item={entry.source_item_instance_id or '-':<10} "
            f"target={entry.target_id or '-'}"
        )

    if len(run_result.combat_log) > event_limit:
        print(f"  ... truncated: showing first {event_limit} of {len(run_result.combat_log)} events")


def _print_timer_trace() -> None:
    trace = get_modifier_timer_trace()
    print("\nModifier timer trace:")
    if not trace:
        print("  (none)")
        return

    for index, entry in enumerate(trace):
        time_value = entry.get("time")
        operation = entry.get("operation", "-")
        modifier = entry.get("modifier", "-")
        item_id = entry.get("item_id", "-")
        old_modifier = entry.get("old_modifier")
        new_modifier = entry.get("new_modifier")
        pending_before = entry.get("pending_event_before")
        remaining_normal = entry.get("remaining_normal")
        pending_after = entry.get("pending_event_after")
        charge_amount = entry.get("charge_amount")

        print(
            f"  #{index:03d} t={time_value} op={operation:<14} mod={modifier:<6} "
            f"item={item_id:<10} old={old_modifier} new={new_modifier} "
            f"pending_before={pending_before} remaining={remaining_normal} "
            f"charge={charge_amount} pending_after={pending_after}"
        )


def run_debug_scenario(name: str, show_full_log: bool, event_limit: int, verbose_timers: bool) -> None:
    payload = SCENARIOS[name]()
    request = SimulationRequest.model_validate(payload)
    clear_modifier_timer_trace()
    response = run_simulation(request)
    run_result = response.runs[0]

    _print_header(name)
    _print_summary(run_result)
    _print_item_use_schedule(run_result)
    _print_status_events(run_result)

    if verbose_timers:
        _print_timer_trace()

    if show_full_log:
        _print_full_log(run_result, event_limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic item-status debug scenarios and print concise combat timelines."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS.keys()],
        default="all",
        help="Scenario to run. Default: all",
    )
    parser.add_argument(
        "--full-log",
        action="store_true",
        help="Print full combat log entries in addition to summary timelines.",
    )
    parser.add_argument(
        "--event-limit",
        type=int,
        default=120,
        help="Maximum combat log entries to print when --full-log is enabled.",
    )
    parser.add_argument(
        "--verbose-timers",
        action="store_true",
        help="Print internal modifier timer math trace entries.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scenario == "all":
        scenario_names = list(SCENARIOS.keys())
    else:
        scenario_names = [args.scenario]

    for index, name in enumerate(scenario_names):
        if index > 0:
            print()
        run_debug_scenario(
            name=name,
            show_full_log=args.full_log,
            event_limit=args.event_limit,
            verbose_timers=args.verbose_timers,
        )


if __name__ == "__main__":
    main()
