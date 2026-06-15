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
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from . import StormRiskConfigEntry
from .const import (
    CONF_CAPE_DIVISOR,
    CONF_CIN_DIVISOR,
    CONF_DEW_POINT_MULTIPLIER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_THRESHOLD_HIGH,
    CONF_THRESHOLD_LOW,
    CONF_THRESHOLD_MEDIUM,
    DEFAULT_CAPE_DIVISOR,
    DEFAULT_CIN_DIVISOR,
    DEFAULT_DEW_POINT_MULTIPLIER,
    DEFAULT_NAME,
    DEFAULT_THRESHOLD_HIGH,
    DEFAULT_THRESHOLD_LOW,
    DEFAULT_THRESHOLD_MEDIUM,
    DOMAIN,
)


def _latitude_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=-90, max=90, step=0.0001, mode=NumberSelectorMode.BOX
        )
    )


def _longitude_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=-180, max=180, step=0.0001, mode=NumberSelectorMode.BOX
        )
    )


def _positive_number_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0.1, step=0.1, mode=NumberSelectorMode.BOX)
    )


def _score_threshold_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER)
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
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]

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
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): _latitude_selector(),
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): _longitude_selector(),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
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
                user_input[CONF_THRESHOLD_LOW]
                < user_input[CONF_THRESHOLD_MEDIUM]
                < user_input[CONF_THRESHOLD_HIGH]
            ):
                errors["base"] = "thresholds_not_ascending"
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
                    CONF_DEW_POINT_MULTIPLIER,
                    default=options.get(
                        CONF_DEW_POINT_MULTIPLIER, DEFAULT_DEW_POINT_MULTIPLIER
                    ),
                ): _positive_number_selector(),
                vol.Required(
                    CONF_THRESHOLD_LOW,
                    default=options.get(CONF_THRESHOLD_LOW, DEFAULT_THRESHOLD_LOW),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_THRESHOLD_MEDIUM,
                    default=options.get(
                        CONF_THRESHOLD_MEDIUM, DEFAULT_THRESHOLD_MEDIUM
                    ),
                ): _score_threshold_selector(),
                vol.Required(
                    CONF_THRESHOLD_HIGH,
                    default=options.get(CONF_THRESHOLD_HIGH, DEFAULT_THRESHOLD_HIGH),
                ): _score_threshold_selector(),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
