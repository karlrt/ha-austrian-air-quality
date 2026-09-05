"""When to fetch, so the fetches stay on the publication grid.

The source publishes half-hourly means on a fixed grid, and a station is worth
fetching once per published value. Counting the update interval from the end of
the previous fetch - which is what a coordinator does when its update interval
never changes - lets the fetches drift by however long a fetch took, some thirty
seconds a time. After roughly sixty cycles the drift has walked past a grid
boundary, one published value is never fetched at all, and the long-term
statistics carry a hole where it should have been.

Anchoring every fetch to the clock instead removes the drift without fetching
any more often. The installation keeps a fixed position inside the window, its
phase, so its cycle stays off the second every other installation arrives on:
an undocumented public endpoint does not need every installation in the country
turning up at once.

Like :mod:`eaqi` and :mod:`selection` this module has no Home Assistant imports
and can be exercised on its own.
"""

from __future__ import annotations

import hashlib


def poll_phase(identifier: str, period: int) -> int:
    """Where inside the window this installation fetches, in seconds after its start.

    ``identifier`` is the installation id. It is stable across restarts and
    different for every installation, so the fetches of one installation stay
    off the second every other installation arrives on. A phase derived from
    the station id would instead put every installation watching the same
    station on the same second.

    Since the fetches are bundled there is one cycle per installation left to
    place, not one per entry: an entry id would tie the position of that cycle
    to whichever entry happened to create it and move it as soon as that entry
    was removed.
    """
    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
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
