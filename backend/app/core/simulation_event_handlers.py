from __future__ import annotations

import heapq
from itertools import count
import random
from typing import Any

from app.core.simulation_board import resolve_effect_target, select_target_item_instance_id
from app.core.simulation_item_modifiers import (
    apply_modifier_duration_halving,
)
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
    EVENT_ITEM_CHARGE,
    EVENT_ITEM_FLIGHT_END,
    EVENT_ITEM_FLIGHT_START,
    EVENT_ITEM_FREEZE_END,
    EVENT_ITEM_FREEZE_START,
    EVENT_ITEM_HASTE_END,
    EVENT_ITEM_HASTE_START,
    EVENT_ITEM_SLOW_END,
    EVENT_ITEM_SLOW_START,
    EVENT_ITEM_USE,
    EVENT_POISON_TICK,
    EVENT_REGEN_TICK,
    POISON_TICK_INTERVAL_SECONDS,
    REGEN_TICK_INTERVAL_SECONDS,
    Event,
    RuntimeBoard,
    RuntimeItem,
    RuntimeItemModifier,
    RuntimePlayer,
    make_event,
)
from app.models.base_models import EffectTarget, ItemRunMetrics, RunMetrics


SPEED_MODIFIER_END_EVENTS = {
    "slow": EVENT_ITEM_SLOW_END,
    "haste": EVENT_ITEM_HASTE_END,
    "freeze": EVENT_ITEM_FREEZE_END,
}

SPEED_MODIFIER_VALUES = {
    "slow": 0.5,
    "haste": 2.0,
    "freeze": 0.0,
}

_MODIFIER_TIMER_TRACE: list[dict[str, Any]] = []


def clear_modifier_timer_trace() -> None:
    _MODIFIER_TIMER_TRACE.clear()


def get_modifier_timer_trace() -> list[dict[str, Any]]:
    return list(_MODIFIER_TIMER_TRACE)


def _append_modifier_timer_trace(entry: dict[str, Any]) -> None:
    _MODIFIER_TIMER_TRACE.append(entry)


def _resolve_item_target_id(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
) -> str | None:
    return select_target_item_instance_id(
        source_item=source_item,
        effect_target=effect_target,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
        rng=rng,
    )


def _find_pending_item_use_event(queue: list[Event], runtime_item: RuntimeItem) -> Event | None:
    earliest: Event | None = None
    for queued_event in queue:
        if queued_event.stale:
            continue
        if queued_event.event_type != EVENT_ITEM_USE:
            continue
        if queued_event.target_id != runtime_item.instance_id:
            continue
        if queued_event.source_item_instance_id != runtime_item.instance_id:
            continue
        if earliest is None or queued_event.time < earliest.time:
            earliest = queued_event
    return earliest


def _cleanup_expired_modifier_instances(runtime_item: RuntimeItem, current_time: float) -> None:
    expired_instance_ids = [
        instance_id
        for instance_id, modifier in runtime_item.active_modifiers.items()
        if modifier.end_time < current_time
    ]
    for instance_id in expired_instance_ids:
        del runtime_item.active_modifiers[instance_id]


def get_effective_cooldown_modifier(runtime_item: RuntimeItem, current_time: float) -> float:
    _cleanup_expired_modifier_instances(runtime_item, current_time)

    slow_count = 0
    haste_count = 0
    freeze_active = False

    for modifier in runtime_item.active_modifiers.values():
        if modifier.end_time < current_time:
            continue
        if modifier.modifier_type == "freeze":
            freeze_active = True
        elif modifier.modifier_type == "slow":
            slow_count += 1
        elif modifier.modifier_type == "haste":
            haste_count += 1

    if freeze_active:
        return 0.0

    return (2.0 ** haste_count) * (0.5 ** slow_count)


def _freeze_active_until(runtime_item: RuntimeItem, current_time: float) -> float | None:
    freeze_end_times = [
        modifier.end_time
        for modifier in runtime_item.active_modifiers.values()
        if modifier.modifier_type == "freeze" and modifier.end_time >= current_time
    ]
    if not freeze_end_times:
        return None
    return max(freeze_end_times)


def _calculate_remaining_normal_time(
    *,
    pending_event_time: float,
    current_time: float,
    old_modifier: float,
    frozen_remaining_cooldown: float | None,
) -> float:
    if old_modifier == 0.0:
        if frozen_remaining_cooldown is not None:
            return max(0.0, frozen_remaining_cooldown)
        return max(0.0, pending_event_time - current_time)

    # pending_event_time is in wall-clock time under old_modifier speed.
    # Convert to base remaining cooldown by multiplying by speed multiplier.
    return max(0.0, (pending_event_time - current_time) * old_modifier)


