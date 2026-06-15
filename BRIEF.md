# Home Assistant Custom Integration — Storm Risk

## Project goal

Build a Home Assistant custom integration that exposes convective storm
forecasting data from the Open-Meteo API. Distribution target is HACS (not
core). This is a first public GitHub repo, so code quality and documentation
matter alongside functionality.

## Data source

Open-Meteo free API (`https://api.open-meteo.com/v1/forecast`). No API key
required. The integration polls one endpoint with these hourly parameters:

`cape, convective_inhibition, temperature_2m, dew_point_2m, wind_speed_10m, wind_direction_10m`

Example URL with test coordinates:

```
https://api.open-meteo.com/v1/forecast?latitude=51.51&longitude=-2.57&hourly=cape,convective_inhibition,temperature_2m,dew_point_2m,wind_speed_10m,wind_direction_10m&forecast_days=2&timezone=Europe%2FLondon
```

**Important quirk:** `lifted_index` returns "undefined" units and null values
for UK locations. Don't request it. CAPE and convective_inhibition work fine.

Response structure: `value_json.hourly.cape` is an array of 48 hourly values
starting at midnight local time. Index into it with the current hour.

Poll interval: 30 minutes.

## Sensors to expose (v1)

1. CAPE Now (J/kg) — current hour CAPE value
2. CIN Now (J/kg) — current hour convective inhibition (always negative or zero)
3. CAPE Max Today (J/kg) — max of next 24 hours of CAPE
4. CAPE Peak Hour Today (HH:MM string) — hour of day when CAPE peaks
5. Temperature (°C) — current temperature
6. Dew Point (°C) — current dew point
7. Storm Risk (%) — composite score from the algorithm below

## Storm Risk algorithm

Composite 0-100 score from three ingredients, each contributing up to 33 points
(max possible 99, displayed as 100):

```
cape = CAPE in J/kg
cin = CIN in J/kg (negative number)
dp = dew point in °C

cape_raw = cape / 40
cape_score = clamp(cape_raw, 0, 33)

cin_raw = (150 + cin) / 4.5  # gets less negative = higher score
cin_score = clamp(cin_raw, 0, 33)

dp_raw = (dp - 10) * 3.3
dp_score = clamp(dp_raw, 0, 33)

storm_risk = round(cape_score + cin_score + dp_score)
```

`clamp(x, lo, hi)` returns `max(lo, min(hi, x))`.

Interpretation:
- 0-25: nothing brewing
- 25-50: ingredients present, unlikely to fire
- 50-75: meaningful potential
- 75+: properly loaded setup

Thresholds configurable in options flow with these defaults.

Expose `cape_score`, `cin_score`, `dp_score` as state attributes on the Storm
Risk sensor for debugging/transparency.

## Configuration

Config flow:
- User step: name (string, default "Storm Risk"), latitude (float), longitude
  (float).
- Options flow: editable scoring constants (the dividers 40, 4.5, 3.3) and
  threshold values for low/medium/high. Default to current values.

Support multiple instances via separate config entries.

## Technical requirements

- Use DataUpdateCoordinator for the polling — one API call shared between all
  sensors
- Async throughout — aiohttp not requests, no blocking calls
- Type hints everywhere, mypy-clean
- Proper device_info so all sensors group under one logical device per
  configured location
- Handle API failures gracefully — sensors should report unavailable, not stale
  values
- manifest.json, hacs.json, translations/en.json all set up correctly
- GitHub Actions for HACS validation on push
- MIT license

## v2 backlog — don't build yet

- Forecast curve graph data (expose 24h CAPE array as attribute)
- ApexCharts dashboard card examples in README
- 7-day outlook sensors
- Map picker for location selection in config flow
- Additional convective parameters (helicity, shear, etc) if Open-Meteo adds
  them
- Lightning detector integration via AS3935
