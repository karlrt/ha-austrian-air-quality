"""Unit tests for the fetch schedule.

Like ``eaqi``, ``schedule`` has no Home Assistant imports, so these run against
a plain Python interpreter:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "austrian_air_quality"
    / "schedule.py"
)
_spec = importlib.util.spec_from_file_location("aaq_schedule_under_test", _SOURCE)
assert _spec is not None and _spec.loader is not None
schedule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schedule)

PERIOD = 1800


class TestPollPhase(unittest.TestCase):
    """The fixed position of an entry inside the publication window."""

    def test_the_phase_is_inside_the_window(self) -> None:
        for entry_id in ("a", "01J0", "b" * 64, ""):
            with self.subTest(entry_id=entry_id):
                phase = schedule.poll_phase(entry_id, PERIOD)
                self.assertGreaterEqual(phase, 0)
                self.assertLess(phase, PERIOD)

    def test_the_same_entry_always_gets_the_same_phase(self) -> None:
        # It has to survive a restart, or every restart would move the station
        # to a different slot and the alignment would be worth nothing.
        first = schedule.poll_phase("01JABCDEF", PERIOD)
        self.assertEqual(first, schedule.poll_phase("01JABCDEF", PERIOD))

    def test_different_entries_get_different_phases(self) -> None:
        # Not a guarantee - two of 1800 slots can collide - but the spread has
        # to be real, or the point of the phase is lost.
        phases = {schedule.poll_phase(f"entry-{i}", PERIOD) for i in range(200)}
        self.assertGreater(len(phases), 150)


class TestNextSlot(unittest.TestCase):
    """Distance to the next slot, in seconds."""

    def test_a_slot_is_a_whole_period_away_from_the_previous_one(self) -> None:
        # Exactly on the slot: the next one is a full window away, never zero.
        self.assertEqual(schedule.seconds_until_next_slot(3600 + 120, 120, PERIOD), PERIOD)

    def test_the_distance_shrinks_as_the_window_passes(self) -> None:
        self.assertEqual(schedule.seconds_until_next_slot(3600 + 130, 120, PERIOD), 1790)
        self.assertEqual(schedule.seconds_until_next_slot(3600 + 1919, 120, PERIOD), 1)

    def test_the_distance_is_always_inside_the_window(self) -> None:
        for offset in range(0, 3 * PERIOD, 37):
            with self.subTest(offset=offset):
                left = schedule.seconds_until_next_slot(offset + 0.5, 743, PERIOD)
                self.assertGreater(left, 0)
                self.assertLessEqual(left, PERIOD)

    def test_the_grid_does_not_drift(self) -> None:
        # The point of the whole module: a fetch that takes half a minute must
        # not push the next one half a minute later. Walking the schedule
        # forward through a day has to land on the same phase every time.
        phase = schedule.poll_phase("some-entry-id", PERIOD)
        now = 1_756_800_000.0
        for _ in range(48):
            now += schedule.seconds_until_next_slot(now, phase, PERIOD)
            self.assertEqual((now - phase) % PERIOD, 0)
            # What the fetch itself costs, before the next distance is measured.
            now += 31.4


if __name__ == "__main__":
    unittest.main()
