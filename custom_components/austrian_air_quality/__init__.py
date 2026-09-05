"""Austrian Air Quality integration."""

from __future__ import annotations

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from . import schedule, selection
from .api import AustrianAirQualityApi, AustrianAirQualityStation
from .const import (
    CONF_STATION_ID,
    DATA_HUB,
    DATA_PREFETCHED,
    DOMAIN,
    PREFETCH_MAX_AGE,
)
from .coordinator import (
    POLL_PERIOD,
    AustrianAirQualityConfigEntry,
    AustrianAirQualityCoordinator,
    AustrianAirQualityHub,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Set up a configuration entry."""
    hub = await _async_hub(hass)

    coordinator = AustrianAirQualityCoordinator(
        hass,
        entry,
        hub,
        entry.data[CONF_STATION_ID],
        entry.data.get(CONF_LATITUDE),
        entry.data.get(CONF_LONGITUDE),
    )
    hub.async_add(coordinator)
    entry.async_on_unload(lambda: _remove_from_hub(hass, hub, coordinator))
    station = _pop_prefetched(hass, entry.data[CONF_STATION_ID])
    fetched = station is not None
    if station is not None:
        # The config flow just fetched this, so the entry can be set up right
        # away rather than making the user wait through a second round.
        coordinator.async_set_updated_data(station)
    elif not entry.options:
        # The migration below is the one thing that still has to know what the
        # station reports, so this setup waits for a fetch. It happens once per
        # entry, on the first start after the selection was introduced, and
        # never again.
        await coordinator.async_config_entry_first_refresh()
        fetched = True

    if not entry.options:
        # An entry from before the selection existed. It starts from what it
        # already has, so that nothing it shows today disappears, plus whatever
        # the station reports right now, so that a pollutant which was missing
        # on the day it was added finally arrives. From here on the selection
        # is the user's, and nothing derives it from the data again.
        hass.config_entries.async_update_entry(
            entry,
            options=selection.default_options(
                reported=coordinator.data.measurements if coordinator.data else (),
                existing=_existing_keys(hass, entry),
            ),
        )

    entry.runtime_data = coordinator
    if not fetched:
        # Nothing here waits for measurements any more: which entities exist
        # comes from the selection alone. A full station takes half a minute of
        # serial requests, and every entry used to spend that inside setup, so
        # Home Assistant reported "waiting for integrations" for as long as all
        # of them together took. The fetch now runs alongside the rest of the
        # start; the sensors are unavailable until it lands, which is what they
        # are for. Failures are logged and retried on the next cycle rather than
        # holding the entry back.
        entry.async_create_background_task(
            hass,
            coordinator.async_refresh(),
            f"{DOMAIN}_first_refresh_{entry.entry_id}",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Unload a configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_hub(hass: HomeAssistant) -> AustrianAirQualityHub:
    """The shared fetch cycle of this installation, created on first use.

    The phase comes from the installation id rather than from an entry id: with
    the fetches bundled there is only one cycle left to place, and it has to
    keep its position on the grid no matter which entry happens to set it up or
    which one is removed. Two installations still arrive at different seconds,
    which is the point of the phase (see :mod:`schedule`).
    """
    data = hass.data.setdefault(DOMAIN, {})
    hub = data.get(DATA_HUB)
    if hub is None:
        hub = AustrianAirQualityHub(
            hass,
            AustrianAirQualityApi(async_get_clientsession(hass)),
            schedule.poll_phase(await instance_id.async_get(hass), POLL_PERIOD),
        )
        data[DATA_HUB] = hub
    return hub


def _remove_from_hub(
    hass: HomeAssistant,
    hub: AustrianAirQualityHub,
    coordinator: AustrianAirQualityCoordinator,
) -> None:
    """Take an unloaded entry out of the shared cycle.

    The hub goes with the last entry, timer and all, so an installation that
    has removed its last station stops fetching instead of keeping a cycle
    alive for nobody.
    """
    if hub.async_remove(coordinator):
        hass.data.get(DOMAIN, {}).pop(DATA_HUB, None)


async def async_reload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> None:
    """Reload a configuration entry after option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


def _existing_keys(
    hass: HomeAssistant, entry: AustrianAirQualityConfigEntry
) -> set[str]:
    """Entity keys this entry already has in the entity registry.

    Every unique id is the station id plus the entity key, so the keys can be
    read back without touching the entities. Registry entries that are
    currently unavailable count too, and that is the point: an entity must not
    be dropped from the selection just because the station happens not to
    report its pollutant at this moment.
    """
    prefix = f"{entry.data[CONF_STATION_ID]}_"
    registry = er.async_get(hass)
    return {
        registry_entry.unique_id.removeprefix(prefix)
        for registry_entry in er.async_entries_for_config_entry(
            registry, entry.entry_id
        )
        if registry_entry.unique_id.startswith(prefix)
    }


def _pop_prefetched(
    hass: HomeAssistant, station_id: str
) -> AustrianAirQualityStation | None:
    """Take the measurements the config flow left behind for this station.

    Returns None when there are none, or when they sat around long enough to
    have gone stale, in which case the caller fetches for itself.
    """
    prefetched = hass.data.get(DOMAIN, {}).get(DATA_PREFETCHED)
    if not prefetched:
        return None

    fetched_at, station = prefetched.pop(station_id, (None, None))
    # A flow that was abandoned after the review screen leaves an entry behind
    # that nothing will ever collect, so expired ones are dropped here too.
    cutoff = dt_util.utcnow() - PREFETCH_MAX_AGE
    for stale_id in [
        other_id
        for other_id, (other_time, _) in prefetched.items()
        if other_time < cutoff
    ]:
        del prefetched[stale_id]

    if fetched_at is None or fetched_at < cutoff:
        return None
    return station
