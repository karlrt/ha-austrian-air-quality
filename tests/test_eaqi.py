"""Unit tests for the EAQI classification.

``eaqi`` deliberately has no Home Assistant imports, so these run against a
plain Python interpreter:

    python -m unittest discover -s tests -v

They are written with :mod:`unittest` rather than pytest fixtures so that no
test dependency is needed; pytest collects them just as happily.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# Loaded straight from the file rather than as part of the package: importing
# austrian_air_quality would run its __init__, which does need Home Assistant,
# and the whole point of eaqi.py is that it does not.
_EAQI_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "austrian_air_quality"
    / "eaqi.py"
)
_spec = importlib.util.spec_from_file_location("eaqi", _EAQI_PATH)
assert _spec is not None and _spec.loader is not None
eaqi = importlib.util.module_from_spec(_spec)
# @dataclass resolves its module through sys.modules, so register before exec.
sys.modules[_spec.name] = eaqi
_spec.loader.exec_module(eaqi)

# Upper bound of every band per pollutant, mirroring the published table.
# Kept separate from the module under test so a typo there is not copied here.
EXPECTED_BANDS = {
    "pm25": (5, 15, 50, 90, 140),
    "pm10": (15, 45, 120, 195, 270),
    "o3": (60, 100, 120, 160, 180),
    "no2": (10, 25, 60, 100, 150),
    "so2": (20, 40, 125, 190, 275),
}


class TestBands(unittest.TestCase):
    """The band table itself."""

    def test_module_matches_published_table(self) -> None:
        self.assertEqual(eaqi.EAQI_BANDS, EXPECTED_BANDS)

    def test_only_the_five_index_pollutants_are_defined(self) -> None:
        self.assertEqual(set(eaqi.EAQI_BANDS), set(EXPECTED_BANDS))
        self.assertNotIn("co", eaqi.EAQI_BANDS)
        self.assertNotIn("no", eaqi.EAQI_BANDS)

    def test_levels_and_numbers_line_up(self) -> None:
        self.assertEqual(len(eaqi.LEVELS), 6)
        self.assertEqual(eaqi.LEVEL_NUMBERS["good"], 1)
        self.assertEqual(eaqi.LEVEL_NUMBERS["extremely_poor"], 6)


class TestBoundaries(unittest.TestCase):
    """A value exactly on a bound belongs to the lower level."""

    def test_upper_bound_stays_in_the_lower_level(self) -> None:
        for pollutant, bounds in EXPECTED_BANDS.items():
            for index, bound in enumerate(bounds):
                with self.subTest(pollutant=pollutant, bound=bound):
                    self.assertEqual(
                        eaqi.index_for(pollutant, bound),
                        eaqi.LEVELS[index],
                        f"{pollutant} {bound} should still be {eaqi.LEVELS[index]}",
                    )

    def test_just_above_a_bound_is_the_next_level(self) -> None:
        for pollutant, bounds in EXPECTED_BANDS.items():
            for index, bound in enumerate(bounds):
                with self.subTest(pollutant=pollutant, bound=bound):
                    self.assertEqual(
                        eaqi.index_for(pollutant, bound + 0.1),
                        eaqi.LEVELS[index + 1],
                    )

    def test_just_below_a_bound_keeps_the_level(self) -> None:
        for pollutant, bounds in EXPECTED_BANDS.items():
            for index, bound in enumerate(bounds):
                with self.subTest(pollutant=pollutant, bound=bound):
                    self.assertEqual(
                        eaqi.index_for(pollutant, bound - 0.1),
                        eaqi.LEVELS[index],
                    )

    def test_zero_is_good_everywhere(self) -> None:
        for pollutant in EXPECTED_BANDS:
            with self.subTest(pollutant=pollutant):
                self.assertEqual(eaqi.index_for(pollutant, 0), eaqi.LEVEL_GOOD)

    def test_above_the_last_bound_is_extremely_poor(self) -> None:
        for pollutant, bounds in EXPECTED_BANDS.items():
            with self.subTest(pollutant=pollutant):
                self.assertEqual(
                    eaqi.index_for(pollutant, bounds[-1] + 0.1),
                    eaqi.LEVEL_EXTREMELY_POOR,
                )
                self.assertEqual(
                    eaqi.index_for(pollutant, bounds[-1] * 10),
                    eaqi.LEVEL_EXTREMELY_POOR,
                )

    def test_documented_example_pm25_five_is_still_good(self) -> None:
        self.assertEqual(eaqi.index_for("pm25", 5), eaqi.LEVEL_GOOD)
        self.assertEqual(eaqi.index_for("pm25", 5.0001), eaqi.LEVEL_FAIR)
        self.assertEqual(eaqi.index_for("pm25", 6), eaqi.LEVEL_FAIR)


class TestUnclassifiableInput(unittest.TestCase):
    """Missing values, unknown keys and negative readings."""

    def test_none_value_has_no_level(self) -> None:
        for pollutant in EXPECTED_BANDS:
            with self.subTest(pollutant=pollutant):
                self.assertIsNone(eaqi.index_for(pollutant, None))

    def test_pollutants_outside_the_index_have_no_level(self) -> None:
        # CO and NO are measured by the integration but are not part of the
        # EAQI, so they must not be given a level of any kind.
        for pollutant in ("co", "no"):
            with self.subTest(pollutant=pollutant):
                self.assertIsNone(eaqi.index_for(pollutant, 1))
                self.assertIsNone(eaqi.index_for(pollutant, 0))
                self.assertFalse(eaqi.is_eaqi_pollutant(pollutant))

    def test_unknown_key_has_no_level(self) -> None:
        self.assertIsNone(eaqi.index_for("nonsense", 10))
        self.assertIsNone(eaqi.index_for("", 10))

    def test_negative_values_are_unclassified_and_never_good(self) -> None:
        for pollutant in EXPECTED_BANDS:
            for value in (-0.1, -1, -100):
                with self.subTest(pollutant=pollutant, value=value):
                    level = eaqi.index_for(pollutant, value)
                    self.assertIsNone(level)
                    self.assertNotEqual(level, eaqi.LEVEL_GOOD)

    def test_sub_indices_skips_what_it_cannot_classify(self) -> None:
        levels = eaqi.sub_indices(
            {"pm25": 3, "o3": None, "no2": -2, "co": 5, "no": 30, "junk": 1}
        )
        self.assertEqual(levels, {"pm25": "good"})


class TestMinimumData(unittest.TestCase):
    """The stricter of the two EEA minimum data rules is applied."""

    def test_no2_o3_and_pm_is_enough(self) -> None:
        self.assertTrue(eaqi.has_minimum_data(("no2", "o3", "pm10")))
        self.assertTrue(eaqi.has_minimum_data(("no2", "o3", "pm25")))
        self.assertTrue(eaqi.has_minimum_data(("no2", "o3", "pm25", "pm10")))

    def test_missing_ozone_is_not_enough(self) -> None:
        # This is the traffic-station rule, which is not applied because the
        # source does not publish the station type.
        self.assertFalse(eaqi.has_minimum_data(("no2", "pm10", "pm25")))

    def test_missing_no2_or_pm_is_not_enough(self) -> None:
        self.assertFalse(eaqi.has_minimum_data(("o3", "pm10")))
        self.assertFalse(eaqi.has_minimum_data(("no2", "o3")))
        self.assertFalse(eaqi.has_minimum_data(()))

    def test_so2_alone_does_not_help(self) -> None:
        self.assertFalse(eaqi.has_minimum_data(("no2", "o3", "so2")))


class TestStationIndex(unittest.TestCase):
    """Aggregation to the station index."""

    def test_worst_sub_index_wins(self) -> None:
        result = eaqi.station_index(
            {"pm25": 3, "pm10": 10, "o3": 170, "no2": 5}
        )
        self.assertEqual(result.level, "very_poor")
        self.assertEqual(result.dominant_pollutant, "o3")
        self.assertEqual(result.number, 5)
        self.assertTrue(result.complete)

    def test_all_good_stays_good(self) -> None:
        result = eaqi.station_index({"pm25": 1, "pm10": 2, "o3": 3, "no2": 4})
        self.assertEqual(result.level, "good")
        self.assertEqual(result.number, 1)

    def test_extremely_poor_propagates(self) -> None:
        result = eaqi.station_index(
            {"pm25": 500, "pm10": 10, "o3": 10, "no2": 5}
        )
        self.assertEqual(result.level, "extremely_poor")
        self.assertEqual(result.dominant_pollutant, "pm25")
        self.assertEqual(result.number, 6)

    def test_pollutants_used_lists_only_classified_ones(self) -> None:
        result = eaqi.station_index(
            {"pm10": 10, "o3": 10, "no2": 5, "so2": None, "co": 3, "no": 40}
        )
        self.assertEqual(result.pollutants_used, ("pm10", "o3", "no2"))

    def test_pollutants_used_follows_a_stable_order(self) -> None:
        result = eaqi.station_index(
            {"so2": 1, "no2": 1, "o3": 1, "pm10": 1, "pm25": 1}
        )
        self.assertEqual(
            result.pollutants_used, ("pm25", "pm10", "o3", "no2", "so2")
        )

    def test_tie_is_broken_in_the_documented_order(self) -> None:
        # Every pollutant lands in "fair"; pm25 comes first in EAQI_POLLUTANTS.
        result = eaqi.station_index({"pm25": 10, "pm10": 20, "o3": 70, "no2": 20})
        self.assertEqual(result.level, "fair")
        self.assertEqual(result.dominant_pollutant, "pm25")

    def test_ozone_only_station_has_no_station_index(self) -> None:
        # The Graz Schlossberg case: ozone is the only measurement, so the
        # sub-index exists but the station index must stay unknown.
        values = {"o3": 70}
        self.assertEqual(eaqi.sub_indices(values), {"o3": "fair"})

        result = eaqi.station_index(values)
        self.assertIsNone(result.level)
        self.assertIsNone(result.number)
        self.assertIsNone(result.dominant_pollutant)
        self.assertFalse(result.complete)
        self.assertEqual(result.pollutants_used, ("o3",))

    def test_incomplete_never_falls_back_to_the_best_value(self) -> None:
        # Good particulate matter and no ozone must not produce "good".
        result = eaqi.station_index({"pm25": 1, "pm10": 1, "no2": 1})
        self.assertIsNone(result.level)
        self.assertNotEqual(result.level, "good")
        self.assertFalse(result.complete)

    def test_incomplete_never_falls_back_to_the_worst_value(self) -> None:
        result = eaqi.station_index({"pm25": 500, "no2": 500})
        self.assertIsNone(result.level)
        self.assertFalse(result.complete)

    def test_negative_reading_removes_the_pollutant_from_the_index(self) -> None:
        # A negative ozone reading leaves the minimum data requirement unmet
        # rather than being treated as a good ozone value.
        result = eaqi.station_index({"pm25": 3, "o3": -0.5, "no2": 5})
        self.assertIsNone(result.level)
        self.assertFalse(result.complete)
        self.assertEqual(result.pollutants_used, ("pm25", "no2"))

    def test_empty_input(self) -> None:
        result = eaqi.station_index({})
        self.assertIsNone(result.level)
        self.assertFalse(result.complete)
        self.assertEqual(result.pollutants_used, ())

    def test_only_non_index_pollutants(self) -> None:
        result = eaqi.station_index({"co": 0.3, "no": 24})
        self.assertIsNone(result.level)
        self.assertFalse(result.complete)
        self.assertEqual(result.pollutants_used, ())


class TestNoHomeAssistantDependency(unittest.TestCase):
    """The module has to stay importable without Home Assistant."""

    def test_module_imports_nothing_from_home_assistant(self) -> None:
        source = Path(eaqi.__file__).read_text(encoding="utf-8")
        self.assertNotIn("homeassistant", source)


if __name__ == "__main__":
    unittest.main()
