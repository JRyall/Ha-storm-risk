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
CONF_CAPE_GATE: Final = "cape_gate"
CONF_DEW_POINT_MULTIPLIER: Final = "dew_point_multiplier"
CONF_DEW_POINT_FLOOR: Final = "dew_point_floor"
CONF_THRESHOLD_QUIET: Final = "threshold_quiet"
CONF_THRESHOLD_WATCH: Final = "threshold_watch"
CONF_THRESHOLD_LOADED: Final = "threshold_loaded"
CONF_THRESHOLD_SEVERE: Final = "threshold_severe"

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

# CIN only matters if there is CAPE for it to inhibit. The cin_score is scaled
# by clamp(cape / CAPE_GATE, 0, 1) so it contributes nothing with zero CAPE and
# ramps to full weight once CAPE is meaningfully present (~100 J/kg = the
# bottom of the "weak instability" band).
DEFAULT_CAPE_GATE: Final = 100.0

# Dew point (moisture) is also gated by CAPE, but only partially: moisture
# alone is not storm potential, yet a hard gate would zero out muggy low-CAPE
# nights (when surface CAPE collapses but elevated instability may persist,
# which Open-Meteo's single CAPE value cannot see). The floor is the fraction
# of dew-point weight retained at zero CAPE:
#   dp_factor = floor + (1 - floor) * clamp(cape / CAPE_GATE, 0, 1)
# 1.0 = ungated (old behaviour), 0.0 = fully gated like CIN.
DEFAULT_DEW_POINT_FLOOR: Final = 0.5

# Constant offsets in the CIN / dew-point formulas. Not user-editable in v1.
CIN_OFFSET: Final = 150.0
DEW_POINT_OFFSET: Final = 10.0

# Each ingredient is capped at this many points.
SCORE_CAP: Final = 33.0

# --- Interpretation thresholds (configurable) --------------------------------
#
# The 0-100 ingredients score is bucketed into five bands. Each threshold is
# the score at which you *enter* that band:
#   score < quiet            -> none
#   quiet  <= score < watch  -> quiet
#   watch  <= score < loaded -> watch
#   loaded <= score < severe -> loaded
#   score >= severe          -> severe

DEFAULT_THRESHOLD_QUIET: Final = 25
DEFAULT_THRESHOLD_WATCH: Final = 45
DEFAULT_THRESHOLD_LOADED: Final = 65
DEFAULT_THRESHOLD_SEVERE: Final = 85

# Human-readable risk bands keyed off the thresholds above.
LEVEL_NONE: Final = "none"
LEVEL_QUIET: Final = "quiet"
LEVEL_WATCH: Final = "watch"
LEVEL_LOADED: Final = "loaded"
LEVEL_SEVERE: Final = "severe"
