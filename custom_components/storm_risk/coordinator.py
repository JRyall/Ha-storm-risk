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
from math import cos, radians, sin, sqrt
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    Event,
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.location import distance

from .const import (
    API_FORECAST_DAYS,
    API_HOURLY_VARIABLES,
    API_URL,
    API_WIND_SPEED_UNIT,
    CIN_OFFSET,
    CONF_CAPE_DIVISOR,
    CONF_CAPE_GATE,
    CONF_CIN_DIVISOR,
    CONF_DEW_POINT_FLOOR,
    CONF_DEW_POINT_MULTIPLIER,
    CONF_ROAMING_ENTITY,
    CONF_SHEAR_LOADED_MIN,
    CONF_SHEAR_SEVERE_MIN,
    CONF_THRESHOLD_LOADED,
    CONF_THRESHOLD_QUIET,
    CONF_THRESHOLD_SEVERE,
    CONF_THRESHOLD_WATCH,
    DEFAULT_CAPE_DIVISOR,
    DEFAULT_CAPE_GATE,
    DEFAULT_CIN_DIVISOR,
    DEFAULT_DEW_POINT_FLOOR,
    DEFAULT_DEW_POINT_MULTIPLIER,
    DEFAULT_SHEAR_LOADED_MIN,
    DEFAULT_SHEAR_SEVERE_MIN,
    DEFAULT_THRESHOLD_LOADED,
    DEFAULT_THRESHOLD_QUIET,
    DEFAULT_THRESHOLD_SEVERE,
    DEFAULT_THRESHOLD_WATCH,
    DEW_POINT_OFFSET,
    DOMAIN,
    EVENT_BAND_CHANGED,
    FORECAST_HOURS,
    LEVEL_LOADED,
    LEVEL_NONE,
    LEVEL_QUIET,
    LEVEL_SEVERE,
    LEVEL_WATCH,
    LEVELS_ORDERED,
    LOOK_AHEAD_HOURS,
    MODE_ORGANISED,
    MODE_PULSE,
    MODE_SUPERCELL,
    MODE_UNKNOWN,
    OUTLOOK_DAYS,
    ROAMING_REFRESH_DISTANCE_M,
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
    # v2: graphable forecast + multi-day outlook.
    forecast: list[dict[str, Any]]
    cape_outlook_max: float
    daily_outlook: list[dict[str, Any]]
    # v3: shear-based organisation, trigger likelihood and the 24h peak.
    # ``shear`` / ``trigger`` are None when the model doesn't provide the
    # underlying data, so dependent features degrade rather than break.
    shear: float | None
    mode: str
    trigger: int | None
    storm_risk_outlook_max: int
    peak_score: int
    peak_time: str
    # v3.1: roaming. ``roaming_active`` is True only when the switch is on *and*
    # the followed entity had a usable GPS fix this poll; ``location_source`` is
    # its friendly name (else None, meaning the fixed home coordinates).
    roaming_active: bool
    location_source: str | None


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
        # Kept for config-entry diagnostics (the last raw API response).
        self.last_payload: dict[str, Any] | None = None
        # Roaming state. ``roaming`` is the switch position; the active_* values
        # record the coordinates actually polled (home, unless roaming with a
        # GPS fix). ``_roaming_unsub`` removes the move listener when off.
        self.roaming: bool = False
        self.roaming_active: bool = False
        self.active_latitude: float = self._latitude
        self.active_longitude: float = self._longitude
        self._location_source: str | None = None
        self._roaming_unsub: CALLBACK_TYPE | None = None

    # --- Options helpers -----------------------------------------------------
    #
    # Options are read fresh on every refresh so changes from the options flow
    # take effect on the next poll (and immediately, because changing options
    # reloads the entry). Defaults mirror const.py.

    def _option(self, key: str, default: float | int) -> Any:
        return self.config_entry.options.get(key, default)

    # --- Roaming -------------------------------------------------------------

    async def async_set_roaming(self, enabled: bool) -> None:
        """Turn roaming on/off (from the switch) and re-poll immediately."""
        self.roaming = enabled
        if enabled:
            self._subscribe_roaming()
        else:
            self._unsubscribe_roaming()
        await self.async_request_refresh()

    def _subscribe_roaming(self) -> None:
        """Watch the followed entity so a big move re-polls out of cycle."""
        self._unsubscribe_roaming()
        entity_id = self.config_entry.options.get(CONF_ROAMING_ENTITY)
        if not entity_id:
            return
        self._roaming_unsub = async_track_state_change_event(
            self.hass, [entity_id], self._handle_tracker_move
        )

    @callback
    def _unsubscribe_roaming(self) -> None:
        """Remove the move listener (on toggle-off or entry unload)."""
        if self._roaming_unsub is not None:
            self._roaming_unsub()
            self._roaming_unsub = None

    @callback
    def _handle_tracker_move(self, event: Event[EventStateChangedData]) -> None:
        """Re-poll early when the followed device moves a meaningful distance."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        lat = new_state.attributes.get("latitude")
        lon = new_state.attributes.get("longitude")
        if lat is None or lon is None:
            return
        moved = distance(self.active_latitude, self.active_longitude, lat, lon)
        if moved is None or moved >= ROAMING_REFRESH_DISTANCE_M:
            self.hass.async_create_task(self.async_request_refresh())

    def _resolve_location(self) -> tuple[float, float, bool, str | None]:
        """Return the (lat, lon, roaming_active, source) to poll this cycle.

        Falls back to the fixed home coordinates whenever roaming is off or the
        followed entity has no usable GPS fix.
        """
        if self.roaming:
            entity_id = self.config_entry.options.get(CONF_ROAMING_ENTITY)
            state = self.hass.states.get(entity_id) if entity_id else None
            if state is not None:
                lat = state.attributes.get("latitude")
                lon = state.attributes.get("longitude")
                if lat is not None and lon is not None:
                    source = state.attributes.get("friendly_name", entity_id)
                    return float(lat), float(lon), True, source
        return self._latitude, self._longitude, False, None

    # --- Polling -------------------------------------------------------------

    async def _async_update_data(self) -> StormRiskData:
        """Fetch the latest forecast and derive every sensor value."""
        lat, lon, self.roaming_active, self._location_source = self._resolve_location()
        self.active_latitude, self.active_longitude = lat, lon
        params: dict[str, str | int | float] = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(API_HOURLY_VARIABLES),
            "forecast_days": API_FORECAST_DAYS,
            "wind_speed_unit": API_WIND_SPEED_UNIT,
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

        self.last_payload = payload
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
        # Optional extras -- a model may not return these. ``.get`` keeps the
        # whole refresh working (shear cap / trigger just degrade) instead of
        # raising on a missing key.
        ws_500: list[float | None] = hourly.get("wind_speed_500hPa") or []
        wd_500: list[float | None] = hourly.get("wind_direction_500hPa") or []
        precip_prob: list[float | None] = (
            hourly.get("precipitation_probability") or []
        )

        utc_offset_seconds = int(payload.get("utc_offset_seconds", 0))
        index = self._current_index(times, utc_offset_seconds)

        cape_now = _value(cape, index)
        cin_now = _value(cin, index)
        dew_now = _value(dew, index)

        # Deep-layer bulk shear (10 m -> 500 hPa) and the trigger likelihood.
        # Both are optional, so missing data yields None rather than an error.
        shear_now = _bulk_shear(
            _opt(wind_speed, index),
            _opt(wind_dir, index),
            _opt(ws_500, index),
            _opt(wd_500, index),
        )
        trigger_raw = _opt(precip_prob, index)
        trigger_now = None if trigger_raw is None else int(round(trigger_raw))
        mode = self._mode(shear_now)

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

        scores = self._score(cape_now, cin_now, dew_now, shear_now)
        forecast = self._build_forecast(times, cape, cin, dew, index)
        daily_outlook = self._build_outlook(times, cape, cin, dew)
        cape_outlook_max = (
            max(day["cape_max"] for day in daily_outlook)
            if daily_outlook
            else round(cape_now, 1)
        )
        storm_risk_outlook_max = (
            max(day["storm_risk_max"] for day in daily_outlook)
            if daily_outlook
            else scores["storm_risk"]
        )

        # Peak of the next-24h score series, for at-a-glance "worst, and when".
        peak_score = scores["storm_risk"]
        peak_time = times[index][11:16]
        for entry in forecast:
            if entry["storm_risk"] > peak_score:
                peak_score = entry["storm_risk"]
                peak_time = entry["datetime"][11:16]

        self._fire_band_change(scores["level"], scores["storm_risk"])

        return StormRiskData(
            cape_now=round(cape_now, 1),
            cin_now=round(cin_now, 1),
            cape_max_today=round(cape_max_today, 1),
            cape_peak_hour=cape_peak_hour,
            temperature=round(_value(temp, index), 1),
            dew_point=round(dew_now, 1),
            wind_speed=round(_value(wind_speed, index), 1),
            wind_direction=round(_value(wind_dir, index)),
            forecast=forecast,
            cape_outlook_max=cape_outlook_max,
            daily_outlook=daily_outlook,
            shear=None if shear_now is None else round(shear_now, 1),
            mode=mode,
            trigger=trigger_now,
            storm_risk_outlook_max=storm_risk_outlook_max,
            peak_score=peak_score,
            peak_time=peak_time,
            roaming_active=self.roaming_active,
            location_source=self._location_source,
            **scores,
        )

    def _fire_band_change(self, new_level: str, storm_risk: int) -> None:
        """Fire an event on the HA bus when the band changes between refreshes.

        Lets automations react to a transition (e.g. "none -> watch") without
        polling. No event is fired on the very first refresh.
        """
        previous = self.data.level if self.data else None
        if previous is None or previous == new_level:
            return
        self.hass.bus.async_fire(
            EVENT_BAND_CHANGED,
            {
                "entry_id": self.config_entry.entry_id,
                "name": self.config_entry.data.get("name"),
                "from_level": previous,
                "to_level": new_level,
                "storm_risk": storm_risk,
            },
        )

    def _build_forecast(
        self,
        times: list[str],
        cape: list[float | None],
        cin: list[float | None],
        dew: list[float | None],
        index: int,
    ) -> list[dict[str, Any]]:
        """Build the next-``FORECAST_HOURS`` hourly series for graphing.

        Each entry carries the local timestamp plus CAPE, CIN, and the
        per-hour Storm Risk score so a single attribute can drive several
        charts. Hours missing any ingredient are skipped.
        """
        end = min(index + FORECAST_HOURS, len(times))
        forecast: list[dict[str, Any]] = []
        for i in range(index, end):
            cape_i, cin_i, dew_i = cape[i], cin[i], dew[i]
            if cape_i is None or cin_i is None or dew_i is None:
                continue
            cape_s, cin_s, dp_s = self._score_components(cape_i, cin_i, dew_i)
            forecast.append(
                {
                    "datetime": times[i],
                    "cape": round(cape_i, 1),
                    "cin": round(cin_i, 1),
                    "storm_risk": round(cape_s + cin_s + dp_s),
                }
            )
        return forecast

    def _build_outlook(
        self,
        times: list[str],
        cape: list[float | None],
        cin: list[float | None],
        dew: list[float | None],
    ) -> list[dict[str, Any]]:
        """Aggregate the hourly series into a per-day outlook (max CAPE etc.).

        Days preserve chronological order; the result is capped at
        ``OUTLOOK_DAYS`` entries.
        """
        days: dict[str, dict[str, Any]] = {}
        for i, stamp in enumerate(times):
            cape_i = cape[i]
            if cape_i is None:
                continue
            date = stamp[:10]
            cin_i, dew_i = cin[i], dew[i]
            storm_risk = 0
            if cin_i is not None and dew_i is not None:
                cape_s, cin_s, dp_s = self._score_components(cape_i, cin_i, dew_i)
                storm_risk = round(cape_s + cin_s + dp_s)

            day = days.get(date)
            if day is None:
                days[date] = {
                    "date": date,
                    "cape_max": round(cape_i, 1),
                    "cape_peak_hour": stamp[11:16],
                    "storm_risk_max": storm_risk,
                }
                continue
            if cape_i > day["cape_max"]:
                day["cape_max"] = round(cape_i, 1)
                day["cape_peak_hour"] = stamp[11:16]
            if storm_risk > day["storm_risk_max"]:
                day["storm_risk_max"] = storm_risk

        return list(days.values())[:OUTLOOK_DAYS]

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

    def _score_components(
        self, cape: float, cin: float, dew_point: float
    ) -> tuple[float, float, float]:
        """Return the (cape, cin, dew point) score components, each 0..33.

        Reads the (possibly user-overridden) scoring constants fresh so the
        same maths backs the live score, the hourly forecast, and the outlook.
        """
        cape_divisor = float(self._option(CONF_CAPE_DIVISOR, DEFAULT_CAPE_DIVISOR))
        cin_divisor = float(self._option(CONF_CIN_DIVISOR, DEFAULT_CIN_DIVISOR))
        cape_gate = float(self._option(CONF_CAPE_GATE, DEFAULT_CAPE_GATE))
        dp_multiplier = float(
            self._option(CONF_DEW_POINT_MULTIPLIER, DEFAULT_DEW_POINT_MULTIPLIER)
        )
        dp_floor = clamp(
            float(self._option(CONF_DEW_POINT_FLOOR, DEFAULT_DEW_POINT_FLOOR)),
            0.0,
            1.0,
        )

        # A favourable lid is only meaningful if there is CAPE to inhibit, so
        # scale the CIN contribution by how much CAPE is present. Without this,
        # zero CAPE + zero CIN would still award the full CIN score.
        cape_factor = clamp(cape / cape_gate, 0.0, 1.0) if cape_gate > 0 else 1.0

        # Moisture alone is not storm potential, so dew point is gated by CAPE
        # too -- but only partially (down to dp_floor) so muggy low-CAPE nights
        # keep a faint signal rather than reading a flat zero.
        dp_factor = dp_floor + (1.0 - dp_floor) * cape_factor

        cape_score = clamp(cape / cape_divisor, 0.0, SCORE_CAP)
        cin_score = clamp((CIN_OFFSET + cin) / cin_divisor, 0.0, SCORE_CAP) * cape_factor
        dp_score = (
            clamp((dew_point - DEW_POINT_OFFSET) * dp_multiplier, 0.0, SCORE_CAP)
            * dp_factor
        )
        return cape_score, cin_score, dp_score

    def _score(
        self, cape: float, cin: float, dew_point: float, shear: float | None = None
    ) -> dict[str, Any]:
        """Compute the composite storm-risk score and its components."""
        cape_score, cin_score, dp_score = self._score_components(cape, cin, dew_point)
        storm_risk = round(cape_score + cin_score + dp_score)

        return {
            "storm_risk": storm_risk,
            "cape_score": round(cape_score, 1),
            "cin_score": round(cin_score, 1),
            "dp_score": round(dp_score, 1),
            "level": self._level(storm_risk, shear),
        }

    def _level(self, storm_risk: int, shear: float | None = None) -> str:
        """Map a score to a band, then cap that band by available shear.

        The score (thermodynamics) is never changed; shear only limits how
        organised storms can get, so it caps the *band*: a loaded airmass with
        little shear is still only "watch" (pulse storms). With no shear data
        the cap is skipped so models without it behave as before.
        """
        quiet = int(self._option(CONF_THRESHOLD_QUIET, DEFAULT_THRESHOLD_QUIET))
        watch = int(self._option(CONF_THRESHOLD_WATCH, DEFAULT_THRESHOLD_WATCH))
        loaded = int(self._option(CONF_THRESHOLD_LOADED, DEFAULT_THRESHOLD_LOADED))
        severe = int(self._option(CONF_THRESHOLD_SEVERE, DEFAULT_THRESHOLD_SEVERE))

        if storm_risk >= severe:
            base = LEVEL_SEVERE
        elif storm_risk >= loaded:
            base = LEVEL_LOADED
        elif storm_risk >= watch:
            base = LEVEL_WATCH
        elif storm_risk >= quiet:
            base = LEVEL_QUIET
        else:
            base = LEVEL_NONE

        if shear is None:
            return base

        loaded_min = float(self._option(CONF_SHEAR_LOADED_MIN, DEFAULT_SHEAR_LOADED_MIN))
        severe_min = float(self._option(CONF_SHEAR_SEVERE_MIN, DEFAULT_SHEAR_SEVERE_MIN))
        if shear >= severe_min:
            cap = LEVEL_SEVERE
        elif shear >= loaded_min:
            cap = LEVEL_LOADED
        else:
            cap = LEVEL_WATCH

        if LEVELS_ORDERED.index(base) > LEVELS_ORDERED.index(cap):
            return cap
        return base

    def _mode(self, shear: float | None) -> str:
        """Classify storm organisation from bulk shear (same thresholds)."""
        if shear is None:
            return MODE_UNKNOWN
        loaded_min = float(self._option(CONF_SHEAR_LOADED_MIN, DEFAULT_SHEAR_LOADED_MIN))
        severe_min = float(self._option(CONF_SHEAR_SEVERE_MIN, DEFAULT_SHEAR_SEVERE_MIN))
        if shear >= severe_min:
            return MODE_SUPERCELL
        if shear >= loaded_min:
            return MODE_ORGANISED
        return MODE_PULSE


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


def _opt(series: list[float | None], index: int) -> float | None:
    """Return ``series[index]`` as a float, or None if absent/missing.

    Used for the optional variables (shear winds, precip probability) so a
    short or null series degrades the dependent feature instead of raising.
    """
    if not series or index >= len(series):
        return None
    value = series[index]
    return None if value is None else float(value)


def _bulk_shear(
    ws_low: float | None,
    wd_low: float | None,
    ws_high: float | None,
    wd_high: float | None,
) -> float | None:
    """Return the 10 m -> 500 hPa bulk wind shear magnitude, or None.

    Decomposes both winds into u/v components and returns the magnitude of
    their vector difference -- a deep-layer shear proxy in the same speed unit
    as the inputs (m/s). The sign convention is irrelevant since only the
    difference magnitude is used.
    """
    if ws_low is None or wd_low is None or ws_high is None or wd_high is None:
        return None
    low, high = radians(wd_low), radians(wd_high)
    u_low, v_low = -ws_low * sin(low), -ws_low * cos(low)
    u_high, v_high = -ws_high * sin(high), -ws_high * cos(high)
    return sqrt((u_high - u_low) ** 2 + (v_high - v_low) ** 2)
