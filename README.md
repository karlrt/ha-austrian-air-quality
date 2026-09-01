# Austrian Air Quality

[![hacs][hacs-badge]][hacs]

Home Assistant integration for air quality measurements in Austria (data source: Umweltbundesamt, Environment Agency Austria).

> **Unofficial project.** This integration is developed independently and is not affiliated with
> the Umweltbundesamt (Environment Agency Austria). There is no warranty for availability,
> timeliness, or accuracy of the data. For legally binding information, refer exclusively to the
> official publication of the Umweltbundesamt.

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

The Umweltbundesamt's Coordination Office Environmental Information confirmed on request
(August 2026) that this endpoint may be used with attribution of the data source, and
recommended the standard 30-minute interval the integration uses. There is currently no
other documented interface; a new documented service is under consideration.

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

## European Air Quality Index (EAQI)

On top of the raw measurements, every station is classified according to the **European
Air Quality Index** of the European Environment Agency. Three kinds of entity are added:

| Entity | State | Content |
|---|---|---|
| *Ozone index*, *PM10 index*, … | `good` … `extremely_poor` | Sub-index of one pollutant |
| *Air quality index* | `good` … `extremely_poor` | Station index: the worst sub-index |
| *Air quality index level* | `1` … `6` | The same, as a number for graphs and comparisons |

The states are English and stable, so automations keep working regardless of the
interface language; the display names are translated.

### Bands

Concentrations in µg/m³. Source: European Environment Agency, *European Air Quality
Index*, <https://airindex.eea.europa.eu/AQI/index.html>, band table as revised in 2024,
retrieved 2026-08-31.

| Pollutant | good | fair | moderate | poor | very poor | extremely poor |
|---|---|---|---|---|---|---|
| PM2.5 | 0–5 | 6–15 | 16–50 | 51–90 | 91–140 | > 140 |
| PM10 | 0–15 | 16–45 | 46–120 | 121–195 | 196–270 | > 270 |
| O₃ | 0–60 | 61–100 | 101–120 | 121–160 | 161–180 | > 180 |
| NO₂ | 0–10 | 11–25 | 26–60 | 61–100 | 101–150 | > 150 |
| SO₂ | 0–20 | 21–40 | 41–125 | 126–190 | 191–275 | > 275 |

A value sitting exactly on a band limit belongs to the lower level: 5 µg/m³ of PM2.5 is
still `good`.

**Carbon monoxide and nitrogen monoxide are not part of the EAQI.** They get no
sub-index and contribute nothing to the station index; their measurement sensors are
unaffected.

### The station index can be unknown

The station index is the worst of the sub-indices – but only once the EEA minimum data
requirement is met: NO₂, O₃ and particulate matter (PM2.5 or PM10 or both) all have to be
present. If they are not, the index is `unknown`. It never falls back to the best
available value, which would understate the situation. A station reporting ozone only
therefore shows an ozone sub-index and an unknown station index.

The EEA asks for less at traffic stations, but the data source does not publish the
station type, so the stricter rule is applied throughout. The `index_complete` attribute
makes this visible.

### Averaging period – an approximation

**The EAQI is defined on hourly means. This integration uses half-hourly means (HMW),**
the freshest figure the source publishes. The index is therefore an approximation, and it
can differ from the official figure – most noticeably during short peaks, which an
hourly mean smooths out more than a half-hourly one.

Every index sensor states this in its `averaging_basis` attribute. Daily means (TMW) are
deliberately not used for the index.

### Attributes

The station index and its numeric twin carry:

| Attribute | Meaning |
|---|---|
| `dominant_pollutant` | Which pollutant determines the level |
| `pollutants_used` | The pollutants that went into the index |
| `index_complete` | Whether the minimum data requirement is met |
| `averaging_basis` | The averaging period actually used |
| `scheme` | The index scheme and its revision |

The sub-index sensors carry `averaging_basis` and `scheme`.

> **The index is not a compliance tool.** The EEA states plainly that the air quality
> index is not a tool for checking compliance with air quality standards and cannot be
> used for that purpose. For legal limit values, refer to the official publication of the
> Umweltbundesamt.

## Automations

The pollutant sensors carry the standard device classes, so the triggers and conditions
of the Home Assistant [Air Quality](https://www.home-assistant.io/integrations/air_quality/)
building block work with them directly – no helper entities needed. Thresholds are a
matter of taste and local rules, so this integration deliberately ships none of its own.

Ozone information threshold, 180 µg/m³:

```yaml
automation:
  - alias: Ozone information threshold reached
    triggers:
      - trigger: air_quality.ozone_crossed_threshold
        target:
          entity_id: sensor.graz_sud_tiergartenweg_ozone
        options:
          behavior: each
          threshold:
            type: above
            value:
              number: 180
              unit_of_measurement: "μg/m³"
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            Ozone above the information threshold of 180 µg/m³:
            {{ states('sensor.graz_sud_tiergartenweg_ozone') }} µg/m³
```

> The Austrian information threshold of 180 µg/m³ is legally defined as a **one-hour
> mean** (MW1). The sensor above is a half-hourly mean, so this automation is an
> approximation and will react a little earlier and a little more often than the official
> assessment. It is a hint to look at the official figures, not a substitute for them.

PM10 as a condition – the Austrian daily limit value is 50 µg/m³ as a daily mean, so the
daily mean sensor is the right one here:

```yaml
automation:
  - alias: Air out only while PM10 is low
    triggers:
      - trigger: state
        entity_id: binary_sensor.living_room_window
        to: "on"
    conditions:
      - condition: air_quality.is_pm10_value
        target:
          entity_id: sensor.graz_don_bosco_particulate_matter_pm10_daily_mean
        options:
          behavior: any
          threshold:
            type: below
            value:
              number: 50
    actions:
      - action: notify.persistent_notification
        data:
          message: PM10 daily mean is below 50 µg/m³ – good time to air out.
```

Replace the entity IDs with your own; they are built from the station name in the
language of your installation.

The index entities work in ordinary state triggers, since their states are stable:

```yaml
automation:
  - alias: Warn when air quality gets poor
    triggers:
      - trigger: state
        entity_id: sensor.graz_sud_tiergartenweg_air_quality_index
        to:
          - poor
          - very_poor
          - extremely_poor
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            Air quality is {{ states('sensor.graz_sud_tiergartenweg_air_quality_index') }},
            driven by
            {{ state_attr('sensor.graz_sud_tiergartenweg_air_quality_index',
                          'dominant_pollutant') }}.
```

## Installation

### HACS (Custom Repository)

The integration is not (yet) part of the HACS default store, so the repository has to be
added once by hand. One click does that and opens the download page directly:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.][my-badge]][my-hacs]

Or manually:

1. Open HACS → Integrations → Menu (⋮) → *Custom repositories*
2. Add `https://github.com/karlrt/ha-austrian-air-quality` as category *Integration*
3. Install "Luftqualität Österreich", restart Home Assistant
4. *Settings → Devices & Services → Create Integration → Luftqualität Österreich*

HACS only offers tagged releases, not the state of the default branch.

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
- Before tagging a release, bump `version` in `manifest.json`; `.github/workflows/release.yml`
  fails the release if tag and manifest version disagree

`eaqi.py` holds the index classification and deliberately imports nothing from Home
Assistant, so its unit tests run against a bare Python interpreter with no extra packages:

```bash
python -m unittest discover -s tests -v
```

See `custom_components/austrian_air_quality/` for the source code.

## License

Apache-2.0 – see [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=karlrt&repository=ha-austrian-air-quality&category=integration
[my-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
