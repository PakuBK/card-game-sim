from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import count
from statistics import mean, median

from app.models.base_models import (
    BatchSummary,
    BoardItemPlacement,
    DamageBreakdown,
    EffectTarget,
    EffectType,
    InitialStatus,
    ItemDefinition,
    ItemRunMetrics,
    NumericSummary,
    PlayerEventMetrics,
    PlayerRunState,
    RunMetrics,
    StatusEffectMetrics,
    SimulationRequest,
    SimulationResponse,
    SimulationRunResult,
)
from app.core.errors import SimulationInputError

BURN_TICK_INTERVAL_SECONDS = 0.5
POISON_TICK_INTERVAL_SECONDS = 1.0
REGEN_TICK_INTERVAL_SECONDS = 1.0

EVENT_ITEM_USE = "item_use"
EVENT_BURN_TICK = "burn_tick"
EVENT_POISON_TICK = "poison_tick"
EVENT_REGEN_TICK = "regen_tick"

EVENT_TYPE_PRIORITY: dict[str, int] = {
    EVENT_ITEM_USE: 0,
    EVENT_BURN_TICK: 1,
    EVENT_POISON_TICK: 2,
    EVENT_REGEN_TICK: 3,
}

PLAYER_EVENT_ORDER: dict[str, int] = {
    "player_a": 0,
    "player_b": 1,
}


@dataclass
class RuntimePlayer:
    player_id: str
    max_health: float
    health: float
    shield: float
    regeneration_per_second: float
    burn: float
    poison: float
    total_damage_done: float = 0.0
    total_healing_done: float = 0.0


@dataclass
class RuntimeItem:
    instance_id: str
    owner_id: str
    definition: ItemDefinition


@dataclass(order=True)
class Event:
    time: float
    priority: int
    source_order: int
    target_order: str
    sequence: int
    event_type: str = field(compare=False)
    source_id: str = field(compare=False)
    target_id: str | None = field(compare=False)
    source_item_instance_id: str | None = field(default=None, compare=False)


def make_event(
    *,
    time: float,
    sequence: count,
    event_type: str,
    source_id: str,
    target_id: str | None,
    source_item_instance_id: str | None = None,
) -> Event:
    return Event(
        time=time,
        priority=EVENT_TYPE_PRIORITY.get(event_type, 99),
        source_order=PLAYER_EVENT_ORDER.get(source_id, 99),
        target_order=target_id or "",
        sequence=next(sequence),
        event_type=event_type,
        source_id=source_id,
        target_id=target_id,
        source_item_instance_id=source_item_instance_id,
    )


def run_simulation(request: SimulationRequest) -> SimulationResponse:
    run_results = [simulate_single_run(request, run_index) for run_index in range(request.runs)]

    winner_counts = {"player_a": 0, "player_b": 0, "draw": 0}
    durations = []
    for result in run_results:
        winner_counts[result.winner_player_id] += 1
        durations.append(result.duration_seconds)

    summary = BatchSummary(
        run_count=request.runs,
        player_a_win_rate=winner_counts["player_a"] / request.runs,
        player_b_win_rate=winner_counts["player_b"] / request.runs,
        draw_rate=winner_counts["draw"] / request.runs,
        duration_seconds=build_numeric_summary(durations),
    )

    return SimulationResponse(runs=run_results, summary=summary)


