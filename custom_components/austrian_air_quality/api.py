"""Client for the JSON interface of the Austrian Environment Agency's air quality map.

Note: This is an undocumented interface used by the public map application
at luft.umweltbundesamt.at. It may change without notice.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

import aiohttp

from .const import (
    AT_BBOX,
    MEANTYPE_CURRENT,
    MEANTYPE_DAILY,
    MEANTYPES,
    POLLUTANT_CO,
    POLLUTANT_NO,
    POLLUTANT_NO2,
    POLLUTANT_O3,
    POLLUTANT_PM10,
    POLLUTANT_PM25,
    POLLUTANT_SO2,
    STATION_BBOX_PADDING,
    measurement_key,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://luft.umweltbundesamt.at/pub/map_chart/index.pl"
REQUEST_TIMEOUT = 30

# The endpoint is public and undocumented, so the pollutant queries are spaced
# out by this many seconds.
REQUEST_DELAY = 0.3

EARTH_RADIUS_KM = 6371.0

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


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def bbox_around(
    latitude: float, longitude: float, radius_km: float
) -> tuple[float, float, float, float]:
    """Bounding box around a point, as (lat_start, lat_end, lng_start, lng_end).

    A rough kilometre-to-degree conversion is entirely sufficient here; the box
    only pre-filters the stations, the exact radius is applied afterwards.
    """
    km_per_degree_lat = 111.0
    lat_delta = radius_km / km_per_degree_lat
    lon_scale = max(cos(radians(latitude)), 0.1)
    lon_delta = radius_km / (km_per_degree_lat * lon_scale)
    return (
        latitude - lat_delta,
        latitude + lat_delta,
        longitude - lon_delta,
        longitude + lon_delta,
    )


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
    altitude: float | None


@dataclass(slots=True)
class AustrianAirQualityStation:
    """A measurement station with all available measurement types."""

    station_id: str
    station_name: str
    location: str | None
    owner: str | None
    latitude: float | None
    longitude: float | None
    altitude: float | None = None
    # Key: measurement key, i.e. pollutant plus averaging period
    # (pm10, pm10_daily, no2, no2_daily, ...) as built by measurement_key().
    # Value: AustrianAirQualityMeasurement
    measurements: dict[str, AustrianAirQualityMeasurement] = field(
        default_factory=dict
    )

    @property
    def pollutants(self) -> list[str]:
        """Pollutant keys this station currently reports, in a stable order.

        Based on the freshest averaging period, which is what the config flow
        shows while the station is being picked.
        """
        return [
            pollutant
            for pollutant in _COMPONENTS
            if measurement_key(pollutant, MEANTYPE_CURRENT) in self.measurements
        ]


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
        altitude=_to_float(coords.get("Z")),
        value_class=entry.get("valueclass"),
    )


# API component name of every pollutant. "_K" marks the continuously measuring
# instruments, which are the only ones the map interface serves.
_COMPONENTS: dict[str, str] = {
    POLLUTANT_PM10: "PM10_K",
    POLLUTANT_PM25: "PM2_5_K",
    POLLUTANT_NO2: "NO2",
    POLLUTANT_NO: "NO",
    POLLUTANT_O3: "O3",
    POLLUTANT_SO2: "SO2",
    POLLUTANT_CO: "CO",
}

# API averaging period of every meantype key. The interface also knows MW1,
# MW3, MW8 and MW24 for all of these components; only the two below are
# fetched, to keep the number of requests per update reasonable.
_API_MEANTYPES: dict[str, str] = {
    MEANTYPE_CURRENT: "HMW",
    MEANTYPE_DAILY: "TMW",
}


def _queries(meantypes: Sequence[str]) -> list[tuple[str, str, str]]:
    """Query plan as (measurement key, API component, API averaging period)."""
    return [
        (measurement_key(pollutant, meantype), component, _API_MEANTYPES[meantype])
        for pollutant, component in _COMPONENTS.items()
        for meantype in meantypes
    ]


class AustrianAirQualityApi:
    """Encapsulates HTTP calls to the map application."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize client with a shared aiohttp session."""
        self._session = session

    async def async_get_stations(
        self, bbox: tuple[float, float, float, float] | None = None
    ) -> list[AustrianAirQualityStation]:
        """Fetch the currently reporting measurement stations in a bounding box.

        Queries every known pollutant and aggregates them per station, so each
        returned station already carries the measurements it currently reports.
        Defaults to all of Austria. Used by the config flow to populate the
        station picker and to show what a station actually measures.

        Only the freshest averaging period is requested here: the picker just
        needs to know what a station measures, and the search may cover all of
        Austria, where every additional averaging period means another large
        response.
        """
        stations = await self._async_collect(
            bbox or AT_BBOX, meantypes=(MEANTYPE_CURRENT,)
        )
        return sorted(stations.values(), key=lambda station: station.station_name)

    async def async_fetch_station_data(
        self,
        station_id: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> AustrianAirQualityStation | None:
        """Fetch all measurements for a single measurement station.

        Covers every pollutant in every averaging period, so the station comes
        back with both its current values and its daily means.

        When the station coordinates are known, a small bounding box around them
        keeps the responses small. Otherwise all of Austria has to be scanned
        and the station is filtered out afterwards.
        """
        if latitude is not None and longitude is not None:
            bbox = (
                latitude - STATION_BBOX_PADDING,
                latitude + STATION_BBOX_PADDING,
                longitude - STATION_BBOX_PADDING,
                longitude + STATION_BBOX_PADDING,
            )
        else:
            bbox = AT_BBOX

        stations = await self._async_collect(bbox, station_id=station_id)
        return stations.get(station_id)

    async def _async_collect(
        self,
        bbox: tuple[float, float, float, float],
        station_id: str | None = None,
        meantypes: Sequence[str] = MEANTYPES,
    ) -> dict[str, AustrianAirQualityStation]:
        """Query every pollutant for a bounding box and group by station.

        Individual query failures are tolerated; only a complete failure of all
        requests is raised, so one flaky parameter does not take the whole
        station down.
        """
        stations: dict[str, AustrianAirQualityStation] = {}
        queries = _queries(meantypes)
        failures = 0

        for index, (key, component, api_meantype) in enumerate(queries):
            if index:
                await asyncio.sleep(REQUEST_DELAY)
            try:
                measurements = await self._async_fetch_pollutant(
                    bbox, component, api_meantype
                )
            except AustrianAirQualityApiError as err:
                _LOGGER.warning(
                    "Error retrieving %s/%s: %s", component, api_meantype, err
                )
                failures += 1
                continue

            for measurement in measurements.values():
                if station_id is not None and measurement.station_id != station_id:
                    continue
                station = stations.get(measurement.station_id)
                if station is None:
                    station = AustrianAirQualityStation(
                        station_id=measurement.station_id,
                        station_name=measurement.station_name,
                        location=measurement.location,
                        owner=measurement.owner,
                        latitude=measurement.latitude,
                        longitude=measurement.longitude,
                        altitude=measurement.altitude,
                    )
                    stations[measurement.station_id] = station
                station.measurements[key] = measurement

        if failures == len(queries):
            raise AustrianAirQualityConnectionError(
                "None of the air quality requests succeeded"
            )

        return stations

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
                        f"HTTP {response.status} for {component}/{meantype}"
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
