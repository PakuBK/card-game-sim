# Engine Data Model

This document describes the current simulation data model and runtime flow used by this repository.

Source of truth:

- API contracts: backend/app/models/base_models.py
- Runtime entities and event ordering: backend/app/core/simulation_types.py
- Main simulation loop: backend/app/core/simulation.py
- Event handlers and item modifier timing: backend/app/core/simulation_event_handlers.py
- Board and target selection: backend/app/core/simulation_board.py

## 1. Model Layers

The engine has two explicit layers.

1. Request and response models (Pydantic)

- Define public API payloads and output schema.
- Validated at API boundaries.

2. Runtime engine models (dataclasses)

- Mutable in-memory state used while a run executes.
- Not exposed directly over the API.

## 2. API Contract Models (Pydantic)

The main request model is SimulationRequest.

SimulationRequest fields:

- seed: int
- runs: int (1..500)
- max_time_seconds: float
- max_events: int
- combat_log_limit: int | null
- item_definitions: list[ItemDefinition]
- players: exactly two PlayerConfig values (player_a and player_b)

Core nested models:

- ItemDefinition
  - id, name, size (1..3)
  - cooldown_seconds, initial_delay_seconds
  - abilities: list[ItemAbility] (min 1)
  - tags: list[str] (optional)
- ItemAbility
  - trigger: ItemTrigger
  - effects: list[ItemEffect] (min 1)
- ItemTrigger
  - type: timed_use | combat_start | adjacent_item_modifier_start
  - modifier_type: slow | haste | freeze (required when type is adjacent_item_modifier_start)
- ItemEffect
  - type: EffectType enum
  - target: EffectTarget enum
  - magnitude: float > 0
  - targeting_mode: single | all | random_n (default: single)
  - target_count: int (required when targeting_mode is random_n)
- PlayerConfig
  - player_id: player_a | player_b
  - stats: PlayerStats
  - board: BoardConfig
  - initial_statuses: list[InitialStatus]
- BoardConfig
  - width
  - placements: list[BoardItemPlacement]

Response model:

- SimulationResponse
  - scope: ScopeLimits
  - runs: list[SimulationRunResult]
  - summary: BatchSummary

Per-run output includes:

- winner_player_id, duration_seconds, stop_reason
- final player states
- run metrics (player and item level)
- combat log entries
- modifier timer trace entries
- combat log truncation metadata

## 3. Runtime Engine Entities (dataclasses)

RuntimePlayer

- player_id
- max_health
- health
- shield
- regeneration_per_second
- burn
- poison
- total_damage_done
- total_healing_done

RuntimeItem

- instance_id
- owner_id
- definition: ItemDefinition
- active_modifiers: dict[str, RuntimeItemModifier]
- flight_end_time: float | null
- frozen_remaining_cooldown: float | null

RuntimeItemModifier

- instance_id
- modifier_type: slow | haste | freeze
- start_time
- end_time
- source_item_instance_id

RuntimeBoardItem

- item_instance_id
- item_definition_id
- start_slot
- end_slot

RuntimeBoard

- player_id
- width
- items_by_instance_id
- adjacency_by_item_instance_id

Event

- time
- priority
- source_order
- target_order
- sequence
- event_type
- source_id
- target_id
- source_item_instance_id
- effect_magnitude
- modifier_instance_id
- stale

Notes:

- The queue is ordered by (time, priority, source_order, target_order, sequence).
- stale events remain in the heap but are skipped when popped.

## 4. Event Taxonomy

Current event types:

- combat_start
- item_use
- item_ability
- burn_tick
- poison_tick
- regen_tick
- item_charge
- item_slow_start, item_slow_end
- item_haste_start, item_haste_end
- item_freeze_start, item_freeze_end
- item_flight_start, item_flight_end

Priority intent:

- item_use and modifier events resolve before periodic status ticks at the same timestamp.

## 5. Current Trigger and Effect Architecture

Important implementation detail:

- Item behavior is defined as a list of event-bound abilities (trigger + effects).
- Timed item use is represented as an ability with trigger type timed_use.
- Additional ability triggers are supported (for example combat_start and adjacent_item_modifier_start).

