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
ATTR_ALTITUDE: Final = "altitude"
ATTR_VALUE_CLASS: Final = "value_class"

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)

# The config flow already downloads everything a station reports in order to
# show it for review. That result is handed to the setup of the new entry under
# this key, so adding a station does not fetch the same data a second time and
# the dialog closes right away instead of waiting out another full round.
DATA_PREFETCHED: Final = "prefetched_stations"

# How long such a handoff stays usable. Long enough to cover a user who reads
# the review screen for a while, short enough that the entry never starts up
# on measurements that have since been superseded.
PREFETCH_MAX_AGE: Final = timedelta(minutes=10)

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
POLLUTANT_NO: Final = "no"
POLLUTANT_O3: Final = "o3"
POLLUTANT_SO2: Final = "so2"
POLLUTANT_CO: Final = "co"

POLLUTANTS: Final[tuple[str, ...]] = (
    POLLUTANT_PM10,
    POLLUTANT_PM25,
    POLLUTANT_NO2,
    POLLUTANT_NO,
    POLLUTANT_O3,
    POLLUTANT_SO2,
    POLLUTANT_CO,
)

# Averaging periods every pollutant is fetched for. The half-hour mean is the
# freshest value the source publishes and therefore carries the plain pollutant
# key; the daily mean is what the Austrian limit values refer to.
MEANTYPE_CURRENT: Final = "current"
MEANTYPE_DAILY: Final = "daily"

MEANTYPES: Final[tuple[str, ...]] = (MEANTYPE_CURRENT, MEANTYPE_DAILY)


def measurement_key(pollutant: str, meantype: str) -> str:
    """Key of one pollutant/averaging-period combination.

    The half-hour mean keeps the bare pollutant key so the entities that
    existed before daily means were added keep their unique IDs and history.
    """
    if meantype == MEANTYPE_CURRENT:
        return pollutant
    return f"{pollutant}_{meantype}"


# Short chemical labels for the config flow. Deliberately language neutral so
# they can be used inside dynamically built select options and markdown, where
# the translation machinery is not available.
POLLUTANT_LABELS: Final[dict[str, str]] = {
    POLLUTANT_PM10: "PM10",
    POLLUTANT_PM25: "PM2.5",
    POLLUTANT_NO2: "NO₂",
    POLLUTANT_NO: "NO",
    POLLUTANT_O3: "O₃",
    POLLUTANT_SO2: "SO₂",
    POLLUTANT_CO: "CO",
}
