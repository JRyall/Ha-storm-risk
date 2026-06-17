"""Binary sensor platform for the Storm Risk integration.

Exposes a single "Storm risk active" sensor that turns on once the score
crosses a configurable threshold -- cleaner for automations and conditions
(and the logbook) than everyone hand-rolling a numeric_state trigger.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StormRiskConfigEntry
from .const import (
    CONF_ACTIVE_THRESHOLD,
    DEFAULT_ACTIVE_THRESHOLD,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import StormRiskCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StormRiskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storm Risk binary sensor from a config entry."""
    async_add_entities([StormRiskActiveBinarySensor(entry.runtime_data, entry)])


class StormRiskActiveBinarySensor(
    CoordinatorEntity[StormRiskCoordinator], BinarySensorEntity
):
    """On when the storm-risk score is at or above the active threshold."""

    _attr_has_entity_name = True
    _attr_translation_key = "storm_risk_active"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:weather-lightning"

    def __init__(
        self,
        coordinator: StormRiskCoordinator,
        entry: StormRiskConfigEntry,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_storm_risk_active"
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
    def _threshold(self) -> int:
        return int(
            self._entry.options.get(CONF_ACTIVE_THRESHOLD, DEFAULT_ACTIVE_THRESHOLD)
        )

    @property
    def is_on(self) -> bool:
        """Return True when the score is at or above the active threshold."""
        return self.coordinator.data.storm_risk >= self._threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the score, band and threshold for context."""
        data = self.coordinator.data
        return {
            "storm_risk": data.storm_risk,
            "level": data.level,
            "threshold": self._threshold,
        }
