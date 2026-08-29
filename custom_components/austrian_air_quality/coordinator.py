"""Data update coordinator for Austrian Air Quality."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AustrianAirQualityApiError,
    AustrianAirQualityAuthError,
    AustrianAirQualityApi,
    AustrianAirQualityStation,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type AustrianAirQualityConfigEntry = ConfigEntry["AustrianAirQualityCoordinator"]


class AustrianAirQualityCoordinator(DataUpdateCoordinator[AustrianAirQualityStation | None]):
    """Fetches measurements for a station periodically."""

    config_entry: AustrianAirQualityConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AustrianAirQualityConfigEntry,
        api: AustrianAirQualityApi,
        station_id: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{station_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.station_id = station_id

    async def _async_update_data(self) -> AustrianAirQualityStation | None:
        """Fetch current measurements."""
        try:
            return await self.api.async_fetch_station_data(self.station_id)
        except AustrianAirQualityAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AustrianAirQualityApiError as err:
            raise UpdateFailed(f"Failed to retrieve air quality data: {err}") from err
