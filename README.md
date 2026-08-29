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
Messstation wird ein Eintrag angelegt.

## Entwicklung

- Domain: `austrian_air_quality` (unveränderlich nach dem ersten Release)
- Anzeigename: `Luftqualität Österreich`
- Repository: `ha-austrian-air-quality`

Siehe `custom_components/austrian_air_quality/` für den Quellcode.

## Lizenz

MIT – siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
