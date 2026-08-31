"""European Air Quality Index (EAQI) classification.

Pure Python on purpose: no Home Assistant imports, so the classification can be
exercised on its own. The sensor platform is the only place that turns the
results below into entities.

Source of the bands
-------------------
European Environment Agency, "European Air Quality Index",
https://airindex.eea.europa.eu/AQI/index.html - the band table as published
after the 2024 revision. Retrieved 2026-08-31.

The same page states the two rules this module implements on top of the bands:
the index "corresponds to the poorest level for any of the five pollutants",
and hourly concentrations are what the levels are defined on.

The EEA is explicit that the index "is not a tool for checking compliance with
air quality standards and cannot be used for this purpose".

Scope
-----
The index covers exactly five pollutants: PM2.5, PM10, O3, NO2 and SO2. Carbon
monoxide and nitrogen monoxide are *not* part of the EAQI, so this module
refuses to classify them rather than inventing a scale for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

# Index levels, worst last. These strings are entity states, so they are
# English and stable; translating them is the frontend's job.
LEVEL_GOOD: Final = "good"
LEVEL_FAIR: Final = "fair"
LEVEL_MODERATE: Final = "moderate"
LEVEL_POOR: Final = "poor"
LEVEL_VERY_POOR: Final = "very_poor"
LEVEL_EXTREMELY_POOR: Final = "extremely_poor"

LEVELS: Final[tuple[str, ...]] = (
    LEVEL_GOOD,
    LEVEL_FAIR,
    LEVEL_MODERATE,
    LEVEL_POOR,
    LEVEL_VERY_POOR,
    LEVEL_EXTREMELY_POOR,
)

# Numeric equivalent of every level, 1 (good) to 6 (extremely poor), for graphs
# and comparisons. Derived from LEVELS so the two can never drift apart.
LEVEL_NUMBERS: Final[dict[str, int]] = {
    level: number for number, level in enumerate(LEVELS, start=1)
}

# Pollutant keys the index is defined for. Deliberately the same spellings the
# rest of the integration uses, so no translation layer is needed.
EAQI_PM25: Final = "pm25"
EAQI_PM10: Final = "pm10"
EAQI_O3: Final = "o3"
EAQI_NO2: Final = "no2"
EAQI_SO2: Final = "so2"

# Order in which pollutants are reported and in which ties for the worst level
# are broken, so the dominant pollutant of a station is reproducible.
EAQI_POLLUTANTS: Final[tuple[str, ...]] = (
    EAQI_PM25,
    EAQI_PM10,
    EAQI_O3,
    EAQI_NO2,
    EAQI_SO2,
)

# Particulate matter counts as present when either fraction is available.
PM_POLLUTANTS: Final[tuple[str, ...]] = (EAQI_PM25, EAQI_PM10)

# Upper bound of every band in µg/m³, in the order of LEVELS. The published
# table lists whole numbers with gaps (PM2.5 "0-5" then "6-15"); the bounds
# below are read as inclusive upper limits of a continuous scale, so a value
# exactly on a bound still belongs to the lower level and the fractional values
# in between are covered. The last level is open ended and therefore has no
# bound of its own.
#
# EEA, European Air Quality Index (2024 revision),
# https://airindex.eea.europa.eu/AQI/index.html, retrieved 2026-08-31.
EAQI_BANDS: Final[dict[str, tuple[float, float, float, float, float]]] = {
    EAQI_PM25: (5, 15, 50, 90, 140),
    EAQI_PM10: (15, 45, 120, 195, 270),
    EAQI_O3: (60, 100, 120, 160, 180),
    EAQI_NO2: (10, 25, 60, 100, 150),
    EAQI_SO2: (20, 40, 125, 190, 275),
}

# Name of the scheme, for the attribute of the same name.
SCHEME: Final = "EAQI (EEA, 2024 revision)"


@dataclass(frozen=True, slots=True)
class StationIndex:
    """Result of aggregating the sub-indices of one station.

    ``level`` is ``None`` whenever the index must not be shown: either no
    pollutant could be classified at all, or the minimum data requirement is
    not met. It is never quietly replaced by the best available sub-index.
    """

    level: str | None
    dominant_pollutant: str | None
    pollutants_used: tuple[str, ...]
    complete: bool

    @property
    def number(self) -> int | None:
        """Numeric level 1-6, or None while there is no level."""
        if self.level is None:
            return None
        return LEVEL_NUMBERS[self.level]


def is_eaqi_pollutant(pollutant: str) -> bool:
    """Whether the index is defined for this pollutant."""
    return pollutant in EAQI_BANDS


def index_for(pollutant: str, value: float | None) -> str | None:
    """Classify one concentration in µg/m³ into an index level.

    Returns None when the value cannot be classified: an unknown pollutant, a
    missing value, or a negative one. Instruments do report slightly negative
    concentrations around zero, but a negative concentration is not physically
    meaningful, so it is reported as "no level" rather than being rounded up
    into ``good``.
    """
    bands = EAQI_BANDS.get(pollutant)
    if bands is None or value is None:
        return None
    if value < 0:
        return None
    for level, upper in zip(LEVELS, bands):
        if value <= upper:
            return level
    return LEVEL_EXTREMELY_POOR


def sub_indices(values: Mapping[str, float | None]) -> dict[str, str]:
    """Classify every pollutant that carries a usable value.

    Keys the index is not defined for - carbon monoxide and nitrogen monoxide
    in particular - are skipped instead of raising, so the caller can hand over
    everything a station reports.
    """
    result: dict[str, str] = {}
    for pollutant in EAQI_POLLUTANTS:
        level = index_for(pollutant, values.get(pollutant))
        if level is not None:
            result[pollutant] = level
    return result


def has_minimum_data(pollutants: Mapping[str, str] | tuple[str, ...]) -> bool:
    """Whether the EEA minimum data requirement is met.

    The EEA asks for NO2, O3 and particulate matter at background and
    industrial stations, and for NO2 and particulate matter at traffic
    stations. The data source does not publish the station type, so the
    stricter of the two rules is applied throughout, and the station index of
    a traffic station may stay unknown where the EEA would still publish one.
    """
    available = set(pollutants)
    return (
        EAQI_NO2 in available
        and EAQI_O3 in available
        and bool(available.intersection(PM_POLLUTANTS))
    )


def station_index(values: Mapping[str, float | None]) -> StationIndex:
    """Aggregate the pollutant values of one station into its index.

    The station index is the worst of the sub-indices, and only exists once the
    minimum data requirement is met. Falling short of it yields a result
    without a level, which still reports the sub-indices that were found.
    """
    levels = sub_indices(values)
    used = tuple(pollutant for pollutant in EAQI_POLLUTANTS if pollutant in levels)
    complete = has_minimum_data(levels)

    if not complete or not used:
        return StationIndex(
            level=None,
            dominant_pollutant=None,
            pollutants_used=used,
            complete=complete,
        )

    # Worst level wins. EAQI_POLLUTANTS decides ties, because max() keeps the
    # first item of equal rank and `used` already follows that order.
    dominant = max(used, key=lambda pollutant: LEVEL_NUMBERS[levels[pollutant]])
    return StationIndex(
        level=levels[dominant],
        dominant_pollutant=dominant,
        pollutants_used=used,
        complete=True,
    )
