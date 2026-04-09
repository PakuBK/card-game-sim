"""
Item status effect timing and modifier calculations.

This module handles the complex timer recalculation logic for item modifiers.
When a modifier (slow, haste, freeze) is applied or removed, the pending
cooldown timer must be recalculated to maintain deterministic timing.

Key concepts from project_spec.md:
- Slow: cooldown progression at 50% speed (0.5x multiplier)
- Haste: cooldown progression at 200% speed (2.0x multiplier)
- Freeze: cooldown progression stops (0.0x multiplier)
- Flight: modifier durations halved (only affects duration, not speed)
"""

from __future__ import annotations


def calculate_remaining_cooldown(
    current_time: float,
    next_use_time: float,
    current_modifier: float,
) -> float:
    """
    Calculate the remaining cooldown accounting for current modifier speed.

    Args:
        current_time: Current simulation time in seconds
        next_use_time: Absolute time the item is scheduled to use next (unmodified basis)
        current_modifier: Speed multiplier (1.0 = normal, 0.5 = slow, 2.0 = haste, 0.0 = freeze)

    Returns:
        Remaining cooldown in seconds as perceived by the current modifier

    Formula:
        remaining = (next_use_time - current_time) / current_modifier

    Note:
        If current_modifier is 0.0 (freeze), the remaining time is unbounded.
        This function should not be called with modifier=0; freezing items don't progress.
    """
    if current_modifier == 0.0:
        # Frozen items don't progress. Return placeholder; don't use this value.
        # The caller should handle freeze case separately.
        raise ValueError("Cannot calculate remaining cooldown with freeze modifier (0.0)")

    return (next_use_time - current_time) / current_modifier


def recalculate_timer_after_modifier_change(
    current_time: float,
    next_use_time: float,
    old_modifier: float,
    new_modifier: float,
    freeze_applied_at: float | None = None,
) -> float:
    """
    Recalculate the next trigger time when a modifier changes.

    When a modifier is applied or removed, the pending cooldown event must be
    rescheduled. This function computes the new absolute trigger time.

    Args:
        current_time: Current simulation time in seconds
        next_use_time: Absolute time the item was scheduled to use (under old modifier)
        old_modifier: Previous speed multiplier
        new_modifier: New speed multiplier
        freeze_applied_at: If old_modifier is 0.0, the time freeze was applied
                          (needed to calculate remaining without progress)

    Returns:
        New absolute trigger time under the new modifier

    Examples (from project_spec.md):

    **Slow Example:**
        Initial: cooldown=4, current_time=8, next_use=12, remaining=4
        Slow (0.5x) applied for 2s at t=8
        Slow ends at t=10: remaining = 4 - (2 × 0.5) = 3
        New next_use = 10 + 3 = 13

    **Haste Example:**
        Initial: cooldown=4, current_time=8, next_use=12, remaining=4
        Haste (2.0x) applied for 2s at t=8
        Progress during haste: 2 × 2.0 = 4 (completes!)
        New next_use = 8 + 2 = 10

    **Freeze Example:**
        Initial: cooldown=4, current_time=8, next_use=12, remaining=4
        Freeze (0.0x) applied for 2s at t=8
        During freeze: no progress
        Freeze ends at t=10, remaining still 4
        New next_use = 10 + 4 = 14
    """
    # Handle freeze specially: frozen items don't progress
    if old_modifier == 0.0:
        # Item was frozen. Remaining cooldown hasn't changed.
        # Use freeze_applied_at to calculate original remaining.
        if freeze_applied_at is None:
            raise ValueError("freeze_applied_at required when removing freeze modifier")
        remaining = next_use_time - freeze_applied_at
    else:
        # Calculate remaining cooldown under old modifier
        remaining = calculate_remaining_cooldown(current_time, next_use_time, old_modifier)

    # Apply new modifier
    if new_modifier == 0.0:
        # Applying freeze: return placeholder value that encodes the remaining time
        # NOTE: freeze_applied_at should be set by the caller to current_time
        return current_time + remaining
    else:
        # Normal modifier: calculate new absolute trigger time
        return current_time + (remaining / new_modifier)


def calculate_next_use_time_after_modifier_application(
    current_time: float,
    next_use_time: float,
    old_modifier: float,
    new_modifier: float,
    duration_seconds: float,
) -> float:
    """
    Calculate the final use time after applying a temporary modifier.

    This accounts for the modifier duration ending later. If the item would
    complete during the modifier window, the trigger time is the in-window time.
    Otherwise, the remaining cooldown carries past the modifier end.
    """
    remaining_normal = calculate_remaining_cooldown(current_time, next_use_time, old_modifier)

    if new_modifier == 0.0:
        return current_time + duration_seconds + remaining_normal

    progress_during_modifier = duration_seconds * new_modifier
    if remaining_normal <= progress_during_modifier:
        return current_time + (remaining_normal / new_modifier)

    remaining_after_modifier = remaining_normal - progress_during_modifier
    return current_time + duration_seconds + remaining_after_modifier


def apply_modifier_duration_halving(duration_seconds: float, is_flying: bool) -> float:
    """
    Apply Flight modifier duration halving rule.

    If an item has Flight status active, modifier durations (slow/haste/freeze)
    last for half the specified duration.

    Args:
        duration_seconds: Original modifier duration
        is_flying: Whether the target item is currently flying

    Returns:
        Effective duration (halved if flying, otherwise unchanged)
    """
    if is_flying:
        return duration_seconds / 2.0
    return duration_seconds


def get_active_modifier_and_end_time(
    current_time: float,
    slow_end_time: float | None,
    haste_end_time: float | None,
    freeze_end_time: float | None,
) -> tuple[float, str | None]:
    """
    Determine the currently active modifier and its type.

    Only one modifier should be active at a time. This function returns
    the active modifier and its type, or (1.0, None) if no modifier is active.

    Args:
        current_time: Current simulation time
        slow_end_time: When (if) slow expires, or None
        haste_end_time: When (if) haste expires, or None
        freeze_end_time: When (if) freeze expires, or None

    Returns:
        Tuple of (modifier_multiplier, modifier_type_string or None)

    Note:
        If multiple modifiers are somehow active (shouldn't happen), freeze takes precedence,
        then haste, then slow.
    """
    active_modifiers = []

    if freeze_end_time is not None and freeze_end_time > current_time:
        active_modifiers.append((0.0, "freeze"))
    if haste_end_time is not None and haste_end_time > current_time:
        active_modifiers.append((2.0, "haste"))
    if slow_end_time is not None and slow_end_time > current_time:
        active_modifiers.append((0.5, "slow"))

    if not active_modifiers:
        return (1.0, None)

    # Freeze takes precedence if multiple are active (shouldn't happen in normal flow)
    if active_modifiers[0][1] == "freeze":
        return active_modifiers[0]
    # Then haste
    for modifier, mod_type in active_modifiers:
        if mod_type == "haste":
            return (modifier, mod_type)
    # Then slow
    return active_modifiers[0]
