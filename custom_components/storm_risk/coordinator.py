"""DataUpdateCoordinator for the Storm Risk integration.

A single coordinator performs one Open-Meteo API call per configured location
and shares the parsed, derived result with every sensor entity. All scoring is
done here so the entities stay thin and the algorithm lives in one place.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_FORECAST_DAYS,
    API_HOURLY_VARIABLES,
    API_URL,
    CIN_OFFSET,
    CONF_CAPE_DIVISOR,
    CONF_CIN_DIVISOR,
    CONF_DEW_POINT_MULTIPLIER,
    CONF_THRESHOLD_HIGH,
    CONF_THRESHOLD_LOW,
    CONF_THRESHOLD_MEDIUM,
    DEFAULT_CAPE_DIVISOR,
    DEFAULT_CIN_DIVISOR,
    DEFAULT_DEW_POINT_MULTIPLIER,
    DEFAULT_THRESHOLD_HIGH,
    DEFAULT_THRESHOLD_LOW,
    DEFAULT_THRESHOLD_MEDIUM,
    DEW_POINT_OFFSET,
    DOMAIN,
    LEVEL_LOADED,
    LEVEL_MEANINGFUL,
    LEVEL_NONE,
    LEVEL_PRESENT,
    LOOK_AHEAD_HOURS,
    SCORE_CAP,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Be a good API citizen: don't hang HA's update loop if the network stalls.
_REQUEST_TIMEOUT = 30


def clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` constrained to the inclusive range [low, high]."""
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class StormRiskData:
    """Processed, ready-to-display result of one coordinator refresh.

    Every value is derived for the current hour (or, for the look-ahead
    sensors, the next ``LOOK_AHEAD_HOURS`` hours) so sensors only have to read
    a field rather than re-parse the raw forecast.
    """

    cape_now: float
    cin_now: float
    cape_max_today: float
    cape_peak_hour: str
    temperature: float
    dew_point: float
    wind_speed: float
    wind_direction: float
    storm_risk: int
    cape_score: float
    cin_score: float
    dp_score: float
    level: str


