from __future__ import annotations

import random

from app.core.errors import SimulationInputError
from app.core.simulation_types import RuntimeBoard, RuntimeBoardItem, RuntimeItem, RuntimePlayer
from app.models.base_models import BoardItemPlacement, EffectTarget, ItemDefinition, SimulationRequest


def opponent_player_id(player_id: str) -> str:
    return "player_b" if player_id == "player_a" else "player_a"


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


def build_runtime_boards(
    request: SimulationRequest,
    item_lookup: dict[str, ItemDefinition],
) -> dict[str, RuntimeBoard]:
    runtime_boards: dict[str, RuntimeBoard] = {}

    for player_cfg in request.players:
        occupied_slots: set[int] = set()
        seen_item_instance_ids: set[str] = set()
        runtime_board_items: list[RuntimeBoardItem] = []

        for placement in player_cfg.board.placements:
            if placement.item_instance_id in seen_item_instance_ids:
                raise SimulationInputError(
                    (
                        f"Duplicate item_instance_id {placement.item_instance_id} "
                        f"for {player_cfg.player_id}"
                    ),
                    code="DUPLICATE_ITEM_INSTANCE_ID",
                )
            seen_item_instance_ids.add(placement.item_instance_id)

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

            runtime_board_items.append(
                RuntimeBoardItem(
                    item_instance_id=placement.item_instance_id,
                    item_definition_id=placement.item_definition_id,
                    start_slot=placement.start_slot,
                    end_slot=item_end_slot,
                )
            )

        runtime_board_items.sort(
            key=lambda board_item: (
                board_item.start_slot,
                board_item.end_slot,
                board_item.item_instance_id,
            )
        )
        runtime_boards[player_cfg.player_id] = RuntimeBoard(
            player_id=player_cfg.player_id,
            width=player_cfg.board.width,
            items_by_instance_id={
                board_item.item_instance_id: board_item for board_item in runtime_board_items
            },
            adjacency_by_item_instance_id=build_adjacency_lookup(runtime_board_items),
        )

    return runtime_boards


