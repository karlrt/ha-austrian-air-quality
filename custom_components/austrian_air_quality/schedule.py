"""When to fetch a station, so the fetches stay on the publication grid.

The source publishes half-hourly means on a fixed grid, and a station is worth
fetching once per published value. Counting the update interval from the end of
the previous fetch - which is what a coordinator does when its update interval
never changes - lets the fetches drift by however long a fetch took, some thirty
seconds a time. After roughly sixty cycles the drift has walked past a grid
boundary, one published value is never fetched at all, and the long-term
statistics carry a hole where it should have been.

Anchoring every fetch to the clock instead removes the drift without fetching
any more often. Each entry keeps a fixed position inside the window, its phase,
so the fetches of one installation stay apart from each other and from those of
every other installation: an undocumented public endpoint does not need every
installation in the country arriving on the same second.

Like :mod:`eaqi` and :mod:`selection` this module has no Home Assistant imports
and can be exercised on its own.
"""

from __future__ import annotations

import hashlib


def poll_phase(entry_id: str, period: int) -> int:
    """Where inside the window this entry fetches, in seconds after its start.

    Derived from the config entry id, so it is the same after every restart and
    different for every entry - between the stations of one installation, and
    between installations, because the id is generated per entry. A phase
    derived from the station id would instead put every installation watching
    the same station on the same second.
    """
    digest = hashlib.sha256(entry_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % period


def seconds_until_next_slot(now: float, phase: int, period: int) -> float:
    """Seconds from ``now`` until this entry's next slot.

    ``now`` is a POSIX timestamp, which makes the grid the same wall clock grid
    for every installation regardless of its time zone. Sitting exactly on a
    slot yields a full period rather than zero, so a fetch never schedules the
    next one for the same instant.
    """
    elapsed = (now - phase) % period
    return period - elapsed
