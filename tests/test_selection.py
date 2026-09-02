"""Unit tests for the entity selection and the query plan it implies.

Like ``eaqi``, ``selection`` has no Home Assistant imports, so these run
against a plain Python interpreter:

    python -m unittest discover -s tests -v

Unlike ``eaqi`` it does import its siblings, so it cannot be loaded from its
file alone. A stand-in package is registered under a name of its own and
pointed at the integration directory; that resolves the relative imports
without executing the integration's ``__init__``, which really does need Home
Assistant.
"""

from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from pathlib import Path

_PACKAGE = "austrian_air_quality_under_test"
_SOURCE = (
    Path(__file__).resolve().parents[1] / "custom_components" / "austrian_air_quality"
)

if _PACKAGE not in sys.modules:
    _stand_in = types.ModuleType(_PACKAGE)
    _stand_in.__path__ = [str(_SOURCE)]  # type: ignore[attr-defined]
    sys.modules[_PACKAGE] = _stand_in

const = importlib.import_module(f"{_PACKAGE}.const")
eaqi = importlib.import_module(f"{_PACKAGE}.eaqi")
selection = importlib.import_module(f"{_PACKAGE}.selection")

CURRENT = const.MEANTYPE_CURRENT
DAILY = const.MEANTYPE_DAILY


def options(**kwargs: object) -> dict[str, object]:
    """Entry options with only the keys a test cares about."""
    return dict(kwargs)


class TestCatalogue(unittest.TestCase):
    """The catalogue is the full set, independent of any station."""

    def test_every_pollutant_in_every_averaging_period(self) -> None:
        self.assertEqual(
            len(const.MEASUREMENT_KEYS),
            len(const.POLLUTANTS) * len(const.MEANTYPES),
        )

    def test_the_current_value_keeps_the_bare_pollutant_key(self) -> None:
        self.assertIn("pm10", const.MEASUREMENT_KEYS)
        self.assertIn("pm10_daily", const.MEASUREMENT_KEYS)

    def test_one_sub_index_per_index_pollutant(self) -> None:
        self.assertEqual(len(selection.INDEX_KEYS), len(eaqi.EAQI_POLLUTANTS))
        self.assertNotIn("co_index", selection.INDEX_KEYS)
        self.assertNotIn("no_index", selection.INDEX_KEYS)


class TestReadingTheSelection(unittest.TestCase):
    """What is stored, and what happens when it is odd."""

    def test_an_entry_without_options_tracks_everything(self) -> None:
        # The moment before the defaults are written. Nothing may vanish here.
        self.assertEqual(selection.wanted_measurements({}), const.MEASUREMENT_KEYS)
        self.assertEqual(selection.wanted_indexes({}), selection.INDEX_KEYS)
        self.assertTrue(selection.wants_station_index({}))
        self.assertTrue(selection.wants_location({}))

    def test_an_empty_selection_is_honoured(self) -> None:
        # Not the same as "no selection stored": this one was made on purpose.
        self.assertEqual(
            selection.wanted_measurements(options(measurements=[])), ()
        )

    def test_keys_that_no_longer_exist_are_ignored(self) -> None:
        stored = options(measurements=["pm10", "unobtainium", "pm10_mw8"])
        self.assertEqual(selection.wanted_measurements(stored), ("pm10",))

    def test_a_broken_option_does_not_take_the_entry_down(self) -> None:
        self.assertEqual(
            selection.wanted_measurements(options(measurements="pm10")), ()
        )

    def test_the_catalogue_decides_the_order(self) -> None:
        stored = options(measurements=["co_daily", "pm10"])
        self.assertEqual(
            selection.wanted_measurements(stored), ("pm10", "co_daily")
        )


