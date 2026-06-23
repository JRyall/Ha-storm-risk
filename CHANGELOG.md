# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.4.0] - 2026-06-23

### Added

- **Trigger-type classification** (`trigger_source`) — beyond the 0–100%
  likelihood, a best-effort label for the *kind* of trigger forecast over the
  next 24 h: `none` (cap likely holds), `diurnal` (afternoon-peaked, steady
  pressure — heating), or `synoptic` (falling pressure or non-afternoon precip
  — forced lift). Shown on the card's trigger chip and as a `source` attribute
  on the Trigger sensor. **Orographic** and **sea-breeze convergence** triggers
  are intentionally *not* inferred — they need terrain/coastline data
  Open-Meteo doesn't expose per grid point, so guessing them would mislead.
  Fetches `pressure_msl` for the pressure-tendency signal; degrades gracefully
  (timing-only, or `unknown`) when data is missing.

## [3.3.0] - 2026-06-23

### Added

Three firing-likelihood classifiers, so a big day tells you more than "33/33":

- **`cape_magnitude`** — how maxed the CAPE really is (weak / moderate /
  significant / major / extreme), since the bar saturates near 1000 J/kg.
  Shown under the CAPE bar ("3500 J/kg · Extreme") and as a `magnitude`
  attribute on the CAPE sensor.
- **`cin_trend`** — the cap's trajectory vs 6 h ago (strengthening / holding /
  weakening), the best "will it fire" tell. Shown under the CIN bar and as
  `trend` / `trend_delta_6h` on the CIN sensor. (A past day of data is now
  fetched to power the lookback.)
- **`cap_state`** — whether the lid can break (locked / loadable / unlocked),
  from CIN strength. Shown in the card's context line ("Loaded · Locked") and
  on the CIN sensor.

All three are also exposed on the Storm risk sensor for the card and
automations. Pure classifiers over existing data — the score is unchanged.

## [3.2.2] - 2026-06-19

### Fixed

- **Card "Configuration Error" / wrong default entity.** Adding the card from
  the picker pre-filled a hardcoded `sensor.storm_risk_storm_risk`, which only
  exists if your location is literally named that — everyone else got an
  unusable card. `getStubConfig` now finds the real `sensor.<name>_storm_risk`
  on your system. And a missing/blank `entity` no longer throws a cryptic
  "Configuration Error"; the card shows a clear hint telling you which entity to
  set instead.

## [3.2.1] - 2026-06-19

### Fixed

- **Broken card layout from 3.2.0.** The gauge tooltip was attached to the
  score `.value`, whose `position: relative` (from the shared `.tip` style)
  overrode its centring, dropping the big number out of the ring and onto the
  forecast title. The tooltip now lives on the gauge container, so the number
  stays centred.

## [3.2.0] - 2026-06-18

### Added

- **Explanatory tooltips on the card.** Hover (or focus) the **CAPE**, **CIN**
  and **Dew point** labels, the central **score gauge**, or the **forecast**
  title for a plain-language explanation of what each one means — so the card
  teaches itself. Dotted underlines hint at what's hoverable, and the tooltips
  are keyboard-accessible.

## [3.1.0] - 2026-06-18

### Added

- **Roaming mode.** A per-location **Roaming** switch makes the forecast follow
  a predefined device's live GPS (a `person` or `device_tracker`, chosen in the
  options) instead of its fixed coordinates — for taking the forecast with you
  when you travel. While on it re-polls early after a move of ~10 km, falls back
  to home if the device has no GPS fix, and remembers its position across
  restarts. The card shows a `📍 Following <device>` indicator and the Storm
  risk sensor exposes `roaming` / `location_source` attributes.