def _reschedule_pending_item_use(
    *,
    runtime_item: RuntimeItem,
    pending_event: Event,
    current_time: float,
    old_modifier: float,
    new_modifier: float,
    queue: list[Event],
    sequence: count,
) -> tuple[float, float]:
    pending_event.stale = True
    remaining_normal = _calculate_remaining_normal_time(
        pending_event_time=pending_event.time,
        current_time=current_time,
        old_modifier=old_modifier,
        frozen_remaining_cooldown=runtime_item.frozen_remaining_cooldown,
    )

    if new_modifier == 0.0:
        runtime_item.frozen_remaining_cooldown = remaining_normal
        freeze_until = _freeze_active_until(runtime_item, current_time) or current_time
        new_event_time = freeze_until + runtime_item.frozen_remaining_cooldown
    else:
        if old_modifier == 0.0 and runtime_item.frozen_remaining_cooldown is not None:
            remaining_normal = runtime_item.frozen_remaining_cooldown
        runtime_item.frozen_remaining_cooldown = None
        new_event_time = current_time + (remaining_normal / new_modifier)

    heapq.heappush(
        queue,
        make_event(
            time=new_event_time,
            sequence=sequence,
            event_type=EVENT_ITEM_USE,
            source_id=runtime_item.owner_id,
            target_id=runtime_item.instance_id,
            source_item_instance_id=runtime_item.instance_id,
        ),
    )
    return (remaining_normal, new_event_time)


def _mark_pending_events_stale(
    queue: list[Event],
    *,
    target_item_id: str,
    event_types: set[str],
) -> None:
    for queued_event in queue:
        if queued_event.stale:
            continue
        if queued_event.target_id != target_item_id:
            continue
        if queued_event.event_type in event_types:
            queued_event.stale = True


