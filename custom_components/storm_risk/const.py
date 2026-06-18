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
#
# The pressure-level winds (10 m + 500 hPa) let us derive a deep-layer bulk
# shear proxy, and ``precipitation_probability`` is the "will anything actually
# fire" trigger signal. Both are handled defensively: if a model returns null
# for them the dependent features simply degrade (no band cap / unknown
# trigger) rather than breaking the score.
API_HOURLY_VARIABLES: Final = (
    "cape",
    "convective_inhibition",
    "temperature_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_speed_500hPa",
    "wind_direction_500hPa",
    "precipitation_probability",
)

# Wind speeds are requested in m/s so the derived bulk shear is in m/s, the
# unit the shear thresholds below are expressed in.
API_WIND_SPEED_UNIT: Final = "ms"

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

# Deep-layer bulk shear (m/s) required to *unlock* the upper bands. Shear is
# what organises convection: with too little of it even a thermodynamically
# loaded airmass only manages disorganised pulse storms, so the band is capped.
CONF_SHEAR_LOADED_MIN: Final = "shear_loaded_min"
CONF_SHEAR_SEVERE_MIN: Final = "shear_severe_min"

# Score at or above which the "Storm risk active" binary sensor turns on.
CONF_ACTIVE_THRESHOLD: Final = "active_threshold"

# Entity (person / device_tracker) whose live GPS the location follows while
# "roaming mode" is switched on.
CONF_ROAMING_ENTITY: Final = "roaming_entity"

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

# Human-readable risk bands keyed off the thresholds above, in ascending order
# of severity (used as a rank when capping the band by shear).
LEVEL_NONE: Final = "none"
LEVEL_QUIET: Final = "quiet"
LEVEL_WATCH: Final = "watch"
LEVEL_LOADED: Final = "loaded"
LEVEL_SEVERE: Final = "severe"
LEVELS_ORDERED: Final = (
    LEVEL_NONE,
    LEVEL_QUIET,
    LEVEL_WATCH,
    LEVEL_LOADED,
    LEVEL_SEVERE,
)

# --- Shear / storm-organisation thresholds (configurable) --------------------
#
# Bulk shear (m/s) gates how organised storms can get, and therefore the
# highest band the score is allowed to reach:
#   shear < loaded_min          -> capped at "watch"  (pulse / single cell)
#   loaded_min <= shear < severe_min -> capped at "loaded" (multicell, organised)
#   shear >= severe_min         -> uncapped            (supercell potential)
# 10 m/s ~= 20 kt, 18 m/s ~= 35 kt -- the usual marginal / supercell guides.
DEFAULT_SHEAR_LOADED_MIN: Final = 10.0
DEFAULT_SHEAR_SEVERE_MIN: Final = 18.0

# Storm-organisation descriptor derived from the same thresholds.
MODE_UNKNOWN: Final = "unknown"
MODE_PULSE: Final = "pulse"
MODE_ORGANISED: Final = "organised"
MODE_SUPERCELL: Final = "supercell"

# Default score at/above which the "Storm risk active" binary sensor is on.
# Mirrors the "watch" band so the binary sensor lights up once it's worth
# watching.
DEFAULT_ACTIVE_THRESHOLD: Final = 45

# Event fired on the HA bus whenever a location's band changes (e.g. for
# "notify me when it crosses into Watch" automations without polling).
EVENT_BAND_CHANGED: Final = f"{DOMAIN}_band_changed"

# While roaming, a move of at least this many metres since the last poll
# triggers an out-of-cycle refresh so the forecast keeps up while travelling
# (the regular 30-minute poll still applies otherwise).
ROAMING_REFRESH_DISTANCE_M: Final = 10_000
