from __future__ import annotations

import random

from app.core.errors import SimulationInputError
from app.core.simulation_types import RuntimeBoard, RuntimeBoardItem, RuntimeItem, RuntimePlayer
from app.models.base_models import BoardItemPlacement, EffectTarget, TargetingMode, ItemDefinition, SimulationRequest


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
    elif scope == "any":
        target_player_ids = [source_item.owner_id, opponent_player_id(source_item.owner_id)]
    else:
        raise ValueError(f"Unknown scope: {scope}")

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


def _pick_left_or_right_neighbor_instance_id(
    *,
    source_item_instance_id: str,
    direction: str,
    board_by_player: dict[str, RuntimeBoard],
    source_player_id: str,
) -> str | None:
    board = board_by_player[source_player_id]
    source_board_item = board.items_by_instance_id.get(source_item_instance_id)
    if source_board_item is None:
        return None

    # Build deterministic view of board item positions.
    sorted_items = sorted(
        board.items_by_instance_id.values(),
        key=lambda item: (item.start_slot, item.end_slot, item.item_instance_id),
    )

    if direction == "left":
        for item in reversed(sorted_items):
            if item.end_slot == source_board_item.start_slot:
                return item.item_instance_id
            if item.end_slot < source_board_item.start_slot:
                break
        return None

    if direction == "right":
        for item in sorted_items:
            if item.start_slot == source_board_item.end_slot:
                return item.item_instance_id
            if item.start_slot > source_board_item.end_slot:
                break
        return None

    raise ValueError(f"Unknown direction: {direction}")


def select_target_player_ids(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    rng: random.Random,
) -> list[str]:
    if effect_target in {EffectTarget.SELF}:
        return [source_item.owner_id]

    if effect_target in {EffectTarget.OPPONENT}:
        return [opponent_player_id(source_item.owner_id)]

    # Targets that refer to items are not valid player selectors.
    return []


def _select_single_item_instance_id(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
    trigger_item_instance_id: str | None = None,
    trigger_source_item_instance_id: str | None = None,
) -> str | None:
    # Trigger-context item selectors.
    if effect_target == EffectTarget.TRIGGER_ITEM:
        return trigger_item_instance_id
    if effect_target == EffectTarget.TRIGGER_SOURCE_ITEM:
        return trigger_source_item_instance_id

    # Direct self/opponent item selectors.
    if effect_target == EffectTarget.SELF_ITEM:
        return source_item.instance_id

    if effect_target == EffectTarget.OPPONENT_ITEM:
        return select_deterministic_target_item(
            source_player_id=source_item.owner_id,
            source_item_instance_id=source_item.instance_id,
            target_player_id=opponent_player_id(source_item.owner_id),
            board_by_player=board_by_player,
        )

    # Adjacency.
    if effect_target == EffectTarget.ITEM_TO_LEFT:
        return _pick_left_or_right_neighbor_instance_id(
            source_item_instance_id=source_item.instance_id,
            direction="left",
            board_by_player=board_by_player,
            source_player_id=source_item.owner_id,
        )

    if effect_target == EffectTarget.ITEM_TO_RIGHT:
        return _pick_left_or_right_neighbor_instance_id(
            source_item_instance_id=source_item.instance_id,
            direction="right",
            board_by_player=board_by_player,
            source_player_id=source_item.owner_id,
        )

    # Scope + pattern selectors.
    scope: str
    pattern: str
    if effect_target == EffectTarget.SELF_RANDOM:
        scope, pattern = "self", "random"
    elif effect_target == EffectTarget.ENEMY_RANDOM:
        scope, pattern = "enemy", "random"
    elif effect_target == EffectTarget.ANY_RANDOM:
        scope, pattern = "any", "random"
    elif effect_target == EffectTarget.SELF_LEFT_MOST:
        scope, pattern = "self", "left_most"
    elif effect_target == EffectTarget.SELF_RIGHT_MOST:
        scope, pattern = "self", "right_most"
    elif effect_target == EffectTarget.ENEMY_LEFT_MOST:
        scope, pattern = "enemy", "left_most"
    elif effect_target == EffectTarget.ENEMY_RIGHT_MOST:
        scope, pattern = "enemy", "right_most"
    elif effect_target == EffectTarget.ANY_LEFT_MOST:
        scope, pattern = "any", "left_most"
    elif effect_target == EffectTarget.ANY_RIGHT_MOST:
        scope, pattern = "any", "right_most"
    elif effect_target == EffectTarget.SELF_SMALL_ITEM:
        scope, pattern = "self", "small_item"
    elif effect_target == EffectTarget.SELF_MEDIUM_ITEM:
        scope, pattern = "self", "medium_item"
    elif effect_target == EffectTarget.SELF_LARGE_ITEM:
        scope, pattern = "self", "large_item"
    elif effect_target == EffectTarget.ENEMY_SMALL_ITEM:
        scope, pattern = "enemy", "small_item"
    elif effect_target == EffectTarget.ENEMY_MEDIUM_ITEM:
        scope, pattern = "enemy", "medium_item"
    elif effect_target == EffectTarget.ENEMY_LARGE_ITEM:
        scope, pattern = "enemy", "large_item"
    elif effect_target == EffectTarget.ANY_SMALL_ITEM:
        scope, pattern = "any", "small_item"
    elif effect_target == EffectTarget.ANY_MEDIUM_ITEM:
        scope, pattern = "any", "medium_item"
    elif effect_target == EffectTarget.ANY_LARGE_ITEM:
        scope, pattern = "any", "large_item"
    elif effect_target == EffectTarget.ENEMY_ADJACENT:
        base = select_deterministic_target_item(
            source_player_id=source_item.owner_id,
            source_item_instance_id=source_item.instance_id,
            target_player_id=opponent_player_id(source_item.owner_id),
            board_by_player=board_by_player,
        )
        if base is None:
            return None
        enemy_board = board_by_player[opponent_player_id(source_item.owner_id)]
        neighbors = enemy_board.adjacency_by_item_instance_id.get(base, [])
        if not neighbors:
            return None
        # Deterministic adjacent selection.
        return sorted(neighbors)[0]
    else:
        return None

    candidates = _build_scope_candidates(
        source_item=source_item,
        scope=scope,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
    )
    filtered = _filter_candidates_by_pattern(candidates, pattern)
    selected = _pick_candidate_for_pattern(
        candidates=filtered,
        pattern=pattern if pattern in {"left_most", "right_most", "random"} else "random",
        board_by_player=board_by_player,
        rng=rng,
    )
    return selected.instance_id if selected is not None else None


