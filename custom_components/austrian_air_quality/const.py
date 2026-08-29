"""Constants for the Austrian Air Quality integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "austrian_air_quality"

MANUFACTURER: Final = "Austrian Environment Agency"
ATTRIBUTION: Final = "Data: Federal Environment Agency Austria (unofficial integration)"

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)

# Keys for measurement types. Used by both the API client and the
# sensor descriptions in sensor.py.
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
