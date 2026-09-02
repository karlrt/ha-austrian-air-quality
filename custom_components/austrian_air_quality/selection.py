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

# The two halves of the catalogue, in catalogue order. The setup asks for them
# on separate steps - the freshest value of a pollutant is what nearly everyone
# is after, the daily mean is a second thought - while the stored selection
# stays one list, so nothing downstream has to know about the split.
CURRENT_KEYS: tuple[str, ...] = tuple(
    key
    for key, (_, meantype) in _MEASUREMENT_PARTS.items()
    if meantype == MEANTYPE_CURRENT
)

DAILY_KEYS: tuple[str, ...] = tuple(
    key
    for key, (_, meantype) in _MEASUREMENT_PARTS.items()
    if meantype != MEANTYPE_CURRENT
)


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


def daily_counterparts(measurements: Iterable[str]) -> tuple[str, ...]:
    """The daily mean keys belonging to these measurement keys.

    Someone who wants a pollutant usually wants both of its averaging periods,
    so the second step of the setup starts from the counterparts of what the
    first one got. Unknown keys are ignored, as everywhere else here.
    """
    pollutants = {
        _MEASUREMENT_PARTS[key][0]
        for key in measurements
        if key in _MEASUREMENT_PARTS
    }
    return tuple(key for key in DAILY_KEYS if _MEASUREMENT_PARTS[key][0] in pollutants)


def station_index_default(pollutants: Iterable[str]) -> bool:
    """Whether the station index starts out ticked for these pollutants.

    Only where it can actually reach a level: either EEA coverage rule will do,
    but a single index pollutant is not enough for either, and ticking it on
    such a station produces two entities that stay unknown for good. It stays
    one click away, because the forms offer it either way.

    Takes the pollutants rather than the chosen sub-indices on purpose. The
    setup no longer picks sub-indices by default, so reading the rule off them
    would answer "no" everywhere.
    """
    reported = set(pollutants)
    return eaqi.has_minimum_data(
        tuple(pollutant for pollutant in eaqi.EAQI_POLLUTANTS if pollutant in reported)
    )


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
        # An installation that already has the station index keeps it whatever
        # the coverage rule says - unticking it here would drop an entity and
        # its history over a default.
        OPT_STATION_INDEX: station_index_default(index_pollutants)
        or KEY_STATION_INDEX in have,
        OPT_INDEXES: list(indexes),
        OPT_LOCATION: True,
    }


def default_for_confirm(pollutants: Iterable[str]) -> dict[str, Any]:
    """The selection the first step of the setup starts from.

    Deliberately the lean end of the catalogue: the freshest value of every
    pollutant the station reports, plus the station index where it can reach a
    level. The daily means, the sub-indices and the coordinates entity are not
    in it - they are what the second step is for, and a setup that never opens
    that step leaves them out rather than creating a dozen entities the user
    never saw offered.

    Contrast :func:`default_options`, which stays generous because it answers a
    different question: what an entry from before the selection existed should
    keep, where dropping anything would take an entity and its history with it.
    """
    reported = set(pollutants)
    return {
        OPT_MEASUREMENTS: [
            key for key in CURRENT_KEYS if _MEASUREMENT_PARTS[key][0] in reported
        ],
        OPT_STATION_INDEX: station_index_default(reported),
        OPT_INDEXES: [],
        OPT_LOCATION: False,
    }
