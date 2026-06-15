# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