def simulate_single_run(request: SimulationRequest, run_index: int) -> SimulationRunResult:
    item_lookup = {item.id: item for item in request.item_definitions}

    players: dict[str, RuntimePlayer] = {}
    runtime_items: list[RuntimeItem] = []

    for player_cfg in request.players:
        players[player_cfg.player_id] = RuntimePlayer(
            player_id=player_cfg.player_id,
            max_health=player_cfg.stats.max_health,
            health=player_cfg.stats.start_health or player_cfg.stats.max_health,
            shield=player_cfg.stats.start_shield,
            regeneration_per_second=player_cfg.stats.regeneration_per_second,
            burn=0.0,
            poison=0.0,
        )

        apply_initial_statuses(players[player_cfg.player_id], player_cfg.initial_statuses)

        for placement in player_cfg.board.placements:
            runtime_items.append(
                RuntimeItem(
                    instance_id=placement.item_instance_id,
                    owner_id=player_cfg.player_id,
                    definition=resolve_item_definition(item_lookup, placement),
                )
            )

    validate_board_layouts(request, item_lookup)

    queue: list[Event] = []
    sequence = count()

    runtime_item_lookup = {item.instance_id: item for item in runtime_items}

    metrics = RunMetrics(
        total_events_processed=0,
        player_a=PlayerEventMetrics(item_uses=0, burn_ticks=0, poison_ticks=0, regen_ticks=0),
        player_b=PlayerEventMetrics(item_uses=0, burn_ticks=0, poison_ticks=0, regen_ticks=0),
    )

    item_metrics_by_instance: dict[str, ItemRunMetrics] = {}
    for item in runtime_items:
        item_metric = ItemRunMetrics(
            item_instance_id=item.instance_id,
            item_definition_id=item.definition.id,
            owner_player_id=item.owner_id,
        )
        item_metrics_by_instance[item.instance_id] = item_metric
        owner_metrics = select_player_metrics(metrics, item.owner_id)
        owner_metrics.item_metrics.append(item_metric)

    for item in runtime_items:
        initial_delay = item.definition.initial_delay_seconds
        first_use_time = initial_delay if initial_delay is not None else item.definition.cooldown_seconds
        heapq.heappush(
            queue,
            make_event(
                time=first_use_time,
                sequence=sequence,
                event_type=EVENT_ITEM_USE,
                source_id=item.owner_id,
                target_id=item.instance_id,
                source_item_instance_id=item.instance_id,
            ),
        )

    for player in players.values():
        if player.burn > 0:
            heapq.heappush(
                queue,
                make_event(
                    time=BURN_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_BURN_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )
        if player.poison > 0:
            heapq.heappush(
                queue,
                make_event(
                    time=POISON_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_POISON_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )
        if player.regeneration_per_second > 0:
            heapq.heappush(
                queue,
                make_event(
                    time=REGEN_TICK_INTERVAL_SECONDS,
                    sequence=sequence,
                    event_type=EVENT_REGEN_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )

    current_time = 0.0
    winner = "draw"

    while queue and metrics.total_events_processed < request.max_events:
        event = heapq.heappop(queue)
        if event.time > request.max_time_seconds:
            current_time = request.max_time_seconds
            break

        current_time = event.time
        remaining_event_budget = request.max_events - metrics.total_events_processed
        same_time_events = [event]
        while (
            queue
            and queue[0].time == current_time
            and len(same_time_events) < remaining_event_budget
        ):
            same_time_events.append(heapq.heappop(queue))

        alive_at_time = {player_id for player_id, player in players.items() if player.health > 0}
        for same_time_event in same_time_events:
            metrics.total_events_processed += 1

            if same_time_event.event_type == EVENT_ITEM_USE:
                owner_metrics = select_player_metrics(metrics, same_time_event.source_id)
                owner_metrics.item_uses += 1
                owner = players[same_time_event.source_id]
                if same_time_event.source_id in alive_at_time:
                    runtime_item = runtime_item_lookup[same_time_event.target_id or ""]
                    item_metric = item_metrics_by_instance.get(runtime_item.instance_id)
                    if item_metric is not None:
                        increment_counter(item_metric.events_triggered, "used")
                    resolve_item_use(
                        runtime_item,
                        owner,
                        players,
                        metrics,
                        item_metric,
                        current_time,
                        queue,
                        sequence,
                    )
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

            elif same_time_event.event_type == EVENT_BURN_TICK:
                player = players[same_time_event.target_id or ""]
                if player.player_id == "player_a":
                    metrics.player_a.burn_ticks += 1
                elif player.player_id == "player_b":
                    metrics.player_b.burn_ticks += 1
                if player.health > 0 and player.burn > 0:
                    burn_damage = apply_damage(player, player.burn)
                    record_damage_to_opponent(
                        metrics=metrics,
                        players=players,
                        source_player_id=same_time_event.source_id,
                        target_player_id=player.player_id,
                        damage_type="burn",
                        amount=burn_damage,
                        item_metrics_by_instance=item_metrics_by_instance,
                        source_item_instance_id=same_time_event.source_item_instance_id,
                    )
                    if (
                        burn_damage > 0
                        and same_time_event.source_id in players
                        and same_time_event.source_id != player.player_id
                    ):
                        players[same_time_event.source_id].total_damage_done += burn_damage
                    if same_time_event.source_item_instance_id is not None:
                        item_metric = item_metrics_by_instance.get(same_time_event.source_item_instance_id)
                        if item_metric is not None:
                            increment_counter(item_metric.events_triggered, EVENT_BURN_TICK)
                    player.burn = max(0.0, player.burn - 1)
                    if player.burn > 0:
                        heapq.heappush(
                            queue,
                            make_event(
                                time=current_time + BURN_TICK_INTERVAL_SECONDS,
                                sequence=sequence,
                                event_type=EVENT_BURN_TICK,
                                source_id=same_time_event.source_id,
                                target_id=player.player_id,
                                source_item_instance_id=same_time_event.source_item_instance_id,
                            ),
                        )

            elif same_time_event.event_type == EVENT_POISON_TICK:
                player = players[same_time_event.target_id or ""]
                if player.player_id == "player_a":
                    metrics.player_a.poison_ticks += 1
                elif player.player_id == "player_b":
                    metrics.player_b.poison_ticks += 1
                if player.health > 0 and player.poison > 0:
                    poison_damage = apply_damage(player, player.poison)
                    record_damage_to_opponent(
                        metrics=metrics,
                        players=players,
                        source_player_id=same_time_event.source_id,
                        target_player_id=player.player_id,
                        damage_type="poison",
                        amount=poison_damage,
                        item_metrics_by_instance=item_metrics_by_instance,
                        source_item_instance_id=same_time_event.source_item_instance_id,
                    )
                    if (
                        poison_damage > 0
                        and same_time_event.source_id in players
                        and same_time_event.source_id != player.player_id
                    ):
                        players[same_time_event.source_id].total_damage_done += poison_damage
                    if same_time_event.source_item_instance_id is not None:
                        item_metric = item_metrics_by_instance.get(same_time_event.source_item_instance_id)
                        if item_metric is not None:
                            increment_counter(item_metric.events_triggered, EVENT_POISON_TICK)
                    player.poison = max(0.0, player.poison - 1)
                    if player.poison > 0:
                        heapq.heappush(
                            queue,
                            make_event(
                                time=current_time + POISON_TICK_INTERVAL_SECONDS,
                                sequence=sequence,
                                event_type=EVENT_POISON_TICK,
                                source_id=same_time_event.source_id,
                                target_id=player.player_id,
                                source_item_instance_id=same_time_event.source_item_instance_id,
                            ),
                        )

            elif same_time_event.event_type == EVENT_REGEN_TICK:
                player = players[same_time_event.target_id or ""]
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

        living_players = [p for p in players.values() if p.health > 0]
        if len(living_players) <= 1:
            winner = living_players[0].player_id if living_players else "draw"
            break

    if winner == "draw":
        player_a_alive = players["player_a"].health > 0
        player_b_alive = players["player_b"].health > 0
        if player_a_alive and not player_b_alive:
            winner = "player_a"
        elif player_b_alive and not player_a_alive:
            winner = "player_b"

    return SimulationRunResult(
        run_index=run_index,
        seed_used=request.seed + run_index,
        winner_player_id=winner,
        duration_seconds=round(current_time, 6),
        players=[
            PlayerRunState(
                player_id="player_a",
                health=round(players["player_a"].health, 6),
                shield=round(players["player_a"].shield, 6),
                burn=round(players["player_a"].burn, 6),
                poison=round(players["player_a"].poison, 6),
                total_damage_done=round(players["player_a"].total_damage_done, 6),
                total_healing_done=round(players["player_a"].total_healing_done, 6),
            ),
            PlayerRunState(
                player_id="player_b",
                health=round(players["player_b"].health, 6),
                shield=round(players["player_b"].shield, 6),
                burn=round(players["player_b"].burn, 6),
                poison=round(players["player_b"].poison, 6),
                total_damage_done=round(players["player_b"].total_damage_done, 6),
                total_healing_done=round(players["player_b"].total_healing_done, 6),
            ),
        ],
        metrics=metrics,
    )


def resolve_item_use(
    runtime_item: RuntimeItem,
    owner: RuntimePlayer,
    players: dict[str, RuntimePlayer],
    metrics: RunMetrics,
    item_metric: ItemRunMetrics | None,
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    item = runtime_item.definition
    opponent_id = "player_b" if owner.player_id == "player_a" else "player_a"
    owner_metrics = select_player_metrics(metrics, owner.player_id)

    for effect in item.effects:
        target_player = owner if effect.target == EffectTarget.SELF else players[opponent_id]
        if item_metric is not None:
            increment_counter(item_metric.events_triggered, effect.type.value)

        if effect.type == EffectType.DAMAGE:
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

        elif effect.type == EffectType.HEAL:
            healed = apply_heal(target_player, effect.magnitude)
            owner.total_healing_done += healed

        elif effect.type == EffectType.SHIELD:
            target_player.shield += effect.magnitude

        elif effect.type == EffectType.APPLY_BURN:
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

        elif effect.type == EffectType.APPLY_POISON:
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


def schedule_status(
    player: RuntimePlayer,
    status: str,
    amount: float,
    source_player_id: str,
    source_item_instance_id: str | None,
    current_time: float,
    queue: list[Event],
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


def select_player_metrics(metrics: RunMetrics, player_id: str) -> PlayerEventMetrics:
    return metrics.player_a if player_id == "player_a" else metrics.player_b


def increment_counter(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def track_status_metrics(status_metric: StatusEffectMetrics, amount: float) -> None:
    status_metric.applications += 1
    status_metric.total_value += amount


def track_damage_breakdown(breakdown: DamageBreakdown, damage_type: str, amount: float) -> None:
    if amount <= 0:
        return

    breakdown.total += amount
    if damage_type == "direct":
        breakdown.direct += amount
    elif damage_type == "burn":
        breakdown.burn += amount
    elif damage_type == "poison":
        breakdown.poison += amount


def record_damage_to_opponent(
    *,
    metrics: RunMetrics,
    players: dict[str, RuntimePlayer],
    source_player_id: str,
    target_player_id: str,
    damage_type: str,
    amount: float,
    item_metrics_by_instance: dict[str, ItemRunMetrics] | None,
    source_item_instance_id: str | None,
    fallback_item_metric: ItemRunMetrics | None = None,
) -> None:
    if amount <= 0:
        return

    if source_player_id not in players:
        return

    if source_player_id == target_player_id:
        return

    source_metrics = select_player_metrics(metrics, source_player_id)
    track_damage_breakdown(source_metrics.damage_to_opponent, damage_type, amount)

    item_metric = fallback_item_metric
    if item_metric is None and item_metrics_by_instance is not None and source_item_instance_id is not None:
        item_metric = item_metrics_by_instance.get(source_item_instance_id)

    if item_metric is not None:
        track_damage_breakdown(item_metric.damage_done, damage_type, amount)


def apply_initial_statuses(player: RuntimePlayer, statuses: list[InitialStatus]) -> None:
    for status in statuses:
        if status.type.value == "burn":
            player.burn += status.value
        elif status.type.value == "poison":
            player.poison += status.value


def resolve_item_definition(
    item_lookup: dict[str, ItemDefinition], placement: BoardItemPlacement
) -> ItemDefinition:
    item = item_lookup.get(placement.item_definition_id)
    if item is None:
        raise SimulationInputError(
            f"Unknown item_definition_id: {placement.item_definition_id}",
            code="UNKNOWN_ITEM_DEFINITION",
        )
    return item


def validate_board_layouts(request: SimulationRequest, item_lookup: dict[str, ItemDefinition]) -> None:
    for player_cfg in request.players:
        occupied_slots: set[int] = set()
        for placement in player_cfg.board.placements:
            item = item_lookup.get(placement.item_definition_id)
            if item is None:
                raise SimulationInputError(
                    f"Unknown item_definition_id: {placement.item_definition_id}",
                    code="UNKNOWN_ITEM_DEFINITION",
                )

            item_end_slot = placement.start_slot + item.size
            if item_end_slot > player_cfg.board.width:
                raise SimulationInputError(
                    f"Item {placement.item_instance_id} exceeds board width for {player_cfg.player_id}",
                    code="ITEM_OUT_OF_BOUNDS",
                )

            for slot in range(placement.start_slot, item_end_slot):
                if slot in occupied_slots:
                    raise SimulationInputError(
                        f"Overlapping item placements on slot {slot} for {player_cfg.player_id}",
                        code="OVERLAPPING_ITEM_PLACEMENTS",
                    )
                occupied_slots.add(slot)


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


def apply_heal(player: RuntimePlayer, amount: float) -> float:
    original_health = player.health
    player.health = min(player.max_health, player.health + amount)
    return player.health - original_health


def build_numeric_summary(values: list[float]) -> NumericSummary:
    sorted_values = sorted(values)
    return NumericSummary(
        average=round(mean(sorted_values), 6),
        median=round(median(sorted_values), 6),
        p50=round(percentile(sorted_values, 50), 6),
        p90=round(percentile(sorted_values, 90), 6),
        p95=round(percentile(sorted_values, 95), 6),
    )


def percentile(sorted_values: list[float], pct: int) -> float:
    if not sorted_values:
        return 0.0

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * (pct / 100)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction
