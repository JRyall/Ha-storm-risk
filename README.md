# Storm Risk — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/jryall/ha-storm-risk/actions/workflows/validate.yaml/badge.svg)](https://github.com/jryall/ha-storm-risk/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration that surfaces **convective storm forecasting
data** from the free [Open-Meteo](https://open-meteo.com/) API and distils it
into a handful of sensors — including a composite **Storm Risk** score — so you
can watch thunderstorm potential build over the day.

It's aimed at amateur meteorology enthusiasts, storm chasers, and anyone who
likes knowing *why* the air feels like it might do something interesting later.
The goal is to help you understand the ingredients, not just read a number.

> ⚠️ **This is a model forecast, not a nowcast or a warning service.** It is for
> curiosity and education. Do **not** use it for safety-critical decisions. See
> [Limitations](#limitations).

---

## What it does

Convective storms need a few ingredients to come together: instability (energy
for air to rise), a lack of a "lid" holding that energy down, and enough
low-level moisture to feed developing clouds. This integration polls Open-Meteo
for the relevant parameters and exposes them as sensors, then combines three of
them into a single 0–100 score.

### Sensors

| Sensor | Unit | Meaning |
| --- | --- | --- |
| **CAPE now** | J/kg | Convective Available Potential Energy for the current hour — the "fuel" available to rising air. |
| **CIN now** | J/kg | Convective Inhibition for the current hour — the strength of the "lid" suppressing storms (zero or negative). |
| **CAPE max today** | J/kg | The highest CAPE in the next 24 hours. |
| **CAPE peak hour today** | `HH:MM` | The local time at which CAPE is forecast to peak. |
| **Temperature** | °C | Current 2 m air temperature. |
| **Dew point** | °C | Current 2 m dew point — a direct measure of low-level moisture. |
| **Storm risk** | % | Composite 0–100 score from CAPE, CIN, and dew point (see below). |

The **Storm risk** sensor also exposes `cape_score`, `cin_score`, `dp_score`,
and `level` as state attributes so you can see exactly how the score was built.

### Reading the numbers — a climatological scale

These are rough rules of thumb for **mid-latitude / UK** conditions. Thresholds
that matter for severe weather are much lower in the UK than in, say, the US
Great Plains.

**CAPE (J/kg)** — instability / fuel:

| Value | Interpretation |
| --- | --- |
| 0–100 | Stable. Nothing convective. |
| 100–500 | Weak instability. Showers possible with a trigger. |
| 500–1000 | Moderate. Thunderstorms plausible in the UK. |
| 1000–2500 | Strong (a big day for the UK). |
| 2500+ | Very strong; common in continental/US setups, rare in the UK. |

**CIN (J/kg)** — the lid (always ≤ 0):

| Value | Interpretation |
| --- | --- |
| 0 to −25 | Weak cap. Storms can fire easily if CAPE is present. |
| −25 to −100 | Moderate cap. Needs a decent trigger to break. |
| < −100 | Strong cap. Storms unlikely unless something forces the lid. |

Note that a *strong* cap can be a loaded gun: it lets CAPE build all afternoon,
then breaks explosively. High CAPE **and** moderate CIN is the classic
"primed" signature.

**Dew point (°C)** — low-level moisture:

| Value | Interpretation |
| --- | --- |
| < 10 | Dry. Limited storm fuel. |
| 10–15 | Modest moisture. |
| 15–18 | Moist; supportive of UK convection. |
| 18+ | Very humid; muggy, thundery feel. |

### The Storm Risk score

The score sums three ingredients, each capped at 33 points (max 99, displayed
as 100):

```text
cape_score = clamp(cape / 40,           0, 33)
cin_score  = clamp((150 + cin) / 4.5,   0, 33)   # cin is negative
dp_score   = clamp((dew_point - 10) * 3.3, 0, 33)

storm_risk = round(cape_score + cin_score + dp_score)
```

where `clamp(x, lo, hi) = max(lo, min(hi, x))`.

| Score | `level` | Interpretation |
| --- | --- | --- |
| 0–25 | `none` | Nothing brewing. |
| 25–50 | `present` | Ingredients present, unlikely to fire. |
| 50–75 | `meaningful` | Meaningful potential. |
| 75+ | `loaded` | Properly loaded setup. |

The divisors/multiplier and the band thresholds are all editable in the
[options flow](#options).

---

## Installation

### HACS (recommended)

This integration is distributed as a **HACS custom repository** (it is not in
the default HACS store).

1. In Home Assistant, open **HACS → Integrations**.
2. Click the **⋮** menu (top right) → **Custom repositories**.
3. Add the repository URL `https://github.com/jryall/ha-storm-risk` with the
   category **Integration**, then click **Add**.
4. Find **Storm Risk** in the list, open it, and click **Download**.
5. **Restart Home Assistant.**

### Manual

1. Copy `custom_components/storm_risk` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

Configuration is entirely through the UI — there is no YAML.

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Storm Risk**.
3. Enter a **name** (e.g. `Home`), and the **latitude** and **longitude** to
   monitor. The fields default to your Home Assistant location.

![Config flow](docs/screenshots/config_flow.png)

You can add the integration multiple times to track several locations (home,
work, the in-laws' place); each becomes its own device with its own sensors.

### Options

After setup, click **Configure** on the integration to tune the scoring:

![Options flow](docs/screenshots/options_flow.png)

- **CAPE divisor** (default `40`) — lower = more sensitive to instability.
- **CIN divisor** (default `4.5`) — lower = more sensitive to the cap weakening.
- **Dew point multiplier** (default `3.3`) — higher = more sensitive to moisture.
- **Low / Medium / High thresholds** (default `25 / 50 / 75`) — the boundaries
  for the `level` attribute. Must increase from low to high.

Changing options reloads the integration, so new values apply immediately.

---

## Example dashboard card

A simple entities + gauge card:

```yaml
type: vertical-stack
cards:
  - type: gauge
    name: Storm Risk
    entity: sensor.home_storm_risk
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 25
      red: 50
  - type: entities
    title: Convective ingredients
    entities:
      - entity: sensor.home_cape_now
      - entity: sensor.home_cin_now
      - entity: sensor.home_cape_max_today
      - entity: sensor.home_cape_peak_hour_today
      - entity: sensor.home_dew_point
      - entity: sensor.home_temperature
```

> Entity IDs depend on the name you chose during setup. Check
> **Settings → Devices & services → Storm Risk** for the exact IDs.

---

## Example automation

Notify when the setup gets meaningfully loaded:

```yaml
alias: Storm risk alert
trigger:
  - platform: numeric_state
    entity_id: sensor.home_storm_risk
    above: 60
    for:
      minutes: 30
condition:
  # Only during daylight hours, say.
  - condition: sun
    after: sunrise
    before: sunset
action:
  - service: notify.notify
    data:
      title: "⛈️ Storm potential rising"
      message: >-
        Storm risk is {{ states('sensor.home_storm_risk') }}%
        (CAPE {{ states('sensor.home_cape_now') }} J/kg,
        peak forecast around
        {{ states('sensor.home_cape_peak_hour_today') }}).
mode: single
```

---

## Limitations

Please read these before reading too much into the numbers.

- **Grid resolution ~25 km.** Open-Meteo's global model resolves features at
  roughly this scale. Individual storms and local terrain effects are far
  smaller than one grid box.
- **Forecast, not observation.** Every value is a *model prediction* for that
  hour, not a measurement. Models routinely get the timing and magnitude of
  convection wrong.
- **CAPE/CIN are necessary, not sufficient.** Storms also need a trigger
  (fronts, sea breezes, terrain). High CAPE with no trigger often produces
  nothing at all.
- **Not a warning service.** This integration does not detect lightning and is
  not a substitute for official warnings. **Never** rely on it for safety.

### Verify against the real world

- ⚡ Live lightning: [lightningmaps.org](https://www.lightningmaps.org/)
- 🇬🇧 Official UK warnings:
  [Met Office weather warnings](https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings)

---

## Data source & attribution

Weather data by [Open-Meteo.com](https://open-meteo.com/) under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). No API key is
required. The integration makes one request every 30 minutes per configured
location.

> **A note on `lifted_index`:** Open-Meteo offers a lifted-index parameter, but
> for UK locations it returns `"undefined"` units and `null` values, so this
> integration deliberately does not request it. CAPE and convective inhibition
> are reliable and used instead.

---

## Contributing

Issues and pull requests are welcome. This is a learning project and a first
public repo, so constructive feedback on the code is genuinely appreciated.

## License

[MIT](LICENSE) © 2026 JRyall
