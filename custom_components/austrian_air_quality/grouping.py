"""Which bounding boxes a set of stations is fetched with.

The source is not queried by station id but by a geographic rectangle plus a
pollutant and an averaging period. One rectangle therefore answers for every
station inside it, and the number of requests per cycle follows the number of
rectangles, not the number of stations.

Putting *all* stations of an installation into one rectangle would be the
simplest rule, and for the common case - a few stations around one town - it is
also the right one. It stops being right when the stations are far apart:
Bregenz plus Vienna spans the country, and the answer then carries every station
in Austria. Measured on 2026-09-05: a rectangle around one town answers with
6-9 kB, a rectangle around all of Austria with 190-200 kB for the same
pollutant. Fetching a hundred foreign stations to read three of them is not what
"fewer requests" was supposed to mean.

So the stations are grouped: rectangles are merged as long as the merged one
stays within :data:`MAX_BOX_KM`, and stations further apart than that get a
rectangle of their own. An installation watching one town keeps one rectangle;
one watching both ends of the country pays two, not the whole country.

Like :mod:`eaqi`, :mod:`selection` and :mod:`schedule` this module has no Home
Assistant imports and can be exercised on its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import cos, radians

from .const import AT_BBOX, STATION_BBOX_PADDING

# Rough conversion, and rough is enough: the rectangle only preselects, the
# answer is filtered by station id afterwards.
KM_PER_DEGREE_LAT = 111.0

# How large a merged rectangle may get, in kilometres, along either edge. Sized
# to hold a city and its surroundings in one rectangle - the stations of Graz
# lie some ten kilometres apart - while keeping two distant stations apart
# rather than dragging the country in between into every answer.
MAX_BOX_KM = 60.0

# A bounding box as the interface wants it: (lat_start, lat_end, lng_start,
# lng_end).
type BoundingBox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class StationGroup:
    """One request rectangle and the stations it answers for."""

    bbox: BoundingBox
    station_ids: tuple[str, ...]


def _box_around(latitude: float, longitude: float, padding: float) -> BoundingBox:
    """The smallest rectangle for a single station."""
    return (
        latitude - padding,
        latitude + padding,
        longitude - padding,
        longitude + padding,
    )


def _merged(first: BoundingBox, second: BoundingBox) -> BoundingBox:
    """The smallest rectangle containing both."""
    return (
        min(first[0], second[0]),
        max(first[1], second[1]),
        min(first[2], second[2]),
        max(first[3], second[3]),
    )


def _extent_km(box: BoundingBox) -> tuple[float, float]:
    """Height and width of a rectangle in kilometres."""
    lat_start, lat_end, lng_start, lng_end = box
    middle = (lat_start + lat_end) / 2
    height = (lat_end - lat_start) * KM_PER_DEGREE_LAT
    width = (lng_end - lng_start) * KM_PER_DEGREE_LAT * max(cos(radians(middle)), 0.1)
    return height, width


def _area(box: BoundingBox) -> float:
    """Area of a rectangle in square kilometres, for comparing merges."""
    height, width = _extent_km(box)
    return height * width


def _fits(box: BoundingBox, max_km: float) -> bool:
    """Whether a rectangle is still small enough to be worth one request."""
    height, width = _extent_km(box)
    return height <= max_km and width <= max_km


def boxes_for(
    coordinates: Mapping[str, tuple[float | None, float | None]],
    padding: float = STATION_BBOX_PADDING,
    max_km: float = MAX_BOX_KM,
) -> tuple[StationGroup, ...]:
    """Group stations into the rectangles they are fetched with.

    ``coordinates`` maps station id to its (latitude, longitude); either may be
    ``None`` for a station whose position is not known yet.

    A station without coordinates cannot be placed in a rectangle at all, and
    the only rectangle certain to contain it is the country. Since that one
    contains every other station too, one group covers them all in that case -
    the same fallback a single station has always used, just not paid for twice.

    The result is deterministic: the same stations produce the same grouping
    whatever order they arrive in, so a restart does not reshuffle the requests.
    """
    if not coordinates:
        return ()

    placed: dict[str, BoundingBox] = {}
    for station_id in sorted(coordinates):
        latitude, longitude = coordinates[station_id]
        if latitude is None or longitude is None:
            return (StationGroup(AT_BBOX, tuple(sorted(coordinates))),)
        placed[station_id] = _box_around(latitude, longitude, padding)

    # Start with one rectangle per station and merge the cheapest pair as long
    # as the result stays inside the limit. With a handful of stations the
    # quadratic search costs nothing, and merging by smallest resulting area
    # keeps the rectangles tighter than merging in arrival order would.
    groups: list[tuple[list[str], BoundingBox]] = [
        ([station_id], box) for station_id, box in placed.items()
    ]

    while len(groups) > 1:
        best: tuple[float, int, int, BoundingBox] | None = None
        for first in range(len(groups)):
            for second in range(first + 1, len(groups)):
                candidate = _merged(groups[first][1], groups[second][1])
                if not _fits(candidate, max_km):
                    continue
                area = _area(candidate)
                if best is None or area < best[0]:
                    best = (area, first, second, candidate)
        if best is None:
            break
        _, first, second, candidate = best
        ids = groups[first][0] + groups[second][0]
        for index in (second, first):
            del groups[index]
        groups.append((sorted(ids), candidate))

    return tuple(
        StationGroup(box, tuple(ids))
        for ids, box in sorted(groups, key=lambda group: group[0][0])
    )
