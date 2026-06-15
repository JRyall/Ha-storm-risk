# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
