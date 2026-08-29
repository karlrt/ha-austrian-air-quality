"""Config flow for Austrian Air Quality."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import dt as dt_util

from .api import (
    AustrianAirQualityApi,
    AustrianAirQualityApiError,
    AustrianAirQualityMeasurement,
    AustrianAirQualityStation,
    bbox_around,
    distance_km,
)
from .const import (
    AT_BBOX,
    CONF_LOCATION,
    CONF_QUERY,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DATA_PREFETCHED,
    DEFAULT_RADIUS_KM,
    DOMAIN,
    MAX_RADIUS_KM,
    POLLUTANT_LABELS,
)

_LOGGER = logging.getLogger(__name__)

# The picker and the overview table stay readable up to roughly this many
# stations; beyond that the user is asked to narrow the search.
MAX_RESULTS = 25


def _format_pollutants(station: AustrianAirQualityStation) -> str:
    """Comma separated short labels of everything the station measures."""
    return ", ".join(POLLUTANT_LABELS[key] for key in station.pollutants)


def _cell(text: str) -> str:
    """Escape a value so it cannot break out of a markdown table cell."""
    return text.replace("|", r"\|")


def _format_distance(distance: float | None) -> str:
    """Distance in kilometres, or a dash when no reference point is known."""
    return "–" if distance is None else f"{distance:.1f} km"


def _format_time(measurement: AustrianAirQualityMeasurement) -> str:
    """Timestamp of a measurement, formatted for the details table."""
    if measurement.measured_at is not None:
        return measurement.measured_at.strftime("%d.%m.%Y %H:%M")
    return _cell(measurement.measured_at_raw or "–")


class AustrianAirQualityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Guides the user from a location or a name to a concrete station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._candidates: list[AustrianAirQualityStation] = []
        self._distances: dict[str, float] = {}
        self._all_stations: list[AustrianAirQualityStation] | None = None
        self._selected: AustrianAirQualityStation | None = None
        self._prefetch: asyncio.Task[AustrianAirQualityStation | None] | None = None
        self._prefetch_for: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how to look for a station."""
        return self.async_show_menu(
            step_id="user", menu_options=["location", "name"]
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for stations around a point on the map."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = float(location[CONF_LATITUDE])
            longitude = float(location[CONF_LONGITUDE])
            radius_km = float(user_input[CONF_RADIUS])

            api = AustrianAirQualityApi(async_get_clientsession(self.hass))
            try:
                stations = await api.async_get_stations(
                    bbox_around(latitude, longitude, radius_km)
                )
            except AustrianAirQualityApiError as err:
                _LOGGER.warning("Station search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # The bounding box is a rectangle, so cut it back to the circle
                # the user actually drew on the map.
                self._distances = {}
                within: list[AustrianAirQualityStation] = []
                for station in stations:
                    if station.latitude is None or station.longitude is None:
                        continue
                    distance = distance_km(
                        latitude, longitude, station.latitude, station.longitude
                    )
                    if distance <= radius_km:
                        self._distances[station.station_id] = distance
                        within.append(station)

                remaining = self._drop_configured(within)
                if not within:
                    errors["base"] = "no_stations"
                elif not remaining:
                    # Everything inside the circle is already set up, which is
                    # a different situation than finding nothing at all.
                    errors["base"] = "all_configured"
                else:
                    self._candidates = sorted(
                        remaining,
                        key=lambda station: self._distances[station.station_id],
                    )
                    return await self.async_step_station()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION,
                    default={
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                ): LocationSelector(),
                # The radius lives in its own field rather than in the location
                # selector, whose built-in radius is fixed to metres.
                vol.Required(
                    CONF_RADIUS, default=DEFAULT_RADIUS_KM
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=MAX_RADIUS_KM,
                        step=1,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="location", data_schema=schema, errors=errors
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for stations by name or municipality."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = str(user_input[CONF_QUERY]).strip().casefold()
            try:
                stations = await self._async_all_stations()
            except AustrianAirQualityApiError as err:
                _LOGGER.warning("Station search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # The address is searched as well, so that a municipality or a
                # district finds the station standing there. Those hits are
                # ranked behind the ones carrying the term in their name,
                # otherwise a "Klagenfurter Straße" in another town outranks
                # the stations actually called Klagenfurt.
                matches: list[AustrianAirQualityStation] = []
                by_name: set[str] = set()
                for station in stations:
                    if query in station.station_name.casefold():
                        by_name.add(station.station_id)
                    elif query not in (station.location or "").casefold():
                        continue
                    matches.append(station)

                # Within each of the two groups the nearest station to home
                # comes first, so the closest "Graz ..." is the one offered.
                self._distances = self._distances_from_home(matches)
                remaining = self._drop_configured(matches)
                if not matches:
                    errors["base"] = "no_stations"
                elif not remaining:
                    errors["base"] = "all_configured"
                elif len(remaining) > MAX_RESULTS:
                    errors["base"] = "too_many_stations"
                else:
                    self._candidates = sorted(
                        remaining,
                        key=lambda station: (
                            station.station_id not in by_name,
                            self._distances.get(station.station_id, float("inf")),
                        ),
                    )
                    return await self.async_step_station()

        schema = vol.Schema(
            {vol.Required(CONF_QUERY): TextSelector(TextSelectorConfig())}
        )
        return self.async_show_form(
            step_id="name", data_schema=schema, errors=errors
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the stations that were found."""
        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            self._selected = next(
                station
                for station in self._candidates
                if station.station_id == station_id
            )
            self._start_prefetch(self._selected)
            return await self.async_step_details()

        shown = self._candidates[:MAX_RESULTS]
        options = [
            SelectOptionDict(
                value=station.station_id,
                label=" · ".join(
                    part
                    for part in (
                        station.station_name,
                        _format_distance(self._distances.get(station.station_id))
                        if self._distances
                        else None,
                        _format_pollutants(station),
                    )
                    if part
                ),
            )
            for station in shown
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="station", data_schema=schema)

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show what the selected station measures before adding it."""
        if self._selected is None:
            return await self.async_step_user()
        station = self._selected

        rows = "\n".join(
            "| {label} | {value} {unit} | {time} |".format(
                label=POLLUTANT_LABELS[key],
                value=f"{station.measurements[key].value:g}",
                unit=_cell(station.measurements[key].unit),
                time=_format_time(station.measurements[key]),
            )
            for key in station.pollutants
        )

        return self.async_show_menu(
            step_id="details",
            menu_options=["confirm", "station", "user"],
            description_placeholders={
                "station": station.station_name,
                "address": station.location or "–",
                "owner": station.owner or "–",
                "distance": _format_distance(
                    self._distances.get(station.station_id)
                ),
                "measurements": rows,
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry for the selected station."""
        if self._selected is None:
            return await self.async_step_user()
        station = self._selected

        await self.async_set_unique_id(station.station_id)
        self._abort_if_unique_id_configured()

        # Hand the full measurements over to the setup that follows, so it does
        # not repeat the round of requests that has been running in the
        # background since this station was picked.
        complete = await self._async_take_prefetch(station.station_id)
        if complete is not None:
            prefetched = self.hass.data.setdefault(DOMAIN, {}).setdefault(
                DATA_PREFETCHED, {}
            )
            prefetched[station.station_id] = (dt_util.utcnow(), complete)

        return self.async_create_entry(
            title=station.station_name,
            data={
                CONF_STATION_ID: station.station_id,
                CONF_STATION_NAME: station.station_name,
                CONF_LATITUDE: station.latitude,
                CONF_LONGITUDE: station.longitude,
            },
        )

    def _start_prefetch(self, station: AustrianAirQualityStation) -> None:
        """Begin loading everything the chosen station reports.

        The picker only knows the current values, while the entry also needs
        the daily means. Fetching those while the review screen is on display
        means most of the wait is over by the time the station is confirmed.
        """
        if self._prefetch is not None and self._prefetch_for == station.station_id:
            return
        self._cancel_prefetch()

        api = AustrianAirQualityApi(async_get_clientsession(self.hass))
        self._prefetch_for = station.station_id
        self._prefetch = self.hass.async_create_background_task(
            api.async_fetch_station_data(
                station.station_id, station.latitude, station.longitude
            ),
            f"{DOMAIN} prefetch {station.station_id}",
        )

    def _cancel_prefetch(self) -> None:
        """Drop a running prefetch, for instance after picking another station."""
        if self._prefetch is not None and not self._prefetch.done():
            self._prefetch.cancel()
        self._prefetch = None
        self._prefetch_for = None

    async def _async_take_prefetch(
        self, station_id: str
    ) -> AustrianAirQualityStation | None:
        """Wait for the prefetch of this station and hand over its result.

        Waiting here is never slower than letting the setup fetch by itself,
        and a failed request simply leaves that to the setup.
        """
        if self._prefetch is None or self._prefetch_for != station_id:
            return None
        try:
            return await self._prefetch
        except (AustrianAirQualityApiError, asyncio.CancelledError) as err:
            _LOGGER.debug("Prefetch for %s failed: %s", station_id, err)
            return None
        finally:
            self._prefetch = None
            self._prefetch_for = None

    async def async_remove(self) -> None:
        """Clean up when the flow is abandoned."""
        self._cancel_prefetch()

    def _distances_from_home(
        self, stations: list[AustrianAirQualityStation]
    ) -> dict[str, float]:
        """Distance of each station to the Home Assistant home coordinates."""
        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude
        if home_lat is None or home_lon is None:
            return {}
        return {
            station.station_id: distance_km(
                home_lat, home_lon, station.latitude, station.longitude
            )
            for station in stations
            if station.latitude is not None and station.longitude is not None
        }

    def _drop_configured(
        self, stations: list[AustrianAirQualityStation]
    ) -> list[AustrianAirQualityStation]:
        """Hide stations that already have a config entry."""
        configured = self._async_current_ids()
        return [
            station for station in stations if station.station_id not in configured
        ]

    async def _async_all_stations(self) -> list[AustrianAirQualityStation]:
        """All reporting stations in Austria, fetched at most once per flow."""
        if self._all_stations is None:
            api = AustrianAirQualityApi(async_get_clientsession(self.hass))
            self._all_stations = await api.async_get_stations(AT_BBOX)
        return self._all_stations
