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
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LOCATION,
    ATTR_MEASURED_AT,
    ATTR_OWNER,
    ATTR_STATION_ID,
    ATTRIBUTION,
    CONF_STATION_NAME,
    DOMAIN,
    MANUFACTURER,
    POLLUTANT_CO,
    POLLUTANT_NO2,
    POLLUTANT_O3,
    POLLUTANT_PM10,
    POLLUTANT_PM25,
    POLLUTANT_SO2,
)
from .coordinator import AustrianAirQualityConfigEntry, AustrianAirQualityCoordinator


@dataclass(frozen=True, kw_only=True)
class AustrianAirQualitySensorDescription(SensorEntityDescription):
    """Description of a pollutant sensor."""

    pollutant: str


SENSOR_DESCRIPTIONS: tuple[AustrianAirQualitySensorDescription, ...] = (
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_PM10,
        pollutant=POLLUTANT_PM10,
        translation_key=POLLUTANT_PM10,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_PM25,
        pollutant=POLLUTANT_PM25,
        translation_key=POLLUTANT_PM25,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_NO2,
        pollutant=POLLUTANT_NO2,
        translation_key=POLLUTANT_NO2,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_O3,
        pollutant=POLLUTANT_O3,
        translation_key=POLLUTANT_O3,
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_SO2,
        pollutant=POLLUTANT_SO2,
        translation_key=POLLUTANT_SO2,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    AustrianAirQualitySensorDescription(
        key=POLLUTANT_CO,
        pollutant=POLLUTANT_CO,
        translation_key=POLLUTANT_CO,
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        suggested_display_precision=2,
    ),
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
        if description.pollutant in available
    ]
    if coordinator.station_coordinates != (None, None):
        entities.append(AustrianAirQualityLocationSensor(coordinator, entry))

    async_add_entities(entities)


class AustrianAirQualityEntity(CoordinatorEntity[AustrianAirQualityCoordinator]):
    """Shared device registration and station metadata of a station's entities."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
    ) -> None:
        """Register the entity with the station's device."""
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
        return attributes


class AustrianAirQualitySensor(AustrianAirQualityEntity, SensorEntity):
    """A pollutant measurement from a station."""

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
        if self.coordinator.data is None:
            return None
        measurement = self.coordinator.data.measurements.get(self.entity_description.pollutant)
        return measurement.value if measurement else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Station metadata plus the timestamp of this measurement."""
        attributes = super().extra_state_attributes
        station = self.coordinator.data
        if station is None:
            return attributes
        measurement = station.measurements.get(self.entity_description.pollutant)
        if measurement is not None and measurement.measured_at is not None:
            attributes[ATTR_MEASURED_AT] = measurement.measured_at.isoformat()
        return attributes

    @property
    def available(self) -> bool:
        """Whether the measurement is currently available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.pollutant in self.coordinator.data.measurements
        )


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
