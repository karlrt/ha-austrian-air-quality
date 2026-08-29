"""Client for the JSON interface of the Austrian Environment Agency's air quality map.

Note: This is an undocumented interface used by the public map application
at luft.umweltbundesamt.at. It may change without notice.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://luft.umweltbundesamt.at/pub/map_chart/index.pl"
REQUEST_TIMEOUT = 30

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    )
}

_TIME_RE = re.compile(
    r"^(\d{1,2})\s+(\w{3})\s+(\d{4})\s+"
    r"(\d{2}):(\d{2}):(\d{2})\s*(?:GMT)?\s*([+-]\d{4})?$"
)


class AustrianAirQualityApiError(Exception):
    """Error retrieving air quality data."""


class AustrianAirQualityConnectionError(AustrianAirQualityApiError):
    """Network error or unexpected response."""


class AustrianAirQualityAuthError(AustrianAirQualityApiError):
    """Authentication failed or access denied."""


def parse_measurement_time(raw: str | None) -> datetime | None:
    """Robustly parse the interface timestamp in a locale-independent manner.

    Example value: "28 Aug 2026 13:30:00 GMT+0100".

    Warning: The source provides times in CET according to country documentation,
    also during daylight saving time. The offset is used as provided.
    """
    if not raw:
        return None
    match = _TIME_RE.match(raw.strip())
    if not match:
        _LOGGER.debug("Unknown time format: %s", raw)
        return None
    day, month, year, hour, minute, second, offset = match.groups()
    if month not in _MONTHS:
        return None
    tzinfo = timezone.utc
    if offset:
        sign = 1 if offset[0] == "+" else -1
        tzinfo = timezone(
            sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        )
    try:
        return datetime(
            int(year),
            _MONTHS[month],
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=tzinfo,
        )
    except ValueError:
        return None


@dataclass(slots=True)
class AustrianAirQualityMeasurement:
    """A measurement from a station."""

    station_id: str
    station_name: str
    location: str | None
    owner: str | None
    value: float
    unit: str
    measured_at: datetime | None
    measured_at_raw: str | None
    value_class: str | None
    latitude: float | None
    longitude: float | None


@dataclass(slots=True)
class AustrianAirQualityStation:
    """A measurement station with all available measurement types."""

    station_id: str
    station_name: str
    location: str | None
    owner: str | None
    latitude: float | None
    longitude: float | None
    # Key: pollutant_key (pm10, pm25, no2, o3, so2, co)
    # Value: AustrianAirQualityMeasurement
    measurements: dict[str, AustrianAirQualityMeasurement]


def _to_float(raw: object) -> float | None:
    """Convert a value (with comma or decimal point) to float."""
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _parse_measurement(entry: dict) -> AustrianAirQualityMeasurement | None:
    """Parse a single measurement from the API response."""
    station_id = entry.get("stationid")
    value = _to_float(entry.get("value"))
    if not station_id or value is None:
        return None

    meta = entry.get("MetaInfo") or {}
    coords = ((entry.get("gml$Point") or {}).get("gml$coord")) or {}
    raw_time = entry.get("time")

    return AustrianAirQualityMeasurement(
        station_id=str(station_id),
        station_name=str(meta.get("Name") or station_id),
        location=meta.get("Location"),
        owner=meta.get("Owner"),
        value=value,
        unit=str(entry.get("unit") or ""),
        measured_at=parse_measurement_time(raw_time),
        measured_at_raw=raw_time,
        # The interface provides longitude under X and latitude under Y,
        # despite the EPSG:31287 label.
        latitude=_to_float(coords.get("Y")),
        longitude=_to_float(coords.get("X")),
        value_class=entry.get("valueclass"),
    )


# Mapping of integration keys to API components and averaging periods.
# For simplified API: only HMW (half-hour average) or most common variant.
_POLLUTANT_MAPPING = {
    "pm10": ("PM10_K", "HMW"),
    "pm25": ("PM2_5_K", "HMW"),
    "no2": ("NO2", "HMW"),
    "o3": ("O3", "HMW"),
    "so2": ("SO2", "HMW"),
    "co": ("CO", "HMW"),
}


class AustrianAirQualityApi:
    """Encapsulates HTTP calls to the map application."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize client with a shared aiohttp session."""
        self._session = session

    async def async_fetch_station_data(
        self, station_id: str
    ) -> AustrianAirQualityStation | None:
        """Fetch all measurements for a single measurement station.

        Calls the API for each pollutant individually and aggregates
        results into one station.
        """
        # Query a small bounding box around the station.
        # We don't know the coordinates in advance, so we use a wide box
        # and filter by station_id.
        bbox = (46.2, 49.3, 9.3, 17.3)  # All of Austria

        all_measurements: dict[str, AustrianAirQualityMeasurement] = {}
        station_info = None

        for pollutant_key, (component, meantype) in _POLLUTANT_MAPPING.items():
            try:
                measurements = await self._async_fetch_pollutant(
                    bbox, component, meantype
                )
                if station_id in measurements:
                    m = measurements[station_id]
                    all_measurements[pollutant_key] = m
                    # Station-Info vom ersten erfolgreich abgerufenen Messwert nutzen
                    if station_info is None:
                        station_info = AustrianAirQualityStation(
                            station_id=m.station_id,
                            station_name=m.station_name,
                            location=m.location,
                            owner=m.owner,
                            latitude=m.latitude,
                            longitude=m.longitude,
                            measurements={},
                        )
            except AustrianAirQualityApiError as err:
                _LOGGER.warning(
                    "Fehler beim Abruf von %s für Station %s: %s",
                    pollutant_key,
                    station_id,
                    err,
                )
                # Weitermachen mit den anderen Schadsstoffen

        if not station_info:
            return None

        station_info.measurements = all_measurements
        return station_info

    async def _async_fetch_pollutant(
        self,
        bbox: tuple[float, float, float, float],
        component: str,
        meantype: str,
    ) -> dict[str, AustrianAirQualityMeasurement]:
        """Fetch all stations in a bounding box for a parameter.

        bbox is (lat_start, lat_end, lng_start, lng_end).
        Returns: station_id -> AustrianAirQualityMeasurement.
        """
        lat_start, lat_end, lng_start, lng_end = bbox
        params = {
            "runmode": "values_json",
            "LAT_START": f"{lat_start:.6f}",
            "LAT_END": f"{lat_end:.6f}",
            "LNG_START": f"{lng_start:.6f}",
            "LNG_END": f"{lng_end:.6f}",
            "MEANTYPE": meantype,
            "COMPONENT": component,
        }

        try:
            async with self._session.get(
                BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if response.status == 401:
                    raise AustrianAirQualityAuthError(f"HTTP {response.status}")
                if response.status != 200:
                    raise AustrianAirQualityConnectionError(
                        f"HTTP {response.status} für {component}/{meantype}"
                    )
                # The interface responds with text/plain instead of JSON.
                text = await response.text()
        except asyncio.TimeoutError as err:
            raise AustrianAirQualityConnectionError(
                f"Timeout for {component}/{meantype}"
            ) from err
        except aiohttp.ClientError as err:
            raise AustrianAirQualityConnectionError(
                f"Connection error for {component}/{meantype}: {err}"
            ) from err

        try:
            payload = json.loads(text)
        except ValueError as err:
            raise AustrianAirQualityConnectionError(
                f"Response for {component}/{meantype} is not valid JSON"
            ) from err

        stations = payload.get("stations")
        if not isinstance(stations, list):
            return {}

        result: dict[str, AustrianAirQualityMeasurement] = {}
        for entry in stations:
            if not isinstance(entry, dict):
                continue
            measurement = _parse_measurement(entry)
            if measurement is not None:
                result[measurement.station_id] = measurement
        return result
