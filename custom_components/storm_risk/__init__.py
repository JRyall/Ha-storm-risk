"""The Storm Risk integration.

Exposes convective-storm forecasting data from the free Open-Meteo API as a
set of Home Assistant sensors, including a composite "Storm Risk" score.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import StormRiskCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# This integration is configured only via config entries (UI); there are no
# YAML options under the `storm_risk:` key. Required because we define
# async_setup (to register the bundled card).
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type StormRiskConfigEntry = ConfigEntry[StormRiskCoordinator]

# Bundled Lovelace card, served from the integration and auto-loaded on the
# frontend so users get it without registering a dashboard resource by hand.
_CARD_FILENAME = "storm-risk-card.js"
_CARD_URL = f"/{DOMAIN}/{_CARD_FILENAME}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled frontend card once for the whole integration."""
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card's JS and tell the frontend to load it as a module."""
    card_path = Path(__file__).parent / "www" / _CARD_FILENAME
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, str(card_path), cache_headers=False)]
        )
        # Cache-bust on upgrade so browsers pick up new card versions.
        add_extra_js_url(hass, f"{_CARD_URL}?v={_card_version()}")
    except RuntimeError:
        # Path already registered (e.g. integration reloaded) — harmless.
        _LOGGER.debug("Storm Risk card already registered")


def _card_version() -> str:
    """Return the integration version for frontend cache-busting."""
    manifest = Path(__file__).parent / "manifest.json"
    try:
        return str(json.loads(manifest.read_text()).get("version", "0"))
    except (OSError, ValueError):
        return "0"


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