def build_adjacency_lookup(items: list[RuntimeBoardItem]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {item.item_instance_id: [] for item in items}

    for left_index, left_item in enumerate(items):
        for right_item in items[left_index + 1 :]:
            if left_item.end_slot == right_item.start_slot:
                adjacency[left_item.item_instance_id].append(right_item.item_instance_id)
                adjacency[right_item.item_instance_id].append(left_item.item_instance_id)
                break

            if left_item.end_slot < right_item.start_slot:
                break

    return {item_instance_id: sorted(neighbors) for item_instance_id, neighbors in adjacency.items()}


def slot_distance(source_slot: int, target_start_slot: int, target_end_slot: int) -> int:
    if target_start_slot <= source_slot < target_end_slot:
        return 0
    if source_slot < target_start_slot:
        return target_start_slot - source_slot
    return source_slot - (target_end_slot - 1)


def select_deterministic_target_item(
    *,
    source_player_id: str,
    source_item_instance_id: str,
    target_player_id: str,
    board_by_player: dict[str, RuntimeBoard],
) -> str | None:
    source_board = board_by_player[source_player_id]
    target_board = board_by_player[target_player_id]

    source_board_item = source_board.items_by_instance_id.get(source_item_instance_id)
    if source_board_item is None:
        return None

    if not target_board.items_by_instance_id:
        return None

    source_anchor_slot = source_board_item.start_slot
    candidates: list[tuple[int, int, int, str]] = []
    for target_item in target_board.items_by_instance_id.values():
        has_adjacent = bool(
            target_board.adjacency_by_item_instance_id.get(target_item.item_instance_id, [])
        )
        item_distance = slot_distance(
            source_anchor_slot,
            target_item.start_slot,
            target_item.end_slot,
        )
        candidates.append(
            (
                0 if has_adjacent else 1,
                item_distance,
                target_item.start_slot,
                target_item.item_instance_id,
            )
        )

    candidates.sort()
    return candidates[0][3]


def _build_scope_candidates(
    *,
    source_item: RuntimeItem,
    scope: str,
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
) -> list[RuntimeItem]:
    if scope == "self":
        target_player_ids = [source_item.owner_id]
    elif scope == "enemy":
        target_player_ids = [opponent_player_id(source_item.owner_id)]
    else:
        target_player_ids = [source_item.owner_id, opponent_player_id(source_item.owner_id)]

    candidates: list[RuntimeItem] = []
    for target_player_id in target_player_ids:
        board = board_by_player[target_player_id]
        sorted_board_items = sorted(
            board.items_by_instance_id.values(),
            key=lambda item: (item.start_slot, item.end_slot, item.item_instance_id),
        )
        for board_item in sorted_board_items:
            runtime_item = runtime_item_lookup.get(board_item.item_instance_id)
            if runtime_item is None:
                continue
            candidates.append(runtime_item)
    return candidates


def _filter_candidates_by_pattern(candidates: list[RuntimeItem], pattern: str) -> list[RuntimeItem]:
    if pattern == "random":
        return candidates
    if pattern == "small_item":
        return [item for item in candidates if item.definition.size == 1]
    if pattern == "medium_item":
        return [item for item in candidates if item.definition.size == 2]
    if pattern == "large_item":
        return [item for item in candidates if item.definition.size == 3]
    if pattern in {"left_most", "right_most"}:
        # The caller resolves left/right from board ordering.
        return candidates
    return []


def _pick_candidate_for_pattern(
    *,
    candidates: list[RuntimeItem],
    pattern: str,
    board_by_player: dict[str, RuntimeBoard],
    rng: random.Random,
) -> RuntimeItem | None:
    if not candidates:
        return None

    sortable = sorted(
        candidates,
        key=lambda item: (
            item.owner_id,
            board_by_player[item.owner_id].items_by_instance_id[item.instance_id].start_slot,
            board_by_player[item.owner_id].items_by_instance_id[item.instance_id].end_slot,
            item.instance_id,
        ),
    )

    if pattern == "right_most":
        return max(
            sortable,
            key=lambda item: (
                board_by_player[item.owner_id].items_by_instance_id[item.instance_id].end_slot,
                board_by_player[item.owner_id].items_by_instance_id[item.instance_id].start_slot,
                item.instance_id,
            ),
        )

    if pattern == "left_most":
        return min(
            sortable,
            key=lambda item: (
                board_by_player[item.owner_id].items_by_instance_id[item.instance_id].start_slot,
                board_by_player[item.owner_id].items_by_instance_id[item.instance_id].end_slot,
                item.instance_id,
            ),
        )

    if pattern == "random":
        return sortable[rng.randrange(len(sortable))]

    return sortable[0]


def select_target_item_instance_id(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
) -> str | None:
    target_value = effect_target.value

    if target_value in {EffectTarget.SELF_ITEM.value, EffectTarget.SELF.value}:
        return source_item.instance_id

    if target_value in {EffectTarget.OPPONENT_ITEM.value, EffectTarget.ENEMY_ADJACENT.value}:
        target_player_id = opponent_player_id(source_item.owner_id)
        return select_deterministic_target_item(
            source_player_id=source_item.owner_id,
            source_item_instance_id=source_item.instance_id,
            target_player_id=target_player_id,
            board_by_player=board_by_player,
        )

    if target_value == EffectTarget.ENEMY_RANDOM.value:
        scope, pattern = "enemy", "random"
    elif target_value == EffectTarget.SELF_RANDOM.value:
        scope, pattern = "self", "random"
    elif target_value == EffectTarget.ANY_RANDOM.value:
        scope, pattern = "any", "random"
    elif target_value.startswith("enemy_"):
        scope, pattern = "enemy", target_value.removeprefix("enemy_")
    elif target_value.startswith("self_"):
        scope, pattern = "self", target_value.removeprefix("self_")
    elif target_value.startswith("any_"):
        scope, pattern = "any", target_value.removeprefix("any_")
    else:
        return None

    candidates = _build_scope_candidates(
        source_item=source_item,
        scope=scope,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
    )
    filtered = _filter_candidates_by_pattern(candidates, pattern)
    if pattern in {"left_most", "right_most", "random"}:
        selected = _pick_candidate_for_pattern(
            candidates=filtered,
            pattern=pattern,
            board_by_player=board_by_player,
            rng=rng,
        )
    else:
        selected = _pick_candidate_for_pattern(
            candidates=filtered,
            pattern="random",
            board_by_player=board_by_player,
            rng=rng,
        )
    return selected.instance_id if selected is not None else None


def resolve_effect_target(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    players: dict[str, RuntimePlayer],
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
) -> tuple[RuntimePlayer, str | None]:
    if effect_target == EffectTarget.SELF:
        return players[source_item.owner_id], source_item.instance_id

    if effect_target == EffectTarget.OPPONENT:
        opponent_id = opponent_player_id(source_item.owner_id)
        return players[opponent_id], opponent_id

    target_item_instance_id = select_target_item_instance_id(
        source_item=source_item,
        effect_target=effect_target,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
        rng=rng,
    )
    if target_item_instance_id is None:
        opponent_id = opponent_player_id(source_item.owner_id)
        return players[opponent_id], None

    target_runtime_item = runtime_item_lookup.get(target_item_instance_id)
    if target_runtime_item is None:
        opponent_id = opponent_player_id(source_item.owner_id)
        return players[opponent_id], None

    return players[target_runtime_item.owner_id], target_item_instance_id
