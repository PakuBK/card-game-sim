from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

from app.models.base_models import ItemDefinition

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