def select_target_item_instance_ids(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    targeting_mode: TargetingMode,
    target_count: int | None,
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
    trigger_item_instance_id: str | None = None,
    trigger_source_item_instance_id: str | None = None,
) -> list[str]:
    # SINGLE stays compatible with the old model.
    if targeting_mode == TargetingMode.SINGLE:
        target = _select_single_item_instance_id(
            source_item=source_item,
            effect_target=effect_target,
            board_by_player=board_by_player,
            runtime_item_lookup=runtime_item_lookup,
            rng=rng,
            trigger_item_instance_id=trigger_item_instance_id,
            trigger_source_item_instance_id=trigger_source_item_instance_id,
        )
        return [target] if target is not None else []

    # For ALL / RANDOM_N, interpret the EffectTarget as a candidate set.
    if effect_target in {EffectTarget.SELF_ITEM}:
        candidates = [source_item.instance_id]
    elif effect_target in {EffectTarget.OPPONENT_ITEM}:
        deterministic = _select_single_item_instance_id(
            source_item=source_item,
            effect_target=effect_target,
            board_by_player=board_by_player,
            runtime_item_lookup=runtime_item_lookup,
            rng=rng,
            trigger_item_instance_id=trigger_item_instance_id,
            trigger_source_item_instance_id=trigger_source_item_instance_id,
        )
        candidates = [deterministic] if deterministic is not None else []
    elif effect_target in {EffectTarget.TRIGGER_ITEM}:
        candidates = [trigger_item_instance_id] if trigger_item_instance_id is not None else []
    elif effect_target in {EffectTarget.TRIGGER_SOURCE_ITEM}:
        candidates = (
            [trigger_source_item_instance_id]
            if trigger_source_item_instance_id is not None
            else []
        )
    else:
        # Build a deterministic candidate list using the SINGLE selector with random replaced by
        # an explicit candidate set when possible.
        scope: str | None = None
        pattern: str | None = None
        if effect_target in {EffectTarget.SELF_RANDOM}:
            scope, pattern = "self", "random"
        elif effect_target in {EffectTarget.ENEMY_RANDOM}:
            scope, pattern = "enemy", "random"
        elif effect_target in {EffectTarget.ANY_RANDOM}:
            scope, pattern = "any", "random"
        elif effect_target in {EffectTarget.SELF_LEFT_MOST}:
            scope, pattern = "self", "left_most"
        elif effect_target in {EffectTarget.SELF_RIGHT_MOST}:
            scope, pattern = "self", "right_most"
        elif effect_target in {EffectTarget.ENEMY_LEFT_MOST}:
            scope, pattern = "enemy", "left_most"
        elif effect_target in {EffectTarget.ENEMY_RIGHT_MOST}:
            scope, pattern = "enemy", "right_most"
        elif effect_target in {EffectTarget.ANY_LEFT_MOST}:
            scope, pattern = "any", "left_most"
        elif effect_target in {EffectTarget.ANY_RIGHT_MOST}:
            scope, pattern = "any", "right_most"
        elif effect_target in {EffectTarget.SELF_SMALL_ITEM}:
            scope, pattern = "self", "small_item"
        elif effect_target in {EffectTarget.SELF_MEDIUM_ITEM}:
            scope, pattern = "self", "medium_item"
        elif effect_target in {EffectTarget.SELF_LARGE_ITEM}:
            scope, pattern = "self", "large_item"
        elif effect_target in {EffectTarget.ENEMY_SMALL_ITEM}:
            scope, pattern = "enemy", "small_item"
        elif effect_target in {EffectTarget.ENEMY_MEDIUM_ITEM}:
            scope, pattern = "enemy", "medium_item"
        elif effect_target in {EffectTarget.ENEMY_LARGE_ITEM}:
            scope, pattern = "enemy", "large_item"
        elif effect_target in {EffectTarget.ANY_SMALL_ITEM}:
            scope, pattern = "any", "small_item"
        elif effect_target in {EffectTarget.ANY_MEDIUM_ITEM}:
            scope, pattern = "any", "medium_item"
        elif effect_target in {EffectTarget.ANY_LARGE_ITEM}:
            scope, pattern = "any", "large_item"
        elif effect_target in {EffectTarget.ENEMY_ADJACENT}:
            single = _select_single_item_instance_id(
                source_item=source_item,
                effect_target=effect_target,
                board_by_player=board_by_player,
                runtime_item_lookup=runtime_item_lookup,
                rng=rng,
                trigger_item_instance_id=trigger_item_instance_id,
                trigger_source_item_instance_id=trigger_source_item_instance_id,
            )
            candidates = [single] if single is not None else []
            scope = None
            pattern = None
        else:
            scope = None
            pattern = None

        if scope is not None and pattern is not None:
            runtime_candidates = _build_scope_candidates(
                source_item=source_item,
                scope=scope,
                board_by_player=board_by_player,
                runtime_item_lookup=runtime_item_lookup,
            )
            filtered = _filter_candidates_by_pattern(runtime_candidates, pattern)
            sortable = sorted(
                filtered,
                key=lambda item: (
                    item.owner_id,
                    board_by_player[item.owner_id].items_by_instance_id[item.instance_id].start_slot,
                    board_by_player[item.owner_id].items_by_instance_id[item.instance_id].end_slot,
                    item.instance_id,
                ),
            )
            candidates = [item.instance_id for item in sortable]
        elif scope is None and pattern is None and 'candidates' not in locals():
            candidates = []

    # Deterministic final selection.
    candidates = [c for c in candidates if c is not None]
    if targeting_mode == TargetingMode.ALL:
        return list(dict.fromkeys(candidates))
    if targeting_mode == TargetingMode.RANDOM_N:
        if not candidates:
            return []
        count = min(target_count or 0, len(candidates))
        if count <= 0:
            return []
        # Sample without replacement using deterministic candidate ordering.
        indices = list(range(len(candidates)))
        rng.shuffle(indices)
        picked = [candidates[i] for i in indices[:count]]
        return picked

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
    # Backwards-compatible wrapper. This function *only* returns item instance ids.
    selected = select_target_item_instance_ids(
        source_item=source_item,
        effect_target=effect_target,
        targeting_mode=TargetingMode.SINGLE,
        target_count=None,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
        rng=rng,
    )
    return selected[0] if selected else None


def resolve_effect_target(
    *,
    source_item: RuntimeItem,
    effect_target: EffectTarget,
    players: dict[str, RuntimePlayer],
    board_by_player: dict[str, RuntimeBoard],
    runtime_item_lookup: dict[str, RuntimeItem],
    rng: random.Random,
) -> tuple[RuntimePlayer, str | None]:
    # Deprecated: prefer selecting player and item targets separately.
    player_ids = select_target_player_ids(source_item=source_item, effect_target=effect_target, rng=rng)
    if player_ids:
        return players[player_ids[0]], player_ids[0]

    item_ids = select_target_item_instance_ids(
        source_item=source_item,
        effect_target=effect_target,
        targeting_mode=TargetingMode.SINGLE,
        target_count=None,
        board_by_player=board_by_player,
        runtime_item_lookup=runtime_item_lookup,
        rng=rng,
    )
    if not item_ids:
        opponent_id = opponent_player_id(source_item.owner_id)
        return players[opponent_id], None

    target_runtime_item = runtime_item_lookup.get(item_ids[0])
    if target_runtime_item is None:
        opponent_id = opponent_player_id(source_item.owner_id)
        return players[opponent_id], None

    return players[target_runtime_item.owner_id], item_ids[0]
