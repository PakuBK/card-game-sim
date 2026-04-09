from __future__ import annotations

from app.core.simulation_types import RuntimePlayer
from app.models.base_models import (
    CombatLogStateDelta,
    DamageBreakdown,
    ItemRunMetrics,
    PlayerEventMetrics,
    RunMetrics,
    StatusEffectMetrics,
)


def snapshot_player_states(players: dict[str, RuntimePlayer]) -> dict[str, tuple[float, float, float, float]]:
    return {
        player_id: (player.health, player.shield, player.burn, player.poison)
        for player_id, player in players.items()
    }


def build_state_deltas(
    state_before_event: dict[str, tuple[float, float, float, float]],
    players: dict[str, RuntimePlayer],
) -> list[CombatLogStateDelta]:
    deltas: list[CombatLogStateDelta] = []

    for player_id in ("player_a", "player_b"):
        before = state_before_event[player_id]
        player = players[player_id]
        after = (player.health, player.shield, player.burn, player.poison)

        health_delta = round(after[0] - before[0], 6)
        shield_delta = round(after[1] - before[1], 6)
        burn_delta = round(after[2] - before[2], 6)
        poison_delta = round(after[3] - before[3], 6)

        if health_delta == 0 and shield_delta == 0 and burn_delta == 0 and poison_delta == 0:
            continue

        deltas.append(
            CombatLogStateDelta(
                player_id=player_id,
                health_delta=health_delta,
                shield_delta=shield_delta,
                burn_delta=burn_delta,
                poison_delta=poison_delta,
                health_after=round(after[0], 6),
                shield_after=round(after[1], 6),
                burn_after=round(after[2], 6),
                poison_after=round(after[3], 6),
            )
        )

    return deltas


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
