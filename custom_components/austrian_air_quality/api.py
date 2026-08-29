"""Client für die JSON-Schnittstelle der Luftgütekarte des Umweltbundesamts.

Hinweis: Es handelt sich um eine nicht dokumentierte Schnittstelle, die von der
öffentlichen Kartenanwendung unter luft.umweltbundesamt.at verwendet wird. Sie
kann sich ohne Ankündigung ändern.
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
    """Fehler beim Abruf der Luftqualitätsdaten."""


class AustrianAirQualityConnectionError(AustrianAirQualityApiError):
    """Netzwerkfehler oder unerwartete Antwort."""


class AustrianAirQualityAuthError(AustrianAirQualityApiError):
    """Authentifizierung fehlgeschlagen bzw. Zugriff verweigert."""


def parse_measurement_time(raw: str | None) -> datetime | None:
    """Zeitstempel der Schnittstelle robust und locale-unabhängig parsen.

    Beispielwert: "28 Aug 2026 13:30:00 GMT+0100".

    Achtung: Die Quelle gibt Zeiten laut Dokumentation der Länder in MEZ an,
    auch während der Sommerzeit. Der Offset wird übernommen wie geliefert.
    """
    if not raw:
        return None
    match = _TIME_RE.match(raw.strip())
    if not match:
        _LOGGER.debug("Unbekanntes Zeitformat: %s", raw)
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
    """Ein Messwert einer Station."""

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
    """Eine Messstation mit allen verfügbaren Messgrößen."""

    station_id: str
    station_name: str
    location: str | None
    owner: str | None
    latitude: float | None
    longitude: float | None
    # Schlüssel: pollutant_key (pm10, pm25, no2, o3, so2, co)
    # Wert: AustrianAirQualityMeasurement
    measurements: dict[str, AustrianAirQualityMeasurement]


def _to_float(raw: object) -> float | None:
    """Konvertiere einen Wert (mit Komma oder Punkt) zu float."""
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _parse_measurement(entry: dict) -> AustrianAirQualityMeasurement | None:
    """Parse einen einzelnen Messwert aus der API-Antwort."""
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
        # Die Schnittstelle liefert unter X die geographische Länge und
        # unter Y die Breite, trotz des Labels EPSG:31287.
        latitude=_to_float(coords.get("Y")),
        longitude=_to_float(coords.get("X")),
        value_class=entry.get("valueclass"),
    )


# Mapping von Integrations-Schlüsseln zu API-Komponenten und Mittelungszeiträumen.
# Für vereinfachte API: nur HMW (Halbstunden-Mittelwert) oder häufigste Variante.
_POLLUTANT_MAPPING = {
    "pm10": ("PM10_K", "HMW"),
    "pm25": ("PM2_5_K", "HMW"),
    "no2": ("NO2", "HMW"),
    "o3": ("O3", "HMW"),
    "so2": ("SO2", "HMW"),
    "co": ("CO", "HMW"),
}


class AustrianAirQualityApi:
    """Kapselt die HTTP-Aufrufe gegen die Kartenanwendung."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Client mit einer geteilten aiohttp-Session initialisieren."""
        self._session = session

    async def async_fetch_station_data(
        self, station_id: str
    ) -> AustrianAirQualityStation | None:
        """Hole alle Messwerte für eine einzelne Messstation.

        Ruft die API für jeden Schadstoff einzeln auf und aggregiert die Ergebnisse
        zu einer Station.
        """
        # Eine kleine Bounding-Box um die Station abfragen.
        # Wir wissen die Koordinaten nicht im Voraus, also verwenden wir eine
        # breite Box und filtern dann nach station_id.
        bbox = (46.2, 49.3, 9.3, 17.3)  # Ganz Österreich

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
        """Hole alle Stationen einer Bounding-Box für einen Parameter.

        bbox ist (lat_start, lat_end, lng_start, lng_end).
        Rückgabe: station_id -> AustrianAirQualityMeasurement.
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
                # Die Schnittstelle antwortet mit text/plain statt JSON.
                text = await response.text()
        except asyncio.TimeoutError as err:
            raise AustrianAirQualityConnectionError(
                f"Zeitüberschreitung bei {component}/{meantype}"
            ) from err
        except aiohttp.ClientError as err:
            raise AustrianAirQualityConnectionError(
                f"Verbindungsfehler bei {component}/{meantype}: {err}"
            ) from err

        try:
            payload = json.loads(text)
        except ValueError as err:
            raise AustrianAirQualityConnectionError(
                f"Antwort für {component}/{meantype} ist kein gültiges JSON"
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
