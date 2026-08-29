"""Constants for the Austrian Air Quality integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "austrian_air_quality"

MANUFACTURER: Final = "Austrian Environment Agency"
ATTRIBUTION: Final = "Data: Federal Environment Agency Austria (unofficial integration)"

CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_LOCATION: Final = "location"
CONF_QUERY: Final = "query"

# State attributes of the pollutant sensors. latitude and longitude are the
# names the map card looks for, so they have to stay exactly these.
ATTR_STATION_ID: Final = "station_id"
ATTR_LOCATION: Final = "location"
ATTR_OWNER: Final = "owner"
ATTR_MEASURED_AT: Final = "measured_at"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)

# Default and maximum radius of the station search, in kilometres.
DEFAULT_RADIUS_KM: Final = 15
MAX_RADIUS_KM: Final = 100

# Bounding box covering all of Austria (with a little margin),
# as (lat_start, lat_end, lng_start, lng_end).
AT_BBOX: Final[tuple[float, float, float, float]] = (46.2, 49.3, 9.3, 17.3)

# Once the station coordinates are known, its measurements are fetched with a
# small bounding box around them. 0.03 degrees are roughly 3 km, which is tight
# enough to keep the responses small.
STATION_BBOX_PADDING: Final = 0.03

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

# Short chemical labels for the config flow. Deliberately language neutral so
# they can be used inside dynamically built select options and markdown, where
# the translation machinery is not available.
POLLUTANT_LABELS: Final[dict[str, str]] = {
    POLLUTANT_PM10: "PM10",
    POLLUTANT_PM25: "PM2.5",
    POLLUTANT_NO2: "NO\u2082",
    POLLUTANT_O3: "O\u2083",
    POLLUTANT_SO2: "SO\u2082",
    POLLUTANT_CO: "CO",
}
