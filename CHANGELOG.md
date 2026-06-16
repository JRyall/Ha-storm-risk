# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.2] - 2026-06-16

### Fixed

- Define `CONFIG_SCHEMA` (config-entry-only) so hassfest passes now that the
  integration implements `async_setup` for the bundled card.
- CI: bump `actions/checkout` to v5 (Node 24) and skip the HACS `brands` check,
  which only applies to the default store, not custom-repository installs.

[1.4.2]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.4.2

## [1.4.1] - 2026-06-16

### Added

- Storm Risk sensor now exposes the raw current-hour `cape`, `cin`, and
  `dew_point` values as attributes.
- Storm Risk card shows those real values (J/kg, J/kg, °C) as sub-text beneath
  each score bar, so you get the at-a-glance score plus the underlying data.

[1.4.1]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.4.1

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

[1.4.0]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.4.0

## [1.3.2] - 2026-06-15

### Fixed

- Storm Risk card now guards against being defined twice, so it is safe to
  load both via the automatic registration and as a manual dashboard resource.
- Removed non-ASCII characters from the card source to avoid any charset/encoding
  surprises when the file is served.

### Docs

- Added a card troubleshooting section (full restart, frontend cache, and a
  manual dashboard-resource fallback) to the README.

[1.3.2]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.3.2

## [1.3.1] - 2026-06-15

### Fixed

- Storm Risk card: the `%` sign in the gauge now sits next to the number as a
  superscript instead of floating to the top of the gauge.

[1.3.1]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.3.1

## [1.3.0] - 2026-06-15

### Added

- **Bundled Lovelace card** (`custom:storm-risk-card`): a self-contained card
  showing a risk gauge, the CAPE/CIN/dew-point score breakdown, and a 24h
  forecast sparkline — all from the single Storm Risk sensor. The integration
  serves and auto-registers it on the frontend, so there is no separate
  install and no manual dashboard resource to add. It also appears in the card
  picker.

[1.3.0]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.3.0

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

[1.2.0]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.2.0

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

[1.1.0]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.1.0

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

[1.0.0]: https://github.com/jryall/ha-storm-risk/releases/tag/v1.0.0
