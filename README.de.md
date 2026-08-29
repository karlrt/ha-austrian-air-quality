# Luftqualität Österreich

[![hacs][hacs-badge]][hacs]

Home-Assistant-Integration für Luftqualitätsmessdaten in Österreich (Datenquelle: Umweltbundesamt).

> **Inoffizielles Projekt.** Diese Integration wird unabhängig entwickelt und steht in keiner
> Verbindung zum Umweltbundesamt GmbH. Es besteht keine Gewähr für Verfügbarkeit, Aktualität
> oder Richtigkeit der Daten. Für rechtsverbindliche Auskünfte gilt ausschließlich die
> offizielle Veröffentlichung des Umweltbundesamts.

*English version: [README.md](README.md)*

## Status

**Funktionsfähig.** Messstationen werden über den Config Flow gefunden und eingerichtet, ihre
Sensoren werden alle 30 Minuten aktualisiert.

Die Daten stammen aus der JSON-Schnittstelle der öffentlichen Luftgütekarte auf
`luft.umweltbundesamt.at`. Diese Schnittstelle ist **nicht dokumentiert** und kann sich
jederzeit ändern oder wegfallen – die Integration liest sie so, wie es die Kartenanwendung
<<<<<<< Updated upstream
selbst tut. Gelesen wird ausschließlich der Halbstundenmittelwert (HMW); jeder Schadstoff wird
einzeln und mit kurzer Pause dazwischen abgefragt, ein einzelner Fehlschlag legt die Station
nicht lahm.

Benötigt Home Assistant 2026.8.0 oder neuer. Keine zusätzlichen Python-Abhängigkeiten.

## Messgrößen

Es werden nur die Schadstoffe als Sensoren angelegt, die die Station tatsächlich liefert.

| Schadstoff | Sensorname | Einheit |
|---|---|---|
| Feinstaub PM10 | Feinstaub PM10 | µg/m³ |
| Feinstaub PM2.5 | Feinstaub PM2.5 | µg/m³ |
| Stickstoffdioxid NO₂ | Stickstoffdioxid | µg/m³ |
| Ozon O₃ | Ozon | µg/m³ |
| Schwefeldioxid SO₂ | Schwefeldioxid | µg/m³ |
| Kohlenmonoxid CO | Kohlenmonoxid | mg/m³ |
=======
selbst tut. Gelesen werden zwei Mittelungszeiträume, der Halbstundenmittelwert (HMW) und der
Tagesmittelwert (TMW), macht 14 Abfragen pro Station und Aktualisierung; jeder Schadstoff und
Zeitraum wird einzeln und mit kurzer Pause dazwischen abgefragt, ein einzelner Fehlschlag legt
die Station nicht lahm.

## Messgrößen

Jeder Schadstoff wird zweifach angelegt: als aktueller Wert – der Halbstundenmittelwert, der
frischeste Wert der Datenquelle – und als Tagesmittelwert, auf den sich die österreichischen
Grenzwerte beziehen. Das Tagesmittel umfasst den laufenden Tag ab Mitternacht und wächst
daher im Lauf des Tages mit.

| Schadstoff | Aktueller Wert | Tagesmittel | Einheit |
|---|---|---|---|
| Feinstaub PM10 | Feinstaub PM10 | Feinstaub PM10 Tagesmittel | µg/m³ |
| Feinstaub PM2.5 | Feinstaub PM2.5 | Feinstaub PM2.5 Tagesmittel | µg/m³ |
| Stickstoffdioxid NO₂ | Stickstoffdioxid | Stickstoffdioxid Tagesmittel | µg/m³ |
| Stickstoffmonoxid NO | Stickstoffmonoxid | Stickstoffmonoxid Tagesmittel | µg/m³ |
| Ozon O₃ | Ozon | Ozon Tagesmittel | µg/m³ |
| Schwefeldioxid SO₂ | Schwefeldioxid | Schwefeldioxid Tagesmittel | µg/m³ |
| Kohlenmonoxid CO | Kohlenmonoxid | Kohlenmonoxid Tagesmittel | mg/m³ |
>>>>>>> Stashed changes

Jeder Sensor trägt die passende Device Class und `state_class: measurement`, die Werte landen
also in der Langzeitstatistik. Die Entity-ID entsteht aus Stationsname und Sensorname in der
Sprache der Home-Assistant-Installation, zum Beispiel
<<<<<<< Updated upstream
`sensor.graz_don_bosco_feinstaub_pm10`.
=======
`sensor.graz_don_bosco_feinstaub_pm10_tagesmittel`.
>>>>>>> Stashed changes

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
  den gewünschten Suchradius ziehen (Standard 15 km, maximal 100 km). Alle Messstellen im
  Kreis werden nach Entfernung sortiert aufgelistet, die nächstgelegene zuerst.
- **Nach Stationsname** – einen Teil des Namens oder der Adresse eingeben, z. B. `Graz` oder
  `Stephansplatz`.

Die Trefferliste zeigt bereits, welche Werte jede Station liefert. Nach der Auswahl folgt eine
Detailansicht mit Adresse, Betreiber, Entfernung und den aktuellen Messwerten aller
Schadstoffe, bevor der Eintrag angelegt wird. Bereits eingerichtete Messstellen werden
ausgeblendet. Liefert eine Suche mehr als 25 Stationen, wird statt der Liste ein genauerer
Suchbegriff verlangt.

<<<<<<< Updated upstream
Die Benutzeroberfläche gibt es auf Deutsch und Englisch.
=======
Es werden nur die Schadstoffe als Sensoren angelegt, die die Station tatsächlich liefert –
jeder davon als aktueller Wert und als Tagesmittel.
>>>>>>> Stashed changes

## Station auf der Karte

Jede Station bekommt zusätzlich eine Diagnose-Entität **Koordinaten**, deren Zustand die
Position als `47.06695, 15.44226` anzeigt. Sie steht auf der Geräteseite unter *Diagnose* und
ist der passende Eintrag für eine Karten-Karte, weil es sie genau einmal pro Station gibt.

Jeder Sensor – auch die Koordinaten-Entität – liefert die Stationsdaten als Attribute mit:

| Attribut | Bedeutung |
|---|---|
| `latitude`, `longitude` | Koordinaten der Messstelle |
| `location` | Adresse laut Umweltbundesamt |
| `owner` | Betreiber der Messstelle |
| `station_id` | Kennung der Messstelle |
<<<<<<< Updated upstream
| `measured_at` | Zeitpunkt der Messung (ISO 8601, nur bei Schadstoffsensoren) |
=======
| `altitude` | Seehöhe der Messstelle in Metern |
| `measured_at` | Zeitpunkt der Messung (ISO 8601, nur bei Schadstoffsensoren) |
| `value_class` | Belastungsklasse des Werts – die Farbskala der offiziellen Karte – nur vorhanden, wenn die Quelle eine vergibt |
>>>>>>> Stashed changes

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
- Jeder Push wird von hassfest und der HACS-Action geprüft (siehe `.github/workflows/validate.yml`)

Siehe `custom_components/austrian_air_quality/` für den Quellcode.

## Lizenz

Apache-2.0 – siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
