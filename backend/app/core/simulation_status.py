from __future__ import annotations

import heapq
from itertools import count
from math import ceil

from app.core.simulation_types import (
    BURN_TICK_INTERVAL_SECONDS,
    EVENT_BURN_TICK,
    EVENT_POISON_TICK,
    POISON_TICK_INTERVAL_SECONDS,
    RuntimePlayer,
    make_event,
)
from app.models.base_models import InitialStatus


def schedule_status(
    player: RuntimePlayer,
    status: str,
    amount: float,
    source_player_id: str,
    source_item_instance_id: str | None,
    current_time: float,
    queue: list,
    sequence: count,
) -> None:
    if status == "burn":
        was_zero = player.burn <= 0
        player.burn += amount
        if was_zero:
            heapq.heappush(
                queue,
                make_event(
                    time=current_time + BURN_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_BURN_TICK,
                    source_id=source_player_id,
                    target_id=player.player_id,
                    source_item_instance_id=source_item_instance_id,
                ),
            )

    elif status == "poison":
        was_zero = player.poison <= 0
        player.poison += amount
        if was_zero:
            heapq.heappush(
                queue,
                make_event(
                    time=current_time + POISON_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_POISON_TICK,
                    source_id=source_player_id,
                    target_id=player.player_id,
                    source_item_instance_id=source_item_instance_id,
                ),
            )


def apply_initial_statuses(player: RuntimePlayer, statuses: list[InitialStatus]) -> None:
    for status in statuses:
        if status.type.value == "burn":
            player.burn += status.value
        elif status.type.value == "poison":
            player.poison += status.value


def apply_damage(player: RuntimePlayer, amount: float) -> float:
    remaining = amount
    if player.shield > 0:
        absorbed = min(player.shield, remaining)
        player.shield -= absorbed
        remaining -= absorbed

    dealt = 0.0
    if remaining > 0:
        original_health = player.health
        player.health = max(0.0, player.health - remaining)
        dealt = original_health - player.health

    return dealt


def apply_burn_tick_damage(player: RuntimePlayer, burn_value: float) -> float:
    shield_block = min(player.shield, burn_value)
    return burn_value - (shield_block / 2)


def apply_poison_tick_damage(player: RuntimePlayer, poison_value: float) -> float:
    return poison_value


def apply_health_damage(player: RuntimePlayer, amount: float) -> float:
    if amount <= 0:
        return 0.0

    original_health = player.health
    player.health = max(0.0, player.health - amount)
    return original_health - player.health


def reduce_burn_over_time(current_burn: float) -> float:
    if current_burn <= 0:
        return 0.0

    burn_decay = max(1.0, ceil(current_burn * 0.03))
    return max(0.0, current_burn - burn_decay)


def apply_heal_status_reduction(player: RuntimePlayer, healed_amount: float) -> None:
    if healed_amount <= 0:
        return

    status_reduction = healed_amount * 0.05
    player.burn = max(0.0, player.burn - status_reduction)
    player.poison = max(0.0, player.poison - status_reduction)


def apply_heal(player: RuntimePlayer, amount: float) -> float:
    original_health = player.health
    player.health = min(player.max_health, player.health + amount)
    return player.health - original_health
