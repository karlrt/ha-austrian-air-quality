"""Constants for the Austrian Air Quality integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "austrian_air_quality"

MANUFACTURER: Final = "Umweltbundesamt"
ATTRIBUTION: Final = (
    "Data: Umweltbundesamt (Environment Agency Austria), luft.umweltbundesamt.at"
)

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

# Attributes of the EAQI index sensors.
ATTR_DOMINANT_POLLUTANT: Final = "dominant_pollutant"
ATTR_POLLUTANTS_USED: Final = "pollutants_used"
ATTR_INDEX_COMPLETE: Final = "index_complete"
ATTR_AVERAGING_BASIS: Final = "averaging_basis"
ATTR_SCHEME: Final = "scheme"

# The EAQI is defined on hourly means, but the source publishes half-hourly
# means as its freshest figure, so that is what the index is built on. Every
# index sensor carries this so the approximation is visible on the entity
# itself and not only in the documentation.
AVERAGING_BASIS: Final = "HMW (approximation of hourly mean)"

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
#
# TMW is the mean of the *completed previous* calendar day, not a running mean
# of the current day. Verified 2026-09-02: TMW carries the timestamp of the day
# boundary (00:00) and stays constant all day, while MW24 carries the current
# hour and moves with it. The day is a CET day (UTC+1 year round), so in summer
# it runs 01:00 to 01:00 local time.
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


# Every pollutant/averaging-period combination the integration knows, in a
# stable order. This is the catalogue an entry picks from. What a station
# happens to report at some moment must never shorten it: a choice built from
# a snapshot freezes at the moment it was taken, and a value the station only
# reports again later would stay unreachable.
MEASUREMENT_KEYS: Final[tuple[str, ...]] = tuple(
    measurement_key(pollutant, meantype)
    for pollutant in POLLUTANTS
    for meantype in MEANTYPES
)


# Entity keys of the EAQI sensors. The sub-index of a pollutant is that
# pollutant's key plus this suffix, which cannot collide with an averaging
# period key because no meantype is called "index".
INDEX_SUFFIX: Final = "_index"

KEY_STATION_INDEX: Final = "air_quality_index"
KEY_STATION_INDEX_LEVEL: Final = "air_quality_index_level"


def index_key(pollutant: str) -> str:
    """Entity key of the sub-index of one pollutant."""
    return f"{pollutant}{INDEX_SUFFIX}"


# Entity key of the diagnostic coordinates entity.
KEY_STATION_LOCATION: Final = "location"

# Keys of the entry options. They hold what the user picked, and they alone
# decide which entities exist; whether an entity carries a value is decided at
# runtime from what the station reports. Keeping those two apart is the point:
# tying them together is what used to freeze the entity set at setup time.
OPT_MEASUREMENTS: Final = "measurements"
OPT_INDEXES: Final = "indexes"
OPT_STATION_INDEX: Final = "station_index"
OPT_LOCATION: Final = "location_entity"

# Config flow only, never stored: whether the second step with the index and
# diagnostic entities follows the measurement selection.
CONF_ADVANCED: Final = "advanced"


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
