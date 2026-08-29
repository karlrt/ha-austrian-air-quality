"""Austrian Air Quality integration."""

from __future__ import annotations

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import AustrianAirQualityApi, AustrianAirQualityStation
from .const import CONF_STATION_ID, DATA_PREFETCHED, DOMAIN, PREFETCH_MAX_AGE
from .coordinator import AustrianAirQualityConfigEntry, AustrianAirQualityCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Set up a configuration entry."""
    session = async_get_clientsession(hass)
    api = AustrianAirQualityApi(session)

    coordinator = AustrianAirQualityCoordinator(
        hass,
        entry,
        api,
        entry.data[CONF_STATION_ID],
        entry.data.get(CONF_LATITUDE),
        entry.data.get(CONF_LONGITUDE),
    )
    station = _pop_prefetched(hass, entry.data[CONF_STATION_ID])
    if station is not None:
        # The config flow just fetched this, so the entry can be set up right
        # away rather than making the user wait through a second round.
        coordinator.async_set_updated_data(station)
    else:
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Unload a configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> None:
    """Reload a configuration entry after option changes."""
    await hass.config_entries.async_reload(entry.entry_id)


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
