"""Sensor platform for the Storm Risk integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StormRiskConfigEntry
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import StormRiskCoordinator, StormRiskData

# J/kg is not a Home Assistant unit constant, so define it locally.
UNIT_JOULES_PER_KG = "J/kg"


@dataclass(frozen=True, kw_only=True)
class StormRiskSensorDescription(SensorEntityDescription):
    """Describes a Storm Risk sensor and how to read its value."""

    value_fn: Callable[[StormRiskData], float | int | str | None]
    attributes_fn: Callable[[StormRiskData], dict[str, Any]] | None = None


SENSORS: tuple[StormRiskSensorDescription, ...] = (
    StormRiskSensorDescription(
        key="cape_now",
        translation_key="cape_now",
        native_unit_of_measurement=UNIT_JOULES_PER_KG,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-lightning",
        suggested_display_precision=0,
        value_fn=lambda data: data.cape_now,
        # "How maxed" the CAPE is (weak/moderate/significant/major/extreme),
        # since the score bar saturates near 1000 J/kg.
        attributes_fn=lambda data: {"magnitude": data.cape_magnitude},
    ),
    StormRiskSensorDescription(
        key="cin_now",
        translation_key="cin_now",
        native_unit_of_measurement=UNIT_JOULES_PER_KG,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shield-cloud",
        suggested_display_precision=0,
        value_fn=lambda data: data.cin_now,
        # Cap trajectory vs 6h ago (strengthening/holding/weakening) plus the
        # delta, and whether the cap can realistically break.
        attributes_fn=lambda data: {
            "trend": data.cin_trend,
            "trend_delta_6h": data.cin_trend_delta,
            "cap_state": data.cap_state,
        },
    ),
    StormRiskSensorDescription(
        key="cape_max_today",
        translation_key="cape_max_today",
        native_unit_of_measurement=UNIT_JOULES_PER_KG,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-lightning",
        suggested_display_precision=0,
        value_fn=lambda data: data.cape_max_today,
    ),
    StormRiskSensorDescription(
        key="cape_peak_hour",
        translation_key="cape_peak_hour",
        icon="mdi:clock-alert-outline",
        value_fn=lambda data: data.cape_peak_hour,
    ),
    StormRiskSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temperature,
    ),
    StormRiskSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.dew_point,
    ),
    StormRiskSensorDescription(
        key="cape_outlook",
        translation_key="cape_outlook",
        native_unit_of_measurement=UNIT_JOULES_PER_KG,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-week",
        suggested_display_precision=0,
        value_fn=lambda data: data.cape_outlook_max,
        attributes_fn=lambda data: {"daily": data.daily_outlook},
    ),
    StormRiskSensorDescription(
        key="shear",
        translation_key="shear",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-windy",
        suggested_display_precision=1,
        value_fn=lambda data: data.shear,
        attributes_fn=lambda data: {"mode": data.mode},
    ),
    StormRiskSensorDescription(
        key="trigger",
        translation_key="trigger",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-pouring",
        suggested_display_precision=0,
        value_fn=lambda data: data.trigger,
        # Best-effort trigger type: none / diurnal / synoptic / unknown.
        attributes_fn=lambda data: {"source": data.trigger_source},
    ),
    StormRiskSensorDescription(
        key="storm_risk_outlook",
        translation_key="storm_risk_outlook",
        # Unitless 0-100 score, like the main Storm risk sensor.
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-alert",
        suggested_display_precision=0,
        value_fn=lambda data: data.storm_risk_outlook_max,
        attributes_fn=lambda data: {"daily": data.daily_outlook},
    ),
    StormRiskSensorDescription(
        key="storm_risk",
        translation_key="storm_risk",
        # No unit: this is a 0-100 "ingredients" score, not a probability/%.
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-lightning-rainy",
        suggested_display_precision=0,
        value_fn=lambda data: data.storm_risk,
        attributes_fn=lambda data: {
            "cape_score": data.cape_score,
            "cin_score": data.cin_score,
            "dp_score": data.dp_score,
            "level": data.level,
            # Raw current-hour values, so the card can show the real data
            # alongside the score breakdown.
            "cape": data.cape_now,
            "cin": data.cin_now,
            "dew_point": data.dew_point,
            # Organisation (shear) and trigger context -- shown on the card and
            # available to automations. None when the model lacks the data.
            "shear": data.shear,
            "mode": data.mode,
            "trigger": data.trigger,
            # Next-24h peak, for notifications and the card's peak marker.
            "peak_score": data.peak_score,
            "peak_time": data.peak_time,
            # Roaming: whether the location is currently following a device.
            "roaming": data.roaming_active,
            "location_source": data.location_source,
            # Firing-likelihood context for the card.
            "cape_magnitude": data.cape_magnitude,
            "cin_trend": data.cin_trend,
            "cap_state": data.cap_state,
            "trigger_source": data.trigger_source,
            # Next-24h series for ApexCharts / history graphing.
            "forecast": data.forecast,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StormRiskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storm Risk sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        StormRiskSensor(coordinator, entry, description) for description in SENSORS
    )


class StormRiskSensor(CoordinatorEntity[StormRiskCoordinator], SensorEntity):
    """A single Storm Risk sensor backed by the shared coordinator."""

    entity_description: StormRiskSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StormRiskCoordinator,
        entry: StormRiskConfigEntry,
        description: StormRiskSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", DEFAULT_NAME),
            manufacturer="Open-Meteo",
            model="Convective storm forecast",
            configuration_url="https://open-meteo.com/",
        )

    @property
    def available(self) -> bool:
        """Return True only when the last refresh produced usable data."""
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value for this sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes (e.g. score breakdown for Storm Risk)."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