class StormRiskCoordinator(DataUpdateCoordinator[StormRiskData]):
    """Coordinate polling of the Open-Meteo forecast for one location."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise the coordinator from a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self._latitude: float = config_entry.data["latitude"]
        self._longitude: float = config_entry.data["longitude"]

    # --- Options helpers -----------------------------------------------------
    #
    # Options are read fresh on every refresh so changes from the options flow
    # take effect on the next poll (and immediately, because changing options
    # reloads the entry). Defaults mirror const.py.

    def _option(self, key: str, default: float | int) -> Any:
        return self.config_entry.options.get(key, default)

    # --- Polling -------------------------------------------------------------

    async def _async_update_data(self) -> StormRiskData:
        """Fetch the latest forecast and derive every sensor value."""
        params = {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "hourly": ",".join(API_HOURLY_VARIABLES),
            "forecast_days": API_FORECAST_DAYS,
            # Let Open-Meteo resolve the timezone from the coordinates so the
            # hourly series is anchored to the location's local midnight.
            "timezone": "auto",
        }

        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                response = await self._session.get(API_URL, params=params)
                response.raise_for_status()
                payload: dict[str, Any] = await response.json()
        except (ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with Open-Meteo: {err}") from err

        try:
            return self._process(payload)
        except (KeyError, TypeError, ValueError, IndexError) as err:
            raise UpdateFailed(f"Malformed response from Open-Meteo: {err}") from err

    # --- Processing ----------------------------------------------------------

    def _process(self, payload: dict[str, Any]) -> StormRiskData:
        """Turn a raw Open-Meteo payload into a :class:`StormRiskData`."""
        hourly: dict[str, Any] = payload["hourly"]
        times: list[str] = hourly["time"]
        cape: list[float | None] = hourly["cape"]
        cin: list[float | None] = hourly["convective_inhibition"]
        temp: list[float | None] = hourly["temperature_2m"]
        dew: list[float | None] = hourly["dew_point_2m"]
        wind_speed: list[float | None] = hourly["wind_speed_10m"]
        wind_dir: list[float | None] = hourly["wind_direction_10m"]

        utc_offset_seconds = int(payload.get("utc_offset_seconds", 0))
        index = self._current_index(times, utc_offset_seconds)

        cape_now = _value(cape, index)
        cin_now = _value(cin, index)
        dew_now = _value(dew, index)

        # Look-ahead window for the "today" sensors: find the peak CAPE and the
        # local time at which it occurs over the next LOOK_AHEAD_HOURS hours.
        window_end = min(index + LOOK_AHEAD_HOURS, len(cape))
        peak_value: float | None = None
        peak_time: str | None = None
        for i in range(index, window_end):
            value = cape[i]
            if value is None:
                continue
            if peak_value is None or value > peak_value:
                peak_value = value
                peak_time = times[i]

        if peak_value is not None and peak_time is not None:
            cape_max_today = peak_value
            cape_peak_hour = peak_time[11:16]  # "YYYY-MM-DDTHH:MM" -> "HH:MM"
        else:
            cape_max_today = cape_now
            cape_peak_hour = times[index][11:16]

        scores = self._score(cape_now, cin_now, dew_now)

        return StormRiskData(
            cape_now=round(cape_now, 1),
            cin_now=round(cin_now, 1),
            cape_max_today=round(cape_max_today, 1),
            cape_peak_hour=cape_peak_hour,
            temperature=round(_value(temp, index), 1),
            dew_point=round(dew_now, 1),
            wind_speed=round(_value(wind_speed, index), 1),
            wind_direction=round(_value(wind_dir, index)),
            **scores,
        )

    def _current_index(self, times: list[str], utc_offset_seconds: int) -> int:
        """Return the index in ``times`` matching the current local hour.

        Open-Meteo returns local-time stamps (because of ``timezone=auto``).
        We reconstruct the location's current local hour from UTC plus the
        reported offset and match it against the series, falling back to a
        clamped position if the exact stamp is missing.
        """
        local_now = datetime.now(timezone.utc) + timedelta(seconds=utc_offset_seconds)
        stamp = local_now.strftime("%Y-%m-%dT%H:00")
        try:
            return times.index(stamp)
        except ValueError:
            # Fall back to hour-of-day from midnight, clamped to the array.
            return min(local_now.hour, len(times) - 1)

    def _score(
        self, cape: float, cin: float, dew_point: float
    ) -> dict[str, Any]:
        """Compute the composite storm-risk score and its components."""
        cape_divisor = float(self._option(CONF_CAPE_DIVISOR, DEFAULT_CAPE_DIVISOR))
        cin_divisor = float(self._option(CONF_CIN_DIVISOR, DEFAULT_CIN_DIVISOR))
        dp_multiplier = float(
            self._option(CONF_DEW_POINT_MULTIPLIER, DEFAULT_DEW_POINT_MULTIPLIER)
        )

        cape_score = clamp(cape / cape_divisor, 0.0, SCORE_CAP)
        cin_score = clamp((CIN_OFFSET + cin) / cin_divisor, 0.0, SCORE_CAP)
        dp_score = clamp((dew_point - DEW_POINT_OFFSET) * dp_multiplier, 0.0, SCORE_CAP)

        storm_risk = round(cape_score + cin_score + dp_score)

        return {
            "storm_risk": storm_risk,
            "cape_score": round(cape_score, 1),
            "cin_score": round(cin_score, 1),
            "dp_score": round(dp_score, 1),
            "level": self._level(storm_risk),
        }

    def _level(self, storm_risk: int) -> str:
        """Map a numeric score to a human-readable interpretation band."""
        low = int(self._option(CONF_THRESHOLD_LOW, DEFAULT_THRESHOLD_LOW))
        medium = int(self._option(CONF_THRESHOLD_MEDIUM, DEFAULT_THRESHOLD_MEDIUM))
        high = int(self._option(CONF_THRESHOLD_HIGH, DEFAULT_THRESHOLD_HIGH))

        if storm_risk >= high:
            return LEVEL_LOADED
        if storm_risk >= medium:
            return LEVEL_MEANINGFUL
        if storm_risk >= low:
            return LEVEL_PRESENT
        return LEVEL_NONE


def _value(series: list[float | None], index: int) -> float:
    """Return ``series[index]`` as a float, raising if it is missing.

    A ``None`` here means the model genuinely had no value for the current
    hour, which we treat as a malformed response so the entities go
    unavailable rather than reporting a misleading zero.
    """
    value = series[index]
    if value is None:
        raise ValueError(f"missing value at index {index}")
    return float(value)