class TestQueryPlan(unittest.TestCase):
    """What has to be fetched follows from the entities, not the other way."""

    def test_only_what_is_selected_is_fetched(self) -> None:
        stored = options(
            measurements=["o3", "pm10_daily"],
            indexes=[],
            station_index=False,
        )
        self.assertEqual(
            selection.required_queries(stored),
            (("pm10", DAILY), ("o3", CURRENT)),
        )

    def test_nothing_selected_asks_the_source_for_nothing(self) -> None:
        stored = options(measurements=[], indexes=[], station_index=False)
        self.assertEqual(selection.required_queries(stored), ())

    def test_a_sub_index_pulls_in_its_own_pollutant(self) -> None:
        # The measurement entity is not wanted, the classification of it is.
        stored = options(measurements=[], indexes=["o3_index"], station_index=False)
        self.assertEqual(selection.required_queries(stored), (("o3", CURRENT),))

    def test_the_station_index_pulls_in_all_five(self) -> None:
        stored = options(measurements=[], indexes=[], station_index=True)
        self.assertEqual(
            set(selection.required_queries(stored)),
            {(pollutant, CURRENT) for pollutant in eaqi.EAQI_POLLUTANTS},
        )

    def test_dropping_a_measurement_does_not_empty_the_station_index(self) -> None:
        # Ozone is what the minimum data requirement fails on first, so a
        # selection that keeps the index but drops the ozone sensor must still
        # fetch ozone. Anything else turns a saved request into an index that
        # silently reads unknown.
        stored = options(
            measurements=["pm10", "no2"], indexes=[], station_index=True
        )
        self.assertIn(("o3", CURRENT), selection.required_queries(stored))

    def test_the_full_catalogue_is_the_upper_bound(self) -> None:
        self.assertEqual(
            len(selection.required_queries({})), len(const.MEASUREMENT_KEYS)
        )


class TestDefaults(unittest.TestCase):
    """The starting point of an entry, from the station and from what exists."""

    def test_what_the_station_reports_is_preselected(self) -> None:
        defaults = selection.default_options(reported=["o3", "o3_daily"])
        self.assertEqual(defaults[const.OPT_MEASUREMENTS], ["o3", "o3_daily"])
        self.assertEqual(defaults[const.OPT_INDEXES], ["o3_index"])

    def test_a_station_without_index_pollutants_gets_no_index(self) -> None:
        defaults = selection.default_options(reported=["co", "no"])
        self.assertEqual(defaults[const.OPT_INDEXES], [])
        self.assertFalse(defaults[const.OPT_STATION_INDEX])

    def test_the_station_index_is_preselected_where_it_can_have_a_level(self) -> None:
        defaults = selection.default_options(reported=["no2", "o3", "pm10"])
        self.assertTrue(defaults[const.OPT_STATION_INDEX])
        self.assertTrue(
            eaqi.has_minimum_data(("no2", "o3", "pm10")),
            "the preselection has to follow the minimum data requirement",
        )

    def test_a_station_short_of_the_minimum_data_gets_no_station_index(self) -> None:
        # Graz Schlossberg reports ozone alone: neither coverage rule is met,
        # so the two index entities would never leave "unknown". The ozone
        # sub-index it can reach stays preselected.
        ozone_only = selection.default_options(reported=["o3"])
        self.assertFalse(ozone_only[const.OPT_STATION_INDEX])
        self.assertEqual(ozone_only[const.OPT_INDEXES], ["o3_index"])

    def test_a_station_without_ozone_gets_the_station_index(self) -> None:
        # Graz Mitte Gries: no ozone, so the traffic rule applies and the index
        # can reach a level. The preselection follows whichever rule is met.
        no_ozone = selection.default_options(reported=["pm25", "no2", "co"])
        self.assertTrue(no_ozone[const.OPT_STATION_INDEX])
        self.assertEqual(no_ozone[const.OPT_INDEXES], ["pm25_index", "no2_index"])

    def test_particulate_matter_alone_is_not_enough_for_the_station_index(self) -> None:
        # Neither rule works without NO2.
        defaults = selection.default_options(reported=["pm10", "pm25"])
        self.assertFalse(defaults[const.OPT_STATION_INDEX])

    def test_particulate_matter_counts_as_one_group(self) -> None:
        # PM2.5 or PM10 satisfies the particulate part, neither is required.
        for particulate in ("pm25", "pm10"):
            with self.subTest(particulate=particulate):
                defaults = selection.default_options(
                    reported=["no2", "o3", particulate]
                )
                self.assertTrue(defaults[const.OPT_STATION_INDEX])

    def test_an_existing_station_index_survives_the_stricter_default(self) -> None:
        # An installation that already carries the entity keeps it: a default
        # must not drop an entity and its history behind the user's back.
        defaults = selection.default_options(
            reported=["o3"], existing=["o3", const.KEY_STATION_INDEX]
        )
        self.assertTrue(defaults[const.OPT_STATION_INDEX])

    def test_an_existing_entity_survives_a_station_that_pauses(self) -> None:
        # Graz Sued Tiergartenweg, 2026-09-01: the sulphur dioxide sensor had
        # been there for weeks, the station stopped reporting it for a day, and
        # a restart deriving the entity set from that moment dropped it for
        # good. The selection has to keep it.
        defaults = selection.default_options(
            reported=["pm10", "o3", "no2"],
            existing=["so2", "so2_index", "pm10", "o3", "no2"],
        )
        self.assertIn("so2", defaults[const.OPT_MEASUREMENTS])
        self.assertIn("so2_index", defaults[const.OPT_INDEXES])

    def test_a_pollutant_the_station_reports_again_is_picked_up(self) -> None:
        # The other direction of the same fault: back in the data, no entity.
        defaults = selection.default_options(
            reported=["so2"], existing=["pm10", "pm10_daily"]
        )
        self.assertIn("so2", defaults[const.OPT_MEASUREMENTS])
        self.assertIn("pm10_daily", defaults[const.OPT_MEASUREMENTS])

    def test_nothing_known_selects_nothing(self) -> None:
        defaults = selection.default_options()
        self.assertEqual(defaults[const.OPT_MEASUREMENTS], [])

    def test_defaults_round_trip_through_the_readers(self) -> None:
        defaults = selection.default_options(reported=["pm25", "pm25_daily", "co"])
        self.assertEqual(
            selection.wanted_measurements(defaults), ("pm25", "pm25_daily", "co")
        )
        self.assertEqual(selection.wanted_indexes(defaults), ("pm25_index",))


