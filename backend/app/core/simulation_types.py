from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Literal

from app.models.base_models import ItemDefinition

BURN_TICK_INTERVAL_SECONDS = 0.5
POISON_TICK_INTERVAL_SECONDS = 1.0
REGEN_TICK_INTERVAL_SECONDS = 1.0

EVENT_ITEM_USE = "item_use"
EVENT_BURN_TICK = "burn_tick"
EVENT_POISON_TICK = "poison_tick"
EVENT_REGEN_TICK = "regen_tick"

# Item status effect events
EVENT_ITEM_CHARGE = "item_charge"
EVENT_ITEM_SLOW_START = "item_slow_start"
EVENT_ITEM_SLOW_END = "item_slow_end"
EVENT_ITEM_HASTE_START = "item_haste_start"
EVENT_ITEM_HASTE_END = "item_haste_end"
EVENT_ITEM_FREEZE_START = "item_freeze_start"
EVENT_ITEM_FREEZE_END = "item_freeze_end"
EVENT_ITEM_FLIGHT_START = "item_flight_start"
EVENT_ITEM_FLIGHT_END = "item_flight_end"

EVENT_TYPE_PRIORITY: dict[str, int] = {
    EVENT_ITEM_USE: 0,
    EVENT_ITEM_CHARGE: 1,
    EVENT_ITEM_SLOW_START: 2,
    EVENT_ITEM_SLOW_END: 2,
    EVENT_ITEM_HASTE_START: 2,
    EVENT_ITEM_HASTE_END: 2,
    EVENT_ITEM_FREEZE_START: 2,
    EVENT_ITEM_FREEZE_END: 2,
    EVENT_ITEM_FLIGHT_START: 2,
    EVENT_ITEM_FLIGHT_END: 2,
    EVENT_BURN_TICK: 10,
    EVENT_POISON_TICK: 11,
    EVENT_REGEN_TICK: 12,
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
class RuntimeItemModifier:
    instance_id: str
    modifier_type: Literal["slow", "haste", "freeze"]
    start_time: float
    end_time: float
    source_item_instance_id: str | None = None


@dataclass
class RuntimeItem:
    instance_id: str
    owner_id: str
    definition: ItemDefinition

    # Active speed modifiers keyed by unique instance_id.
    active_modifiers: dict[str, RuntimeItemModifier] = field(default_factory=dict)

    # Flight remains a binary timed status.
    flight_end_time: float | None = None

    # Remaining base cooldown captured when transitioning into frozen state.
    frozen_remaining_cooldown: float | None = None


@dataclass(frozen=True)
class RuntimeBoardItem:
    item_instance_id: str
    item_definition_id: str
    start_slot: int
    end_slot: int


@dataclass
class RuntimeBoard:
    player_id: str
    width: int
    items_by_instance_id: dict[str, RuntimeBoardItem]
    adjacency_by_item_instance_id: dict[str, list[str]]


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
    effect_magnitude: float | None = field(default=None, compare=False)
    modifier_instance_id: str | None = field(default=None, compare=False)
    stale: bool = field(default=False, compare=False)


def make_event(
    *,
    time: float,
    sequence: count,
    event_type: str,
    source_id: str,
    target_id: str | None,
    source_item_instance_id: str | None = None,
    effect_magnitude: float | None = None,
    modifier_instance_id: str | None = None,
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
        effect_magnitude=effect_magnitude,
        modifier_instance_id=modifier_instance_id,
    )