What exists now:

- Trigger dispatch via ItemAbility.trigger
- EffectType enum-based dispatch in event handlers
- EffectTarget-based target resolution
- Multi-target execution via targeting_mode (single/all/random_n)
- Deterministic selectors plus RNG-based selection via seeded RNG

What does not exist yet:

- Generic Trigger object graph with arbitrary conditions
- Expression tree evaluation language

## 6. Board and Target Selection Model

Board validation at runtime build:

- unknown item definition checks
- duplicate instance id checks
- out-of-bounds checks
- overlap checks

Adjacency:

- Built from touching item boundaries on each board.
- Stored per item instance in adjacency_by_item_instance_id.

Target selection capabilities:

- self and opponent player
- self_item and opponent_item
- deterministic enemy item selection by slot distance
- random selectors (enemy/self/any)
- size selectors (small/medium/large)
- positional selectors (left_most/right_most)
- adjacency selectors (enemy_adjacent, item_to_left, item_to_right)
- trigger-context selectors (trigger_item, trigger_source_item)

## 7. Cooldown and Modifier Timing Model

Cooldown scheduling is absolute-time event based:

- item_use events are queued at specific timestamps.

Modifier stack model:

- Multiple active slow and haste modifiers are supported.
- Effective speed is computed as (2^haste_count) \* (0.5^slow_count).
- Any active freeze yields effective speed 0.

Rescheduling behavior:

- On modifier start/end, pending item_use is marked stale.
- Remaining cooldown is recomputed and a new item_use event is queued.
- Freeze stores frozen_remaining_cooldown for resume.

Flight interaction:

- Flight is a timed binary item state.
- Slow and freeze durations are halved while target item is flying.

## 8. Status Model

Player status values:

- burn
- poison
- regeneration_per_second

Status scheduling model:

- burn and poison schedule periodic tick events only when status becomes active.
- regen schedules periodic regen_tick while regen_per_second > 0.

Status dynamics:

- burn tick damage uses shield-sensitive logic (via status helpers)
- poison tick damage ignores shield in its calculation path
- burn decays over time
- healing can reduce burn and poison by a small amount

## 9. Metrics and Log Model

RunMetrics captures:

- total events processed
- player-level counters: item uses, burn ticks, poison ticks, regen ticks
- player damage-to-opponent breakdown
- status applied/received summaries
- per-item metrics

Combat log model:

- event index and timestamp
- event type and source ids
- target id
- per-player state deltas before/after

Notes:

- combat_start is logged as an event at time 0.
- system-emitted events use source_player_id = system.

Modifier timer trace:

- records modifier start/end and charge timer operations
- includes before/after pending event times and effective modifiers

## 10. API Error Model

Structured API errors use:

- ApiErrorResponse
  - error.type: validation_error | simulation_input_error | simulation_runtime_error
  - error.code
  - error.message
  - error.details[] with optional location path

Status code mapping:

- 422: request validation error
- 400: simulation input error (domain/runtime board validation)
- 500: unexpected runtime error

## 11. Simulation Loop (Current)

High-level single-run flow:

1. Build lookup tables and runtime boards.
2. Initialize RuntimePlayer and RuntimeItem instances.
3. Apply initial statuses.
4. Seed initial queue:

- combat_start at time 0
- first item_use for each item that has a timed_use ability
- initial burn/poison/regen ticks where applicable

5. Loop while queue not empty and event budget remains:

- pop next event
- stop on max_time_seconds
- process same-time events in deterministic order
- skip stale events
- dispatch to event-specific handlers
- update metrics and append combat log entries
- check win condition

6. Finalize winner and stop reason.
7. Return SimulationRunResult with metrics, logs, and modifier trace.

Batch flow:

- Repeat single-run with seed + run_index.
- Aggregate win rates, duration summaries, and performance counters into BatchSummary.

## 12. Design Constraints and Invariants

Current invariants:

- Deterministic outcomes for identical request and seed.
- Exactly two players (player_a and player_b).
- Item placement validity enforced before run execution.
- Event ordering stability through explicit priority plus deterministic tie-breakers.
- Public contract stability through Pydantic response models.
