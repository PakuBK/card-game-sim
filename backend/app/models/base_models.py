from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    status: str = "ok"
    now: datetime


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    location: list[str | int] | None = None


class ApiError(BaseModel):
    type: Literal["validation_error", "simulation_input_error", "simulation_runtime_error"]
    code: str
    message: str
    details: list[ApiErrorDetail] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    error: ApiError


class StatusType(str, Enum):
    BURN = "burn"
    POISON = "poison"


class EffectType(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    SHIELD = "shield"
    APPLY_BURN = "apply_burn"
    APPLY_POISON = "apply_poison"


class EffectTarget(str, Enum):
    SELF = "self"
    OPPONENT = "opponent"


class RunStopReason(str, Enum):
    NATURAL_WIN = "natural_win"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    EVENT_LIMIT_EXCEEDED = "event_limit_exceeded"


class ScopeLimits(BaseModel):
    statuses: list[StatusType] = Field(default_factory=lambda: [StatusType.BURN, StatusType.POISON])
    trigger_modes: list[str] = Field(default_factory=lambda: ["timed_use_only"])
    effect_types: list[EffectType] = Field(
        default_factory=lambda: [
            EffectType.DAMAGE,
            EffectType.HEAL,
            EffectType.SHIELD,
            EffectType.APPLY_BURN,
            EffectType.APPLY_POISON,
        ]
    )
    percentile_set: list[int] = Field(default_factory=lambda: [50, 90, 95])


class ItemEffect(BaseModel):
    type: EffectType
    target: EffectTarget
    magnitude: float = Field(gt=0)


class ItemDefinition(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    size: int = Field(ge=1, le=3)
    cooldown_seconds: float = Field(gt=0)
    initial_delay_seconds: float | None = Field(default=None, ge=0)
    effects: list[ItemEffect] = Field(min_length=1)


class BoardItemPlacement(BaseModel):
    item_instance_id: str = Field(min_length=1, max_length=64)
    item_definition_id: str = Field(min_length=1, max_length=64)
    start_slot: int = Field(ge=0)


class BoardConfig(BaseModel):
    width: int = Field(default=10, ge=1)
    placements: list[BoardItemPlacement] = Field(default_factory=list)


class PlayerStats(BaseModel):
    max_health: float = Field(gt=0)
    start_health: float | None = Field(default=None, gt=0)
    start_shield: float = Field(default=0, ge=0)
    regeneration_per_second: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_start_health(self) -> "PlayerStats":
        if self.start_health is None:
            self.start_health = self.max_health
        if self.start_health > self.max_health:
            raise ValueError("start_health must be less than or equal to max_health")
        return self


class InitialStatus(BaseModel):
    type: StatusType
    value: float = Field(gt=0)


class PlayerConfig(BaseModel):
    player_id: Literal["player_a", "player_b"]
    stats: PlayerStats
    board: BoardConfig
    initial_statuses: list[InitialStatus] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    seed: int
    runs: int = Field(default=1, ge=1, le=500)
    max_time_seconds: float = Field(default=60, gt=0)
    max_events: int = Field(default=10_000, gt=0)
    combat_log_limit: int | None = Field(default=None, gt=0)
    item_definitions: list[ItemDefinition] = Field(min_length=1)
    players: list[PlayerConfig] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_players(self) -> "SimulationRequest":
        player_ids = sorted(player.player_id for player in self.players)
        if player_ids != ["player_a", "player_b"]:
            raise ValueError("players must include exactly player_a and player_b")
        return self


class PlayerRunState(BaseModel):
    player_id: Literal["player_a", "player_b"]
    health: float
    shield: float
    burn: float
    poison: float
    total_damage_done: float
    total_healing_done: float


class DamageBreakdown(BaseModel):
    total: float = 0.0
    direct: float = 0.0
    burn: float = 0.0
    poison: float = 0.0


class StatusEffectMetrics(BaseModel):
    applications: int = 0
    total_value: float = 0.0


class StatusMetrics(BaseModel):
    burn: StatusEffectMetrics = Field(default_factory=StatusEffectMetrics)
    poison: StatusEffectMetrics = Field(default_factory=StatusEffectMetrics)


class ItemRunMetrics(BaseModel):
    item_instance_id: str
    item_definition_id: str
    owner_player_id: Literal["player_a", "player_b"]
    damage_done: DamageBreakdown = Field(default_factory=DamageBreakdown)
    events_triggered: dict[str, int] = Field(default_factory=dict)
    status_effects_applied: StatusMetrics = Field(default_factory=StatusMetrics)
    status_effects_received: dict[str, int] = Field(default_factory=dict)


class PlayerEventMetrics(BaseModel):
    item_uses: int
    burn_ticks: int
    poison_ticks: int
    regen_ticks: int
    damage_to_opponent: DamageBreakdown = Field(default_factory=DamageBreakdown)
    status_effects_received: StatusMetrics = Field(default_factory=StatusMetrics)
    status_effects_applied: StatusMetrics = Field(default_factory=StatusMetrics)
    item_metrics: list[ItemRunMetrics] = Field(default_factory=list)


class RunMetrics(BaseModel):
    total_events_processed: int
    player_a: PlayerEventMetrics
    player_b: PlayerEventMetrics


class CombatLogStateDelta(BaseModel):
    player_id: Literal["player_a", "player_b"]
    health_delta: float
    shield_delta: float
    burn_delta: float
    poison_delta: float
    health_after: float
    shield_after: float
    burn_after: float
    poison_after: float


class CombatLogEntry(BaseModel):
    event_index: int
    time_seconds: float
    event_type: str
    source_player_id: Literal["player_a", "player_b"]
    source_item_instance_id: str | None = None
    target_id: str | None = None
    state_deltas: list[CombatLogStateDelta] = Field(default_factory=list)


class SimulationRunResult(BaseModel):
    run_index: int
    seed_used: int
    winner_player_id: Literal["player_a", "player_b", "draw"]
    duration_seconds: float
    stop_reason: RunStopReason
    players: list[PlayerRunState]
    metrics: RunMetrics
    combat_log: list[CombatLogEntry] = Field(default_factory=list)
    combat_log_total_events: int = 0
    combat_log_truncated: bool = False


class NumericSummary(BaseModel):
    average: float
    median: float
    p50: float
    p90: float
    p95: float


class BatchPerformanceMetrics(BaseModel):
    total_events_across_batch: int
    average_events_per_run: float
    stop_reason_breakdown: dict[str, int] = Field(default_factory=dict)


class BatchSummary(BaseModel):
    run_count: int
    player_a_win_rate: float
    player_b_win_rate: float
    draw_rate: float
    duration_seconds: NumericSummary
    performance: BatchPerformanceMetrics = Field(default_factory=BatchPerformanceMetrics)


class SimulationResponse(BaseModel):
    scope: ScopeLimits = Field(default_factory=ScopeLimits)
    runs: list[SimulationRunResult]
    summary: BatchSummary


class SimulationSchemaResponse(BaseModel):
    scope: ScopeLimits = Field(default_factory=ScopeLimits)
