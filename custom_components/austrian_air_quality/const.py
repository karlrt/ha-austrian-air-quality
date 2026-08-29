"""Konstanten für die Integration Luftqualität Österreich."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "austrian_air_quality"

MANUFACTURER: Final = "Umweltbundesamt"
ATTRIBUTION: Final = "Daten: Umweltbundesamt GmbH (inoffizielle Integration)"

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)

# Schlüssel der Messgrößen. Werden sowohl vom API-Client als auch von den
# Sensor-Beschreibungen in sensor.py verwendet.
POLLUTANT_PM10: Final = "pm10"
POLLUTANT_PM25: Final = "pm25"
POLLUTANT_NO2: Final = "no2"
POLLUTANT_O3: Final = "o3"
POLLUTANT_SO2: Final = "so2"
POLLUTANT_CO: Final = "co"

POLLUTANTS: Final[tuple[str, ...]] = (
    POLLUTANT_PM10,
    POLLUTANT_PM25,
    POLLUTANT_NO2,
    POLLUTANT_O3,
    POLLUTANT_SO2,
    POLLUTANT_CO,
)
