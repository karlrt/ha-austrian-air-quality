"""Sensor-Plattform für Luftqualität Österreich."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
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
    """Beschreibung eines Schadstoff-Sensors."""

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
    """Sensoren für einen Konfigurationseintrag anlegen."""
    coordinator = entry.runtime_data
    available = coordinator.data.values if coordinator.data else {}

    async_add_entities(
        AustrianAirQualitySensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
        if description.pollutant in available
    )


class AustrianAirQualitySensor(CoordinatorEntity[AustrianAirQualityCoordinator], SensorEntity):
    """Ein Schadstoff-Messwert einer Station."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: AustrianAirQualitySensorDescription

    def __init__(
        self,
        coordinator: AustrianAirQualityCoordinator,
        entry: AustrianAirQualityConfigEntry,
        description: AustrianAirQualitySensorDescription,
    ) -> None:
        """Sensor initialisieren."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.station_id)},
            name=entry.data.get(CONF_STATION_NAME, coordinator.station_id),
            manufacturer=MANUFACTURER,
            model="Luftqualitäts-Messstelle",
        )

    @property
    def native_value(self) -> float | None:
        """Aktuellen Messwert zurückgeben."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.values.get(self.entity_description.pollutant)

    @property
    def available(self) -> bool:
        """Ob der Messwert derzeit vorliegt."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.pollutant in self.coordinator.data.values
        )
