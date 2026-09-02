"""What a config entry tracks, and what it costs to fetch.

Two things are deliberately kept apart here.

The *selection* says which entities exist. It belongs to the user, it lives in
the entry options, and nothing else may change it. What a station reports at
any given moment says whether those entities carry a value, and that is decided
at runtime, by the entities themselves. Deriving the entity set from a snapshot
of the measurements ties the two together, and then the set freezes at the
moment the entry happened to be created: a pollutant the station drops for an
hour disappears for good, and one it starts reporting later never arrives.

The *query plan* is derived from the selection rather than read off it. An
index needs the half-hourly mean of its pollutant even when nobody wants that
measurement as an entity, so switching a measurement off removes an entity but
never quietly empties an index that is still switched on.

Like :mod:`eaqi` this module has no Home Assistant imports and can be exercised
on its own.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from . import eaqi
from .const import (
    KEY_STATION_INDEX,
    MEANTYPE_CURRENT,
    MEASUREMENT_KEYS,
    MEANTYPES,
    OPT_INDEXES,
    OPT_LOCATION,
    OPT_MEASUREMENTS,
    OPT_STATION_INDEX,
    POLLUTANTS,
    index_key,
    measurement_key,
)

# Sub-index keys in a stable order, for the same reason as MEASUREMENT_KEYS.
INDEX_KEYS: tuple[str, ...] = tuple(
    index_key(pollutant) for pollutant in eaqi.EAQI_POLLUTANTS
)

# The pollutant and averaging period behind every measurement key. Insertion
# order is the catalogue order, which is what the query plan is returned in.
_MEASUREMENT_PARTS: dict[str, tuple[str, str]] = {
    measurement_key(pollutant, meantype): (pollutant, meantype)
    for pollutant in POLLUTANTS
    for meantype in MEANTYPES
}

_INDEX_POLLUTANTS: dict[str, str] = {
    index_key(pollutant): pollutant for pollutant in eaqi.EAQI_POLLUTANTS
}


def _kept(stored: Any, catalogue: tuple[str, ...]) -> tuple[str, ...]:
    """The stored keys that are still known, in catalogue order.

    Options outlive updates, so a key that has since been renamed or dropped is
    ignored rather than allowed to break the setup.
    """
    if not isinstance(stored, (list, tuple, set, frozenset)):
        return ()
    chosen = {str(item) for item in stored}
    return tuple(key for key in catalogue if key in chosen)


def wanted_measurements(options: Mapping[str, Any]) -> tuple[str, ...]:
    """Measurement keys this entry wants an entity for.

    An entry that has never been through the selection - one from before it
    existed, in the moment before the defaults are written - is treated as
    wanting everything, so nothing disappears while that is being sorted out.
    """
    if OPT_MEASUREMENTS not in options:
        return MEASUREMENT_KEYS
    return _kept(options[OPT_MEASUREMENTS], MEASUREMENT_KEYS)


def wanted_indexes(options: Mapping[str, Any]) -> tuple[str, ...]:
    """Sub-index keys this entry wants an entity for."""
    if OPT_INDEXES not in options:
        return INDEX_KEYS
    return _kept(options[OPT_INDEXES], INDEX_KEYS)


def wants_station_index(options: Mapping[str, Any]) -> bool:
    """Whether the station index and its numeric twin are wanted."""
    return bool(options.get(OPT_STATION_INDEX, True))


def wants_location(options: Mapping[str, Any]) -> bool:
    """Whether the diagnostic coordinates entity is wanted."""
    return bool(options.get(OPT_LOCATION, True))


def required_queries(options: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """The (pollutant, averaging period) pairs this entry has to fetch.

    Derived from the selected entities, not from the measurements alone: a
    sub-index needs the half-hourly mean of its pollutant, and the station
    index needs every index pollutant, because any one of them can turn out to
    be the worst and because the minimum data requirement asks for three of
    them at once. Switching off a measurement therefore drops its entity
    without pulling the ground out from under an index that stays on.
    """
    needed: set[tuple[str, str]] = set()
    for key in wanted_measurements(options):
        needed.add(_MEASUREMENT_PARTS[key])
    for key in wanted_indexes(options):
        needed.add((_INDEX_POLLUTANTS[key], MEANTYPE_CURRENT))
    if wants_station_index(options):
        needed.update(
            (pollutant, MEANTYPE_CURRENT) for pollutant in eaqi.EAQI_POLLUTANTS
        )
    return tuple(pair for pair in _MEASUREMENT_PARTS.values() if pair in needed)


def default_options(
    reported: Iterable[str] = (), existing: Iterable[str] = ()
) -> dict[str, Any]:
    """The selection an entry starts from.

    ``reported`` are the measurement keys the station currently delivers,
    ``existing`` the entity keys the installation already has. Their union is
    used: what is already there keeps its entity and its history, and what the
    station reports on top of that is picked up right away instead of waiting
    for the next reload.

    This is a starting point, never a limit. The forms offer the full
    catalogue, so a pollutant that is missing at this moment stays one click
    away rather than becoming unreachable.
    """
    have = set(reported) | set(existing)
    measurements = tuple(key for key in MEASUREMENT_KEYS if key in have)
    indexes = tuple(
        key
        for key, pollutant in zip(INDEX_KEYS, eaqi.EAQI_POLLUTANTS)
        if key in have or measurement_key(pollutant, MEANTYPE_CURRENT) in measurements
    )
    index_pollutants = tuple(
        pollutant
        for key, pollutant in zip(INDEX_KEYS, eaqi.EAQI_POLLUTANTS)
        if key in indexes
    )
    return {
        OPT_MEASUREMENTS: list(measurements),
        # The station index is preselected only where it can actually reach a
        # level: either coverage rule will do, but a single index pollutant is
        # not enough for either. Ticking it on such a station used to produce
        # two entities that stay unknown for good. It stays one click away in
        # the forms, which offer it either way, and an installation that
        # already has the entity keeps it - unticking it here would drop an
        # entity and its history over a default.
        OPT_STATION_INDEX: eaqi.has_minimum_data(index_pollutants)
        or KEY_STATION_INDEX in have,
        OPT_INDEXES: list(indexes),
        OPT_LOCATION: True,
    }


def default_for_pollutants(pollutants: Iterable[str]) -> dict[str, Any]:
    """The selection to start from for a station that reports these pollutants.

    Both averaging periods are picked for each of them. The station list is
    built from the freshest values alone, so nothing is known about the daily
    means at that point, and assuming they exist is the friendlier guess: a
    daily mean the source does not publish leaves an entity without a value,
    which is visible and one click away from being switched off, while a
    missing entity is neither.
    """
    return default_options(
        reported=[
            measurement_key(pollutant, meantype)
            for pollutant in pollutants
            for meantype in MEANTYPES
        ]
    )
