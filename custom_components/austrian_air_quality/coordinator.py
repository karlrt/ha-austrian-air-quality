"""Data update coordinator for Austrian Air Quality."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import selection
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
        latitude: float | None = None,
        longitude: float | None = None,
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
        """Fetch the measurements this entry tracks.

        The plan is read on every cycle rather than kept from the setup, so it
        is right even for the update that a changed selection triggers.
        """
        try:
            return await self.api.async_fetch_station_data(
                self.station_id,
                self.latitude,
                self.longitude,
                selection.required_queries(self.config_entry.options),
            )
        except AustrianAirQualityAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AustrianAirQualityApiError as err:
            raise UpdateFailed(f"Failed to retrieve air quality data: {err}") from err
