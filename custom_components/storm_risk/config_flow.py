"""Config and options flow for the Storm Risk integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from . import StormRiskConfigEntry
from .const import (
    CONF_ACTIVE_THRESHOLD,
    CONF_CAPE_DIVISOR,
    CONF_CAPE_GATE,
    CONF_CIN_DIVISOR,
    CONF_DEW_POINT_FLOOR,
    CONF_DEW_POINT_MULTIPLIER,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_ROAMING_ENTITY,
    CONF_SHEAR_LOADED_MIN,
    CONF_SHEAR_SEVERE_MIN,
    CONF_THRESHOLD_LOADED,
    CONF_THRESHOLD_QUIET,
    CONF_THRESHOLD_SEVERE,
    CONF_THRESHOLD_WATCH,
    DEFAULT_ACTIVE_THRESHOLD,
    DEFAULT_CAPE_DIVISOR,
    DEFAULT_CAPE_GATE,
    DEFAULT_CIN_DIVISOR,
    DEFAULT_DEW_POINT_FLOOR,
    DEFAULT_DEW_POINT_MULTIPLIER,
    DEFAULT_NAME,
    DEFAULT_SHEAR_LOADED_MIN,
    DEFAULT_SHEAR_SEVERE_MIN,
    DEFAULT_THRESHOLD_LOADED,
    DEFAULT_THRESHOLD_QUIET,
    DEFAULT_THRESHOLD_SEVERE,
    DEFAULT_THRESHOLD_WATCH,
    DOMAIN,
)


def _positive_number_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0.1, step=0.1, mode=NumberSelectorMode.BOX)
    )


def _cape_gate_selector() -> NumberSelector:
    # CAPE (J/kg) below which the CIN contribution is suppressed; 0 disables it.
    return NumberSelector(
        NumberSelectorConfig(min=0, step=10, mode=NumberSelectorMode.BOX)
    )


def _fraction_selector() -> NumberSelector:
    # A 0..1 fraction (e.g. the dew-point floor), shown as a slider.
    return NumberSelector(
        NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.SLIDER)
    )


def _score_threshold_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER)
    )


def _shear_selector() -> NumberSelector:
    # Bulk shear in m/s; 0 effectively disables that band's shear requirement.
    return NumberSelector(
        NumberSelectorConfig(min=0, max=50, step=0.5, mode=NumberSelectorMode.BOX)
    )


class StormRiskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a Storm Risk location."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect a name and the coordinates for this location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]

            # One config entry per coordinate pair; allow multiple distinct
            # locations (home, work, ...).
            unique_id = f"{round(latitude, 4)}_{round(longitude, 4)}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(
                    CONF_LOCATION,
                    default={
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                ): LocationSelector(),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let an existing location's name and coordinates be edited in place."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]
            unique_id = f"{round(latitude, 4)}_{round(longitude, 4)}"

            # Only re-check uniqueness if the coordinates actually moved, so a
            # name-only edit doesn't trip over the entry's own unique id.
            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            return self.async_update_reload_and_abort(
                entry,
                unique_id=unique_id,
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=entry.data.get(CONF_NAME, DEFAULT_NAME)
                ): cv.string,
                vol.Required(
                    CONF_LOCATION,
                    default={
                        CONF_LATITUDE: entry.data[CONF_LATITUDE],
                        CONF_LONGITUDE: entry.data[CONF_LONGITUDE],
                    },
                ): LocationSelector(),
            }
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: StormRiskConfigEntry,
    ) -> StormRiskOptionsFlow:
        """Return the options flow handler."""
        return StormRiskOptionsFlow()


class StormRiskOptionsFlow(OptionsFlow):
    """Handle editing the scoring constants and interpretation thresholds."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (
                user_input[CONF_THRESHOLD_QUIET]
                < user_input[CONF_THRESHOLD_WATCH]
                < user_input[CONF_THRESHOLD_LOADED]
                < user_input[CONF_THRESHOLD_SEVERE]
            ):
                errors["base"] = "thresholds_not_ascending"
            elif user_input[CONF_SHEAR_SEVERE_MIN] < user_input[CONF_SHEAR_LOADED_MIN]:
                errors["base"] = "shear_not_ascending"
            else:
                return self.async_create_entry(data=user_input)

        options = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CAPE_DIVISOR,
                    default=options.get(CONF_CAPE_DIVISOR, DEFAULT_CAPE_DIVISOR),
                ): _positive_number_selector(),
                vol.Required(
                    CONF_CIN_DIVISOR,
                    default=options.get(CONF_CIN_DIVISOR, DEFAULT_CIN_DIVISOR),
                ): _positive_number_selector(),
                vol.Required(
                    CONF_CAPE_GATE,
                    default=options.get(CONF_CAPE_GATE, DEFAULT_CAPE_GATE),
                ): _cape_gate_selector(),
                vol.Required(
                    CONF_DEW_POINT_MULTIPLIER,
                    default=options.get(
                        CONF_DEW_POINT_MULTIPLIER, DEFAULT_DEW_POINT_MULTIPLIER
                    ),
                ): _positive_number_selector(),
                vol.Required(
                    CONF_DEW_POINT_FLOOR,
                    default=options.get(
                        CONF_DEW_POINT_FLOOR, DEFAULT_DEW_POINT_FLOOR
                    ),
                ): _fraction_selector(),
                vol.Required(
                    CONF_THRESHOLD_QUIET,
                    default=options.get(
                        CONF_THRESHOLD_QUIET, DEFAULT_THRESHOLD_QUIET
                    ),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_THRESHOLD_WATCH,
                    default=options.get(
                        CONF_THRESHOLD_WATCH, DEFAULT_THRESHOLD_WATCH
                    ),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_THRESHOLD_LOADED,
                    default=options.get(
                        CONF_THRESHOLD_LOADED, DEFAULT_THRESHOLD_LOADED
                    ),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_THRESHOLD_SEVERE,
                    default=options.get(
                        CONF_THRESHOLD_SEVERE, DEFAULT_THRESHOLD_SEVERE
                    ),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_SHEAR_LOADED_MIN,
                    default=options.get(
                        CONF_SHEAR_LOADED_MIN, DEFAULT_SHEAR_LOADED_MIN
                    ),
                ): _shear_selector(),
                vol.Required(
                    CONF_SHEAR_SEVERE_MIN,
                    default=options.get(
                        CONF_SHEAR_SEVERE_MIN, DEFAULT_SHEAR_SEVERE_MIN
                    ),
                ): _shear_selector(),
                vol.Required(
                    CONF_ACTIVE_THRESHOLD,
                    default=options.get(
                        CONF_ACTIVE_THRESHOLD, DEFAULT_ACTIVE_THRESHOLD
                    ),
                ): _score_threshold_selector(),
                # Optional, and intentionally without a `default` so clearing
                # the picker (to disable roaming) actually sticks.
                vol.Optional(
                    CONF_ROAMING_ENTITY,
                    description={
                        "suggested_value": options.get(CONF_ROAMING_ENTITY)
                    },
                ): EntitySelector(
                    EntitySelectorConfig(domain=["person", "device_tracker"])
                ),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
