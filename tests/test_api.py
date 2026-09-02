"""Unit tests for the timestamp parsing of the map interface client.

``api`` imports its siblings and ``aiohttp``, so it cannot be loaded from its
file alone. A stand-in package is registered under a name of its own and
pointed at the integration directory, the same way ``test_selection`` does it,
and a minimal ``aiohttp`` stand-in covers the import where the real package is
missing. Nothing here touches the network, so the stub is never called:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PACKAGE = "austrian_air_quality_under_test"
_SOURCE = (
    Path(__file__).resolve().parents[1] / "custom_components" / "austrian_air_quality"
)

if _PACKAGE not in sys.modules:
    _stand_in = types.ModuleType(_PACKAGE)
    _stand_in.__path__ = [str(_SOURCE)]  # type: ignore[attr-defined]
    sys.modules[_PACKAGE] = _stand_in

try:  # pragma: no cover - depends on the interpreter the tests run on
    import aiohttp  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - the bare interpreter case
    _aiohttp = types.ModuleType("aiohttp")
    for _name in ("ClientSession", "ClientTimeout", "ClientError"):
        setattr(_aiohttp, _name, type(_name, (Exception,), {}))
    sys.modules["aiohttp"] = _aiohttp

api = importlib.import_module(f"{_PACKAGE}.api")

CET = timezone(timedelta(hours=1))


class TestParseMeasurementTime(unittest.TestCase):
    """The timestamp the interface puts on every measurement."""

    def setUp(self) -> None:
        # The "no offset" warning fires once per process; every test that cares
        # about it starts from the same state.
        api._missing_offset_warned = False

    def test_the_documented_format_parses(self) -> None:
        self.assertEqual(
            api.parse_measurement_time("28 Aug 2026 13:30:00 GMT+0100"),
            datetime(2026, 8, 28, 13, 30, 0, tzinfo=CET),
        )

    def test_every_english_month_parses(self) -> None:
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        for number, month in enumerate(months, start=1):
            with self.subTest(month=month):
                parsed = api.parse_measurement_time(
                    f"2 {month} 2026 00:00:00 GMT+0100"
                )
                assert parsed is not None
                self.assertEqual(parsed.month, number)

    def test_german_month_abbreviations_parse(self) -> None:
        # Everything the endpoint would name differently in German, including
        # the Austrian "Jän". Without these the timestamp silently disappears.
        german = (("Jän", 1), ("Mär", 3), ("Mai", 5), ("Okt", 10), ("Dez", 12))
        for month, number in german:
            with self.subTest(month=month):
                parsed = api.parse_measurement_time(
                    f"2 {month} 2026 00:00:00 GMT+0100"
                )
                assert parsed is not None
                self.assertEqual(parsed.month, number)

    def test_an_unknown_month_yields_none(self) -> None:
        self.assertIsNone(api.parse_measurement_time("2 Foo 2026 00:00:00 GMT+0100"))

    def test_the_offset_is_used_as_provided(self) -> None:
        parsed = api.parse_measurement_time("2 Sep 2026 12:00:00 GMT+0200")
        assert parsed is not None
        self.assertEqual(parsed.utcoffset(), timedelta(hours=2))
        self.assertEqual(
            parsed.astimezone(timezone.utc),
            datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc),
        )

    def test_a_negative_offset_is_used_as_provided(self) -> None:
        parsed = api.parse_measurement_time("2 Sep 2026 12:00:00 GMT-0130")
        assert parsed is not None
        self.assertEqual(parsed.utcoffset(), -timedelta(hours=1, minutes=30))

    def test_a_missing_offset_is_read_as_cet(self) -> None:
        # Reading it as UTC would move every timestamp by an hour, and nothing
        # about the value would look wrong.
        with self.assertLogs(api._LOGGER, level="WARNING"):
            parsed = api.parse_measurement_time("2 Sep 2026 00:00:00")
        assert parsed is not None
        self.assertEqual(parsed.utcoffset(), timedelta(hours=1))
        self.assertEqual(
            parsed.astimezone(timezone.utc),
            datetime(2026, 9, 1, 23, 0, 0, tzinfo=timezone.utc),
        )

    def test_the_missing_offset_is_only_warned_about_once(self) -> None:
        with self.assertLogs(api._LOGGER, level="WARNING") as captured:
            api.parse_measurement_time("2 Sep 2026 00:00:00")
        self.assertEqual(len(captured.records), 1)
        with self.assertNoLogs(api._LOGGER, level="WARNING"):
            api.parse_measurement_time("3 Sep 2026 00:00:00")

    def test_a_complete_timestamp_does_not_warn(self) -> None:
        with self.assertNoLogs(api._LOGGER, level="WARNING"):
            api.parse_measurement_time("2 Sep 2026 00:00:00 GMT+0100")

    def test_broken_input_yields_none(self) -> None:
        for raw in (
            None,
            "",
            "   ",
            "not a timestamp",
            "31 Feb 2026 00:00:00 GMT+0100",
            "2 Sep 2026 25:00:00 GMT+0100",
            "2026-09-02T00:00:00+01:00",
        ):
            with self.subTest(raw=raw):
                self.assertIsNone(api.parse_measurement_time(raw))


class TestToFloat(unittest.TestCase):
    """Values arrive with a comma or a decimal point, depending on the field."""

    def test_both_decimal_separators_parse(self) -> None:
        self.assertEqual(api._to_float("12,5"), 12.5)
        self.assertEqual(api._to_float("12.5"), 12.5)
        self.assertEqual(api._to_float(7), 7.0)

    def test_unusable_values_yield_none(self) -> None:
        for raw in (None, "", "n/a", {}):
            with self.subTest(raw=raw):
                self.assertIsNone(api._to_float(raw))


class TestParseMeasurement(unittest.TestCase):
    """A single station entry out of the JSON response."""

    def _entry(self, **overrides: object) -> dict:
        entry = {
            "stationid": "S123",
            "value": "12,5",
            "unit": "µg/m³",
            "time": "28 Aug 2026 13:30:00 GMT+0100",
            "valueclass": "2",
            "MetaInfo": {"Name": "Graz Süd", "Location": "Graz", "Owner": "Land"},
            "gml$Point": {"gml$coord": {"X": "15,45", "Y": "47,05", "Z": "340"}},
        }
        entry.update(overrides)
        return entry

    def test_a_complete_entry_parses(self) -> None:
        measurement = api._parse_measurement(self._entry())
        assert measurement is not None
        self.assertEqual(measurement.station_id, "S123")
        self.assertEqual(measurement.station_name, "Graz Süd")
        self.assertEqual(measurement.value, 12.5)
        # X is the longitude and Y the latitude, despite the EPSG:31287 label.
        self.assertEqual(measurement.longitude, 15.45)
        self.assertEqual(measurement.latitude, 47.05)
        self.assertEqual(
            measurement.measured_at, datetime(2026, 8, 28, 13, 30, 0, tzinfo=CET)
        )

    def test_an_unparsable_time_keeps_the_raw_value(self) -> None:
        measurement = api._parse_measurement(self._entry(time="gestern"))
        assert measurement is not None
        self.assertIsNone(measurement.measured_at)
        self.assertEqual(measurement.measured_at_raw, "gestern")

    def test_entries_without_id_or_value_are_dropped(self) -> None:
        for entry in (
            self._entry(stationid=None),
            self._entry(stationid=""),
            self._entry(value=None),
            self._entry(value="n/a"),
            {},
        ):
            with self.subTest(entry=entry):
                self.assertIsNone(api._parse_measurement(entry))

    def test_missing_metadata_falls_back_to_the_station_id(self) -> None:
        measurement = api._parse_measurement(
            {"stationid": "S1", "value": "1", "unit": "µg/m³"}
        )
        assert measurement is not None
        self.assertEqual(measurement.station_name, "S1")
        self.assertIsNone(measurement.latitude)
        self.assertIsNone(measurement.measured_at)


if __name__ == "__main__":
    unittest.main()
