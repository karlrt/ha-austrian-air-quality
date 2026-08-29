# Austrian Air Quality

[![hacs][hacs-badge]][hacs]

Home Assistant integration for air quality measurements in Austria (data source: Federal Environment Agency Austria).

> **Unofficial project.** This integration is developed independently and is not affiliated with
> the Federal Environment Agency Austria (Umweltbundesamt). There is no warranty for availability,
> timeliness, or accuracy of the data. For legally binding information, refer exclusively to the
> official publication of the Federal Environment Agency Austria.

*Deutsche Fassung: [README.de.md](README.de.md)*

## Status

**Working.** Stations are found and set up through the config flow, and their sensors are
updated every 30 minutes.

Data comes from the JSON interface of the public air quality map at
`luft.umweltbundesamt.at`. That interface is **undocumented** and can change or disappear
without notice – the integration reads it the same way the map application does. Two
averaging periods are read, the half-hourly mean (HMW) and the daily mean (TMW), which
makes 14 requests per station and update; every pollutant and period is requested
separately, with a short delay in between, and a single failing request does not take the
whole station down.

Requires Home Assistant 2026.8.0 or newer. No additional Python dependencies.

## Measurements

Every pollutant is created twice: as the current value – the half-hourly mean, the freshest
figure the source publishes – and as the daily mean, which is what the Austrian limit values
refer to. The daily mean covers the running day from midnight, so it grows over the course
of the day.

| Pollutant | Current value | Daily mean | Unit |
|---|---|---|---|
| Particulate matter PM10 | Particulate matter PM10 | Particulate matter PM10 daily mean | µg/m³ |
| Particulate matter PM2.5 | Particulate matter PM2.5 | Particulate matter PM2.5 daily mean | µg/m³ |
| Nitrogen dioxide NO₂ | Nitrogen dioxide | Nitrogen dioxide daily mean | µg/m³ |
| Nitrogen monoxide NO | Nitrogen monoxide | Nitrogen monoxide daily mean | µg/m³ |
| Ozone O₃ | Ozone | Ozone daily mean | µg/m³ |
| Sulphur dioxide SO₂ | Sulphur dioxide | Sulphur dioxide daily mean | µg/m³ |
| Carbon monoxide CO | Carbon monoxide | Carbon monoxide daily mean | mg/m³ |

Every sensor carries the matching device class and `state_class: measurement`, so the values
are recorded in long-term statistics. The entity ID is built from the station name and the
sensor name in the language of the Home Assistant installation, for example
`sensor.graz_don_bosco_particulate_matter_pm10` and
`sensor.graz_don_bosco_particulate_matter_pm10_daily_mean`.

## Installation

### HACS (Custom Repository)

1. Open HACS → Integrations → Menu (⋮) → *Custom repositories*
2. Add `https://github.com/karlrt/ha-austrian-air-quality` as category *Integration*
3. Install "Luftqualität Österreich", restart Home Assistant
4. *Settings → Devices & Services → Create Integration → Luftqualität Österreich*

### Manual

Copy the `custom_components/austrian_air_quality` folder to the `config/custom_components/`
directory of your Home Assistant installation and restart.

## Configuration

Setup is performed entirely through the user interface (Config Flow). One entry is created per
measurement station. Stations can be found in two ways:

- **On the map (by radius)** – drop the marker on your location and drag the circle to the
  search radius (default 15 km, at most 100 km). All stations inside the circle are listed by
  distance, nearest first.
- **By station name** – enter part of a station name or address, e.g. `Graz` or
  `Stephansplatz`.

The result list already shows what each station measures. After picking one, a detail view
shows its address, operator, distance and the current readings for every pollutant it
reports, before the entry is created. Stations that are already configured are hidden. A
search that returns more than 25 stations asks for a more specific term instead of listing
them all.

Only the pollutants a station actually reports are created as sensors – each one as a
current value and as a daily mean.

The user interface is available in English and German.

## Station on a map

Each station also gets a **Coordinates** diagnostic entity whose state shows the position as
`47.06695, 15.44226`. It appears on the device page under *Diagnostic* and is the entity to
put on a map card, since there is exactly one per station.

Every sensor – the coordinates entity included – exposes the station metadata as state
attributes:

| Attribute | Meaning |
|---|---|
| `latitude`, `longitude` | Coordinates of the station |
| `location` | Address as published by the Environment Agency |
| `owner` | Operator of the station |
| `station_id` | Station identifier |
| `altitude` | Altitude of the station in metres |
| `measured_at` | Time of the reading (ISO 8601, pollutant sensors only) |
| `value_class` | Threshold class of the reading – the colour scale of the official map – only present when the source assigns one |

Because `latitude` and `longitude` are present, a station can be placed on a map card
directly:

```yaml
type: map
entities:
  - sensor.graz_don_bosco_coordinates
```

All sensors of a station carry the same coordinates, so one sensor per station is enough –
otherwise several markers end up on exactly the same spot.

## Development

- Domain: `austrian_air_quality` (immutable after the first release)
- Display name: `Luftqualität Österreich`
- Repository: `ha-austrian-air-quality`
- Every push is checked by hassfest and the HACS action (see `.github/workflows/validate.yml`)

See `custom_components/austrian_air_quality/` for the source code.

## License

Apache-2.0 – see [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
