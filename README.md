# Austrian Air Quality

[![hacs][hacs-badge]][hacs]

Home Assistant integration for air quality measurements in Austria (data source: Federal Environment Agency Austria).

> **Unofficial project.** This integration is developed independently and is not affiliated with
> the Federal Environment Agency Austria (Umweltbundesamt). There is no warranty for availability,
> timeliness, or accuracy of the data. For legally binding information, refer exclusively to the
> official publication of the Federal Environment Agency Austria.

## Status

**Early development – not yet functional.** The repository currently contains the skeleton of the
integration. Data access in `api.py` is intentionally implemented as a placeholder: endpoint,
response format, update interval, and data source terms of use have not yet been verified and
must be clarified before the first implementation.

## Measurements (planned)

| Pollutant | Entity Suffix | Unit |
|---|---|---|
| Particulate Matter PM10 | `_pm10` | µg/m³ |
| Particulate Matter PM2.5 | `_pm25` | µg/m³ |
| Nitrogen Dioxide NO₂ | `_no2` | µg/m³ |
| Ozone O₃ | `_o3` | µg/m³ |
| Sulfur Dioxide SO₂ | `_so2` | µg/m³ |
| Carbon Monoxide CO | `_co` | mg/m³ |

## Installation

### HACS (Custom Repository)

1. Open HACS → Integrations → Menu (⋮) → *Custom repositories*
2. Add `https://github.com/karlrt/ha-austrian-air-quality` as category *Integration*
3. Install "Austrian Air Quality", restart Home Assistant
4. *Settings → Devices & Services → Create Integration → Austrian Air Quality*

### Manual

Copy the `custom_components/austrian_air_quality` folder to the `config/custom_components/`
directory of your Home Assistant installation and restart.

## Configuration

Setup is performed entirely through the user interface (Config Flow). One entry is created per
measurement station.

## Development

- Domain: `austrian_air_quality` (immutable after the first release)
- Display name: `Austrian Air Quality`
- Repository: `ha-austrian-air-quality`

See `custom_components/austrian_air_quality/` for the source code.

## License

Apache-2.0 – see [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
