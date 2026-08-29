# Luftqualität Österreich

[![hacs][hacs-badge]][hacs]

Home-Assistant-Integration für Luftqualitätsmessdaten in Österreich (Datenquelle: Umweltbundesamt).

> **Inoffizielles Projekt.** Diese Integration wird unabhängig entwickelt und steht in keiner
> Verbindung zum Umweltbundesamt GmbH. Es besteht keine Gewähr für Verfügbarkeit, Aktualität
> oder Richtigkeit der Daten. Für rechtsverbindliche Auskünfte gilt ausschließlich die
> offizielle Veröffentlichung des Umweltbundesamts.

## Status

**Frühe Entwicklung – noch nicht lauffähig.** Das Repository enthält derzeit das Gerüst der
Integration. Der Datenzugriff in `api.py` ist bewusst als Platzhalter angelegt: Endpunkt,
Antwortformat, Aktualisierungsintervall und Nutzungsbedingungen der Datenquelle sind noch
nicht verifiziert und müssen vor der ersten Implementierung geklärt werden.

## Messgrößen (geplant)

| Schadstoff | Entity-Suffix | Einheit |
|---|---|---|
| Feinstaub PM10 | `_pm10` | µg/m³ |
| Feinstaub PM2.5 | `_pm25` | µg/m³ |
| Stickstoffdioxid NO₂ | `_no2` | µg/m³ |
| Ozon O₃ | `_o3` | µg/m³ |
| Schwefeldioxid SO₂ | `_so2` | µg/m³ |
| Kohlenmonoxid CO | `_co` | mg/m³ |

## Installation

### HACS (benutzerdefiniertes Repository)

1. HACS öffnen → Integrationen → Menü (⋮) → *Benutzerdefinierte Repositories*
2. `https://github.com/karlrt/ha-austrian-air-quality` als Kategorie *Integration* hinzufügen
3. „Luftqualität Österreich" installieren, Home Assistant neu starten
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Luftqualität Österreich*

### Manuell

Den Ordner `custom_components/austrian_air_quality` in das `config/custom_components/`
Verzeichnis der Home-Assistant-Installation kopieren und neu starten.

## Konfiguration

Die Einrichtung erfolgt vollständig über die Benutzeroberfläche (Config Flow). Pro
Messstation wird ein Eintrag angelegt. Die Messstelle kann auf zwei Wegen gesucht werden:

- **Auf der Karte (Umkreis)** – den Marker auf den eigenen Standort setzen und den Kreis auf
  den gewünschten Suchradius ziehen. Alle Messstellen im Kreis werden nach Entfernung
  sortiert aufgelistet, die nächstgelegene zuerst.
- **Nach Stationsname** – einen Teil des Namens oder der Adresse eingeben, z. B. `Graz` oder
  `Stephansplatz`.

Die Trefferliste zeigt bereits, welche Werte jede Station liefert. Nach der Auswahl folgt eine
Detailansicht mit Adresse, Betreiber, Entfernung und den aktuellen Messwerten aller
Schadstoffe, bevor der Eintrag angelegt wird. Bereits eingerichtete Messstellen werden
ausgeblendet.

Es werden nur die Schadstoffe als Sensoren angelegt, die die Station tatsächlich liefert.

## Station auf der Karte

Jede Station bekommt zusätzlich eine Diagnose-Entität **Koordinaten** (Suffix
`_koordinaten`), deren Zustand die Position als `47.06695, 15.44226` anzeigt. Sie steht auf
der Geräteseite unter *Diagnose* und ist der passende Eintrag für eine Karten-Karte, weil es
sie genau einmal pro Station gibt.

Jeder Sensor – auch die Koordinaten-Entität – liefert die Stationsdaten als Attribute mit:

| Attribut | Bedeutung |
|---|---|
| `latitude`, `longitude` | Koordinaten der Messstelle |
| `location` | Adresse laut Umweltbundesamt |
| `owner` | Betreiber der Messstelle |
| `station_id` | Kennung der Messstelle |
| `measured_at` | Zeitpunkt der Messung (ISO 8601) |

Weil `latitude` und `longitude` vorhanden sind, kann die Messstelle direkt in einer
Karten-Karte angezeigt werden:

```yaml
type: map
entities:
  - sensor.graz_don_bosco_koordinaten
```

Alle Sensoren einer Station tragen dieselben Koordinaten – für die Karte genügt daher
ein Sensor pro Station, sonst liegen mehrere Marker exakt übereinander.

## Entwicklung

- Domain: `austrian_air_quality` (unveränderlich nach dem ersten Release)
- Anzeigename: `Luftqualität Österreich`
- Repository: `ha-austrian-air-quality`

Siehe `custom_components/austrian_air_quality/` für den Quellcode.

## Lizenz

MIT – siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
