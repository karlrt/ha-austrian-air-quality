"""Unit tests for the request rectangles.

``grouping`` imports its siblings but no Home Assistant, so it is loaded
through the same stand-in package as ``test_selection``:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib
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
grouping = importlib.import_module(f"{_PACKAGE}.grouping")

# Real stations, so the distances in these tests are the ones the integration
# actually meets. Coordinates as the interface reports them.
GRAZ_DON_BOSCO = (47.0675, 15.4133)
GRAZ_SUED = (47.0347, 15.4444)
GRAZ_SCHLOSSBERG = (47.0758, 15.4375)
WIEN_STEPHANSPLATZ = (48.2083, 16.3731)
BREGENZ = (47.5058, 9.7472)


def contains(box: tuple[float, float, float, float], point: tuple[float, float]) -> bool:
    """Whether a rectangle covers a point."""
    lat_start, lat_end, lng_start, lng_end = box
    return lat_start <= point[0] <= lat_end and lng_start <= point[1] <= lng_end


class TestGrouping(unittest.TestCase):
    """Which rectangles a set of stations produces."""

    def test_no_stations_no_requests(self) -> None:
        self.assertEqual(grouping.boxes_for({}), ())

    def test_single_station_gets_a_tight_box(self) -> None:
        groups = grouping.boxes_for({"06:164": GRAZ_DON_BOSCO})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].station_ids, ("06:164",))
        self.assertTrue(contains(groups[0].bbox, GRAZ_DON_BOSCO))
        height, width = grouping._extent_km(groups[0].bbox)
        self.assertLess(height, 10)
        self.assertLess(width, 10)

    def test_stations_of_one_city_share_a_box(self) -> None:
        """The case this whole module exists for: one request instead of three."""
        groups = grouping.boxes_for(
            {
                "06:164": GRAZ_DON_BOSCO,
                "06:170": GRAZ_SUED,
                "06:018": GRAZ_SCHLOSSBERG,
            }
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].station_ids, ("06:018", "06:164", "06:170"))
        for point in (GRAZ_DON_BOSCO, GRAZ_SUED, GRAZ_SCHLOSSBERG):
            self.assertTrue(contains(groups[0].bbox, point))

    def test_distant_stations_stay_apart(self) -> None:
        """Bregenz plus Vienna must not drag the country into every answer."""
        groups = grouping.boxes_for(
            {"01:0001": BREGENZ, "09:STEF": WIEN_STEPHANSPLATZ}
        )
        self.assertEqual(len(groups), 2)
        for group in groups:
            self.assertLessEqual(max(grouping._extent_km(group.bbox)), grouping.MAX_BOX_KM)

    def test_a_far_station_does_not_break_up_the_near_ones(self) -> None:
        groups = grouping.boxes_for(
            {
                "06:164": GRAZ_DON_BOSCO,
                "06:170": GRAZ_SUED,
                "09:STEF": WIEN_STEPHANSPLATZ,
            }
        )
        self.assertEqual(len(groups), 2)
        by_size = sorted(groups, key=lambda group: len(group.station_ids))
        self.assertEqual(by_size[0].station_ids, ("09:STEF",))
        self.assertEqual(by_size[1].station_ids, ("06:164", "06:170"))

    def test_unknown_coordinates_fall_back_to_the_country(self) -> None:
        """The one rectangle sure to contain a station without a position."""
        groups = grouping.boxes_for(
            {"06:164": GRAZ_DON_BOSCO, "06:999": (None, None)}
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].bbox, const.AT_BBOX)
        self.assertEqual(groups[0].station_ids, ("06:164", "06:999"))

    def test_half_a_position_counts_as_none(self) -> None:
        groups = grouping.boxes_for({"06:999": (47.0, None)})
        self.assertEqual(groups[0].bbox, const.AT_BBOX)

    def test_every_station_ends_up_in_exactly_one_group(self) -> None:
        stations = {
            "06:164": GRAZ_DON_BOSCO,
            "06:170": GRAZ_SUED,
            "06:018": GRAZ_SCHLOSSBERG,
            "09:STEF": WIEN_STEPHANSPLATZ,
            "01:0001": BREGENZ,
        }
        groups = grouping.boxes_for(stations)
        placed = [
            station_id for group in groups for station_id in group.station_ids
        ]
        self.assertEqual(sorted(placed), sorted(stations))
        self.assertEqual(len(placed), len(set(placed)))

    def test_grouping_does_not_depend_on_the_order(self) -> None:
        """A restart must not reshuffle the requests."""
        stations = {
            "06:164": GRAZ_DON_BOSCO,
            "09:STEF": WIEN_STEPHANSPLATZ,
            "06:018": GRAZ_SCHLOSSBERG,
            "01:0001": BREGENZ,
        }
        forward = grouping.boxes_for(stations)
        backward = grouping.boxes_for(dict(reversed(list(stations.items()))))
        self.assertEqual(forward, backward)

    def test_every_group_stays_within_the_limit(self) -> None:
        stations = {
            f"06:{index:03d}": (47.0 + index * 0.2, 15.4 + index * 0.3)
            for index in range(8)
        }
        for group in grouping.boxes_for(stations):
            with self.subTest(group=group.station_ids):
                self.assertLessEqual(
                    max(grouping._extent_km(group.bbox)), grouping.MAX_BOX_KM
                )

    def test_a_group_covers_the_stations_it_claims(self) -> None:
        stations = {
            "06:164": GRAZ_DON_BOSCO,
            "06:170": GRAZ_SUED,
            "06:018": GRAZ_SCHLOSSBERG,
            "09:STEF": WIEN_STEPHANSPLATZ,
        }
        groups = grouping.boxes_for(stations)
        for group in groups:
            for station_id in group.station_ids:
                with self.subTest(station=station_id):
                    self.assertTrue(contains(group.bbox, stations[station_id]))


if __name__ == "__main__":
    unittest.main()
