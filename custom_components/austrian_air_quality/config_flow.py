"""Config flow for Austrian Air Quality."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    AustrianAirQualityApiError,
    AustrianAirQualityConnectionError,
    AustrianAirQualityApi,
    AustrianAirQualityStation,
)
from .const import CONF_STATION_ID, CONF_STATION_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AustrianAirQualityConfigFlow(ConfigFlow, domain=DOMAIN):
    """User interface setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._stations: list[AustrianAirQualityStation] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select station."""
        errors: dict[str, str] = {}

        if not self._stations:
            session = async_get_clientsession(self.hass)
            api = AustrianAirQualityApi(session)
            try:
                self._stations = await api.async_get_stations()
            except AustrianAirQualityConnectionError:
                errors["base"] = "cannot_connect"
            except (AustrianAirQualityApiError, NotImplementedError):
                # TODO: Remove NotImplementedError once api.py is implemented.
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error retrieving station list")
                errors["base"] = "unknown"

        if user_input is not None and not errors:
            station_id = user_input[CONF_STATION_ID]
            await self.async_set_unique_id(station_id)
            self._abort_if_unique_id_configured()

            name = next(
                (s.name for s in self._stations if s.station_id == station_id),
                station_id,
            )
            return self.async_create_entry(
                title=name,
                data={CONF_STATION_ID: station_id, CONF_STATION_NAME: name},
            )

        options = [
            SelectOptionDict(value=station.station_id, label=station.name)
            for station in self._stations
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=True,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
