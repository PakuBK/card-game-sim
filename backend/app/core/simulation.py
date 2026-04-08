from __future__ import annotations

import heapq
from dataclasses import dataclass
from itertools import count
from statistics import mean, median

from app.models.base_models import (
    BatchSummary,
    BoardItemPlacement,
    EffectTarget,
    EffectType,
    InitialStatus,
    ItemDefinition,
    NumericSummary,
    PlayerRunState,
    RunMetrics,
    SimulationRequest,
    SimulationResponse,
    SimulationRunResult,
)

BURN_TICK_INTERVAL_SECONDS = 0.5
POISON_TICK_INTERVAL_SECONDS = 1.0
REGEN_TICK_INTERVAL_SECONDS = 1.0

EVENT_ITEM_USE = "item_use"
EVENT_BURN_TICK = "burn_tick"
EVENT_POISON_TICK = "poison_tick"
EVENT_REGEN_TICK = "regen_tick"


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
    owner_id: str
    definition: ItemDefinition


@dataclass(order=True)
class Event:
    time: float
    sequence: int
    event_type: str
    source_id: str
    target_id: str | None


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
                    owner_id=player_cfg.player_id,
                    definition=resolve_item_definition(item_lookup, placement),
                )
            )

    validate_board_layouts(request, item_lookup)

    queue: list[Event] = []
    sequence = count()

    for item in runtime_items:
        initial_delay = item.definition.initial_delay_seconds
        first_use_time = initial_delay if initial_delay is not None else item.definition.cooldown_seconds
        heapq.heappush(
            queue,
            Event(
                time=first_use_time,
                sequence=next(sequence),
                event_type=EVENT_ITEM_USE,
                source_id=item.owner_id,
                target_id=item.definition.id,
            ),
        )

    for player in players.values():
        if player.burn > 0:
            heapq.heappush(
                queue,
                Event(
                    time=BURN_TICK_INTERVAL_SECONDS,
                    sequence=next(sequence),
                    event_type=EVENT_BURN_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )
        if player.poison > 0:
            heapq.heappush(
                queue,
                Event(
                    time=POISON_TICK_INTERVAL_SECONDS,
                    sequence=next(sequence),
                    event_type=EVENT_POISON_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )
        if player.regeneration_per_second > 0:
            heapq.heappush(
                queue,
                Event(
                    time=REGEN_TICK_INTERVAL_SECONDS,
                    sequence=next(sequence),
                    event_type=EVENT_REGEN_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )

    metrics = RunMetrics(
        total_events_processed=0,
        total_item_uses=0,
        burn_ticks=0,
        poison_ticks=0,
        regen_ticks=0,
    )

    current_time = 0.0
    winner = "draw"

    while queue and metrics.total_events_processed < request.max_events:
        event = heapq.heappop(queue)
        if event.time > request.max_time_seconds:
            current_time = request.max_time_seconds
            break

        current_time = event.time
        metrics.total_events_processed += 1

        if event.event_type == EVENT_ITEM_USE:
            metrics.total_item_uses += 1
            owner = players[event.source_id]
            if owner.health > 0:
                item = item_lookup[event.target_id or ""]
                resolve_item_use(
                    item,
                    owner,
                    players,
                    current_time,
                    queue,
                    sequence,
                )
                heapq.heappush(
                    queue,
                    Event(
                        time=current_time + item.cooldown_seconds,
                        sequence=next(sequence),
                        event_type=EVENT_ITEM_USE,
                        source_id=owner.player_id,
                        target_id=item.id,
                    ),
                )

        elif event.event_type == EVENT_BURN_TICK:
            metrics.burn_ticks += 1
            player = players[event.target_id or ""]
            if player.health > 0 and player.burn > 0:
                apply_damage(player, player.burn)
                player.burn = max(0.0, player.burn - 1)
                if player.burn > 0:
                    heapq.heappush(
                        queue,
                        Event(
                            time=current_time + BURN_TICK_INTERVAL_SECONDS,
                            sequence=next(sequence),
                            event_type=EVENT_BURN_TICK,
                            source_id=player.player_id,
                            target_id=player.player_id,
                        ),
                    )

        elif event.event_type == EVENT_POISON_TICK:
            metrics.poison_ticks += 1
            player = players[event.target_id or ""]
            if player.health > 0 and player.poison > 0:
                apply_damage(player, player.poison)
                player.poison = max(0.0, player.poison - 1)
                if player.poison > 0:
                    heapq.heappush(
                        queue,
                        Event(
                            time=current_time + POISON_TICK_INTERVAL_SECONDS,
                            sequence=next(sequence),
                            event_type=EVENT_POISON_TICK,
                            source_id=player.player_id,
                            target_id=player.player_id,
                        ),
                    )

        elif event.event_type == EVENT_REGEN_TICK:
            metrics.regen_ticks += 1
            player = players[event.target_id or ""]
            if player.health > 0 and player.regeneration_per_second > 0:
                heal_amount = player.regeneration_per_second * REGEN_TICK_INTERVAL_SECONDS
                healed = apply_heal(player, heal_amount)
                player.total_healing_done += healed
                heapq.heappush(
                    queue,
                    Event(
                        time=current_time + REGEN_TICK_INTERVAL_SECONDS,
                        sequence=next(sequence),
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
    item: ItemDefinition,
    owner: RuntimePlayer,
    players: dict[str, RuntimePlayer],
    current_time: float,
    queue: list[Event],
    sequence: count,
) -> None:
    opponent_id = "player_b" if owner.player_id == "player_a" else "player_a"

    for effect in item.effects:
        target_player = owner if effect.target == EffectTarget.SELF else players[opponent_id]

        if effect.type == EffectType.DAMAGE:
            dealt = apply_damage(target_player, effect.magnitude)
            owner.total_damage_done += dealt

        elif effect.type == EffectType.HEAL:
            healed = apply_heal(target_player, effect.magnitude)
            owner.total_healing_done += healed

        elif effect.type == EffectType.SHIELD:
            target_player.shield += effect.magnitude

        elif effect.type == EffectType.APPLY_BURN:
            schedule_status(
                player=target_player,
                status="burn",
                amount=effect.magnitude,
                current_time=current_time,
                queue=queue,
                sequence=sequence,
            )

        elif effect.type == EffectType.APPLY_POISON:
            schedule_status(
                player=target_player,
                status="poison",
                amount=effect.magnitude,
                current_time=current_time,
                queue=queue,
                sequence=sequence,
            )


def schedule_status(
    player: RuntimePlayer,
    status: str,
    amount: float,
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
                Event(
                    time=current_time + BURN_TICK_INTERVAL_SECONDS,
                    sequence=next(sequence),
                    event_type=EVENT_BURN_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )

    elif status == "poison":
        was_zero = player.poison <= 0
        player.poison += amount
        if was_zero:
            heapq.heappush(
                queue,
                Event(
                    time=current_time + POISON_TICK_INTERVAL_SECONDS,
                    sequence=next(sequence),
                    event_type=EVENT_POISON_TICK,
                    source_id=player.player_id,
                    target_id=player.player_id,
                ),
            )


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
        raise ValueError(f"Unknown item_definition_id: {placement.item_definition_id}")
    return item


def validate_board_layouts(request: SimulationRequest, item_lookup: dict[str, ItemDefinition]) -> None:
    for player_cfg in request.players:
        occupied_slots: set[int] = set()
        for placement in player_cfg.board.placements:
            item = item_lookup.get(placement.item_definition_id)
            if item is None:
                raise ValueError(f"Unknown item_definition_id: {placement.item_definition_id}")

            item_end_slot = placement.start_slot + item.size
            if item_end_slot > player_cfg.board.width:
                raise ValueError(
                    f"Item {placement.item_instance_id} exceeds board width for {player_cfg.player_id}"
                )

            for slot in range(placement.start_slot, item_end_slot):
                if slot in occupied_slots:
                    raise ValueError(
                        f"Overlapping item placements on slot {slot} for {player_cfg.player_id}"
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
