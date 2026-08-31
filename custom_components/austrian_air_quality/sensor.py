"""Sensor platform for Austrian Air Quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EntityCategory,
    UnitOfDensity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import eaqi
from .api import AustrianAirQualityMeasurement
from .const import (
    ATTR_ALTITUDE,
    ATTR_AVERAGING_BASIS,
    ATTR_DOMINANT_POLLUTANT,
    ATTR_INDEX_COMPLETE,
    ATTR_LOCATION,
    ATTR_MEASURED_AT,
    ATTR_OWNER,
    ATTR_POLLUTANTS_USED,
    ATTR_SCHEME,
    ATTR_STATION_ID,
    ATTR_VALUE_CLASS,
    ATTRIBUTION,
    AVERAGING_BASIS,
    CONF_STATION_NAME,
    DOMAIN,
    KEY_STATION_INDEX,
    KEY_STATION_INDEX_LEVEL,
    MANUFACTURER,
    MEANTYPE_CURRENT,
    MEANTYPES,
    POLLUTANT_CO,
    POLLUTANT_NO,
    POLLUTANT_NO2,
    POLLUTANT_O3,
    POLLUTANT_PM10,
    POLLUTANT_PM25,
    POLLUTANT_SO2,
    index_key,
    measurement_key,
)
from .coordinator import AustrianAirQualityConfigEntry, AustrianAirQualityCoordinator

# Values without any threshold class carry this placeholder instead of leaving
# the field out, so it must not become an attribute.
NO_VALUE_CLASS = "NOCLASS"


@dataclass(frozen=True, kw_only=True)
class AustrianAirQualitySensorDescription(SensorEntityDescription):
    """Description of a pollutant sensor."""

    pollutant: str
    meantype: str


@dataclass(frozen=True, slots=True)
class PollutantTraits:
    """Everything that depends on the pollutant, not on the averaging period."""

    device_class: SensorDeviceClass
    unit: str
    precision: int


POLLUTANT_TRAITS: dict[str, PollutantTraits] = {
    POLLUTANT_PM10: PollutantTraits(
        device_class=SensorDeviceClass.PM10,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_PM25: PollutantTraits(
        device_class=SensorDeviceClass.PM25,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_NO2: PollutantTraits(
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_NO: PollutantTraits(
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_O3: PollutantTraits(
        device_class=SensorDeviceClass.OZONE,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_SO2: PollutantTraits(
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        precision=1,
    ),
    POLLUTANT_CO: PollutantTraits(
        device_class=SensorDeviceClass.CO,
        unit=UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
        precision=2,
    ),
}

# One sensor per pollutant and averaging period. The measurement key doubles as
# the entity key and the translation key, so another averaging period only needs
# an entry in MEANTYPES plus the matching names in strings.json.
SENSOR_DESCRIPTIONS: tuple[AustrianAirQualitySensorDescription, ...] = tuple(
    AustrianAirQualitySensorDescription(
        key=measurement_key(pollutant, meantype),
        translation_key=measurement_key(pollutant, meantype),
        pollutant=pollutant,
        meantype=meantype,
        device_class=traits.device_class,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=traits.unit,
        suggested_display_precision=traits.precision,
    )
    for pollutant, traits in POLLUTANT_TRAITS.items()
    for meantype in MEANTYPES
)

# One sub-index per pollutant the EAQI is defined for. CO and NO are absent
# from eaqi.EAQI_POLLUTANTS on purpose and therefore get no index sensor.
INDEX_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = tuple(
    SensorEntityDescription(
        key=index_key(pollutant),
        translation_key=index_key(pollutant),
        device_class=SensorDeviceClass.ENUM,
        options=list(eaqi.LEVELS),
    )
    for pollutant in eaqi.EAQI_POLLUTANTS
)

STATION_INDEX_DESCRIPTION = SensorEntityDescription(
    key=KEY_STATION_INDEX,
    translation_key=KEY_STATION_INDEX,
    device_class=SensorDeviceClass.ENUM,
    options=list(eaqi.LEVELS),
)

# The machine readable twin of the station index. SensorDeviceClass.AQI has no
# unit and only allows the measurement state class.
STATION_INDEX_LEVEL_DESCRIPTION = SensorEntityDescription(
    key=KEY_STATION_INDEX_LEVEL,
    translation_key=KEY_STATION_INDEX_LEVEL,
    device_class=SensorDeviceClass.AQI,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AustrianAirQualityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for a configuration entry."""
    coordinator = entry.runtime_data
    available = coordinator.data.measurements if coordinator.data else {}

    entities: list[SensorEntity] = [
        AustrianAirQualitySensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
        if description.key in available
    ]

    # A sub-index for every index pollutant the station currently reports, on
    # the half-hourly mean. A station that reports none of the five gets no
    # index entities at all rather than a permanently unknown one.
    index_pollutants = [
        pollutant
        for pollutant in eaqi.EAQI_POLLUTANTS
        if measurement_key(pollutant, MEANTYPE_CURRENT) in available
    ]
    entities.extend(
        AustrianAirQualityIndexSensor(coordinator, entry, description, pollutant)
        for description, pollutant in zip(INDEX_DESCRIPTIONS, eaqi.EAQI_POLLUTANTS)
        if pollutant in index_pollutants
    )
    if index_pollutants:
        entities.append(
            AustrianAirQualityStationIndexSensor(
                coordinator, entry, STATION_INDEX_DESCRIPTION
            )
        )
        entities.append(
            AustrianAirQualityStationIndexLevelSensor(
                coordinator, entry, STATION_INDEX_LEVEL_DESCRIPTION
            )
        )

    if coordinator.station_coordinates != (None, None):
        entities.append(AustrianAirQualityLocationSensor(coordinator, entry))

    async_add_entities(entities)


