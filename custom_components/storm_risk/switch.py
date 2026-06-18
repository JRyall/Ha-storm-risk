"""Switch platform for the Storm Risk integration.

A per-location "Roaming" switch. While on, the location follows the live GPS of
a predefined person / device_tracker (set in the options) instead of its fixed
coordinates -- handy for taking the forecast with you when you travel.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StormRiskConfigEntry
from .const import CONF_ROAMING_ENTITY, DEFAULT_NAME, DOMAIN
from .coordinator import StormRiskCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StormRiskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storm Risk roaming switch from a config entry."""
    async_add_entities([StormRiskRoamingSwitch(entry.runtime_data, entry)])


class StormRiskRoamingSwitch(
    CoordinatorEntity[StormRiskCoordinator], SwitchEntity, RestoreEntity
):
    """Follow a predefined device's GPS while on; fixed coordinates while off."""

    _attr_has_entity_name = True
    _attr_translation_key = "roaming"
    _attr_icon = "mdi:map-marker-radius"

    def __init__(
        self,
        coordinator: StormRiskCoordinator,
        entry: StormRiskConfigEntry,
    ) -> None:
        """Initialise the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_roaming"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", DEFAULT_NAME),
            manufacturer="Open-Meteo",
            model="Convective storm forecast",
            configuration_url="https://open-meteo.com/",
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last switch position and re-arm roaming if it was on."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state == "on":
            self._attr_is_on = True
            await self.coordinator.async_set_roaming(True)

    @property
    def available(self) -> bool:
        """Only usable once a device to follow has been chosen in options."""
        return bool(self._entry.options.get(CONF_ROAMING_ENTITY))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start following the configured device."""
        self._attr_is_on = True
        await self.coordinator.async_set_roaming(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Return to the fixed home coordinates."""
        self._attr_is_on = False
        await self.coordinator.async_set_roaming(False)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose what's being followed and where it currently resolves to."""
        return {
            "following": self._entry.options.get(CONF_ROAMING_ENTITY),
            "roaming_active": self.coordinator.roaming_active,
            "latitude": self.coordinator.active_latitude,
            "longitude": self.coordinator.active_longitude,
        }
