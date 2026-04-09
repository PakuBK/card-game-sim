from __future__ import annotations

import heapq
from itertools import count
from statistics import mean, median

from app.core.simulation_board import build_runtime_boards, resolve_item_definition
from app.core.simulation_event_handlers import (
    handle_burn_tick_event,
    handle_item_charge_event,
    handle_item_flight_end_event,
    handle_item_flight_start_event,
    handle_item_modifier_end_event,
    handle_item_modifier_start_event,
    handle_item_use_event,
    handle_poison_tick_event,
    handle_regen_tick_event,
)
from app.core.simulation_metrics import build_state_deltas, select_player_metrics, snapshot_player_states
from app.core.simulation_status import apply_initial_statuses
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
    RuntimeItem,
    RuntimePlayer,
    make_event,
)
from app.models.base_models import (
    BatchPerformanceMetrics,
    BatchSummary,
    CombatLogEntry,
    ItemRunMetrics,
    NumericSummary,
    PlayerEventMetrics,
    PlayerRunState,
    RunMetrics,
    RunStopReason,
    SimulationRequest,
    SimulationResponse,
    SimulationRunResult,
)


def run_simulation(request: SimulationRequest) -> SimulationResponse:
    run_results = [simulate_single_run(request, run_index) for run_index in range(request.runs)]

    winner_counts = {"player_a": 0, "player_b": 0, "draw": 0}
    durations = []
    stop_reason_counts: dict[str, int] = {}
    total_events = 0
    
    for result in run_results:
        winner_counts[result.winner_player_id] += 1
        durations.append(result.duration_seconds)
        total_events += result.metrics.total_events_processed
        
        # Track stop reason distribution
        reason_key = result.stop_reason.value
        stop_reason_counts[reason_key] = stop_reason_counts.get(reason_key, 0) + 1

    performance = BatchPerformanceMetrics(
        total_events_across_batch=total_events,
        average_events_per_run=total_events / request.runs if request.runs > 0 else 0,
        stop_reason_breakdown=stop_reason_counts,
    )

    summary = BatchSummary(
        run_count=request.runs,
        player_a_win_rate=winner_counts["player_a"] / request.runs,
        player_b_win_rate=winner_counts["player_b"] / request.runs,
        draw_rate=winner_counts["draw"] / request.runs,
        duration_seconds=build_numeric_summary(durations),
        performance=performance,
    )

    return SimulationResponse(runs=run_results, summary=summary)


def simulate_single_run(request: SimulationRequest, run_index: int) -> SimulationRunResult:
    item_lookup = {item.id: item for item in request.item_definitions}
    board_by_player = build_runtime_boards(request, item_lookup)

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

    queue: list[Event] = []
    sequence = count()

    runtime_item_lookup = {item.instance_id: item for item in runtime_items}
    combat_log: list[CombatLogEntry] = []
    combat_log_total_events = 0
    combat_log_limit = request.combat_log_limit

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
    stop_reason = RunStopReason.NATURAL_WIN

    while queue and metrics.total_events_processed < request.max_events:
        event = heapq.heappop(queue)
        if event.time > request.max_time_seconds:
            current_time = request.max_time_seconds
            stop_reason = RunStopReason.TIME_LIMIT_EXCEEDED
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
            if same_time_event.stale:
                continue

            if same_time_event.event_type == EVENT_ITEM_USE:
                runtime_item = runtime_item_lookup[same_time_event.target_id or ""]
                if (
                    runtime_item.current_cooldown_modifier == 0.0
                    and runtime_item.freeze_end_time is not None
                    and current_time <= runtime_item.freeze_end_time
                ):
                    freeze_applied_at = runtime_item.freeze_applied_at or current_time
                    remaining_cooldown = max(0.0, same_time_event.time - freeze_applied_at)
                    heapq.heappush(
                        queue,
                        make_event(
                            time=runtime_item.freeze_end_time + remaining_cooldown,
                            sequence=sequence,
                            event_type=EVENT_ITEM_USE,
                            source_id=same_time_event.source_id,
                            target_id=same_time_event.target_id,
                            source_item_instance_id=same_time_event.source_item_instance_id,
                        ),
                    )
                    continue

            state_before_event = snapshot_player_states(players)
            metrics.total_events_processed += 1
            log_target_id = same_time_event.target_id

            if same_time_event.event_type == EVENT_ITEM_USE:
                log_target_id = handle_item_use_event(
                    event=same_time_event,
                    alive_at_time=alive_at_time,
                    players=players,
                    runtime_item_lookup=runtime_item_lookup,
                    board_by_player=board_by_player,
                    metrics=metrics,
                    item_metrics_by_instance=item_metrics_by_instance,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_BURN_TICK:
                handle_burn_tick_event(
                    event=same_time_event,
                    players=players,
                    metrics=metrics,
                    item_metrics_by_instance=item_metrics_by_instance,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_POISON_TICK:
                handle_poison_tick_event(
                    event=same_time_event,
                    players=players,
                    metrics=metrics,
                    item_metrics_by_instance=item_metrics_by_instance,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_CHARGE:
                handle_item_charge_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_SLOW_START:
                handle_item_modifier_start_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="slow",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_SLOW_END:
                handle_item_modifier_end_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="slow",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_HASTE_START:
                handle_item_modifier_start_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="haste",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_HASTE_END:
                handle_item_modifier_end_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="haste",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_FREEZE_START:
                handle_item_modifier_start_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="freeze",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_FREEZE_END:
                handle_item_modifier_end_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    modifier_type="freeze",
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_FLIGHT_START:
                handle_item_flight_start_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )
            elif same_time_event.event_type == EVENT_ITEM_FLIGHT_END:
                handle_item_flight_end_event(
                    event=same_time_event,
                    runtime_item_lookup=runtime_item_lookup,
                    current_time=current_time,
                )
            elif same_time_event.event_type == EVENT_REGEN_TICK:
                handle_regen_tick_event(
                    event=same_time_event,
                    players=players,
                    metrics=metrics,
                    current_time=current_time,
                    queue=queue,
                    sequence=sequence,
                )

            state_deltas = build_state_deltas(state_before_event, players)
            log_entry = CombatLogEntry(
                event_index=combat_log_total_events,
                time_seconds=round(current_time, 6),
                event_type=same_time_event.event_type,
                source_player_id=same_time_event.source_id,
                source_item_instance_id=same_time_event.source_item_instance_id,
                target_id=(
                    log_target_id
                    if same_time_event.event_type == EVENT_ITEM_USE
                    else same_time_event.target_id
                ),
                state_deltas=state_deltas,
            )
            combat_log_total_events += 1
            if combat_log_limit is None or len(combat_log) < combat_log_limit:
                combat_log.append(log_entry)

        living_players = [p for p in players.values() if p.health > 0]
        if len(living_players) <= 1:
            winner = living_players[0].player_id if living_players else "draw"
            stop_reason = RunStopReason.NATURAL_WIN
            break

    # Check if we exited loop due to event limit
    if metrics.total_events_processed >= request.max_events and stop_reason == RunStopReason.NATURAL_WIN:
        stop_reason = RunStopReason.EVENT_LIMIT_EXCEEDED

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
        stop_reason=stop_reason,
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
        combat_log=combat_log,
        combat_log_total_events=combat_log_total_events,
        combat_log_truncated=combat_log_total_events > len(combat_log),
    )


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