class AustrianAirQualityEntity(CoordinatorEntity[AustrianAirQualityCoordinator]):
    """Shared device registration and station metadata of the station entities."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
    ) -> None:
        """Register the entity with the station device."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_id)},
            name=entry.data.get(CONF_STATION_NAME, coordinator.station_id),
            manufacturer=MANUFACTURER,
            model="Air quality monitoring station",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Station metadata; latitude and longitude put it on the map card."""
        latitude, longitude = self.coordinator.station_coordinates
        attributes: dict[str, Any] = {ATTR_STATION_ID: self.coordinator.station_id}
        if latitude is not None and longitude is not None:
            attributes[ATTR_LATITUDE] = latitude
            attributes[ATTR_LONGITUDE] = longitude

        station = self.coordinator.data
        if station is None:
            return attributes
        if station.location:
            attributes[ATTR_LOCATION] = station.location
        if station.owner:
            attributes[ATTR_OWNER] = station.owner
        if station.altitude is not None:
            attributes[ATTR_ALTITUDE] = station.altitude
        return attributes


class AustrianAirQualitySensor(AustrianAirQualityEntity, SensorEntity):
    """A pollutant measurement of a station, for one averaging period."""

    entity_description: AustrianAirQualitySensorDescription

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
        description: AustrianAirQualitySensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return current measurement value."""
        measurement = self._measurement
        return measurement.value if measurement else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Station metadata plus timestamp and threshold class of this value."""
        attributes = super().extra_state_attributes
        measurement = self._measurement
        if measurement is None:
            return attributes
        if measurement.measured_at is not None:
            attributes[ATTR_MEASURED_AT] = measurement.measured_at.isoformat()
        if measurement.value_class not in (None, NO_VALUE_CLASS):
            attributes[ATTR_VALUE_CLASS] = measurement.value_class
        return attributes

    @property
    def available(self) -> bool:
        """Whether the measurement is currently available."""
        return super().available and self._measurement is not None

    @property
    def _measurement(self) -> AustrianAirQualityMeasurement | None:
        """The measurement backing this sensor, if the station reports it."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.measurements.get(self.entity_description.key)


class AustrianAirQualityIndexBase(AustrianAirQualityEntity, SensorEntity):
    """Shared plumbing of the EAQI entities.

    Unlike the pollutant sensors these stay available while the station is
    reachable: "the index cannot be determined" is a result in its own right
    and is reported as an unknown state, not as an unavailable entity.
    """

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"

    @property
    def _index_values(self) -> dict[str, float | None]:
        """Half-hourly mean of every index pollutant the station reports."""
        station = self.coordinator.data
        if station is None:
            return {}
        values: dict[str, float | None] = {}
        for pollutant in eaqi.EAQI_POLLUTANTS:
            measurement = station.measurements.get(
                measurement_key(pollutant, MEANTYPE_CURRENT)
            )
            if measurement is not None:
                values[pollutant] = measurement.value
        return values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Station metadata plus how the index was built."""
        attributes = super().extra_state_attributes
        attributes[ATTR_AVERAGING_BASIS] = AVERAGING_BASIS
        attributes[ATTR_SCHEME] = eaqi.SCHEME
        return attributes


class AustrianAirQualityIndexSensor(AustrianAirQualityIndexBase):
    """The EAQI sub-index of a single pollutant."""

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
        description: SensorEntityDescription,
        pollutant: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, description)
        self._pollutant = pollutant

    @property
    def native_value(self) -> str | None:
        """Index level of this pollutant, or None while it has no value."""
        return eaqi.index_for(self._pollutant, self._index_values.get(self._pollutant))


class AustrianAirQualityStationIndexSensor(AustrianAirQualityIndexBase):
    """The EAQI of the station: the worst of its sub-indices."""

    @property
    def native_value(self) -> str | None:
        """Index level, or None while the minimum data requirement is unmet."""
        return eaqi.station_index(self._index_values).level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What went into the index and whether it is complete."""
        attributes = super().extra_state_attributes
        result = eaqi.station_index(self._index_values)
        attributes[ATTR_DOMINANT_POLLUTANT] = result.dominant_pollutant
        attributes[ATTR_POLLUTANTS_USED] = list(result.pollutants_used)
        attributes[ATTR_INDEX_COMPLETE] = result.complete
        return attributes


class AustrianAirQualityStationIndexLevelSensor(AustrianAirQualityStationIndexSensor):
    """The station index as a number from 1 to 6, for graphs and comparisons.

    Deliberately unknown whenever the enum sensor is unknown; there is no
    fallback to 0, which would read as a level better than "good".
    """

    @property
    def native_value(self) -> int | None:
        """Numeric index level, or None while there is no level."""
        return eaqi.station_index(self._index_values).number


class AustrianAirQualityLocationSensor(AustrianAirQualityEntity, SensorEntity):
    """Coordinates of the station, so they show up in the device information."""

    _attr_translation_key = "station_location"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{coordinator.station_id}_location"

    @property
    def native_value(self) -> str | None:
        """Coordinates as a readable pair, e.g. "47.06695, 15.44226"."""
        latitude, longitude = self.coordinator.station_coordinates
        if latitude is None or longitude is None:
            return None
        return f"{latitude:.5f}, {longitude:.5f}"
