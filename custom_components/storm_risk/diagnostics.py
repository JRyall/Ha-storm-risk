"""Diagnostics support for the Storm Risk integration.

Returns a one-click dump (config entry data/options, the computed result and
the last raw Open-Meteo response) for troubleshooting, with the coordinates
redacted.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import StormRiskConfigEntry

TO_REDACT = {"latitude", "longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StormRiskConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "computed": asdict(data) if data is not None else None,
        "last_api_response": async_redact_data(
            coordinator.last_payload or {}, TO_REDACT
        ),
    }
