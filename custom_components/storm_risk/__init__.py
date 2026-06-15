"""The Storm Risk integration.

Exposes convective-storm forecasting data from the free Open-Meteo API as a
set of Home Assistant sensors, including a composite "Storm Risk" score.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import StormRiskCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type StormRiskConfigEntry = ConfigEntry[StormRiskCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StormRiskConfigEntry) -> bool:
    """Set up Storm Risk from a config entry."""
    coordinator = StormRiskCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StormRiskConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: StormRiskConfigEntry
) -> None:
    """Reload the entry when its options change so new scoring takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