[3.1.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v3.1.0

## [3.0.0] - 2026-06-17

Makes the "Severe" band mean something, adds a trigger cross-check, surfaces a
multi-day composite outlook, and rounds out the Home Assistant integration.

### Added

- **Wind shear → band cap.** A deep-layer (10 m → 500 hPa) bulk-shear proxy now
  gates how high the band can go: too little shear caps a loaded airmass at
  *Watch* (pulse storms), more shear unlocks *Loaded*, then *Severe*. The score
  itself is unchanged — shear only affects the band — so "Severe" now requires
  the kinematics that actually organise storms. New **Wind shear** sensor (m/s)
  with a `mode` of pulse / organised / supercell.
- **Trigger likelihood sensor** (precipitation probability) — a "will anything
  actually fire" cross-check, shown on the card but deliberately kept out of
  the score.
- **Storm risk outlook (7 day)** sensor — the highest composite score over the
  next week, with a per-day breakdown.
- **Storm risk active** `binary_sensor`, on once the score crosses a new
  **active threshold** option (default 45).
- **`storm_risk_band_changed` event** on the HA bus for transition-based
  automations.
- **Reconfigure flow** — move or rename a location without deleting the entry
  (and its history).
- **Config-entry diagnostics** — redacted dump of config, computed result and
  the last raw API response.
- New options: **Shear for Loaded / Severe** (default 10 / 18 m/s) and
  **Active threshold**. The card gained a context line (organisation · shear ·
  trigger), and `peak_score` / `peak_time` are exposed for notifications.

### Changed (breaking)

- The `level` / band of a location can now be **capped by wind shear**, so a
  high score may report a lower band than before (e.g. 90 with weak shear is
  *Watch*, not *Severe*). Automations keying off the band may see different
  values. Shear and trigger rely on optional Open-Meteo variables and degrade
  gracefully (cap skipped, sensors *unknown*) if a model omits them.

[3.0.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v3.0.0

## [2.1.0] - 2026-06-17

### Added

- The card's 24-hour forecast sparkline now **marks the peak hour** with a dot
  and a small `HH:MM · NN/100` label, so the otherwise flat-looking trend has a
  concrete "worst it gets, and when" readout.

[2.1.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v2.1.0

## [2.0.0] - 2026-06-17

The headline number was being read as a probability ("29% chance of a storm"),
which it never was. It's reframed as an unitless **0–100 ingredients score**,
and the interpretation bands are expanded from four to five.

### Changed (breaking)

- **The Storm Risk sensor is now unitless** (was `%`). The state value is
  unchanged (still 0–100); only the displayed unit is dropped, and the card now
  shows `NN/100` instead of `NN%`. Numeric automations (`above: 60`) keep
  working; dashboards that printed the `%` unit will simply lose it.
- **Five interpretation bands** instead of four. The `level` attribute values
  are now `none` / `quiet` / `watch` / `loaded` / `severe` (was `none` /
  `present` / `meaningful` / `loaded`). Automations that key off the old
  `present` / `meaningful` strings must be updated.
- **Threshold options renamed** from `threshold_low/medium/high` to
  `threshold_quiet/watch/loaded/severe` (defaults `25 / 45 / 65 / 85`). Existing
  custom threshold values are not migrated and fall back to these defaults —
  re-set them in the options flow if you had tuned them.

### Changed

- Card tags expanded to **None / Quiet / Watch / Loaded / Severe** with a
  five-step green→red colour ramp.

[2.0.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v2.0.0

## [1.5.0] - 2026-06-16

### Changed

- **Dew point is now gated by CAPE** (partially). Moisture alone is not storm
  potential, so a muggy but dead-stable airmass no longer inflates the score.
  The dew-point contribution scales with CAPE down to a configurable floor
  (`dp_factor = floor + (1 - floor) * cape_factor`).

### Added

- **Dew point floor** option (default `0.5`): the fraction of the dew-point
  score kept at zero CAPE. `1` restores the previous ungated behaviour, `0`
  gates dew point as hard as CIN. The floor deliberately keeps a faint moisture
  signal on low-CAPE nights, since Open-Meteo's single CAPE value can't see
  elevated/nocturnal instability.

### Docs

- README: updated the scoring formula and added a limitation note about the
  surface-CAPE / nocturnal-storm blind spot.

[1.5.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.5.0

## [1.4.2] - 2026-06-16

### Fixed

- Define `CONFIG_SCHEMA` (config-entry-only) so hassfest passes now that the
  integration implements `async_setup` for the bundled card.
- CI: bump `actions/checkout` to v5 (Node 24) and skip the HACS `brands` check,
  which only applies to the default store, not custom-repository installs.

[1.4.2]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.4.2

## [1.4.1] - 2026-06-16

### Added

- Storm Risk sensor now exposes the raw current-hour `cape`, `cin`, and
  `dew_point` values as attributes.
- Storm Risk card shows those real values (J/kg, J/kg, °C) as sub-text beneath
  each score bar, so you get the at-a-glance score plus the underlying data.

[1.4.1]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.4.1

## [1.4.0] - 2026-06-16

### Added

- **Storm Risk alert blueprint**: a one-import automation that sends a mobile
  notification when the score stays at or above a configurable threshold for a
  configurable duration (e.g. over 65% for 30 minutes), to a chosen device.
  Uses Home Assistant's native sustained-state trigger.

### Changed

- Storm Risk card: the score-breakdown bars now show each ingredient's
  contribution as `N/33` so the scale is clear.

### Docs

- README: added a "Companion: live lightning strikes" section recommending the
  Blitzortung integration for ad-free real-time strikes on an HA map, with a
  Map-card + zone example, framed as the observation counterpart to the
  forecast.

[1.4.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.4.0

## [1.3.2] - 2026-06-15

### Fixed

- Storm Risk card now guards against being defined twice, so it is safe to
  load both via the automatic registration and as a manual dashboard resource.
- Removed non-ASCII characters from the card source to avoid any charset/encoding
  surprises when the file is served.

### Docs

- Added a card troubleshooting section (full restart, frontend cache, and a
  manual dashboard-resource fallback) to the README.

[1.3.2]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.3.2

## [1.3.1] - 2026-06-15

### Fixed

- Storm Risk card: the `%` sign in the gauge now sits next to the number as a
  superscript instead of floating to the top of the gauge.

[1.3.1]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.3.1

## [1.3.0] - 2026-06-15

### Added

- **Bundled Lovelace card** (`custom:storm-risk-card`): a self-contained card
  showing a risk gauge, the CAPE/CIN/dew-point score breakdown, and a 24h
  forecast sparkline — all from the single Storm Risk sensor. The integration
  serves and auto-registers it on the frontend, so there is no separate
  install and no manual dashboard resource to add. It also appears in the card
  picker.

[1.3.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.3.0

## [1.2.0] - 2026-06-15

### Fixed

- **CIN no longer scores without CAPE.** Convective inhibition is only
  meaningful when there is instability for it to suppress, but previously a
  favourable CIN (e.g. 0 J/kg) awarded its full 33 points even with zero CAPE,
  producing a misleadingly high storm risk on completely stable days. The CIN
  contribution is now scaled by `clamp(cape / cape_gate, 0, 1)`.

### Added

- **CAPE gate** option (default 100 J/kg): the CAPE level at which the CIN
  score reaches full weight. Set to 0 to restore the previous unconditional
  behaviour.

[1.2.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.2.0

## [1.1.0] - 2026-06-15

### Added

- **24h forecast attribute** on the Storm Risk sensor (`forecast`): an hourly
  list of `{datetime, cape, cin, storm_risk}` for the next 24 hours, ready to
  graph with apexcharts-card.
- **7-day outlook** via a new **CAPE max (7 day)** sensor, with a `daily`
  attribute listing each day's max CAPE, peak hour, and max storm risk.
- **Map picker** in the config flow (replaces the latitude/longitude number
  inputs with a draggable map marker).
- ApexCharts dashboard examples and a recorder-exclusion note in the README.

### Changed

- The forecast request now covers 7 days (was 2) to power the outlook.

### Not included (and why)

- *Helicity / wind shear parameters* — not exposed by the Open-Meteo forecast
  API, so there is nothing to request yet.
- *AS3935 lightning-detector support* — that is local sensor hardware and
  belongs in a separate integration, not this cloud-polling one.

[1.1.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.1.0

## [1.0.0] - 2026-06-15

Initial release.

### Added

- Config-flow setup with name + latitude/longitude; supports multiple
  locations as separate config entries.
- `DataUpdateCoordinator` polling the Open-Meteo forecast API every 30 minutes,
  sharing one request across all sensors per location.
- Seven sensors per location: CAPE now, CIN now, CAPE max today, CAPE peak hour
  today, temperature, dew point, and a composite Storm Risk (%) score.
- Storm Risk score breakdown (`cape_score`, `cin_score`, `dp_score`, `level`)
  exposed as state attributes.
- Options flow to tune the scoring divisors/multiplier and the interpretation
  thresholds.
- Graceful handling of API/network failures and malformed responses
  (entities report unavailable rather than stale values).
- HACS metadata and GitHub Actions workflow for HACS + hassfest validation.
- README covering installation, configuration, sensor meanings with a
  climatological scale, example dashboard/automation YAML, and limitations.

[1.0.0]: https://github.com/JRyall/Ha-storm-risk/releases/tag/v1.0.0