class TestCatalogueHalves(unittest.TestCase):
    """The setup asks for the two averaging periods on separate steps.

    The split lives in the forms only. Whatever it does to the presentation,
    the two halves have to add back up to the catalogue the stored selection is
    read against, or a key becomes unreachable in the setup.
    """

    def test_the_halves_add_up_to_the_catalogue(self) -> None:
        self.assertEqual(
            set(selection.CURRENT_KEYS) | set(selection.DAILY_KEYS),
            set(const.MEASUREMENT_KEYS),
        )
        self.assertEqual(
            len(selection.CURRENT_KEYS) + len(selection.DAILY_KEYS),
            len(const.MEASUREMENT_KEYS),
        )

    def test_no_key_is_in_both_halves(self) -> None:
        self.assertEqual(
            set(selection.CURRENT_KEYS) & set(selection.DAILY_KEYS), set()
        )

    def test_each_half_keeps_the_catalogue_order(self) -> None:
        for half in (selection.CURRENT_KEYS, selection.DAILY_KEYS):
            with self.subTest(half=half[:1]):
                self.assertEqual(
                    half,
                    tuple(key for key in const.MEASUREMENT_KEYS if key in set(half)),
                )

    def test_the_current_half_is_the_bare_pollutant_keys(self) -> None:
        self.assertEqual(selection.CURRENT_KEYS, const.POLLUTANTS)


class TestDailyCounterparts(unittest.TestCase):
    """What the second step starts from."""

    def test_a_chosen_pollutant_brings_its_daily_mean(self) -> None:
        self.assertEqual(
            selection.daily_counterparts(["o3", "no2"]), ("no2_daily", "o3_daily")
        )

    def test_the_catalogue_decides_the_order(self) -> None:
        self.assertEqual(
            selection.daily_counterparts(["co", "pm10"]), ("pm10_daily", "co_daily")
        )

    def test_nothing_chosen_brings_nothing(self) -> None:
        self.assertEqual(selection.daily_counterparts([]), ())

    def test_unknown_keys_are_ignored(self) -> None:
        self.assertEqual(selection.daily_counterparts(["radon", "o3"]), ("o3_daily",))