def handle_item_charge_event(
    *,
    event: Event,
    runtime_item_lookup: dict[str, RuntimeItem],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    target_item = runtime_item_lookup[event.target_id or ""]
    pending_event = _find_pending_item_use_event(queue, target_item)
    if pending_event is None:
        return

    charge_amount = event.effect_magnitude or 0.0
    if charge_amount <= 0:
        return

    pending_event.stale = True
    old_event_time = pending_event.time
    remaining_cooldown = max(0.0, pending_event.time - current_time - charge_amount)
    new_event_time = current_time + remaining_cooldown

    heapq.heappush(
        queue,
        make_event(
            time=new_event_time,
            sequence=sequence,
            event_type=EVENT_ITEM_USE,
            source_id=target_item.owner_id,
            target_id=target_item.instance_id,
            source_item_instance_id=target_item.instance_id,
        ),
    )

    effective_modifier = get_effective_cooldown_modifier(target_item, current_time)

    _append_modifier_timer_trace(
        {
            "time": round(current_time, 6),
            "operation": "charge",
            "item_id": target_item.instance_id,
            "old_modifier": effective_modifier,
            "new_modifier": effective_modifier,
            "pending_event_before": round(old_event_time, 6),
            "remaining_before": round(max(0.0, old_event_time - current_time), 6),
            "charge_amount": round(charge_amount, 6),
            "pending_event_after": round(new_event_time, 6),
        }
    )


def handle_item_modifier_start_event(
    *,
    event: Event,
    runtime_item_lookup: dict[str, RuntimeItem],
    modifier_type: str,
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    target_item = runtime_item_lookup[event.target_id or ""]
    pending_event = _find_pending_item_use_event(queue, target_item)
    old_modifier = get_effective_cooldown_modifier(target_item, current_time)

    duration_seconds = event.effect_magnitude or 0.0
    is_flying = target_item.flight_end_time is not None and target_item.flight_end_time > current_time
    should_halve_for_flight = modifier_type in {"slow", "freeze"}
    effective_duration = (
        apply_modifier_duration_halving(duration_seconds, is_flying)
        if should_halve_for_flight
        else duration_seconds
    )

    modifier_instance_id = (
        event.modifier_instance_id
        or f"{modifier_type}:{event.source_item_instance_id or 'unknown'}:{event.sequence}"
    )
    target_item.active_modifiers[modifier_instance_id] = RuntimeItemModifier(
        instance_id=modifier_instance_id,
        modifier_type=modifier_type,
        start_time=current_time,
        end_time=current_time + effective_duration,
        source_item_instance_id=event.source_item_instance_id,
    )

    new_modifier = get_effective_cooldown_modifier(target_item, current_time)

    if pending_event is not None and (old_modifier != new_modifier or modifier_type == "freeze"):
        remaining_normal, new_event_time = _reschedule_pending_item_use(
            runtime_item=target_item,
            pending_event=pending_event,
            current_time=current_time,
            old_modifier=old_modifier,
            new_modifier=new_modifier,
            queue=queue,
            sequence=sequence,
        )
        _append_modifier_timer_trace(
            {
                "time": round(current_time, 6),
                "operation": "modifier_start",
                "modifier": modifier_type,
                "modifier_instance_id": modifier_instance_id,
                "item_id": target_item.instance_id,
                "old_modifier": old_modifier,
                "new_modifier": new_modifier,
                "duration": round(effective_duration, 6),
                "pending_event_before": round(pending_event.time, 6),
                "remaining_normal": round(remaining_normal, 6),
                "pending_event_after": round(new_event_time, 6),
            }
        )

    if modifier_type not in SPEED_MODIFIER_END_EVENTS:
        return

    end_event_type = SPEED_MODIFIER_END_EVENTS[modifier_type]
    heapq.heappush(
        queue,
        make_event(
            time=current_time + effective_duration,
            sequence=sequence,
            event_type=end_event_type,
            source_id=event.source_id,
            target_id=target_item.instance_id,
            source_item_instance_id=event.source_item_instance_id,
            effect_magnitude=duration_seconds,
            modifier_instance_id=modifier_instance_id,
        ),
    )


def handle_item_modifier_end_event(
    *,
    event: Event,
    runtime_item_lookup: dict[str, RuntimeItem],
    modifier_type: str,
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    target_item = runtime_item_lookup[event.target_id or ""]
    pending_event = _find_pending_item_use_event(queue, target_item)
    old_modifier = get_effective_cooldown_modifier(target_item, current_time)

    modifier_instance_id = event.modifier_instance_id
    if modifier_instance_id is None:
        return
    removed = target_item.active_modifiers.pop(modifier_instance_id, None)
    if removed is None:
        return

    new_modifier = get_effective_cooldown_modifier(target_item, current_time)

    if pending_event is not None and (old_modifier != new_modifier or modifier_type == "freeze"):
        remaining_normal, new_event_time = _reschedule_pending_item_use(
            runtime_item=target_item,
            pending_event=pending_event,
            current_time=current_time,
            old_modifier=old_modifier,
            new_modifier=new_modifier,
            queue=queue,
            sequence=sequence,
        )
        _append_modifier_timer_trace(
            {
                "time": round(current_time, 6),
                "operation": "modifier_end",
                "modifier": modifier_type,
                "modifier_instance_id": modifier_instance_id,
                "item_id": target_item.instance_id,
                "old_modifier": old_modifier,
                "new_modifier": new_modifier,
                "pending_event_before": round(pending_event.time, 6),
                "remaining_normal": round(remaining_normal, 6),
                "pending_event_after": round(new_event_time, 6),
            }
        )


def handle_item_flight_start_event(
    *,
    event: Event,
    runtime_item_lookup: dict[str, RuntimeItem],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    target_item = runtime_item_lookup[event.target_id or ""]
    target_item.flight_end_time = current_time + (event.effect_magnitude or 0.0)

    _mark_pending_events_stale(
        queue,
        target_item_id=target_item.instance_id,
        event_types={EVENT_ITEM_FLIGHT_END},
    )

    heapq.heappush(
        queue,
        make_event(
            time=target_item.flight_end_time,
            sequence=sequence,
            event_type=EVENT_ITEM_FLIGHT_END,
            source_id=event.source_id,
            target_id=target_item.instance_id,
            source_item_instance_id=event.source_item_instance_id,
            effect_magnitude=event.effect_magnitude,
        ),
    )


def handle_item_flight_end_event(
    *,
    event: Event,
    runtime_item_lookup: dict[str, RuntimeItem],
    current_time: float,
) -> None:
    target_item = runtime_item_lookup[event.target_id or ""]
    if target_item.flight_end_time is not None and target_item.flight_end_time > current_time:
        return

    target_item.flight_end_time = None


def resolve_item_use(
    runtime_item: RuntimeItem,
    owner: RuntimePlayer,
    players: dict[str, RuntimePlayer],
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    metrics: RunMetrics,
    item_metric: ItemRunMetrics | None,
    current_time: float,
    queue: list[Event],
    sequence: count,
    rng: random.Random,
) -> str | None:
    item = runtime_item.definition
    owner_metrics = select_player_metrics(metrics, owner.player_id)
    target_player_id: str | None = None

    for effect in item.effects:
        effect_type = effect.type.value
        target_player, effect_target_id = resolve_effect_target(
            source_item=runtime_item,
            effect_target=effect.target,
            players=players,
            board_by_player=board_by_player,
            runtime_item_lookup=runtime_item_lookup,
            rng=rng,
        )
        if effect_target_id is None and effect.target != EffectTarget.SELF and effect.target != EffectTarget.OPPONENT:
            continue
        # Track the target player ID (the actual recipient of effects, not the item)
        if target_player_id is None:
            target_player_id = target_player.player_id
        if item_metric is not None:
            increment_counter(item_metric.events_triggered, effect_type)

        if effect_type == "damage":
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

        elif effect_type == "heal":
            healed = apply_heal(target_player, effect.magnitude)
            owner.total_healing_done += healed
            apply_heal_status_reduction(target_player, healed)

        elif effect_type == "shield":
            target_player.shield += effect.magnitude

        elif effect_type == "apply_burn":
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

        elif effect_type == "apply_poison":
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

        elif effect_type in {"apply_item_slow", "apply_item_haste", "apply_item_freeze"}:
            target_item_id = _resolve_item_target_id(
                source_item=runtime_item,
                effect_target=effect.target,
                board_by_player=board_by_player,
                runtime_item_lookup=runtime_item_lookup,
                rng=rng,
            )
            if target_item_id is not None:
                event_type = {
                    "apply_item_slow": EVENT_ITEM_SLOW_START,
                    "apply_item_haste": EVENT_ITEM_HASTE_START,
                    "apply_item_freeze": EVENT_ITEM_FREEZE_START,
                }[effect_type]
                heapq.heappush(
                    queue,
                    make_event(
                        time=current_time,
                        sequence=sequence,
                        event_type=event_type,
                        source_id=owner.player_id,
                        target_id=target_item_id,
                        source_item_instance_id=runtime_item.instance_id,
                        effect_magnitude=effect.magnitude,
                    ),
                )

        elif effect_type == "apply_item_flight":
            target_item_id = _resolve_item_target_id(
                source_item=runtime_item,
                effect_target=effect.target,
                board_by_player=board_by_player,
                runtime_item_lookup=runtime_item_lookup,
                rng=rng,
            )
            if target_item_id is not None:
                heapq.heappush(
                    queue,
                    make_event(
                        time=current_time,
                        sequence=sequence,
                        event_type=EVENT_ITEM_FLIGHT_START,
                        source_id=owner.player_id,
                        target_id=target_item_id,
                        source_item_instance_id=runtime_item.instance_id,
                        effect_magnitude=effect.magnitude,
                    ),
                )

        elif effect_type == "apply_item_charge":
            target_item_id = _resolve_item_target_id(
                source_item=runtime_item,
                effect_target=effect.target,
                board_by_player=board_by_player,
                runtime_item_lookup=runtime_item_lookup,
                rng=rng,
            )
            if target_item_id is not None:
                heapq.heappush(
                    queue,
                    make_event(
                        time=current_time,
                        sequence=sequence,
                        event_type=EVENT_ITEM_CHARGE,
                        source_id=owner.player_id,
                        target_id=target_item_id,
                        source_item_instance_id=runtime_item.instance_id,
                        effect_magnitude=effect.magnitude,
                    ),
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
    rng: random.Random,
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
            runtime_item_lookup,
            metrics,
            item_metric,
            current_time,
            queue,
            sequence,
            rng,
        )
        log_target_id = resolved_target_id or runtime_item.instance_id
        cooldown_modifier = get_effective_cooldown_modifier(runtime_item, current_time)
        if cooldown_modifier <= 0:
            next_use_time = current_time + runtime_item.definition.cooldown_seconds
        else:
            next_use_time = current_time + (
                runtime_item.definition.cooldown_seconds / cooldown_modifier
            )
        heapq.heappush(
            queue,
            make_event(
                time=next_use_time,
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
