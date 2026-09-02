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

Every pollutant is available twice: as the current value – the half-hourly mean, the freshest
figure the source publishes – and as the daily mean, which is what the Austrian limit values
refer to. Which of them actually become sensors is decided by the selection during setup, see
[Choosing what to track](#choosing-what-to-track).

**The daily mean is the mean of the completed previous day**, not a running mean of the
current day. It arrives shortly after midnight CET and then stays unchanged until the next
one. Note that the source works in CET all year round, so in summer the day it covers runs
from 01:00 to 01:00 local time.

| Pollutant | Current value | Daily mean (previous day) | Unit |
|---|---|---|---|
| Particulate matter PM10 | Particulate matter PM10 | Particulate matter PM10 daily mean (previous day) | µg/m³ |
| Particulate matter PM2.5 | Particulate matter PM2.5 | Particulate matter PM2.5 daily mean (previous day) | µg/m³ |
| Nitrogen dioxide NO₂ | Nitrogen dioxide | Nitrogen dioxide daily mean (previous day) | µg/m³ |
| Nitrogen monoxide NO | Nitrogen monoxide | Nitrogen monoxide daily mean (previous day) | µg/m³ |
| Ozone O₃ | Ozone | Ozone daily mean (previous day) | µg/m³ |
| Sulphur dioxide SO₂ | Sulphur dioxide | Sulphur dioxide daily mean (previous day) | µg/m³ |
| Carbon monoxide CO | Carbon monoxide | Carbon monoxide daily mean (previous day) | mg/m³ |

Every sensor carries the matching device class and `state_class: measurement`, so the values
are recorded in long-term statistics. The entity ID is built from the station name and the
sensor name in the language of the Home Assistant installation, for example
`sensor.graz_don_bosco_particulate_matter_pm10` and
`sensor.graz_don_bosco_particulate_matter_pm10_daily_mean_previous_day`.

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

### The station index and its two coverage rules

The station index is the worst of the sub-indices – but only once one of the two EEA
coverage rules is met:

| Rule | Needs | `index_basis` | `index_complete` |
|---|---|---|---|
| Standard (background and industrial stations) | NO₂, O₃ **and** particulate matter | `standard` | `true` |
| Traffic stations | NO₂ **and** particulate matter | `traffic_rule` | `false` |

Particulate matter means PM2.5 or PM10 or both. Neither rule works without NO₂ or without
particulate matter: a station short of those has no station index, and the value stays
`unknown`. It never falls back to the best available sub-index, which would understate the
situation. A station reporting ozone only therefore shows an ozone sub-index and an unknown
station index.

**A station without ozone is measured against the traffic rule.** The data source does not
publish the station type, so a traffic station cannot be told apart from a background
station that simply measures no ozone. Applying the milder rule to both is a deliberate
trade: it gives an index to the many stations that report no ozone, and at a background
station it can read too optimistically in summer, when ozone is often the pollutant that
would have decided the level. Read `index_basis` before trusting a level, and compare
levels only within the same basis – `traffic_rule` and `standard` are not the same scale.

A station that meets neither rule does not get the station index ticked when the entry is
created – two entities that could never leave `unknown` are worth less than their absence.
It stays one click away in the form, and an entry that already has the entity keeps it.

### Averaging period – an approximation

**The EAQI is defined on hourly means. This integration uses half-hourly means (HMW),**
the freshest figure the source publishes. The index is therefore an approximation, and it
can differ from the official figure – most noticeably during short peaks, which an
hourly mean smooths out more than a half-hourly one.

Every index sensor states this in its `averaging_basis` attribute. Daily means (TMW) are
deliberately not used for the index – they describe the previous day, not the present.

### Attributes

The station index and its numeric twin carry:

| Attribute | Meaning |
|---|---|
| `dominant_pollutant` | Which pollutant determines the level |
| `pollutants_used` | The pollutants that went into the index |
| `index_basis` | Which coverage rule the level was built on: `standard` or `traffic_rule` |
| `index_complete` | Whether all three groups the standard rule asks for were there |
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

### Blueprint: notification above a threshold

For the most common case – *tell me when a value goes above X* – the repository ships a
ready-made automation. One click imports it into your installation:

[![Open your Home Assistant instance and show the blueprint import dialog.][my-blueprint-badge]][my-blueprint]

| Input | What it is for |
|---|---|
| **Sensor** | The measurement to watch. Only the numeric sensors of this integration are offered; for the index itself pick *Air quality index level* (1 to 6). |
| **Threshold** | The value the sensor has to rise above, in the unit of that sensor. Deliberately not pre-filled – see below. |
| **Notification** | What happens on an exceedance. Pre-filled with a persistent notification; replace it with a call of your own notification service. The variables `sensor_name`, `value`, `unit`, `threshold`, `station` and `measured_at` are available inside it. |
| **Minimum time between two notifications** | One hour by default. A value hovering around the threshold crosses it over and over; within this period further crossings are ignored, so one exceedance stays one message. |

> **No threshold is pre-filled, and that is deliberate.** The Austrian limit values,
> information and alert thresholds are defined in the IG-L and the Ozongesetz, and every
> one of them refers to a specific averaging period. The blueprint cannot check that the
> sensor you pick matches the period the value is written for, and an official-looking
> threshold applied to the wrong mean is worse than no warning at all. Look the figure up
> in the legal text ([RIS](https://www.ris.bka.gv.at)) and pick the sensor with the
> matching averaging period.

The waiting period is a delay at the end of the automation, which runs in `single` mode:
while it waits, further crossings find it busy and are dropped silently. Reloading the
automations or restarting Home Assistant ends that wait early.

The blueprint file is `blueprints/automation/austrian_air_quality/threshold_notification.yaml`;
[a German version](blueprints/automation/austrian_air_quality/schwellenwert_benachrichtigung.yaml)
of the same automation exists next to it.

### Writing them by hand

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
daily mean sensor is the right one here. Keep in mind that it reports **yesterday**, so this
reads as "yesterday was clean" rather than "the air is clean right now":

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
          entity_id: sensor.graz_don_bosco_particulate_matter_pm10_daily_mean_previous_day
        options:
          behavior: any
          threshold:
            type: below
            value:
              number: 50
    actions:
      - action: notify.persistent_notification
        data:
          message: Yesterday's PM10 daily mean was below 50 µg/m³ – good time to air out.
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

### Pre-releases (alpha/beta)

Alpha and beta releases are marked as *pre-release* on GitHub and stay invisible in HACS by
default. To test one, once the repository has been downloaded through HACS:

1. *Settings → Devices & Services → HACS*, on the "Luftqualität Österreich" device enable
   the *Pre-release* entity, which is disabled by default
2. Wait about 30 seconds, then turn the switch on
3. In HACS, on the repository: menu (⋮) → *Redownload*, pick the pre-release
4. Restart Home Assistant

The switch applies to this repository only. Turning it off does not downgrade an installed
pre-release — the next regular release supersedes it.

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

The user interface is available in English and German.

### Choosing what to track

The detail view is followed by the measurement selection. What is offered is always the full
catalogue – seven pollutants times two averaging periods – with whatever the station is
reporting at that moment ticked. The difference matters: a pollutant the station happens to
be skipping while the entry is being created can be ticked all the same, and starts
delivering as soon as it is back.

The switch *Choose the other entities as well* opens a second step with the EAQI sub-indices,
the station index and the coordinates entity. Left unticked, they are created to match the
measurement selection.

Everything can be changed afterwards through *Configure* on the entry, where the full extent
sits in a single form. The entry is reloaded automatically afterwards.

**What the selection costs.** Every ticked measurement is one request per update cycle, so
every 30 minutes. The full set is 14 requests per station; a selection of two values is two.

**When it fetches.** The source publishes on a fixed half-hourly grid, and every entry fetches
once per published value, at a fixed position inside the half-hourly window. That position is
derived from the entry id: it stays the same across restarts, and differs between the stations
of one installation and between installations. So the fetches do not slowly drift past the
grid (skipping the occasional half-hourly value on the way), and the installations do not all
arrive on the same second.

**The start does not wait for measurements.** Which entities exist comes from the selection, so
the first fetch runs in the background alongside the rest of the start. Until it lands the
sensors are *unavailable* – before this, every entry held up the Home Assistant start for the
length of a full fetch, around half a minute per station.

**Unticked entities are not deleted.** They are simply no longer created and show up in Home
Assistant as *unavailable*. The registry entry and the long-term statistics stay, and ticking
them again brings them back with the same entity ID and their history. Getting rid of them
for good is a deliberate delete in Home Assistant – which takes the history with it.

**The station index needs more than its own entity.** It is built from NO₂ and particulate
matter at the least, and from ozone on top of them wherever the station reports it. While it
is selected, the values it needs are fetched even when the matching measurement sensors are
not. Unticking a measurement therefore costs
its entity, but never quietly empties the index. The same holds for the sub-indices.

**The set of entities depends on the selection alone** – not on what the station happened to
report at the moment the entry was created or Home Assistant last restarted. A gap in the
data leaves a sensor *unavailable* for a while and it carries on by itself afterwards; before
this, it disappeared for good and only came back when the entry was reloaded.

Existing entries are given a selection automatically when they update: everything they
already have, plus everything their station reports on the first fetch afterwards. Nothing is
lost, and a sensor that went missing through such a gap comes back.

## Station on a map

Each station also gets a **Coordinates** diagnostic entity – when it is enabled in the
selection – whose state shows the position as `47.06695, 15.44226`. It appears on the device page under *Diagnostic* and is the entity to
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

## Dashboard

A finished view with the current readings, the station on a map and the last 24 hours.
Open *Edit dashboard → ⋮ → Raw configuration editor*, paste the block below under `views:`
and replace the entity IDs with your own:

```yaml
- title: Air quality
  path: air-quality
  icon: mdi:air-filter
  type: sections
  max_columns: 2
  sections:
    - type: grid
      cards:
        - type: heading
          heading: Graz Don Bosco
        - type: entities
          title: Current readings
          state_color: true
          entities:
            - entity: sensor.graz_don_bosco_air_quality_index
            - entity: sensor.graz_don_bosco_particulate_matter_pm10
            - entity: sensor.graz_don_bosco_particulate_matter_pm2_5
            - entity: sensor.graz_don_bosco_nitrogen_dioxide
            - entity: sensor.graz_don_bosco_ozone
            - type: attribute
              entity: sensor.graz_don_bosco_particulate_matter_pm10
              attribute: measured_at
              name: Reading from
    - type: grid
      cards:
        - type: heading
          heading: Station
        - type: map
          entities:
            - sensor.graz_don_bosco_coordinates
          theme_mode: auto
          auto_fit: true
    - type: grid
      cards:
        - type: heading
          heading: Last 24 hours
        - type: history-graph
          hours_to_show: 24
          entities:
            - entity: sensor.graz_don_bosco_particulate_matter_pm10
            - entity: sensor.graz_don_bosco_nitrogen_dioxide
            - entity: sensor.graz_don_bosco_ozone
```

Notes on the three cards:

- **Current readings** – the half-hourly means, with the `measured_at` attribute as the
  last row: it says how old the figures on the card are. The daily mean sensors fit here
  too, as long as it stays clear that they report [yesterday](#measurements).
- **Station** – the map needs exactly one entity per station, otherwise several markers end
  up on the same spot; see [Station on a map](#station-on-a-map).
- **Last 24 hours** – the history graph only shows what the recorder has kept. Right after
  setting the integration up the graph is empty and fills over the following day.

Only entities that were enabled in the selection exist; delete the rows for the rest, or
add them in *Configure*.

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

`tests/test_api.py` covers the timestamp and value parsing of the map interface client.
`api.py` does import `aiohttp`; where that package is missing, the test file stands in for
it, so this suite too needs nothing but the interpreter.

The two files under `blueprints/automation/austrian_air_quality/` are the same automation
in two languages; only the labels may differ. `tests/test_blueprints.py` compares them and
fails when they drift apart – it is the one test that needs PyYAML and skips itself on an
interpreter without it.

See `custom_components/austrian_air_quality/` for the source code.

### Versioning

`0.MINOR.PATCH`, following SemVer:

- **PATCH** (`0.5.1`): bug fixes, wording, translations, internal refactors — nothing an
  existing user has to touch after the update
- **MINOR** (`0.6.0`): new sensors or options, changed behaviour, and anything breaking —
  changed `unique_id`s, units, `device_class`/`state_class`, removed entities, a raised
  minimum Home Assistant version

Pre-releases carry the number of the planned version plus a suffix (`0.6.0a1`, `0.6.0b1`)
and are published as a GitHub *pre-release*. Tag and `manifest.json` must agree, with the
tag additionally carrying a `v`: `v0.6.0a1`.

## License

Apache-2.0 – see [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=karlrt&repository=ha-austrian-air-quality&category=integration
[my-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[my-blueprint]: https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkarlrt%2Fha-austrian-air-quality%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Faustrian_air_quality%2Fthreshold_notification.yaml
[my-blueprint-badge]: https://my.home-assistant.io/badges/blueprint_import.svg
