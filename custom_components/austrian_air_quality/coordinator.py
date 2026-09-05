"""One fetch cycle for the whole installation, and the per-entry views of it.

The source is queried by rectangle, not by station: one request answers for
every station inside the rectangle. Letting each config entry fetch for itself
therefore pays for the same answer once per station. Three stations around one
town used to mean three times the same request.

:class:`AustrianAirQualityHub` is the one place that fetches. It collects what
all entries together need, groups the stations into as few rectangles as they
fit into (see :mod:`grouping`), and hands each entry its own station out of the
shared answer. The number of requests per cycle follows the number of
rectangles and the union of the selections - not the number of stations.

:class:`AustrianAirQualityCoordinator` stays, one per entry, because that is
what the entities are bound to. It no longer fetches on its own: it is fed by
the hub, and where something does ask it to refresh - the setup of a new entry,
or `homeassistant.update_entity` on one of its sensors - it asks the hub for a
cycle rather than going to the source by itself.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import grouping, schedule, selection
from .api import (
    AustrianAirQualityApi,
    AustrianAirQualityApiError,
    AustrianAirQualityAuthError,
    AustrianAirQualityStation,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type AustrianAirQualityConfigEntry = ConfigEntry["AustrianAirQualityCoordinator"]

# The publication grid in seconds. The source publishes half-hourly means and
# the update interval is one of them, so the two are the same number.
POLL_PERIOD: int = int(DEFAULT_SCAN_INTERVAL.total_seconds())

# How long a starting cycle waits for entries that are still being set up, in
# seconds. Long enough for the siblings of one installation, short enough to be
# nothing next to a cycle that takes half a minute of serial requests.
SETTLE_DELAY: float = 1.0


class AustrianAirQualityHub:
    """The single fetch cycle behind every entry of this installation."""

    def __init__(self, hass: HomeAssistant, api: AustrianAirQualityApi, phase: int) -> None:
        """Initialize the hub with the phase its cycles sit on."""
        self.hass = hass
        self.api = api
        self._phase = phase
        self._coordinators: dict[str, AustrianAirQualityCoordinator] = {}
        self._cycle: asyncio.Task[None] | None = None
        # Entries awaiting the running cycle. They read their station off its
        # result, so pushing it to them as well would set the same data twice
        # and notify every entity twice with it.
        self._joined: set[str] = set()
        self._stations: dict[str, AustrianAirQualityStation] = {}
        self._errors: dict[str, AustrianAirQualityApiError] = {}
        self._covered: frozenset[str] = frozenset()
        self._unsub_tick: CALLBACK_TYPE | None = None

    @callback
    def async_add(self, coordinator: AustrianAirQualityCoordinator) -> None:
        """Take a coordinator into the shared cycle."""
        self._coordinators[coordinator.config_entry.entry_id] = coordinator
        if self._unsub_tick is None:
            self._async_schedule_tick()

    @callback
    def async_remove(self, coordinator: AustrianAirQualityCoordinator) -> bool:
        """Drop a coordinator; returns whether the hub is now empty.

        An empty hub stops its timer, so an installation that has removed its
        last station does not keep fetching for nobody.
        """
        self._coordinators.pop(coordinator.config_entry.entry_id, None)
        if self._coordinators:
            return False
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None
        return True

    async def async_cycle(
        self, caller: AustrianAirQualityCoordinator | None = None
    ) -> tuple[
        dict[str, AustrianAirQualityStation], dict[str, AustrianAirQualityApiError]
    ]:
        """Run a cycle, or join the one already running, and return its result.

        Several entries starting up at the same second must not turn into
        several cycles, so a cycle already in flight is awaited instead of a
        second one being started. Every caller gets the same answer; the
        exception of a failed cycle reaches all of them alike.

        A caller whose station was not part of the running cycle - an entry
        added while it ran - gets a second, fresh cycle rather than an answer
        that could not contain it.
        """
        for _ in range(2):
            if self._cycle is None or self._cycle.done():
                self._joined = set()
                self._cycle = self.hass.async_create_task(
                    self._async_run(), f"{DOMAIN}_cycle"
                )
            cycle = self._cycle
            if caller is not None:
                self._joined.add(caller.config_entry.entry_id)
            await cycle
            if caller is None or caller.station_id in self._covered:
                break
        return self._stations, self._errors

    async def _async_run(self) -> None:
        """Fetch every rectangle once and hand the results to the entries."""
        # Home Assistant sets the entries of an integration up side by side, so
        # the first of them reaches this point while its siblings are still
        # being created. Waiting a moment before the plan is fixed lets them
        # join the same cycle - which is the whole point - instead of finding
        # themselves left out of it and starting one of their own.
        await asyncio.sleep(SETTLE_DELAY)

        wanted: set[tuple[str, str]] = set()
        coordinates: dict[str, tuple[float | None, float | None]] = {}
        for coordinator in self._coordinators.values():
            wanted.update(selection.required_queries(coordinator.config_entry.options))
            coordinates[coordinator.station_id] = coordinator.station_coordinates

        groups = grouping.boxes_for(coordinates)
        plan = selection.in_plan_order(wanted)
        stations: dict[str, AustrianAirQualityStation] = {}
        errors: dict[str, AustrianAirQualityApiError] = {}

        for group in groups:
            try:
                stations.update(
                    await self.api.async_fetch_group(
                        group.bbox, group.station_ids, plan
                    )
                )
            except AustrianAirQualityApiError as err:
                # One failed rectangle is not the others' business: the stations
                # of the rectangles that came through keep their fresh values.
                _LOGGER.debug("Rectangle %s failed: %s", group.bbox, err)
                for station_id in group.station_ids:
                    errors[station_id] = err

        self._stations = stations
        self._errors = errors
        self._covered = frozenset(
            station_id for group in groups for station_id in group.station_ids
        )
        _LOGGER.debug(
            "Cycle done: %d rectangle(s), %d quer(y|ies) each, %d station(s) answered",
            len(groups),
            len(plan),
            len(stations),
        )
        self._async_publish()

    @callback
    def _async_publish(self) -> None:
        """Hand every waiting entry its station, or the failure of its rectangle."""
        for coordinator in list(self._coordinators.values()):
            if coordinator.config_entry.entry_id in self._joined:
                continue
            error = self._errors.get(coordinator.station_id)
            if error is not None:
                coordinator.async_set_update_error(
                    UpdateFailed(f"Failed to retrieve air quality data: {error}")
                )
                continue
            coordinator.async_set_updated_data(self._stations.get(coordinator.station_id))

    @callback
    def _async_schedule_tick(self) -> None:
        """Put the next cycle on the publication grid.

        See :mod:`schedule`: anchoring to the clock rather than counting from
        the end of the previous fetch keeps the cycles from drifting past a
        grid boundary, and the phase keeps this installation off the second
        every other installation arrives on.
        """
        now = dt_util.utcnow()
        due = now + timedelta(
            seconds=schedule.seconds_until_next_slot(
                now.timestamp(), self._phase, POLL_PERIOD
            )
        )
        self._unsub_tick = async_track_point_in_utc_time(
            self.hass, self._async_tick, due
        )

    @callback
    def _async_tick(self, _now: datetime) -> None:
        """Run the scheduled cycle and line the next one up."""
        self._unsub_tick = None
        if not self._coordinators:
            return
        self._async_schedule_tick()
        self.hass.async_create_task(self._async_cycle_quietly(), f"{DOMAIN}_scheduled")

    async def _async_cycle_quietly(self) -> None:
        """A scheduled cycle reports through the entries, not through the task.

        Every entry learns of a failure from its own coordinator, which is where
        it belongs; letting it escape the task on top would only add an
        unhandled exception to the log.
        """
        try:
            await self.async_cycle()
        except Exception:  # noqa: BLE001 - a background task must not die silently
            _LOGGER.exception("Scheduled air quality cycle failed")


class AustrianAirQualityCoordinator(DataUpdateCoordinator[AustrianAirQualityStation | None]):
    """The measurements of one station, as fed by the hub."""

    config_entry: AustrianAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AustrianAirQualityConfigEntry,
        hub: AustrianAirQualityHub,
        station_id: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{station_id}",
            # No interval of its own: the hub holds the schedule, because one
            # cycle serves every station at once.
            update_interval=None,
        )
        self.hub = hub
        self.station_id = station_id
        self.latitude = latitude
        self.longitude = longitude

    @property
    def station_coordinates(self) -> tuple[float | None, float | None]:
        """Coordinates of the station, freshest first.

        The API repeats them with every measurement; the values captured when
        the station was added serve as a fallback while it reports nothing.
        """
        station = self.data
        if station is not None and station.latitude is not None and station.longitude is not None:
            return station.latitude, station.longitude
        return self.latitude, self.longitude

    async def _async_update_data(self) -> AustrianAirQualityStation | None:
        """Ask the hub for a cycle and take this station out of it.

        Reached from the setup of an entry and from an explicit refresh of one
        of its entities. Either way the cycle covers every station of the
        installation, so a second entry asking at the same moment joins this
        one instead of doubling the requests.
        """
        stations, errors = await self.hub.async_cycle(self)
        error = errors.get(self.station_id)
        if isinstance(error, AustrianAirQualityAuthError):
            raise ConfigEntryAuthFailed(str(error)) from error
        if error is not None:
            raise UpdateFailed(f"Failed to retrieve air quality data: {error}")
        return stations.get(self.station_id)
