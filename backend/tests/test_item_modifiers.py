"""
Test suite for item status effect timer recalculation logic.

These tests validate the timer math against spec examples from project_spec.md.
Correctness here is critical: incorrect recalculation breaks determinism.
"""

from pathlib import Path
import sys
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.simulation_item_modifiers import (
    apply_modifier_duration_halving,
    calculate_remaining_cooldown,
    get_active_modifier_and_end_time,
    recalculate_timer_after_modifier_change,
)


class TestCalculateRemainingCooldown(unittest.TestCase):
    """Test basic remaining cooldown calculation."""

    def test_normal_speed_full_cooldown(self):
        """Normal speed (1.0x): remaining = next_use - current_time."""
        current_time = 5.0
        next_use_time = 8.0
        modifier = 1.0
        remaining = calculate_remaining_cooldown(current_time, next_use_time, modifier)
        self.assertEqual(remaining, 3.0)

    def test_slow_doubled_remaining(self):
        """Slow (0.5x): perceived remaining cooldown is doubled."""
        current_time = 8.0
        next_use_time = 12.0
        modifier = 0.5
        remaining = calculate_remaining_cooldown(current_time, next_use_time, modifier)
        self.assertEqual(remaining, 8.0)

    def test_haste_halved_remaining(self):
        """Haste (2.0x): perceived remaining cooldown is halved."""
        current_time = 8.0
        next_use_time = 12.0
        modifier = 2.0
        remaining = calculate_remaining_cooldown(current_time, next_use_time, modifier)
        self.assertEqual(remaining, 2.0)

    def test_freeze_raises_error(self):
        """Freeze (0.0x): should raise error (don't call with freeze)."""
        with self.assertRaises(ValueError):
            calculate_remaining_cooldown(8.0, 12.0, 0.0)


class TestRecalculateTimer(unittest.TestCase):
    """Test timer recalculation against spec examples."""

    def test_slow_applied_spec_example(self):
        """Slow applied: cooldown extends."""
        current_time = 8.0
        next_use_time = 12.0
        old_modifier = 1.0
        new_modifier = 0.5
        new_next_use = recalculate_timer_after_modifier_change(
            current_time, next_use_time, old_modifier, new_modifier
        )
        self.assertEqual(new_next_use, 16.0)

    def test_slow_ends_recalculates(self):
        """Slow ends: cooldown resumes."""
        current_time = 10.0
        next_use_time = 16.0  # scheduled under slow
        old_modifier = 0.5
        new_modifier = 1.0
        new_next_use = recalculate_timer_after_modifier_change(
            current_time, next_use_time, old_modifier, new_modifier
        )
        self.assertEqual(new_next_use, 22.0)

    def test_haste_applied_spec_example(self):
        """Haste applied: cooldown accelerates."""
        current_time = 8.0
        next_use_time = 12.0
        old_modifier = 1.0
        new_modifier = 2.0
        new_next_use = recalculate_timer_after_modifier_change(
            current_time, next_use_time, old_modifier, new_modifier
        )
        self.assertEqual(new_next_use, 10.0)

    def test_freeze_applied_stops_progression(self):
        """Freeze applied: timer paused."""
        current_time = 8.0
        next_use_time = 12.0
        old_modifier = 1.0
        new_modifier = 0.0
        new_next_use = recalculate_timer_after_modifier_change(
            current_time, next_use_time, old_modifier, new_modifier
        )
        self.assertEqual(new_next_use, 12.0)

    def test_freeze_ends_recalculates_timer(self):
        """Freeze ends: timer resumes with correct remaining."""
        current_time = 10.0
        next_use_time = 12.0
        old_modifier = 0.0
        new_modifier = 1.0
        freeze_applied_at = 8.0
        new_next_use = recalculate_timer_after_modifier_change(
            current_time,
            next_use_time,
            old_modifier,
            new_modifier,
            freeze_applied_at=freeze_applied_at,
        )
        self.assertEqual(new_next_use, 14.0)

    def test_freeze_requires_applied_at(self):
        """Removing freeze without freeze_applied_at raises error."""
        with self.assertRaises(ValueError):
            recalculate_timer_after_modifier_change(
                10.0, 12.0, 0.0, 1.0, freeze_applied_at=None
            )


class TestApplyModifierDurationHalving(unittest.TestCase):
    """Test Flight modifier duration halving rule."""

    def test_normal_duration_not_flying(self):
        """Non-flying item: duration unchanged."""
        result = apply_modifier_duration_halving(2.0, False)
        self.assertEqual(result, 2.0)

    def test_halved_duration_flying(self):
        """Flying item: duration halved."""
        result = apply_modifier_duration_halving(2.0, True)
        self.assertEqual(result, 1.0)

    def test_odd_duration_flying(self):
        """Flying item with odd duration: properly halved."""
        result = apply_modifier_duration_halving(3.0, True)
        self.assertEqual(result, 1.5)


class TestGetActiveModifierAndEndTime(unittest.TestCase):
    """Test active modifier detection."""

    def test_no_active_modifiers(self):
        """No modifiers active."""
        modifier, mod_type = get_active_modifier_and_end_time(5.0, None, None, None)
        self.assertEqual(modifier, 1.0)
        self.assertIsNone(mod_type)

    def test_slow_active(self):
        """Slow modifier active."""
        modifier, mod_type = get_active_modifier_and_end_time(
            5.0, slow_end_time=10.0, haste_end_time=None, freeze_end_time=None
        )
        self.assertEqual(modifier, 0.5)
        self.assertEqual(mod_type, "slow")

    def test_haste_active(self):
        """Haste modifier active."""
        modifier, mod_type = get_active_modifier_and_end_time(
            5.0, slow_end_time=None, haste_end_time=10.0, freeze_end_time=None
        )
        self.assertEqual(modifier, 2.0)
        self.assertEqual(mod_type, "haste")

    def test_freeze_active(self):
        """Freeze modifier active."""
        modifier, mod_type = get_active_modifier_and_end_time(
            5.0, slow_end_time=None, haste_end_time=None, freeze_end_time=10.0
        )
        self.assertEqual(modifier, 0.0)
        self.assertEqual(mod_type, "freeze")

    def test_modifier_expired(self):
        """Modifier end time in past."""
        modifier, mod_type = get_active_modifier_and_end_time(
            15.0, slow_end_time=10.0, haste_end_time=None, freeze_end_time=None
        )
        self.assertEqual(modifier, 1.0)
        self.assertIsNone(mod_type)

    def test_multiple_modifiers_precedence(self):
        """Multiple somehow active: freeze takes precedence."""
        modifier, mod_type = get_active_modifier_and_end_time(
            5.0, slow_end_time=10.0, haste_end_time=10.0, freeze_end_time=10.0
        )
        self.assertEqual(modifier, 0.0)
        self.assertEqual(mod_type, "freeze")


if __name__ == "__main__":
    unittest.main()
