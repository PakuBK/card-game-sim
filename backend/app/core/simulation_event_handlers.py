from __future__ import annotations

import heapq
from itertools import count

from app.core.simulation_board import resolve_effect_target
from app.core.simulation_metrics import (
    increment_counter,
    record_damage_to_opponent,
    select_player_metrics,
    track_status_metrics,
)
from app.core.simulation_status import (
    apply_burn_tick_damage,
    apply_damage,
    apply_heal,
    apply_heal_status_reduction,
    apply_health_damage,
    apply_poison_tick_damage,
    reduce_burn_over_time,
    schedule_status,
)
from app.core.simulation_types import (
    BURN_TICK_INTERVAL_SECONDS,
    EVENT_BURN_TICK,
    EVENT_ITEM_USE,
    EVENT_POISON_TICK,
    EVENT_REGEN_TICK,
    POISON_TICK_INTERVAL_SECONDS,
    REGEN_TICK_INTERVAL_SECONDS,
    Event,
    RuntimeBoard,
    RuntimeItem,
    RuntimePlayer,
    make_event,
)
from app.models.base_models import ItemRunMetrics, RunMetrics


def resolve_item_use(
    runtime_item: RuntimeItem,
    owner: RuntimePlayer,
    players: dict[str, RuntimePlayer],
    board_by_player: dict[str, RuntimeBoard],
    metrics: RunMetrics,
    item_metric: ItemRunMetrics | None,
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> str | None:
    item = runtime_item.definition
    owner_metrics = select_player_metrics(metrics, owner.player_id)
    target_player_id: str | None = None

    for effect in item.effects:
        target_player, effect_target_id = resolve_effect_target(
            source_item=runtime_item,
            effect_target=effect.target,
            players=players,
            board_by_player=board_by_player,
        )
        # Track the target player ID (the actual recipient of effects, not the item)
        if target_player_id is None:
            target_player_id = target_player.player_id
        if item_metric is not None:
            increment_counter(item_metric.events_triggered, effect.type.value)

        if effect.type.value == "damage":
            dealt = apply_damage(target_player, effect.magnitude)
            owner.total_damage_done += dealt
            record_damage_to_opponent(
                metrics=metrics,
                players=players,
                source_player_id=owner.player_id,
                target_player_id=target_player.player_id,
                damage_type="direct",
                amount=dealt,
                item_metrics_by_instance=None,
                source_item_instance_id=runtime_item.instance_id,
                fallback_item_metric=item_metric,
            )

        elif effect.type.value == "heal":
            healed = apply_heal(target_player, effect.magnitude)
            owner.total_healing_done += healed
            apply_heal_status_reduction(target_player, healed)

        elif effect.type.value == "shield":
            target_player.shield += effect.magnitude

        elif effect.type.value == "apply_burn":
            track_status_metrics(owner_metrics.status_effects_applied.burn, effect.magnitude)
            target_metrics = select_player_metrics(metrics, target_player.player_id)
            track_status_metrics(target_metrics.status_effects_received.burn, effect.magnitude)
            if item_metric is not None:
                track_status_metrics(item_metric.status_effects_applied.burn, effect.magnitude)
            schedule_status(
                player=target_player,
                status="burn",
                amount=effect.magnitude,
                source_player_id=owner.player_id,
                source_item_instance_id=runtime_item.instance_id,
                current_time=current_time,
                queue=queue,
                sequence=sequence,
            )

        elif effect.type.value == "apply_poison":
            track_status_metrics(owner_metrics.status_effects_applied.poison, effect.magnitude)
            target_metrics = select_player_metrics(metrics, target_player.player_id)
            track_status_metrics(target_metrics.status_effects_received.poison, effect.magnitude)
            if item_metric is not None:
                track_status_metrics(item_metric.status_effects_applied.poison, effect.magnitude)
            schedule_status(
                player=target_player,
                status="poison",
                amount=effect.magnitude,
                source_player_id=owner.player_id,
                source_item_instance_id=runtime_item.instance_id,
                current_time=current_time,
                queue=queue,
                sequence=sequence,
            )

    return target_player_id


def handle_item_use_event(
    *,
    event: Event,
    alive_at_time: set[str],
    players: dict[str, RuntimePlayer],
    runtime_item_lookup: dict[str, RuntimeItem],
    board_by_player: dict[str, RuntimeBoard],
    metrics: RunMetrics,
    item_metrics_by_instance: dict[str, ItemRunMetrics],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> str | None:
    owner_metrics = select_player_metrics(metrics, event.source_id)
    owner_metrics.item_uses += 1
    owner = players[event.source_id]
    log_target_id = event.target_id

    if event.source_id in alive_at_time:
        runtime_item = runtime_item_lookup[event.target_id or ""]
        item_metric = item_metrics_by_instance.get(runtime_item.instance_id)
        if item_metric is not None:
            increment_counter(item_metric.events_triggered, "used")
        resolved_target_id = resolve_item_use(
            runtime_item,
            owner,
            players,
            board_by_player,
            metrics,
            item_metric,
            current_time,
            queue,
            sequence,
        )
        log_target_id = resolved_target_id or runtime_item.instance_id
        heapq.heappush(
            queue,
            make_event(
                time=current_time + runtime_item.definition.cooldown_seconds,
                sequence=sequence,
                event_type=EVENT_ITEM_USE,
                source_id=owner.player_id,
                target_id=runtime_item.instance_id,
                source_item_instance_id=runtime_item.instance_id,
            ),
        )

    return log_target_id


def handle_burn_tick_event(
    *,
    event: Event,
    players: dict[str, RuntimePlayer],
    metrics: RunMetrics,
    item_metrics_by_instance: dict[str, ItemRunMetrics],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    player = players[event.target_id or ""]
    if player.player_id == "player_a":
        metrics.player_a.burn_ticks += 1
    elif player.player_id == "player_b":
        metrics.player_b.burn_ticks += 1

    if player.health > 0 and player.burn > 0:
        burn_damage = apply_burn_tick_damage(player, player.burn)
        burn_damage = apply_health_damage(player, burn_damage)
        record_damage_to_opponent(
            metrics=metrics,
            players=players,
            source_player_id=event.source_id,
            target_player_id=player.player_id,
            damage_type="burn",
            amount=burn_damage,
            item_metrics_by_instance=item_metrics_by_instance,
            source_item_instance_id=event.source_item_instance_id,
        )
        if burn_damage > 0 and event.source_id in players and event.source_id != player.player_id:
            players[event.source_id].total_damage_done += burn_damage
        if event.source_item_instance_id is not None:
            item_metric = item_metrics_by_instance.get(event.source_item_instance_id)
            if item_metric is not None:
                increment_counter(item_metric.events_triggered, EVENT_BURN_TICK)
        player.burn = reduce_burn_over_time(player.burn)
        if player.burn > 0:
            heapq.heappush(
                queue,
                make_event(
                    time=current_time + BURN_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_BURN_TICK,
                    source_id=event.source_id,
                    target_id=player.player_id,
                    source_item_instance_id=event.source_item_instance_id,
                ),
            )


def handle_poison_tick_event(
    *,
    event: Event,
    players: dict[str, RuntimePlayer],
    metrics: RunMetrics,
    item_metrics_by_instance: dict[str, ItemRunMetrics],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    player = players[event.target_id or ""]
    if player.player_id == "player_a":
        metrics.player_a.poison_ticks += 1
    elif player.player_id == "player_b":
        metrics.player_b.poison_ticks += 1

    if player.health > 0 and player.poison > 0:
        poison_damage = apply_poison_tick_damage(player, player.poison)
        poison_damage = apply_health_damage(player, poison_damage)
        record_damage_to_opponent(
            metrics=metrics,
            players=players,
            source_player_id=event.source_id,
            target_player_id=player.player_id,
            damage_type="poison",
            amount=poison_damage,
            item_metrics_by_instance=item_metrics_by_instance,
            source_item_instance_id=event.source_item_instance_id,
        )
        if poison_damage > 0 and event.source_id in players and event.source_id != player.player_id:
            players[event.source_id].total_damage_done += poison_damage
        if event.source_item_instance_id is not None:
            item_metric = item_metrics_by_instance.get(event.source_item_instance_id)
            if item_metric is not None:
                increment_counter(item_metric.events_triggered, EVENT_POISON_TICK)
        if player.poison > 0:
            heapq.heappush(
                queue,
                make_event(
                    time=current_time + POISON_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_POISON_TICK,
                    source_id=event.source_id,
                    target_id=player.player_id,
                    source_item_instance_id=event.source_item_instance_id,
                ),
            )


def handle_regen_tick_event(
    *,
    event: Event,
    players: dict[str, RuntimePlayer],
    metrics: RunMetrics,
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    player = players[event.target_id or ""]
    if player.player_id == "player_a":
        metrics.player_a.regen_ticks += 1
    elif player.player_id == "player_b":
        metrics.player_b.regen_ticks += 1

    if player.health > 0 and player.regeneration_per_second > 0:
        heal_amount = player.regeneration_per_second * REGEN_TICK_INTERVAL_SECONDS
        healed = apply_heal(player, heal_amount)
        player.total_healing_done += healed
        heapq.heappush(
            queue,
            make_event(
                time=current_time + REGEN_TICK_INTERVAL_SECONDS,
                sequence=sequence,
                event_type=EVENT_REGEN_TICK,
                source_id=player.player_id,
                target_id=player.player_id,
            ),
        )
