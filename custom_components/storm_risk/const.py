"""Constants for the Storm Risk integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "storm_risk"

# Display name used in the config flow / device registry.
DEFAULT_NAME: Final = "Storm Risk"

# Open-Meteo forecast endpoint. No API key required.
API_URL: Final = "https://api.open-meteo.com/v1/forecast"

# Hourly variables we request from Open-Meteo.
#
# NOTE: ``lifted_index`` is deliberately omitted. For UK locations the API
# returns ``"undefined"`` units and ``null`` values for it, which is useless
# and noisy. CAPE and convective_inhibition behave well, so we stick to the
# parameters below.
API_HOURLY_VARIABLES: Final = (
    "cape",
    "convective_inhibition",
    "temperature_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
)

# Seven days of hourly data powers the 7-day outlook while still giving us
# "now" plus a 24h look-ahead even late in the day.
API_FORECAST_DAYS: Final = 7

# The data is a model forecast that only refreshes hourly upstream; 30 minutes
# is plenty and keeps us well within Open-Meteo's free-tier fair-use limits.
UPDATE_INTERVAL: Final = timedelta(minutes=30)

# How many hours ahead "today" looks for the max / peak-hour sensors.
LOOK_AHEAD_HOURS: Final = 24

# How many hours of hourly data to expose as the graphable forecast attribute.
FORECAST_HOURS: Final = 24

# How many days the 7-day outlook covers.
OUTLOOK_DAYS: Final = 7

# --- Configuration / options keys --------------------------------------------

CONF_NAME: Final = "name"
CONF_LOCATION: Final = "location"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"

CONF_CAPE_DIVISOR: Final = "cape_divisor"
CONF_CIN_DIVISOR: Final = "cin_divisor"
CONF_DEW_POINT_MULTIPLIER: Final = "dew_point_multiplier"
CONF_THRESHOLD_LOW: Final = "threshold_low"
CONF_THRESHOLD_MEDIUM: Final = "threshold_medium"
CONF_THRESHOLD_HIGH: Final = "threshold_high"

# --- Storm Risk scoring defaults ---------------------------------------------
#
# Each of the three ingredients (CAPE, CIN, dew point) contributes up to 33
# points, for a theoretical max of 99 which we display as 100.

# cape_score = clamp(cape / CAPE_DIVISOR, 0, 33)
DEFAULT_CAPE_DIVISOR: Final = 40.0
# cin_score = clamp((150 + cin) / CIN_DIVISOR, 0, 33); cin is negative.
DEFAULT_CIN_DIVISOR: Final = 4.5
# dp_score = clamp((dp - 10) * DEW_POINT_MULTIPLIER, 0, 33)
DEFAULT_DEW_POINT_MULTIPLIER: Final = 3.3

# Constant offsets in the CIN / dew-point formulas. Not user-editable in v1.
CIN_OFFSET: Final = 150.0
DEW_POINT_OFFSET: Final = 10.0

# Each ingredient is capped at this many points.
SCORE_CAP: Final = 33.0

# --- Interpretation thresholds (configurable) --------------------------------

DEFAULT_THRESHOLD_LOW: Final = 25
DEFAULT_THRESHOLD_MEDIUM: Final = 50
DEFAULT_THRESHOLD_HIGH: Final = 75

# Human-readable risk levels keyed off the thresholds above.
LEVEL_NONE: Final = "none"
LEVEL_PRESENT: Final = "present"
LEVEL_MEANINGFUL: Final = "meaningful"
LEVEL_LOADED: Final = "loaded"
