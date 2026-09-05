"""Unit tests for icons.json.

The pollutant sensors get their icon from ``range`` thresholds, and those
thresholds are meant to be the EAQI bands and nothing else. A band that is
corrected in ``eaqi.py`` without ``icons.json`` following would leave the
measurement sensor showing one level while the index sensor next to it shows
another, and nothing in Home Assistant would complain. Hence this test.

Runs on a plain Python interpreter, like ``test_eaqi.py``:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

_COMPONENT = (
    Path(__file__).resolve().parents[1] / "custom_components" / "austrian_air_quality"
)
_ICONS_PATH = _COMPONENT / "icons.json"

_spec = importlib.util.spec_from_file_location("eaqi_for_icons", _COMPONENT / "eaqi.py")
assert _spec is not None and _spec.loader is not None
eaqi = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = eaqi
_spec.loader.exec_module(eaqi)

ICONS = json.loads(_ICONS_PATH.read_text(encoding="utf-8"))
SENSORS = ICONS["entity"]["sensor"]

# The six icons of the level scale, best to worst. The index sensors use the
# same ones for their states, so a measurement sensor and its sub-index show
# the same symbol.
LEVEL_ICONS = (
    "mdi:gauge-empty",
    "mdi:gauge-low",
    "mdi:gauge",
    "mdi:gauge-full",
    "mdi:alert-outline",
    "mdi:alert-octagon-outline",
)


class TestPollutantRanges(unittest.TestCase):
    """The range thresholds have to match the bands in eaqi.py."""

    def test_every_index_pollutant_has_ranges(self) -> None:
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                self.assertIn(pollutant, SENSORS)
                self.assertIn("range", SENSORS[pollutant])

    def test_thresholds_are_the_published_lower_band_bounds(self) -> None:
        """0 plus every upper bound raised by one.

        The EEA publishes whole numbers with gaps: PM2.5 "0-5", then "6-15".
        ``eaqi.py`` stores the upper bounds (5, 15, ...) and reads them as
        inclusive; the icon thresholds are the published lower bounds of the
        next band, which is the same table from the other side.
        """
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                expected = [0] + [bound + 1 for bound in eaqi.EAQI_BANDS[pollutant]]
                actual = [float(key) for key in SENSORS[pollutant]["range"]]
                self.assertEqual(actual, [float(value) for value in expected])

    def test_thresholds_are_sorted(self) -> None:
        """hassfest rejects unsorted range keys."""
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                keys = [float(key) for key in SENSORS[pollutant]["range"]]
                self.assertEqual(keys, sorted(keys))

    def test_icons_are_the_level_scale(self) -> None:
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                self.assertEqual(
                    tuple(SENSORS[pollutant]["range"].values()), LEVEL_ICONS
                )

    def test_measurement_sensors_carry_no_default(self) -> None:
        """Without a default, values outside the bands keep the device class icon.

        That is the point: a negative reading (see eaqi_entscheidungen.md,
        point 6) and an unavailable sensor must not be shown as "good".
        """
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                self.assertNotIn("default", SENSORS[pollutant])

    def test_daily_means_have_no_range_icons(self) -> None:
        """The bands are defined on hourly means, not on daily ones."""
        for pollutant in eaqi.EAQI_POLLUTANTS:
            with self.subTest(pollutant=pollutant):
                self.assertNotIn(f"{pollutant}_daily", SENSORS)

    def test_pollutants_without_bands_have_no_icons_of_their_own(self) -> None:
        """CO and NO are not part of the EAQI, so no threshold is defensible."""
        for pollutant in ("co", "no"):
            with self.subTest(pollutant=pollutant):
                self.assertNotIn(pollutant, SENSORS)


class TestIndexIcons(unittest.TestCase):
    """The enum sensors keep their state mapping."""

    def test_every_level_has_an_icon(self) -> None:
        index_keys = [f"{pollutant}_index" for pollutant in eaqi.EAQI_POLLUTANTS]
        for key in [*index_keys, "air_quality_index"]:
            with self.subTest(key=key):
                states = SENSORS[key]["state"]
                self.assertEqual(tuple(states), tuple(eaqi.LEVELS))
                self.assertEqual(tuple(states.values()), LEVEL_ICONS)

    def test_state_icons_differ_from_the_default(self) -> None:
        """hassfest rejects a state icon that repeats the default."""
        for key, section in SENSORS.items():
            default = section.get("default")
            if not default:
                continue
            for state, icon in section.get("state", {}).items():
                with self.subTest(key=key, state=state):
                    self.assertNotEqual(icon, default)


if __name__ == "__main__":
    unittest.main()
