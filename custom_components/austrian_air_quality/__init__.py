"""Die Integration Luftqualität Österreich."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AustrianAirQualityApi
from .const import CONF_STATION_ID
from .coordinator import AustrianAirQualityConfigEntry, AustrianAirQualityCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Einen Konfigurationseintrag einrichten."""
    session = async_get_clientsession(hass)
    api = AustrianAirQualityApi(session)

    coordinator = AustrianAirQualityCoordinator(
        hass, entry, api, entry.data[CONF_STATION_ID]
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> bool:
    """Einen Konfigurationseintrag entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: AustrianAirQualityConfigEntry) -> None:
    """Einen Konfigurationseintrag nach Optionsänderung neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