class TestStationIndexDefault(unittest.TestCase):
    """The coverage rule, read off the pollutants instead of the sub-indices.

    The setup no longer preselects sub-indices, so deriving the rule from them
    would answer "no" at every station.
    """

    def test_a_station_with_the_standard_coverage(self) -> None:
        self.assertTrue(selection.station_index_default(["no2", "o3", "pm10"]))

    def test_a_station_without_ozone_falls_back_to_the_traffic_rule(self) -> None:
        self.assertTrue(selection.station_index_default(["no2", "pm25", "co"]))

    def test_ozone_alone_reaches_no_level(self) -> None:
        self.assertFalse(selection.station_index_default(["o3"]))

    def test_particulate_matter_alone_is_not_enough(self) -> None:
        self.assertFalse(selection.station_index_default(["pm10", "pm25"]))

    def test_a_station_reporting_nothing_reaches_no_level(self) -> None:
        self.assertFalse(selection.station_index_default([]))


class TestConfirmDefaults(unittest.TestCase):
    """The lean selection the first step of the setup starts from."""

    def test_only_the_freshest_values_are_preselected(self) -> None:
        defaults = selection.default_for_confirm(["pm10", "no2"])
        self.assertEqual(defaults[const.OPT_MEASUREMENTS], ["pm10", "no2"])

    def test_no_daily_mean_sneaks_in(self) -> None:
        defaults = selection.default_for_confirm(const.POLLUTANTS)
        self.assertEqual(
            [
                key
                for key in defaults[const.OPT_MEASUREMENTS]
                if key in set(selection.DAILY_KEYS)
            ],
            [],
        )

    def test_sub_indices_and_coordinates_stay_out(self) -> None:
        defaults = selection.default_for_confirm(["no2", "o3", "pm10"])
        self.assertEqual(defaults[const.OPT_INDEXES], [])
        self.assertFalse(defaults[const.OPT_LOCATION])

    def test_the_station_index_follows_the_coverage_rule(self) -> None:
        self.assertTrue(
            selection.default_for_confirm(["no2", "pm10"])[const.OPT_STATION_INDEX]
        )
        self.assertFalse(
            selection.default_for_confirm(["o3"])[const.OPT_STATION_INDEX]
        )

    def test_it_round_trips_through_the_readers(self) -> None:
        defaults = selection.default_for_confirm(["no2", "pm10"])
        self.assertEqual(selection.wanted_measurements(defaults), ("pm10", "no2"))
        self.assertEqual(selection.wanted_indexes(defaults), ())
        self.assertTrue(selection.wants_station_index(defaults))
        self.assertFalse(selection.wants_location(defaults))


class TestSelectorLabels(unittest.TestCase):
    """Every option the forms offer needs a label in every language.

    The select selectors hand out bare keys and let the translations turn them
    into something readable. A key without a label is not an error anywhere -
    it just shows up as "pm25_daily" in the form.
    """

    FILES = (
        _SOURCE / "strings.json",
        _SOURCE / "translations" / "en.json",
        _SOURCE / "translations" / "de.json",
    )

    def test_every_catalogue_key_has_a_label(self) -> None:
        for path in self.FILES:
            translations = json.loads(path.read_text(encoding="utf-8"))
            selectors = translations["selector"]
            with self.subTest(file=path.name):
                self.assertEqual(
                    set(selectors["measurements"]["options"]),
                    set(const.MEASUREMENT_KEYS),
                )
                self.assertEqual(
                    set(selectors["indexes"]["options"]),
                    set(selection.INDEX_KEYS),
                )

    # The fields each setup step asks for. A field without a label is not an
    # error either - Home Assistant just prints the raw key, which is how
    # "advanced" once ended up on screen under that name.
    STEP_FIELDS = {
        "confirm": {"measurements", "station_index", "advanced"},
        "extras": {"daily_means", "indexes", "location_entity"},
    }

    def test_every_form_field_has_a_label(self) -> None:
        for path in self.FILES:
            translations = json.loads(path.read_text(encoding="utf-8"))
            steps = translations["config"]["step"]
            for step, fields in self.STEP_FIELDS.items():
                with self.subTest(file=path.name, step=step):
                    self.assertEqual(set(steps[step]["data"]), fields)


if __name__ == "__main__":
    unittest.main()
